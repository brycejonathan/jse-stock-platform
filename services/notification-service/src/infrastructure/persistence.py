from datetime import datetime
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from domain.models import Notification, NotificationPreference
from domain.repositories import NotificationRepository, NotificationPreferenceRepository
from infrastructure.config import Settings

class MongoNotificationRepository(NotificationRepository):
    def __init__(self, mongo_client: AsyncIOMotorClient, settings: Settings):
        self.db = mongo_client[settings.MONGODB_DATABASE]
        self.collection = self.db.notifications

    async def create(self, notification: Notification) -> Notification:
        notification_dict = notification.dict(exclude={'id'})
        result = await self.collection.insert_one(notification_dict)
        notification.id = str(result.inserted_id)
        return notification

    async def get_by_id(self, notification_id: str) -> Optional[Notification]:
        result = await self.collection.find_one({"_id": notification_id})
        return Notification(**result) if result else None

    async def get_by_user_id(
        self, user_id: str, limit: int = 10, skip: int = 0
    ) -> List[Notification]:
        cursor = self.collection.find({"user_id": user_id}) \
                              .sort("created_at", -1) \
                              .skip(skip) \
                              .limit(limit)
        notifications = []
        async for doc in cursor:
            notifications.append(Notification(**doc))
        return notifications

    async def update_status(
        self, 
        notification_id: str, 
        status: str, 
        error_message: Optional[str] = None
    ) -> bool:
        update_data = {
            "status": status,
            "sent_at": datetime.utcnow() if status == "sent" else None
        }
        if error_message:
            update_data["error_message"] = error_message

        result = await self.collection.update_one(
            {"_id": notification_id},
            {"$set": update_data}
        )
        return result.modified_count > 0

    async def delete(self, notification_id: str) -> bool:
        result = await self.collection.delete_one({"_id": notification_id})
        return result.deleted_count > 0

class MongoNotificationPreferenceRepository(NotificationPreferenceRepository):
    def __init__(self, mongo_client: AsyncIOMotorClient, settings: Settings):
        self.db = mongo_client[settings.MONGODB_DATABASE]
        self.collection = self.db.notification_preferences

    async def create(self, preference: NotificationPreference) -> NotificationPreference:
        preference_dict = preference.dict(exclude={'id'})
        result = await self.collection.insert_one(preference_dict)
        preference.id = str(result.inserted_id)
        return preference

    async def get_by_user_id(self, user_id: str) -> Optional[NotificationPreference]:
        result = await self.collection.find_one({"user_id": user_id})
        return NotificationPreference(**result) if result else None

    async def update(
        self, user_id: str, preference: NotificationPreference
    ) -> Optional[NotificationPreference]:
        preference_dict = preference.dict(exclude={'id'})
        result = await self.collection.update_one(
            {"user_id": user_id},
            {"$set": preference_dict}
        )
        
        if result.modified_count > 0:
            return preference
        return None

    async def delete(self, user_id: str) -> bool:
        result = await self.collection.delete_one({"user_id": user_id})
        return result.deleted_count > 0