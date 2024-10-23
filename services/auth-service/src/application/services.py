# src/application/services.py
from datetime import datetime, timedelta
import logging
from typing import Optional, Tuple
from uuid import UUID
import jwt
from passlib.hash import bcrypt
from .dto import (
    UserDTO, UserCreateDTO, UserUpdateDTO, LoginRequestDTO,
    LoginResponseDTO, RefreshTokenRequestDTO, TokenPayloadDTO
)
from ..domain.models import User, RefreshToken, UserStatus
from ..domain.repositories import UserRepository, RefreshTokenRepository

logger = logging.getLogger(__name__)

class AuthenticationError(Exception):
    pass

class AuthorizationError(Exception):
    pass

class UserService:
    def __init__(
        self,
        user_repository: UserRepository,
        refresh_token_repository: RefreshTokenRepository,
        jwt_secret: str,
        jwt_algorithm: str = "HS256",
        access_token_expire_minutes: int = 60,
        refresh_token_expire_days: int = 30
    ):
        self.user_repository = user_repository
        self.refresh_token_repository = refresh_token_repository
        self.jwt_secret = jwt_secret
        self.jwt_algorithm = jwt_algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days

    async def create_user(self, user_create_dto: UserCreateDTO) -> UserDTO:
        # Check if username or email already exists
        if await self.user_repository.get_by_username(user_create_dto.username):
            raise ValueError("Username already exists")
        if await self.user_repository.get_by_email(user_create_dto.email):
            raise ValueError("Email already exists")

        # Create new user
        password_hash = bcrypt.hash(user_create_dto.password)
        user = User.create(
            username=user_create_dto.username,
            email=user_create_dto.email,
            password_hash=password_hash,
            role=user_create_dto.role
        )
        
        saved_user = await self.user_repository.save(user)
        return self._to_dto(saved_user)

    async def update_user(self, user_id: UUID, update_dto: UserUpdateDTO) -> UserDTO:
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")

        if update_dto.username and update_dto.username != user.username:
            if await self.user_repository.get_by_username(update_dto.username):
                raise ValueError("Username already exists")
            user.username = update_dto.username

        if update_dto.email and update_dto.email != user.email:
            if await self.user_repository.get_by_email(update_dto.email):
                raise ValueError("Email already exists")
            user.email = update_dto.email

        if update_dto.password:
            user.password_hash = bcrypt.hash(update_dto.password)

        if update_dto.role:
            user.role = update_dto.role

        if update_dto.status:
            user.status = update_dto.status

        user.updated_at = datetime.utcnow()
        updated_user = await self.user_repository.update(user)
        return self._to_dto(updated_user)

    async def login(self, login_dto: LoginRequestDTO) -> LoginResponseDTO:
        user = await self.user_repository.get_by_username(login_dto.username)
        if not user:
            raise AuthenticationError("Invalid username or password")

        if not bcrypt.verify(login_dto.password, user.password_hash):
            raise AuthenticationError("Invalid username or password")

        if user.status != UserStatus.ACTIVE:
            raise AuthorizationError(f"User account is {user.status.value}")

        # Update last login
        user.update_login()
        await self.user_repository.update(user)

        # Generate tokens
        access_token, refresh_token = await self._generate_tokens(user)
        
        return LoginResponseDTO(
            access_token=access_token,
            refresh_token=refresh_token
        )

    async def refresh_token(self, refresh_dto: RefreshTokenRequestDTO) -> LoginResponseDTO:
        refresh_token = await self.refresh_token_repository.get_by_token(refresh_dto.refresh_token)
        if not refresh_token or not refresh_token.is_valid():
            raise AuthenticationError("Invalid refresh token")

        user = await self.user_repository.get_by_id(refresh_token.user_id)
        if not user or user.status != UserStatus.ACTIVE:
            raise AuthorizationError("User account is not active")

        # Revoke old refresh token and generate new ones
        refresh_token.revoke()
        await self.refresh_token_repository.save(refresh_token)

        access_token, new_refresh_token = await self._generate_tokens(user)
        
        return LoginResponseDTO(
            access_token=access_token,
            refresh_token=new_refresh_token
        )

    async def logout(self, user_id: UUID) -> None:
        await self.refresh_token_repository.revoke_all_for_user(user_id)

    async def verify_token(self, token: str) -> TokenPayloadDTO:
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.jwt_algorithm]
            )
            return TokenPayloadDTO(
                sub=UUID(payload["sub"]),
                username=payload["username"],
                role=payload["role"],
                exp=datetime.fromtimestamp(payload["exp"]),
                iat=datetime.fromtimestamp(payload["iat"])
            )
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")

    async def _generate_tokens(self, user: User) -> Tuple[str, str]:
        # Generate access token
        access_token_expires = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        access_token_payload = {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role.value,
            "exp": access_token_expires,
            "iat": datetime.utcnow()
        }
        access_token = jwt.encode(
            access_token_payload,
            self.jwt_secret,
            algorithm=self.jwt_algorithm
        )

        # Generate refresh token
        refresh_token_expires = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        refresh_token = RefreshToken.create(
            user_id=user.id,
            token=uuid4().hex,
            expires_at=refresh_token_expires
        )
        await self.refresh_token_repository.save(refresh_token)

        return access_token, refresh_token.token

    @staticmethod
    def _to_dto(user: User) -> UserDTO:
        return UserDTO(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            status=user.status,
            created_at=user.created_at,
            last_login=user.last_login
        )