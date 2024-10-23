import pytest
from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from ..src.domain.models import Notification, NotificationPreference, NotificationType
from ..src.domain.repositories import NotificationRepository, NotificationPreferenceRepository
from ..src.infrastructure.persistence import MongoNotificationRepository, MongoNotificationPreferenceRepository
from ..src.infrastructure.config import Settings

@pytest.fixture
async def mongo_client():
    settings = Settings(
        MONGODB_URL="mongodb://localhost:27017",
        MONGODB_DATABASE="test_notifications"
    )
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    yield client
    # Cleanup
    await client.drop_database(settings.MONGODB_DATABASE)
    client.close()

@pytest.fixture
def settings():
    return Settings(
        MONGODB_URL="mongodb://localhost:27017",
        MONGODB_DATABASE="test_notifications"
    )

class TestMongoNotificationRepository:
    @pytest.mark.asyncio
    async def test_create_notification(self, mongo_client, settings):
        repo = MongoNotificationRepository(mongo_client, settings)
        notification = Notification(
            user_id="test-user",
            notification_type=NotificationType.EMAIL,
            subject="Test",
            content="Test Content",
            priority="HIGH",
            recipient="test@example.com"
        )
        
        created = await repo.create(notification)
        assert created.id is not None
        assert created.user_id == notification.user_id
        assert created.notification_type == notification.notification_type
        
    @pytest.mark.asyncio
    async def test_get_by_id(self, mongo_client, settings):
        repo = MongoNotificationRepository(mongo_client, settings)
        notification = Notification(
            user_id="test-user",
            notification_type=NotificationType.EMAIL,
            subject="Test",
            content="Test Content",
            priority="HIGH",
            recipient="test@example.com"
        )
        
        created = await repo.create(notification)
        retrieved = await repo.get_by_id(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.user_id == created.user_id
        
    @pytest.mark.asyncio
    async def test_get_by_user_id(self, mongo_client, settings):
        repo = MongoNotificationRepository(mongo_client, settings)
        user_id = "test-user"
        
        # Create multiple notifications
        notifications = []
        for i in range(3):
            notification = Notification(
                user_id=user_id,
                notification_type=NotificationType.EMAIL,
                subject=f"Test {i}",
                content=f"Content {i}",
                priority="HIGH",
                recipient="test@example.com"
            )
            notifications.append(await repo.create(notification))
            
        retrieved = await repo.get_by_user_id(user_id)
        assert len(retrieved) == 3
        assert all(n.user_id == user_id for n in retrieved)

class TestMongoNotificationPreferenceRepository:
    @pytest.mark.asyncio
    async def test_create_preference(self, mongo_client, settings):
        repo = MongoNotificationPreferenceRepository(mongo_client, settings)
        preference = NotificationPreference(
            user_id="test-user",
            email_enabled=True,
            sms_enabled=False,
            email_address="test@example.com"
        )
        
        created = await repo.create(preference)
        assert created.id is not None
        assert created.user_id == preference.user_id
        assert created.email_enabled == preference.email_enabled
        
    @pytest.mark.asyncio
    async def test_get_by_user_id(self, mongo_client, settings):
        repo = MongoNotificationPreferenceRepository(mongo_client, settings)
        preference = NotificationPreference(
            user_id="test-user",
            email_enabled=True,
            sms_enabled=False,
            email_address="test@example.com"
        )
        
        await repo.create(preference)
        retrieved = await repo.get_by_user_id(preference.user_id)
        
        assert retrieved is not None
        assert retrieved.user_id == preference.user_id
        assert retrieved.email_enabled == preference.email_enabled
        
    @pytest.mark.asyncio
    async def test_update_preference(self, mongo_client, settings):
        repo = MongoNotificationPreferenceRepository(mongo_client, settings)
        user_id = "test-user"
        
        # Create initial preference
        original = NotificationPreference(
            user_id=user_id,
            email_enabled=True,
            sms_enabled=False,
            email_address="test@example.com"
        )
        await repo.create(original)
        
        # Update preference
        updated = NotificationPreference(
            user_id=user_id,
            email_enabled=False,
            sms_enabled=True,
            phone_number="1234567890"
        )
        result = await repo.update(user_id, updated)
        
        assert result is not None
        assert result.email_enabled == updated.email_enabled
        assert result.sms_enabled == updated.sms_enabled
        assert result.phone_number == updated.phone_number