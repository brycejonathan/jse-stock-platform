import pytest
from datetime import datetime
from domain.models import (
    Notification, NotificationPreference, NotificationType,
    NotificationStatus, NotificationPriority
)

class TestNotificationModel:
    def test_notification_creation_success(self):
        notification = Notification(
            user_id="test-user",
            notification_type=NotificationType.EMAIL,
            subject="Test Subject",
            content="Test Content",
            priority=NotificationPriority.HIGH,
            recipient="test@example.com"
        )
        
        assert notification.user_id == "test-user"
        assert notification.notification_type == NotificationType.EMAIL
        assert notification.subject == "Test Subject"
        assert notification.priority == NotificationPriority.HIGH
        assert notification.status == NotificationStatus.PENDING
        assert isinstance(notification.created_at, datetime)
        assert notification.sent_at is None
        
    def test_notification_invalid_type(self):
        with pytest.raises(ValueError):
            Notification(
                user_id="test-user",
                notification_type="INVALID",
                subject="Test",
                content="Test",
                priority=NotificationPriority.HIGH,
                recipient="test@example.com"
            )
            
    def test_notification_invalid_priority(self):
        with pytest.raises(ValueError):
            Notification(
                user_id="test-user",
                notification_type=NotificationType.EMAIL,
                subject="Test",
                content="Test",
                priority="INVALID",
                recipient="test@example.com"
            )

class TestNotificationPreferenceModel:
    def test_preference_creation_success(self):
        preference = NotificationPreference(
            user_id="test-user",
            email_enabled=True,
            sms_enabled=False,
            email_address="test@example.com"
        )
        
        assert preference.user_id == "test-user"
        assert preference.email_enabled is True
        assert preference.sms_enabled is False
        assert preference.email_address == "test@example.com"
        assert isinstance(preference.created_at, datetime)
        
    def test_preference_invalid_email(self):
        with pytest.raises(ValueError):
            NotificationPreference(
                user_id="test-user",
                email_enabled=True,
                email_address="invalid-email"
            )