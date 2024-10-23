from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

class NotificationType(str, Enum):
    EMAIL = "email"
    SMS = "sms"

class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"

class Notification(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    notification_type: NotificationType
    priority: NotificationPriority
    subject: str
    content: str
    recipient: str
    status: NotificationStatus = NotificationStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class NotificationPreference(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    email_enabled: bool = True
    sms_enabled: bool = False
    email_address: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        allow_population_by_field_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }