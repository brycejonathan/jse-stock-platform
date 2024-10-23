from typing import List
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from domain.models import Notification, NotificationPreference
from application.services import NotificationService
from infrastructure.auth import get_current_user_id
from infrastructure.exceptions import NotificationServiceException

router = APIRouter()
security = HTTPBearer()

# Dependency to get notification service instance
async def get_notification_service() -> NotificationService:
    # In a real implementation, this would be properly initialized with all dependencies
    # For now, we'll raise an exception
    raise NotImplementedError("Notification service initialization not implemented")

@router.post("/", response_model=Notification)
async def create_notification(
    notification: Notification,
    service: NotificationService = Depends(get_notification_service),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """
    Create and send a new notification
    """
    try:
        user_id = get_current_user_id(credentials.credentials)
        notification.user_id = user_id
        return await service.create_notification(notification)
    except NotificationServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.get("/", response_model=List[Notification])
async def get_notifications(
    skip: int = 0,
    limit: int = 10,
    service: NotificationService = Depends(get_notification_service),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """
    Get all notifications for the current user
    """
    try:
        user_id = get_current_user_id(credentials.credentials)
        return await service.get_user_notifications(user_id, limit, skip)
    except NotificationServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.get("/{notification_id}", response_model=Notification)
async def get_notification(
    notification_id: str,
    service: NotificationService = Depends(get_notification_service),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """
    Get a specific notification by ID
    """
    try:
        user_id = get_current_user_id(credentials.credentials)
        notification = await service.get_notification(notification_id)
        if notification.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to access this notification")
        return notification
    except NotificationServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.get("/preferences", response_model=NotificationPreference)
async def get_notification_preferences(
    service: NotificationService = Depends(get_notification_service),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """
    Get notification preferences for the current user
    """
    try:
        user_id = get_current_user_id(credentials.credentials)
        return await service.get_preferences(user_id)
    except NotificationServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

@router.put("/preferences", response_model=NotificationPreference)
async def update_notification_preferences(
    preferences: NotificationPreference,
    service: NotificationService = Depends(get_notification_service),
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    """
    Update notification preferences for the current user
    """
    try:
        user_id = get_current_user_id(credentials.credentials)
        return await service.update_preferences(user_id, preferences)
    except NotificationServiceException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)