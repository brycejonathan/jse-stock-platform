# src/application/dto.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID
from ..domain.models import UserRole, UserStatus

@dataclass
class UserDTO:
    id: UUID
    username: str
    email: str
    role: UserRole
    status: UserStatus
    created_at: datetime
    last_login: Optional[datetime]

@dataclass
class UserCreateDTO:
    username: str
    email: str
    password: str
    role: Optional[UserRole] = UserRole.USER

@dataclass
class UserUpdateDTO:
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None

@dataclass
class LoginRequestDTO:
    username: str
    password: str

@dataclass
class LoginResponseDTO:
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600  # 1 hour in seconds

@dataclass
class RefreshTokenRequestDTO:
    refresh_token: str

@dataclass
class TokenPayloadDTO:
    sub: UUID  # user_id
    username: str
    role: UserRole
    exp: datetime
    iat: datetime