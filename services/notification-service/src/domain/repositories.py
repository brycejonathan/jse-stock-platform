from abc import ABC, abstractmethod
from typing import List, Optional
from domain.models import Notification, NotificationPreference

class NotificationRepository(ABC):
    @abstractmethod
    async def create(self, notification: Notification) -> Notification:
        pass

    @abstractmethod
    async def get_by_id(self, notification_id: str) -> Optional[Notification]:
        pass

    @abstractmethod
    async def get_by_user_id(self, user_id: str, limit: int = 10, skip: int = 0) -> List[Notification]:
        pass

    @abstractmethod
    async def update_status(self, notification_id: str, status: str, error_message: Optional[str] = None) -> bool:
        pass

    @abstractmethod
    async def delete(self, notification_id: str) -> bool:
        pass

class NotificationPreferenceRepository(ABC):
    @abstractmethod
    async def create(self, preference: NotificationPreference) -> NotificationPreference:
        pass

    @abstractmethod
    async def get_by_user_id(self, user_id: str) -> Optional[NotificationPreference]:
        pass

    @abstractmethod
    async def update(self, user_id: str, preference: NotificationPreference) -> Optional[NotificationPreference]:
        pass

    @abstractmethod
    async def delete(self, user_id: str) -> bool:
        pass