import pytest
from datetime import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from application.routes import router
from application.services import NotificationService
from domain.models import (
    Notification, NotificationPreference,
    NotificationType, NotificationStatus, NotificationPriority
)
from infrastructure.exceptions import (
    ValidationException, NotFoundException,
    NotificationDeliveryException
)

@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/notifications")
    return app

@pytest.fixture
def client(app):
    return TestClient(app)

@pytest.fixture
def mock_notification_service():
    return AsyncMock(spec=NotificationService)

@pytest.fixture
def mock_auth_token():
    return "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0LXVzZXIiLCJleHAiOjE3MzY4NTM5NTB9.test"

class TestNotificationRoutes:
    def test_create_notification_success(self, client, mock_notification_service, mock_auth_token):
        with patch('application.routes.get_notification_service', return_value=mock_notification_service):
            # Arrange
            payload = {
                "notification_type": "email",
                "subject": "Test Notification",
                "content": "Test Content",
                "priority": "high",
                "recipient": "test@example.com"
            }
            
            mock_notification_service.create_notification.return_value = Notification(
                id="test-id",
                user_id="test-user",
                notification_type=NotificationType.EMAIL,
                subject=payload["subject"],
                content=payload["content"],
                priority=NotificationPriority.HIGH,
                recipient=payload["recipient"],
                status=NotificationStatus.SENT,
                created_at=datetime.utcnow()
            )
            
            # Act
            response = client.post(
                "/api/v1/notifications/",
                json=payload,
                headers={"Authorization": mock_auth_token}
            )
            
            # Assert
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["id"] == "test-id"
            assert response_data["status"] == "sent"
            assert response_data["notification_type"] == "email"
            
    def test_create_notification_unauthorized(self, client):
        # Arrange
        payload = {
            "notification_type": "email",
            "subject": "Test",
            "content": "Test Content",
            "priority": "high",
            "recipient": "test@example.com"
        }
        
        # Act
        response = client.post("/api/v1/notifications/", json=payload)
        
        # Assert
        assert response.status_code == 403
        
    def test_create_notification_validation_error(self, client, mock_notification_service, mock_auth_token):
        with patch('application.routes.get_notification_service', return_value=mock_notification_service):
            # Arrange
            mock_notification_service.create_notification.side_effect = ValidationException("Invalid notification settings")
            
            payload = {
                "notification_type": "email",
                "subject": "Test",
                "content": "Test Content",
                "priority": "high",
                "recipient": "test@example.com"
            }
            
            # Act
            response = client.post(
                "/api/v1/notifications/",
                json=payload,
                headers={"Authorization": mock_auth_token}
            )
            
            # Assert
            assert response.status_code == 400
            assert "Invalid notification settings" in response.json()["detail"]
            
    def test_get_notifications_success(self, client, mock_notification_service, mock_auth_token):
        with patch('application.routes.get_notification_service', return_value=mock_notification_service):
            # Arrange
            notifications = [
                Notification(
                    id=f"test-id-{i}",
                    user_id="test-user",
                    notification_type=NotificationType.EMAIL,
                    subject=f"Test {i}",
                    content=f"Content {i}",
                    priority=NotificationPriority.HIGH,
                    recipient="test@example.com",
                    status=NotificationStatus.SENT,
                    created_at=datetime.utcnow()
                ) for i in range(3)
            ]
            
            mock_notification_service.get_user_notifications.return_value = {
                "notifications": notifications,
                "total": len(notifications),
                "page": 1,
                "size": 10
            }
            
            # Act
            response = client.get(
                "/api/v1/notifications/",
                headers={"Authorization": mock_auth_token}
            )
            
            # Assert
            assert response.status_code == 200
            response_data = response.json()
            assert len(response_data["notifications"]) == 3
            assert response_data["total"] == 3
            assert response_data["page"] == 1
            
    def test_get_notification_by_id_success(self, client, mock_notification_service, mock_auth_token):
        with patch('application.routes.get_notification_service', return_value=mock_notification_service):
            # Arrange
            notification = Notification(
                id="test-id",
                user_id="test-user",
                notification_type=NotificationType.EMAIL,
                subject="Test",
                content="Test Content",
                priority=NotificationPriority.HIGH,
                recipient="test@example.com",
                status=NotificationStatus.SENT,
                created_at=datetime.utcnow()
            )
            
            mock_notification_service.get_notification.return_value = notification
            
            # Act
            response = client.get(
                "/api/v1/notifications/test-id",
                headers={"Authorization": mock_auth_token}
            )
            
            # Assert
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["id"] == "test-id"
            assert response_data["status"] == "sent"
            
    def test_get_notification_not_found(self, client, mock_notification_service, mock_auth_token):
        with patch('application.routes.get_notification_service', return_value=mock_notification_service):
            # Arrange
            mock_notification_service.get_notification.side_effect = NotFoundException("Notification", "test-id")
            
            # Act
            response = client.get(
                "/api/v1/notifications/test-id",
                headers={"Authorization": mock_auth_token}
            )
            
            # Assert
            assert response.status_code == 404
            
    def test_get_preferences_success(self, client, mock_notification_service, mock_auth_token):
        with patch('application.routes.get_notification_service', return_value=mock_notification_service):
            # Arrange
            preference = NotificationPreference(
                id="test-id",
                user_id="test-user",
                email_enabled=True,
                sms_enabled=False,
                email_address="test@example.com",
                created_at=datetime.utcnow()
            )
            
            mock_notification_service.get_preferences.return_value = preference
            
            # Act
            response = client.get(
                "/api/v1/notifications/preferences",
                headers={"Authorization": mock_auth_token}
            )
            
            # Assert
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["email_enabled"] is True
            assert response_data["sms_enabled"] is False
            assert response_data["email_address"] == "test@example.com"
            
    def test_update_preferences_success(self, client, mock_notification_service, mock_auth_token):
        with patch('application.routes.get_notification_service', return_value=mock_notification_service):
            # Arrange
            payload = {
                "email_enabled": True,
                "sms_enabled": True,
                "email_address": "test@example.com",
                "phone_number": "1234567890"
            }
            
            preference = NotificationPreference(
                id="test-id",
                user_id="test-user",
                **payload,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            mock_notification_service.update_preferences.return_value = preference
            
            # Act
            response = client.put(
                "/api/v1/notifications/preferences",
                json=payload,
                headers={"Authorization": mock_auth_token}
            )
            
            # Assert
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["email_enabled"] is True
            assert response_data["sms_enabled"] is True
            assert response_data["email_address"] == "test@example.com"
            assert response_data["phone_number"] == "1234567890"
            
    def test_update_preferences_validation_error(self, client, mock_notification_service, mock_auth_token):
        with patch('application.routes.get_notification_service', return_value=mock_notification_service):
            # Arrange
            mock_notification_service.update_preferences.side_effect = ValidationException("Invalid preference settings")
            
            payload = {
                "email_enabled": True,
                "sms_enabled": True
            }
            
            # Act
            response = client.put(
                "/api/v1/notifications/preferences",
                json=payload,
                headers={"Authorization": mock_auth_token}
            )
            
            # Assert
            assert response.status_code == 400
            assert "Invalid preference settings" in response.json()["detail"]