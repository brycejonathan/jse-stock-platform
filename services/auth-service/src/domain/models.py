# src/domain/models.py
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

class UserRole(Enum):
    USER = "user"
    ADMIN = "admin"

class UserStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"

@dataclass
class User:
    id: UUID
    username: str
    email: str
    password_hash: str
    role: UserRole
    status: UserStatus
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None

    @staticmethod
    def create(username: str, email: str, password_hash: str, role: UserRole = UserRole.USER) -> 'User':
        now = datetime.utcnow()
        return User(
            id=uuid4(),
            username=username,
            email=email,
            password_hash=password_hash,
            role=role,
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now
        )

    def suspend(self) -> None:
        self.status = UserStatus.SUSPENDED
        self.updated_at = datetime.utcnow()

    def activate(self) -> None:
        self.status = UserStatus.ACTIVE
        self.updated_at = datetime.utcnow()

    def update_login(self) -> None:
        self.last_login = datetime.utcnow()
        self.updated_at = datetime.utcnow()

@dataclass
class RefreshToken:
    id: UUID
    user_id: UUID
    token: str
    expires_at: datetime
    created_at: datetime
    revoked_at: Optional[datetime] = None

    @staticmethod
    def create(user_id: UUID, token: str, expires_at: datetime) -> 'RefreshToken':
        return RefreshToken(
            id=uuid4(),
            user_id=user_id,
            token=token,
            expires_at=expires_at,
            created_at=datetime.utcnow()
        )

    def revoke(self) -> None:
        self.revoked_at = datetime.utcnow()

    def is_valid(self) -> bool:
        return (
            self.revoked_at is None 
            and self.expires_at > datetime.utcnow()
        )