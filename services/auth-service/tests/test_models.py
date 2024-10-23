# tests/test_models.py
import pytest
from datetime import datetime, timedelta
from uuid import UUID
from src.domain.models import User, RefreshToken, UserRole, UserStatus

def test_user_create():
    username = "testuser"
    email = "test@example.com"
    password_hash = "hashed_password"
    
    user = User.create(username, email, password_hash)
    
    assert isinstance(user.id, UUID)
    assert user.username == username
    assert user.email == email
    assert user.password_hash == password_hash
    assert user.role == UserRole.USER
    assert user.status == UserStatus.ACTIVE
    assert isinstance(user.created_at, datetime)
    assert isinstance(user.updated_at, datetime)
    assert user.last_login is None

def test_user_create_with_admin_role():
    user = User.create(
        "admin",
        "admin@example.com",
        "hashed_password",
        role=UserRole.ADMIN
    )
    assert user.role == UserRole.ADMIN

def test_user_suspend():
    user = User.create("testuser", "test@example.com", "hashed_password")
    original_updated_at = user.updated_at
    
    user.suspend()
    
    assert user.status == UserStatus.SUSPENDED
    assert user.updated_at > original_updated_at

def test_user_activate():
    user = User.create("testuser", "test@example.com", "hashed_password")
    user.suspend()
    original_updated_at = user.updated_at
    
    user.activate()
    
    assert user.status == UserStatus.ACTIVE
    assert user.updated_at > original_updated_at

def test_user_update_login():
    user = User.create("testuser", "test@example.com", "hashed_password")
    original_updated_at = user.updated_at
    
    user.update_login()
    
    assert user.last_login is not None
    assert user.updated_at > original_updated_at
    assert (datetime.utcnow() - user.last_login).total_seconds() < 1

def test_refresh_token_create():
    user_id = UUID('12345678-1234-5678-1234-567812345678')
    token = "test_token"
    expires_at = datetime.utcnow() + timedelta(days=7)
    
    refresh_token = RefreshToken.create(user_id, token, expires_at)
    
    assert isinstance(refresh_token.id, UUID)
    assert refresh_token.user_id == user_id
    assert refresh_token.token == token
    assert refresh_token.expires_at == expires_at
    assert isinstance(refresh_token.created_at, datetime)
    assert refresh_token.revoked_at is None

def test_refresh_token_revoke():
    user_id = UUID('12345678-1234-5678-1234-567812345678')
    token = "test_token"
    expires_at = datetime.utcnow() + timedelta(days=7)
    
    refresh_token = RefreshToken.create(user_id, token, expires_at)
    refresh_token.revoke()
    
    assert refresh_token.revoked_at is not None
    assert (datetime.utcnow() - refresh_token.revoked_at).total_seconds() < 1

def test_refresh_token_is_valid():
    user_id = UUID('12345678-1234-5678-1234-567812345678')
    token = "test_token"
    
    # Test valid token
    expires_at = datetime.utcnow() + timedelta(days=7)
    valid_token = RefreshToken.create(user_id, token, expires_at)
    assert valid_token.is_valid() is True
    
    # Test expired token
    expires_at = datetime.utcnow() - timedelta(days=1)
    expired_token = RefreshToken.create(user_id, token, expires_at)
    assert expired_token.is_valid() is False
    
    # Test revoked token
    valid_token.revoke()
    assert valid_token.is_valid() is False