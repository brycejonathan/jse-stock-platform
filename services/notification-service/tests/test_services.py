import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from ..src.application.services import NotificationService
from ..src.application.dto import (
    NotificationCreateDTO, NotificationPreferenceCreateDTO,
    NotificationResponseDTO, NotificationPreferenceResponseDTO
)
from ..src.domain.models import (
    Notification, NotificationPreference,
    NotificationType, NotificationStatus, NotificationPriority
)
from ..src.infrastructure.exceptions import (
    ValidationException, NotFoundException,
    NotificationDeliveryException
)

@pytest.fixture
def notification_repo():
    return AsyncMock()

@pytest.fixture
def preference_repo():
    return AsyncMock()

@pytest.fixture
def notification_dispatcher():
    return AsyncMock()

@pytest.fixture
def notification_service(notification_repo, preference_repo, notification_dispatcher):
    return NotificationService(notification_repo, preference_repo, notification_dispatcher)

class TestNotificationService:
    @pytest.mark.asyncio
    async def test_create_notification_success(self, notification_service):
        # Arrange
        user_id = "test-user"
        dto = NotificationCreateDTO(
            notification_type=NotificationType.EMAIL,
            subject="Test",
            content="Test Content",
            priority=NotificationPriority.HIGH,
            recipient="test@example.com"
        )
        
        notification_service.preference_repo.get_by_user_id.return_value = \
            NotificationPreference(
                user_id=user_id,
                email_enabled=True,
                email_address="test@example.com"
            )
        
        notification_service.notification_repo.create.return_value = \
            Notification(
                id="test-id",
                user_id=user_id,
                notification_type=dto.notification_type,
                subject=dto.subject,
                content=dto.content,
                priority=dto.priority,
                recipient=dto.recipient,
                status=NotificationStatus.PENDING
            )
            
        # Act
        result = await notification_service.create_notification(user_id, dto)
        
        # Assert
        assert isinstance(result, NotificationResponseDTO)
        assert result.status == NotificationStatus.SENT
        notification_service.notification_dispatcher.send_immediate.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_create_notification_disabled_preference(self, notification_service):
        # Arrange
        user_id = "test-user"
        dto = NotificationCreateDTO(
            notification_type=NotificationType.EMAIL,
            subject="Test",
            content="Test Content",
            priority=NotificationPriority.HIGH,
            recipient="test@example.com"
        )
        
        notification_service.preference_repo.get_by_user_id.return_value = \
            NotificationPreference(
                user_id=user_id,
                email_enabled=False,
                email_address="test@example.com"
            )
            
        # Act & Assert
        with pytest.raises(ValidationException):
            await notification_service.create_notification(user_id, dto)
            
    @pytest.mark.asyncio
    async def test_get_user_notifications(self, notification_service):
        # Arrange
        user_id = "test-user"
        notifications = [
            Notification(
                id=f"test-id-{i}",
                user_id=user_id,
                notification_type=NotificationType.EMAIL,
                subject=f"Test {i}",
                content=f"Content {i}",
                priority=NotificationPriority.HIGH,
                recipient="test@example.com",
                status=NotificationStatus.SENT
            ) for i in range(3)
        ]
        
        notification_service.notification_repo.get_by_user_id.return_value = notifications
        notification_service.notification_repo.count_by_user_id.return_value = len(notifications)
        
        # Act
        result = await notification_service.get_user_notifications(user_id)
        
        # Assert
        assert result.total == 3
        assert len(result.notifications) == 3
        assert all(isinstance(n, NotificationResponseDTO) for n in result.notifications)
        
    @pytest.mark.asyncio
    async def test_update_preferences_success(self, notification_service):
        # Arrange
        user_id = "test-user"
        dto = NotificationPreferenceCreateDTO(
            email_enabled=True,
            sms_enabled=True,
            email_address="test@example.com",
            phone_number="1234567890"
        )
        
        notification_service.preference_repo.update.return_value = \
            NotificationPreference(
                id="test-id",
                user_id=user_id,
                email_enabled=dto.email_enabled,
                sms_enabled=dto.sms_enabled,
                email_address=dto.email_address,
                phone_number=dto.phone_number
            )
            
        # Act
        result = await notification_service.update_preferences(user_id, dto)
        
        # Assert
        assert isinstance(result, NotificationPreferenceResponseDTO)
        assert result.email_enabled == dto.email_enabled
        assert result.sms_enabled == dto.sms_enabled
        assert result.email_address == dto.email_address
        assert result.phone_number == dto.phone_number