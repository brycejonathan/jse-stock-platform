from datetime import datetime
from typing import List, Optional, Dict, Any
from domain.models import (
    Notification, NotificationPreference, NotificationType,
    NotificationStatus, NotificationPriority
)
from domain.repositories import NotificationRepository, NotificationPreferenceRepository
from infrastructure.notifications import NotificationDispatcher
from infrastructure.exceptions import (
    NotificationServiceException, ValidationException,
    NotFoundException, NotificationDeliveryException
)
from application.dto import (
    NotificationCreateDTO, NotificationResponseDTO,
    NotificationPreferenceCreateDTO, NotificationPreferenceResponseDTO,
    NotificationListResponseDTO, NotificationStatsDTO
)
from infrastructure.logging import get_logger

logger = get_logger(__name__)

class NotificationService:
    def __init__(
        self,
        notification_repo: NotificationRepository,
        preference_repo: NotificationPreferenceRepository,
        notification_dispatcher: NotificationDispatcher
    ):
        self.notification_repo = notification_repo
        self.preference_repo = preference_repo
        self.notification_dispatcher = notification_dispatcher

    async def create_notification(
        self, user_id: str, dto: NotificationCreateDTO
    ) -> NotificationResponseDTO:
        """Create and send a new notification"""
        # Validate notification preferences
        preferences = await self.preference_repo.get_by_user_id(user_id)
        if not preferences:
            raise ValidationException("User notification preferences not found")

        self._validate_notification_preferences(dto.notification_type, preferences)

        # Create notification entity
        notification = Notification(
            user_id=user_id,
            notification_type=dto.notification_type,
            subject=dto.subject,
            content=dto.content,
            priority=dto.priority,
            recipient=dto.recipient,
            status=NotificationStatus.PENDING
        )

        # Save notification
        saved_notification = await self.notification_repo.create(notification)

        try:
            # Dispatch notification
            if dto.priority == NotificationPriority.HIGH:
                await self.notification_dispatcher.send_immediate(
                    notification_type=dto.notification_type,
                    recipient=dto.recipient,
                    subject=dto.subject,
                    content={"body": dto.content},
                    template_name=dto.template_name
                )
            else:
                await self.notification_dispatcher.dispatch(
                    notification_type=dto.notification_type,
                    recipient=dto.recipient,
                    subject=dto.subject,
                    content={"body": dto.content},
                    priority=dto.priority,
                    template_name=dto.template_name
                )

            # Update notification status
            saved_notification.status = NotificationStatus.SENT
            saved_notification.sent_at = datetime.utcnow()
            await self.notification_repo.update_status(
                saved_notification.id,
                NotificationStatus.SENT
            )

        except NotificationDeliveryException as e:
            saved_notification.status = NotificationStatus.FAILED
            saved_notification.error_message = str(e)
            await self.notification_repo.update_status(
                saved_notification.id,
                NotificationStatus.FAILED,
                str(e)
            )
            raise

        return NotificationResponseDTO.from_orm(saved_notification)

    async def get_user_notifications(
        self, user_id: str, page: int = 1, size: int = 10
    ) -> NotificationListResponseDTO:
        """Get paginated list of user notifications"""
        skip = (page - 1) * size
        notifications = await self.notification_repo.get_by_user_id(
            user_id, limit=size, skip=skip
        )
        total = await self.notification_repo.count_by_user_id(user_id)

        return NotificationListResponseDTO(
            notifications=[NotificationResponseDTO.from_orm(n) for n in notifications],
            total=total,
            page=page,
            size=size
        )

    async def get_notification(
        self, user_id: str, notification_id: str
    ) -> NotificationResponseDTO:
        """Get specific notification by ID"""
        notification = await self.notification_repo.get_by_id(notification_id)
        if not notification:
            raise NotFoundException("Notification", notification_id)
        if notification.user_id != user_id:
            raise ValidationException("Notification does not belong to user")
        return NotificationResponseDTO.from_orm(notification)

    async def get_notification_stats(
        self, user_id: str, start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> NotificationStatsDTO:
        """Get notification statistics for user"""
        stats = await self.notification_repo.get_stats(
            user_id, start_date, end_date
        )
        return NotificationStatsDTO(**stats)

    async def update_preferences(
        self, user_id: str, dto: NotificationPreferenceCreateDTO
    ) -> NotificationPreferenceResponseDTO:
        """Update user notification preferences"""
        preference = NotificationPreference(
            user_id=user_id,
            email_enabled=dto.email_enabled,
            sms_enabled=dto.sms_enabled,
            email_address=dto.email_address,
            phone_number=dto.phone_number,
            updated_at=datetime.utcnow()
        )

        self._validate_preference_settings(preference)

        updated = await self.preference_repo.update(user_id, preference)
        if not updated:
            updated = await self.preference_repo.create(preference)

        return NotificationPreferenceResponseDTO.from_orm(updated)

    async def get_preferences(
        self, user_id: str
    ) -> NotificationPreferenceResponseDTO:
        """Get user notification preferences"""
        preferences = await self.preference_repo.get_by_user_id(user_id)
        if not preferences:
            raise NotFoundException("NotificationPreference", user_id)
        return NotificationPreferenceResponseDTO.from_orm(preferences)

    def _validate_notification_preferences(
        self, notification_type: str, preferences: NotificationPreference
    ) -> None:
        """Validate notification can be sent based on preferences"""
        if notification_type == NotificationType.EMAIL and not preferences.email_enabled:
            raise ValidationException("Email notifications are disabled")
        if notification_type == NotificationType.SMS and not preferences.sms_enabled:
            raise ValidationException("SMS notifications are disabled")

    def _validate_preference_settings(
        self, preference: NotificationPreference
    ) -> None:
        """Validate notification preference settings"""
        if preference.email_enabled and not preference.email_address:
            raise ValidationException("Email address required when email is enabled")
        if preference.sms_enabled and not preference.phone_number:
            raise ValidationException("Phone number required when SMS is enabled")