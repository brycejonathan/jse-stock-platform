from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

class NotificationCreateDTO(BaseModel):
    notification_type: str
    subject: str
    content: str
    priority: str
    recipient: str
    template_name: Optional[str] = None

class NotificationResponseDTO(BaseModel):
    id: str
    user_id: str
    notification_type: str
    subject: str
    content: str
    priority: str
    recipient: str
    status: str
    created_at: datetime
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None

class NotificationPreferenceCreateDTO(BaseModel):
    email_enabled: bool = True
    sms_enabled: bool = False
    email_address: Optional[EmailStr] = None
    phone_number: Optional[str] = None

class NotificationPreferenceResponseDTO(BaseModel):
    id: str
    user_id: str
    email_enabled: bool
    sms_enabled: bool
    email_address: Optional[EmailStr]
    phone_number: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

class NotificationListResponseDTO(BaseModel):
    notifications: list[NotificationResponseDTO]
    total: int
    page: int
    size: int

class NotificationStatsDTO(BaseModel):
    total_sent: int
    total_failed: int
    total_pending: int
    avg_delivery_time: float = Field(description="Average delivery time in seconds")
    success_rate: float = Field(description="Success rate as percentage")