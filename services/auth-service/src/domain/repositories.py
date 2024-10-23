# src/domain/repositories.py
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncpg
from uuid import UUID
from .models import User, RefreshToken, UserRole, UserStatus

class UserRepository(ABC):
    @abstractmethod
    async def save(self, user: User) -> User:
        """
        Save a new user or update existing user.
        Raises ValueError if user with same email/username already exists.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        raise NotImplementedError

    @abstractmethod
    async def update(self, user: User) -> User:
        """
        Update existing user.
        Raises ValueError if user does not exist.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self, user_id: UUID) -> bool:
        """
        Delete user by ID.
        Returns True if user was deleted, False if user did not exist.
        """
        raise NotImplementedError

    @abstractmethod
    async def list_users(
        self,
        offset: int = 0,
        limit: int = 100,
        filters: Dict[str, Any] = None
    ) -> List[User]:
        """
        List users with pagination and optional filtering.
        filters can include: role, status, created_after, created_before
        """
        raise NotImplementedError

    @abstractmethod
    async def count_users(self, filters: Dict[str, Any] = None) -> int:
        """Count total users matching optional filters."""
        raise NotImplementedError


class PostgresUserRepository(UserRepository):
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def save(self, user: User) -> User:
        async with self.pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    """
                    INSERT INTO users (
                        id, username, email, password_hash, role, status,
                        created_at, updated_at, last_login
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (id) DO UPDATE SET
                        username = EXCLUDED.username,
                        email = EXCLUDED.email,
                        password_hash = EXCLUDED.password_hash,
                        role = EXCLUDED.role,
                        status = EXCLUDED.status,
                        updated_at = EXCLUDED.updated_at,
                        last_login = EXCLUDED.last_login
                    RETURNING *
                    """,
                    user.id,
                    user.username,
                    user.email,
                    user.password_hash,
                    user.role.value,
                    user.status.value,
                    user.created_at,
                    user.updated_at,
                    user.last_login
                )
                return self._row_to_user(row)
            except asyncpg.UniqueViolationError as e:
                if 'users_username_key' in str(e):
                    raise ValueError(f"Username {user.username} already exists")
                if 'users_email_key' in str(e):
                    raise ValueError(f"Email {user.email} already exists")
                raise

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1",
                user_id
            )
            return self._row_to_user(row) if row else None

    async def get_by_email(self, email: str) -> Optional[User]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE email = $1",
                email
            )
            return self._row_to_user(row) if row else None

    async def get_by_username(self, username: str) -> Optional[User]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE username = $1",
                username
            )
            return self._row_to_user(row) if row else None

    async def update(self, user: User) -> User:
        async with self.pool.acquire() as conn:
            try:
                row = await conn.fetchrow(
                    """
                    UPDATE users SET
                        username = $2,
                        email = $3,
                        password_hash = $4,
                        role = $5,
                        status = $6,
                        updated_at = $7,
                        last_login = $8
                    WHERE id = $1
                    RETURNING *
                    """,
                    user.id,
                    user.username,
                    user.email,
                    user.password_hash,
                    user.role.value,
                    user.status.value,
                    user.updated_at,
                    user.last_login
                )
                if not row:
                    raise ValueError(f"User with id {user.id} does not exist")
                return self._row_to_user(row)
            except asyncpg.UniqueViolationError as e:
                if 'users_username_key' in str(e):
                    raise ValueError(f"Username {user.username} already exists")
                if 'users_email_key' in str(e):
                    raise ValueError(f"Email {user.email} already exists")
                raise

    async def delete(self, user_id: UUID) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM users WHERE id = $1",
                user_id
            )
            return result.split()[-1] != '0'

    async def list_users(
        self,
        offset: int = 0,
        limit: int = 100,
        filters: Dict[str, Any] = None
    ) -> List[User]:
        filters = filters or {}
        query = ["SELECT * FROM users WHERE 1=1"]
        params = []
        param_idx = 1

        if filters.get('role'):
            query.append(f"AND role = ${param_idx}")
            params.append(filters['role'].value)
            param_idx += 1

        if filters.get('status'):
            query.append(f"AND status = ${param_idx}")
            params.append(filters['status'].value)
            param_idx += 1

        if filters.get('created_after'):
            query.append(f"AND created_at >= ${param_idx}")
            params.append(filters['created_after'])
            param_idx += 1

        if filters.get('created_before'):
            query.append(f"AND created_at <= ${param_idx}")
            params.append(filters['created_before'])
            param_idx += 1

        query.append(f"ORDER BY created_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}")
        params.extend([limit, offset])

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(' '.join(query), *params)
            return [self._row_to_user(row) for row in rows]

    async def count_users(self, filters: Dict[str, Any] = None) -> int:
        filters = filters or {}
        query = ["SELECT COUNT(*) FROM users WHERE 1=1"]
        params = []
        param_idx = 1

        if filters.get('role'):
            query.append(f"AND role = ${param_idx}")
            params.append(filters['role'].value)
            param_idx += 1

        if filters.get('status'):
            query.append(f"AND status = ${param_idx}")
            params.append(filters['status'].value)
            param_idx += 1

        if filters.get('created_after'):
            query.append(f"AND created_at >= ${param_idx}")
            params.append(filters['created_after'])
            param_idx += 1

        if filters.get('created_before'):
            query.append(f"AND created_at <= ${param_idx}")
            params.append(filters['created_before'])
            param_idx += 1

        async with self.pool.acquire() as conn:
            return await conn.fetchval(' '.join(query), *params)

    @staticmethod
    def _row_to_user(row: asyncpg.Record) -> User:
        return User(
            id=row['id'],
            username=row['username'],
            email=row['email'],
            password_hash=row['password_hash'],
            role=UserRole(row['role']),
            status=UserStatus(row['status']),
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            last_login=row['last_login']
        )


class RefreshTokenRepository(ABC):
    @abstractmethod
    async def save(self, refresh_token: RefreshToken) -> RefreshToken:
        """Save a new refresh token."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_token(self, token: str) -> Optional[RefreshToken]:
        """Get refresh token by token string."""
        raise NotImplementedError

    @abstractmethod
    async def get_active_by_user_id(self, user_id: UUID) -> List[RefreshToken]:
        """Get all active refresh tokens for a user."""
        raise NotImplementedError

    @abstractmethod
    async def revoke_all_for_user(self, user_id: UUID) -> None:
        """Revoke all refresh tokens for a user."""
        raise NotImplementedError

    @abstractmethod
    async def delete_expired(self) -> int:
        """Delete all expired refresh tokens. Returns number of tokens deleted."""
        raise NotImplementedError


class PostgresRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def save(self, refresh_token: RefreshToken) -> RefreshToken:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO refresh_tokens (
                    id, user_id, token, expires_at, created_at, revoked_at
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO UPDATE SET
                    revoked_at = EXCLUDED.revoked_at
                RETURNING *
                """,
                refresh_token.id,
                refresh_token.user_id,
                refresh_token.token,
                refresh_token.expires_at,
                refresh_token.created_at,
                refresh_token.revoked_at
            )
            return self._row_to_refresh_token(row)

    async def get_by_token(self, token: str) -> Optional[RefreshToken]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM refresh_tokens WHERE token = $1",
                token
            )
            return self._row_to_refresh_token(row) if row else None

    async def get_active_by_user_id(self, user_id: UUID) -> List[RefreshToken]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM refresh_tokens 
                WHERE user_id = $1 
                AND revoked_at IS NULL 
                AND expires_at > NOW()
                """,
                user_id
            )
            return [self._row_to_refresh_token(row) for row in rows]

    async def revoke_all_for_user(self, user_id: UUID) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE refresh_tokens 
                SET revoked_at = NOW() 
                WHERE user_id = $1 
                AND revoked_at IS NULL
                """,
                user_id
            )

    async def delete_expired(self) -> int:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM refresh_tokens 
                WHERE expires_at <= NOW() 
                OR revoked_at IS NOT NULL
                """
            )
            return int(result.split()[-1])

    @staticmethod
    def _row_to_refresh_token(row: asyncpg.Record) -> RefreshToken:
        return RefreshToken(
            id=row['id'],
            user_id=row['user_id'],
            token=row['token'],
            expires_at=row['expires_at'],
            created_at=row['created_at'],
            revoked_at=row['revoked_at']
        )