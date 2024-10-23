# tests/test_services.py
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock
import jwt
from uuid import UUID, uuid4

from src.application.services import UserService, AuthenticationError, AuthorizationError
from src.application.dto import (
    UserCreateDTO, UserUpdateDTO, LoginRequestDTO,
    RefreshTokenRequestDTO, UserDTO
)
from src.domain.models import User, RefreshToken, UserRole, UserStatus

@pytest.fixture
def mock_user_repository():
    return AsyncMock()

@pytest.fixture
def mock_refresh_token_repository():
    return AsyncMock()

@pytest.fixture
def user_service(mock_user_repository, mock_refresh_token_repository):
    return UserService(
        user_repository=mock_user_repository,
        refresh_token_repository=mock_refresh_token_repository,
        jwt_secret="test_secret",
        jwt_algorithm="HS256",
        access_token_expire_minutes=60,
        refresh_token_expire_days=30
    )

@pytest.fixture
def test_user():
    return User(
        id=uuid4(),
        username="testuser",
        email="test@example.com",
        password_hash="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY", # bcrypt hash for "password123"
        role=UserRole.USER,
        status=UserStatus.ACTIVE,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

class TestUserService:
    @pytest.mark.asyncio
    async def test_create_user_success(self, user_service, mock_user_repository):
        # Arrange
        user_create_dto = UserCreateDTO(
            username="newuser",
            email="new@example.com",
            password="password123"
        )
        mock_user_repository.get_by_username.return_value = None
        mock_user_repository.get_by_email.return_value = None
        mock_user_repository.save.return_value = User.create(
            username=user_create_dto.username,
            email=user_create_dto.email,
            password_hash="hashed_password"
        )

        # Act
        result = await user_service.create_user(user_create_dto)

        # Assert
        assert isinstance(result, UserDTO)
        assert result.username == user_create_dto.username
        assert result.email == user_create_dto.email
        mock_user_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(self, user_service, mock_user_repository, test_user):
        # Arrange
        user_create_dto = UserCreateDTO(
            username=test_user.username,
            email="different@example.com",
            password="password123"
        )
        mock_user_repository.get_by_username.return_value = test_user

        # Act & Assert
        with pytest.raises(ValueError, match="Username already exists"):
            await user_service.create_user(user_create_dto)

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, user_service, mock_user_repository, test_user):
        # Arrange
        user_create_dto = UserCreateDTO(
            username="different_user",
            email=test_user.email,
            password="password123"
        )
        mock_user_repository.get_by_username.return_value = None
        mock_user_repository.get_by_email.return_value = test_user

        # Act & Assert
        with pytest.raises(ValueError, match="Email already exists"):
            await user_service.create_user(user_create_dto)

    @pytest.mark.asyncio
    async def test_login_success(
        self, user_service, mock_user_repository, mock_refresh_token_repository, test_user
    ):
        # Arrange
        login_request = LoginRequestDTO(
            username=test_user.username,
            password="password123"
        )
        mock_user_repository.get_by_username.return_value = test_user
        mock_refresh_token_repository.save.return_value = None

        # Act
        result = await user_service.login(login_request)

        # Assert
        assert result.access_token is not None
        assert result.refresh_token is not None
        assert result.token_type == "Bearer"
        mock_user_repository.update.assert_called_once()
        mock_refresh_token_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_login_invalid_username(self, user_service, mock_user_repository):
        # Arrange
        login_request = LoginRequestDTO(
            username="nonexistent",
            password="password123"
        )
        mock_user_repository.get_by_username.return_value = None

        # Act & Assert
        with pytest.raises(AuthenticationError, match="Invalid username or password"):
            await user_service.login(login_request)

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, user_service, mock_user_repository, test_user):
        # Arrange
        login_request = LoginRequestDTO(
            username=test_user.username,
            password="wrong_password"
        )
        mock_user_repository.get_by_username.return_value = test_user

        # Act & Assert
        with pytest.raises(AuthenticationError, match="Invalid username or password"):
            await user_service.login(login_request)

    @pytest.mark.asyncio
    async def test_login_inactive_user(self, user_service, mock_user_repository, test_user):
        # Arrange
        test_user.status = UserStatus.SUSPENDED
        login_request = LoginRequestDTO(
            username=test_user.username,
            password="password123"
        )
        mock_user_repository.get_by_username.return_value = test_user

        # Act & Assert
        with pytest.raises(AuthorizationError, match="User account is suspended"):
            await user_service.login(login_request)

    @pytest.mark.asyncio
    async def test_refresh_token_success(
        self, user_service, mock_user_repository, mock_refresh_token_repository, test_user
    ):
        # Arrange
        refresh_token = RefreshToken.create(
            user_id=test_user.id,
            token="valid_refresh_token",
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        refresh_request = RefreshTokenRequestDTO(refresh_token=refresh_token.token)
        
        mock_refresh_token_repository.get_by_token.return_value = refresh_token
        mock_user_repository.get_by_id.return_value = test_user
        mock_refresh_token_repository.save.return_value = None

        # Act
        result = await user_service.refresh_token(refresh_request)

        # Assert
        assert result.access_token is not None
        assert result.refresh_token is not None
        assert result.token_type == "Bearer"
        mock_refresh_token_repository.save.assert_called()

    @pytest.mark.asyncio
    async def test_refresh_token_invalid_token(
        self, user_service, mock_refresh_token_repository
    ):
        # Arrange
        refresh_request = RefreshTokenRequestDTO(refresh_token="invalid_token")
        mock_refresh_token_repository.get_by_token.return_value = None

        # Act & Assert
        with pytest.raises(AuthenticationError, match="Invalid refresh token"):
            await user_service.refresh_token(refresh_request)

    @pytest.mark.asyncio
    async def test_refresh_token_expired(
        self, user_service, mock_refresh_token_repository, test_user
    ):
        # Arrange
        expired_token = RefreshToken.create(
            user_id=test_user.id,
            token="expired_token",
            expires_at=datetime.utcnow() - timedelta(days=1)
        )
        refresh_request = RefreshTokenRequestDTO(refresh_token=expired_token.token)
        mock_refresh_token_repository.get_by_token.return_value = expired_token

        # Act & Assert
        with pytest.raises(AuthenticationError, match="Invalid refresh token"):
            await user_service.refresh_token(refresh_request)

    @pytest.mark.asyncio
    async def test_refresh_token_revoked(
        self, user_service, mock_refresh_token_repository, test_user
    ):
        # Arrange
        revoked_token = RefreshToken.create(
            user_id=test_user.id,
            token="revoked_token",
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        revoked_token.revoke()
        refresh_request = RefreshTokenRequestDTO(refresh_token=revoked_token.token)
        mock_refresh_token_repository.get_by_token.return_value = revoked_token

        # Act & Assert
        with pytest.raises(AuthenticationError, match="Invalid refresh token"):
            await user_service.refresh_token(refresh_request)

    @pytest.mark.asyncio
    async def test_logout_success(
        self, user_service, mock_refresh_token_repository
    ):
        # Arrange
        user_id = uuid4()
        mock_refresh_token_repository.revoke_all_for_user.return_value = None

        # Act
        await user_service.logout(user_id)

        # Assert
        mock_refresh_token_repository.revoke_all_for_user.assert_called_once_with(user_id)

    @pytest.mark.asyncio
    async def test_verify_token_success(self, user_service, test_user):
        # Arrange
        access_token_expires = datetime.utcnow() + timedelta(minutes=60)
        payload = {
            "sub": str(test_user.id),
            "username": test_user.username,
            "role": test_user.role.value,
            "exp": access_token_expires,
            "iat": datetime.utcnow()
        }
        token = jwt.encode(
            payload,
            user_service.jwt_secret,
            algorithm=user_service.jwt_algorithm
        )

        # Act
        result = await user_service.verify_token(token)

        # Assert
        assert str(result.sub) == str(test_user.id)
        assert result.username == test_user.username
        assert result.role == test_user.role

    @pytest.mark.asyncio
    async def test_verify_token_expired(self, user_service, test_user):
        # Arrange
        access_token_expires = datetime.utcnow() - timedelta(minutes=1)
        payload = {
            "sub": str(test_user.id),
            "username": test_user.username,
            "role": test_user.role.value,
            "exp": access_token_expires,
            "iat": datetime.utcnow() - timedelta(minutes=61)
        }
        token = jwt.encode(
            payload,
            user_service.jwt_secret,
            algorithm=user_service.jwt_algorithm
        )

        # Act & Assert
        with pytest.raises(AuthenticationError, match="Invalid token"):
            await user_service.verify_token(token)

    @pytest.mark.asyncio
    async def test_update_user_success(self, user_service, mock_user_repository, test_user):
        # Arrange
        update_dto = UserUpdateDTO(
            username="updated_username",
            email="updated@example.com"
        )
        mock_user_repository.get_by_id.return_value = test_user
        mock_user_repository.get_by_username.return_value = None
        mock_user_repository.get_by_email.return_value = None
        
        updated_user = test_user
        updated_user.username = update_dto.username
        updated_user.email = update_dto.email
        mock_user_repository.update.return_value = updated_user

        # Act
        result = await user_service.update_user(test_user.id, update_dto)

        # Assert
        assert result.username == update_dto.username
        assert result.email == update_dto.email
        mock_user_repository.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_not_found(self, user_service, mock_user_repository):
        # Arrange
        user_id = uuid4()
        update_dto = UserUpdateDTO(username="new_username")
        mock_user_repository.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(ValueError, match="User not found"):
            await user_service.update_user(user_id, update_dto)