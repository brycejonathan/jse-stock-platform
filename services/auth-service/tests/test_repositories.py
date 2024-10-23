# tests/test_repositories.py
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
import asyncpg
from asyncpg import Connection
from typing import AsyncGenerator
import os

from src.domain.models import User, RefreshToken, UserRole, UserStatus
from src.infrastructure.persistence import PostgresUserRepository, PostgresRefreshTokenRepository

# Test database configuration
TEST_DB_HOST = os.getenv("TEST_DB_HOST", "localhost")
TEST_DB_PORT = int(os.getenv("TEST_DB_PORT", "5432"))
TEST_DB_USER = os.getenv("TEST_DB_USER", "postgres")
TEST_DB_PASS = os.getenv("TEST_DB_PASS", "postgres")
TEST_DB_NAME = os.getenv("TEST_DB_NAME", "test_auth_db")

@pytest.fixture
async def db_pool() -> AsyncGenerator[asyncpg.Pool, None]:
    # Create test database
    sys_conn = await asyncpg.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USER,
        password=TEST_DB_PASS,
        database="postgres"
    )
    
    try:
        await sys_conn.execute(f'DROP DATABASE IF EXISTS {TEST_DB_NAME}')
        await sys_conn.execute(f'CREATE DATABASE {TEST_DB_NAME}')
    finally:
        await sys_conn.close()

    # Connect to test database and create schema
    pool = await asyncpg.create_pool(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USER,
        password=TEST_DB_PASS,
        database=TEST_DB_NAME,
        min_size=2,
        max_size=10
    )
    
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE users (
                id UUID PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                status VARCHAR(50) NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                last_login TIMESTAMP
            )
        """)
        
        await conn.execute("""
            CREATE TABLE refresh_tokens (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL,
                token VARCHAR(255) UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL,
                revoked_at TIMESTAMP,
                CONSTRAINT fk_user
                    FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            )
        """)
        
        # Create indexes
        await conn.execute('CREATE INDEX idx_users_username ON users(username)')
        await conn.execute('CREATE INDEX idx_users_email ON users(email)')
        await conn.execute('CREATE INDEX idx_tokens_user_id ON refresh_tokens(user_id)')
        await conn.execute('CREATE INDEX idx_tokens_token ON refresh_tokens(token)')
        await conn.execute('CREATE INDEX idx_tokens_expires_at ON refresh_tokens(expires_at)')
    
    yield pool
    
    # Cleanup
    await pool.close()
    
    sys_conn = await asyncpg.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        user=TEST_DB_USER,
        password=TEST_DB_PASS,
        database="postgres"
    )
    
    try:
        await sys_conn.execute(f'DROP DATABASE {TEST_DB_NAME}')
    finally:
        await sys_conn.close()

@pytest.fixture
def user_repository(db_pool) -> PostgresUserRepository:
    return PostgresUserRepository(db_pool)

@pytest.fixture
def refresh_token_repository(db_pool) -> PostgresRefreshTokenRepository:
    return PostgresRefreshTokenRepository(db_pool)

@pytest.fixture
def test_user() -> User:
    return User.create(
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password"
    )

class TestUserRepository:
    @pytest.mark.asyncio
    async def test_save_user(self, user_repository: PostgresUserRepository, test_user: User):
        # Test saving new user
        saved_user = await user_repository.save(test_user)
        assert saved_user.id == test_user.id
        assert saved_user.username == test_user.username
        assert saved_user.email == test_user.email

        # Verify user was saved
        retrieved_user = await user_repository.get_by_id(test_user.id)
        assert retrieved_user is not None
        assert retrieved_user.id == test_user.id

    @pytest.mark.asyncio
    async def test_save_user_duplicate_username(
        self, user_repository: PostgresUserRepository, test_user: User
    ):
        await user_repository.save(test_user)
        
        duplicate_user = User.create(
            username=test_user.username,
            email="different@example.com",
            password_hash="different_hash"
        )
        
        with pytest.raises(ValueError, match="Username .* already exists"):
            await user_repository.save(duplicate_user)

    @pytest.mark.asyncio
    async def test_save_user_duplicate_email(
        self, user_repository: PostgresUserRepository, test_user: User
    ):
        await user_repository.save(test_user)
        
        duplicate_user = User.create(
            username="different_user",
            email=test_user.email,
            password_hash="different_hash"
        )
        
        with pytest.raises(ValueError, match="Email .* already exists"):
            await user_repository.save(duplicate_user)

    @pytest.mark.asyncio
    async def test_get_by_id(self, user_repository: PostgresUserRepository, test_user: User):
        await user_repository.save(test_user)
        
        # Test successful retrieval
        retrieved_user = await user_repository.get_by_id(test_user.id)
        assert retrieved_user is not None
        assert retrieved_user.id == test_user.id
        
        # Test non-existent user
        non_existent_id = uuid4()
        retrieved_user = await user_repository.get_by_id(non_existent_id)
        assert retrieved_user is None

    @pytest.mark.asyncio
    async def test_get_by_email(self, user_repository: PostgresUserRepository, test_user: User):
        await user_repository.save(test_user)
        
        # Test successful retrieval
        retrieved_user = await user_repository.get_by_email(test_user.email)
        assert retrieved_user is not None
        assert retrieved_user.email == test_user.email
        
        # Test non-existent email
        retrieved_user = await user_repository.get_by_email("nonexistent@example.com")
        assert retrieved_user is None

    @pytest.mark.asyncio
    async def test_get_by_username(self, user_repository: PostgresUserRepository, test_user: User):
        await user_repository.save(test_user)
        
        # Test successful retrieval
        retrieved_user = await user_repository.get_by_username(test_user.username)
        assert retrieved_user is not None
        assert retrieved_user.username == test_user.username
        
        # Test non-existent username
        retrieved_user = await user_repository.get_by_username("nonexistent")
        assert retrieved_user is None

    @pytest.mark.asyncio
    async def test_update_user(self, user_repository: PostgresUserRepository, test_user: User):
        await user_repository.save(test_user)
        
        # Update user fields
        test_user.username = "updated_username"
        test_user.email = "updated@example.com"
        test_user.role = UserRole.ADMIN
        test_user.status = UserStatus.SUSPENDED
        
        updated_user = await user_repository.update(test_user)
        assert updated_user.username == "updated_username"
        assert updated_user.email == "updated@example.com"
        assert updated_user.role == UserRole.ADMIN
        assert updated_user.status == UserStatus.SUSPENDED

        # Verify updates were saved
        retrieved_user = await user_repository.get_by_id(test_user.id)
        assert retrieved_user.username == "updated_username"
        assert retrieved_user.email == "updated@example.com"

    @pytest.mark.asyncio
    async def test_update_nonexistent_user(
        self, user_repository: PostgresUserRepository, test_user: User
    ):
        with pytest.raises(ValueError, match="User .* does not exist"):
            await user_repository.update(test_user)

    @pytest.mark.asyncio
    async def test_delete_user(self, user_repository: PostgresUserRepository, test_user: User):
        await user_repository.save(test_user)
        
        # Test successful deletion
        success = await user_repository.delete(test_user.id)
        assert success is True
        
        # Verify user was deleted
        retrieved_user = await user_repository.get_by_id(test_user.id)
        assert retrieved_user is None
        
        # Test deleting non-existent user
        success = await user_repository.delete(uuid4())
        assert success is False

    @pytest.mark.asyncio
    async def test_list_users(self, user_repository: PostgresUserRepository):
        # Create test users
        users = []
        for i in range(5):
            user = User.create(
                username=f"user{i}",
                email=f"user{i}@example.com",
                password_hash="hash",
                role=UserRole.USER if i % 2 == 0 else UserRole.ADMIN
            )
            await user_repository.save(user)
            users.append(user)

        # Test pagination
        result = await user_repository.list_users(offset=0, limit=3)
        assert len(result) == 3

        result = await user_repository.list_users(offset=3, limit=3)
        assert len(result) == 2

        # Test filtering by role
        result = await user_repository.list_users(
            filters={'role': UserRole.ADMIN}
        )
        assert len(result) == 2
        assert all(u.role == UserRole.ADMIN for u in result)

        # Test filtering by status
        result = await user_repository.list_users(
            filters={'status': UserStatus.ACTIVE}
        )
        assert len(result) == 5
        assert all(u.status == UserStatus.ACTIVE for u in result)

        # Test filtering by creation date
        result = await user_repository.list_users(
            filters={
                'created_after': datetime.utcnow() - timedelta(minutes=1),
                'created_before': datetime.utcnow() + timedelta(minutes=1)
            }
        )
        assert len(result) == 5

class TestRefreshTokenRepository:
    @pytest.mark.asyncio
    async def test_save_refresh_token(
        self,
        user_repository: PostgresUserRepository,
        refresh_token_repository: PostgresRefreshTokenRepository,
        test_user: User
    ):
        await user_repository.save(test_user)
        
        refresh_token = RefreshToken.create(
            user_id=test_user.id,
            token="test_token",
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        
        saved_token = await refresh_token_repository.save(refresh_token)
        assert saved_token.id == refresh_token.id
        assert saved_token.token == refresh_token.token

    @pytest.mark.asyncio
    async def test_get_by_token(
        self,
        user_repository: PostgresUserRepository,
        refresh_token_repository: PostgresRefreshTokenRepository,
        test_user: User
    ):
        await user_repository.save(test_user)
        
        refresh_token = RefreshToken.create(
            user_id=test_user.id,
            token="test_token",
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        await refresh_token_repository.save(refresh_token)
        
        # Test successful retrieval
        retrieved_token = await refresh_token_repository.get_by_token(refresh_token.token)
        assert retrieved_token is not None
        assert retrieved_token.token == refresh_token.token
        
        # Test non-existent token
        retrieved_token = await refresh_token_repository.get_by_token("nonexistent")
        assert retrieved_token is None

    @pytest.mark.asyncio
    async def test_get_active_by_user_id(
        self,
        user_repository: PostgresUserRepository,
        refresh_token_repository: PostgresRefreshTokenRepository,
        test_user: User
    ):
        await user_repository.save(test_user)
        
        # Create active token
        active_token = RefreshToken.create(
            user_id=test_user.id,
            token="active_token",
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        await refresh_token_repository.save(active_token)
        
        # Create expired token
        expired_token = RefreshToken.create(
            user_id=test_user.id,
            token="expired_token",
            expires_at=datetime.utcnow() - timedelta(days=1)
        )
        await refresh_token_repository.save(expired_token)
        
        # Create revoked token
        revoked_token = RefreshToken.create(
            user_id=test_user.id,
            token="revoked_token",
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        revoked_token.revoke()
        await refresh_token_repository.save(revoked_token)
        
        active_tokens = await refresh_token_repository.get_active_by_user_id(test_user.id)
        assert len(active_tokens) == 1
        assert active_tokens[0].token == "active_token"

    @pytest.mark.asyncio
    async def test_revoke_all_for_user(
        self,
        user_repository: PostgresUserRepository,
        refresh_token_repository: PostgresRefreshTokenRepository,
        test_user: User
    ):
        await user_repository.save(test_user)
        
        # Create multiple active tokens
        tokens = []
        for i in range(3):
            token = RefreshToken.create(
                user_id=test_user.id,
                token=f"token_{i}",
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            await refresh_token_repository.save(token)
            tokens.append(token)
        
        # Revoke all tokens
        await refresh_token_repository.revoke_all_for_user(test_user.id)
        
        # Verify all tokens were revoked
        active_tokens = await refresh_token_repository.get_active_by_user_id(test_user.id)
        assert len(active_tokens) == 0

    @pytest.mark.asyncio
    async def test_delete_expired(
        self,
        user_repository: PostgresUserRepository,
        refresh_token_repository: PostgresRefreshTokenRepository,
        test_user: User
    ):
        await user_repository.save(test_user)
        
        # Create expired tokens
        expired_tokens = []
        for i in range(3):
            token = RefreshToken.create(
                user_id=test_user.id,
                token=f"expired_token_{i}",
                expires_at=datetime.utcnow() - timedelta(days=1)
            )
            await refresh_token_repository.save(token)
            expired_tokens.append(token)

        # Create active tokens
        active_tokens = []
        for i in range(2):
            token = RefreshToken.create(
                user_id=test_user.id,
                token=f"active_token_{i}",
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            await refresh_token_repository.save(token)
            active_tokens.append(token)

        # Create revoked tokens
        revoked_tokens = []
        for i in range(2):
            token = RefreshToken.create(
                user_id=test_user.id,
                token=f"revoked_token_{i}",
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            token.revoke()
            await refresh_token_repository.save(token)
            revoked_tokens.append(token)

        # Delete expired and revoked tokens
        deleted_count = await refresh_token_repository.delete_expired()
        assert deleted_count == 5  # 3 expired + 2 revoked

        # Verify only active tokens remain
        remaining_tokens = await refresh_token_repository.get_active_by_user_id(test_user.id)
        assert len(remaining_tokens) == 2
        assert all(t.token.startswith("active_token") for t in remaining_tokens)

    @pytest.mark.asyncio
    async def test_save_refresh_token_update(
        self,
        user_repository: PostgresUserRepository,
        refresh_token_repository: PostgresRefreshTokenRepository,
        test_user: User
    ):
        await user_repository.save(test_user)
        
        # Create initial token
        refresh_token = RefreshToken.create(
            user_id=test_user.id,
            token="test_token",
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        await refresh_token_repository.save(refresh_token)
        
        # Update token (revoke it)
        refresh_token.revoke()
        updated_token = await refresh_token_repository.save(refresh_token)
        
        assert updated_token.revoked_at is not None
        
        # Verify update was saved
        retrieved_token = await refresh_token_repository.get_by_token("test_token")
        assert retrieved_token.revoked_at is not None

    @pytest.mark.asyncio
    async def test_cascade_delete_user_tokens(
        self,
        user_repository: PostgresUserRepository,
        refresh_token_repository: PostgresRefreshTokenRepository,
        test_user: User
    ):
        await user_repository.save(test_user)
        
        # Create tokens for user
        for i in range(3):
            token = RefreshToken.create(
                user_id=test_user.id,
                token=f"token_{i}",
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            await refresh_token_repository.save(token)
        
        # Delete user
        await user_repository.delete(test_user.id)
        
        # Verify tokens were deleted
        remaining_tokens = await refresh_token_repository.get_active_by_user_id(test_user.id)
        assert len(remaining_tokens) == 0

    @pytest.mark.asyncio
    async def test_token_uniqueness(
        self,
        user_repository: PostgresUserRepository,
        refresh_token_repository: PostgresRefreshTokenRepository,
        test_user: User
    ):
        await user_repository.save(test_user)
        
        # Create first token
        token1 = RefreshToken.create(
            user_id=test_user.id,
            token="duplicate_token",
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        await refresh_token_repository.save(token1)
        
        # Try to create second token with same token string
        token2 = RefreshToken.create(
            user_id=test_user.id,
            token="duplicate_token",
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        
        with pytest.raises(Exception):  # Should raise unique constraint violation
            await refresh_token_repository.save(token2)

    @pytest.mark.asyncio
    async def test_get_active_by_user_id_ordering(
        self,
        user_repository: PostgresUserRepository,
        refresh_token_repository: PostgresRefreshTokenRepository,
        test_user: User
    ):
        await user_repository.save(test_user)
        
        # Create tokens with different creation times
        for i in range(3):
            token = RefreshToken.create(
                user_id=test_user.id,
                token=f"token_{i}",
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            await refresh_token_repository.save(token)
            await asyncio.sleep(0.1)  # Ensure different creation timestamps
        
        # Get active tokens
        active_tokens = await refresh_token_repository.get_active_by_user_id(test_user.id)
        
        # Verify tokens are ordered by creation time (newest first)
        assert len(active_tokens) == 3
        for i in range(1, len(active_tokens)):
            assert active_tokens[i-1].created_at > active_tokens[i].created_at

    @pytest.mark.asyncio
    async def test_refresh_token_bulk_operations(
        self,
        user_repository: PostgresUserRepository,
        refresh_token_repository: PostgresRefreshTokenRepository,
        test_user: User
    ):
        await user_repository.save(test_user)
        
        # Create multiple tokens in different states
        tokens = []
        # Active tokens
        for i in range(5):
            token = RefreshToken.create(
                user_id=test_user.id,
                token=f"active_token_{i}",
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            tokens.append(token)
        
        # Expired tokens
        for i in range(3):
            token = RefreshToken.create(
                user_id=test_user.id,
                token=f"expired_token_{i}",
                expires_at=datetime.utcnow() - timedelta(days=1)
            )
            tokens.append(token)
        
        # Revoked tokens
        for i in range(2):
            token = RefreshToken.create(
                user_id=test_user.id,
                token=f"revoked_token_{i}",
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
            token.revoke()
            tokens.append(token)
        
        # Save all tokens
        for token in tokens:
            await refresh_token_repository.save(token)
        
        # Verify counts
        active_tokens = await refresh_token_repository.get_active_by_user_id(test_user.id)
        assert len(active_tokens) == 5
        
        # Delete expired and revoked
        deleted_count = await refresh_token_repository.delete_expired()
        assert deleted_count == 5  # 3 expired + 2 revoked
        
        # Verify final state
        final_tokens = await refresh_token_repository.get_active_by_user_id(test_user.id)
        assert len(final_tokens) == 5
        assert all(t.token.startswith("active_token") for t in final_tokens)