# src/infrastructure/auth.py
from datetime import datetime
import logging
from typing import Optional
from fastapi import Depends, HTTPException, Security
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN
from uuid import UUID

from ..application.services import UserService, AuthenticationError, AuthorizationError
from ..domain.models import UserRole, UserStatus
from ..application.dto import TokenPayloadDTO

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/login",
    scopes={
        "user": "Standard user access",
        "admin": "Administrator access"
    }
)

class AuthHandler:
    def __init__(self, user_service: UserService):
        self.user_service = user_service

    async def get_current_user(
        self,
        security_scopes: SecurityScopes,
        token: str = Depends(oauth2_scheme)
    ) -> TokenPayloadDTO:
        try:
            if security_scopes.scopes:
                authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
            else:
                authenticate_value = "Bearer"

            credentials_exception = HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": authenticate_value},
            )

            # Verify token and get payload
            try:
                token_payload = await self.user_service.verify_token(token)
            except AuthenticationError as e:
                raise credentials_exception from e

            # Check if token has required scopes
            token_scopes = []
            if token_payload.role == UserRole.ADMIN:
                token_scopes = ["user", "admin"]
            elif token_payload.role == UserRole.USER:
                token_scopes = ["user"]

            for scope in security_scopes.scopes:
                if scope not in token_scopes:
                    raise HTTPException(
                        status_code=HTTP_403_FORBIDDEN,
                        detail="Not enough permissions",
                        headers={"WWW-Authenticate": authenticate_value},
                    )

            return token_payload

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            raise credentials_exception from e

    def get_current_active_user(
        self,
        token_payload: TokenPayloadDTO = Security(get_current_user, scopes=["user"])
    ) -> TokenPayloadDTO:
        return token_payload

    def get_current_admin_user(
        self,
        token_payload: TokenPayloadDTO = Security(get_current_user, scopes=["admin"])
    ) -> TokenPayloadDTO:
        return token_payload