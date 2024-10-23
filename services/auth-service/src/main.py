# src/main.py
import asyncio
import logging
import os
from typing import List, Optional, Dict, Any
from uuid import UUID

import asyncpg
from fastapi import FastAPI, Depends, HTTPException, Security, BackgroundTasks, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import SecurityScopes
from starlette.status import (
    HTTP_401_UNAUTHORIZED, 
    HTTP_403_FORBIDDEN, 
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT
)
from starlette.responses import JSONResponse

from .application.dto import (
    UserDTO, UserCreateDTO, UserUpdateDTO,
    LoginRequestDTO, LoginResponseDTO, RefreshTokenRequestDTO
)
from .application.services import UserService, AuthenticationError, AuthorizationError
from .domain.models import UserRole, UserStatus
from .domain.repositories import (
    PostgresUserRepository,
    PostgresRefreshTokenRepository
)
from .infrastructure.auth import AuthHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Auth Service",
    description="Authentication and Authorization Service for JSE Stock Platform",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
TOKEN_CLEANUP_INTERVAL_HOURS = int(os.getenv("TOKEN_CLEANUP_INTERVAL_HOURS", "24"))

# Database pool
async def init_db_pool():
    return await asyncpg.create_pool(
        DATABASE_URL,
        min_size=5,
        max_size=20,
        command_timeout=60,
        server_settings={
            'timezone': 'UTC'
        }
    )

# Dependency providers
async def get_db_pool() -> asyncpg.Pool:
    return app.state.pool

async def get_user_repository(
    pool: asyncpg.Pool = Depends(get_db_pool)
) -> PostgresUserRepository:
    return PostgresUserRepository(pool)

async def get_refresh_token_repository(
    pool: asyncpg.Pool = Depends(get_db_pool)
) -> PostgresRefreshTokenRepository:
    return PostgresRefreshTokenRepository(pool)

async def get_user_service(
    user_repository: PostgresUserRepository = Depends(get_user_repository),
    refresh_token_repository: PostgresRefreshTokenRepository = Depends(get_refresh_token_repository)
) -> UserService:
    return UserService(
        user_repository=user_repository,
        refresh_token_repository=refresh_token_repository,
        jwt_secret=JWT_SECRET_KEY,
        jwt_algorithm=JWT_ALGORITHM,
        access_token_expire_minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
        refresh_token_expire_days=REFRESH_TOKEN_EXPIRE_DAYS
    )

async def get_auth_handler(
    user_service: UserService = Depends(get_user_service)
) -> AuthHandler:
    return AuthHandler(user_service)

# Background tasks
async def cleanup_expired_tokens(app: FastAPI):
    while True:
        try:
            refresh_token_repository = PostgresRefreshTokenRepository(app.state.pool)
            deleted_count = await refresh_token_repository.delete_expired()
            logger.info(f"Cleaned up {deleted_count} expired refresh tokens")
        except Exception as e:
            logger.error(f"Error during token cleanup: {str(e)}")
        finally:
            await asyncio.sleep(TOKEN_CLEANUP_INTERVAL_HOURS * 3600)

# Exception handlers
@app.exception_handler(AuthenticationError)
async def authentication_error_handler(request: Request, exc: AuthenticationError):
    return JSONResponse(
        status_code=HTTP_401_UNAUTHORIZED,
        content={"detail": str(exc)},
        headers={"WWW-Authenticate": "Bearer"}
    )

@app.exception_handler(AuthorizationError)
async def authorization_error_handler(request: Request, exc: AuthorizationError):
    return JSONResponse(
        status_code=HTTP_403_FORBIDDEN,
        content={"detail": str(exc)}
    )

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    # Initialize database pool
    app.state.pool = await init_db_pool()
    
    # Start background tasks
    asyncio.create_task(cleanup_expired_tokens(app))

@app.on_event("shutdown")
async def shutdown_event():
    await app.state.pool.close()

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Auth endpoints
@app.post("/auth/register", response_model=UserDTO)
async def register(
    user_create: UserCreateDTO,
    user_service: UserService = Depends(get_user_service)
):
    try:
        return await user_service.create_user(user_create)
    except ValueError as e:
        raise HTTPException(
            status_code=HTTP_409_CONFLICT,
            detail=str(e)
        )

@app.post("/auth/login", response_model=LoginResponseDTO)
async def login(
    login_request: LoginRequestDTO,
    user_service: UserService = Depends(get_user_service)
):
    return await user_service.login(login_request)

@app.post("/auth/refresh", response_model=LoginResponseDTO)
async def refresh_token(
    refresh_request: RefreshTokenRequestDTO,
    user_service: UserService = Depends(get_user_service)
):
    return await user_service.refresh_token(refresh_request)

@app.post("/auth/logout")
async def logout(
    user_service: UserService = Depends(get_user_service),
    auth_handler: AuthHandler = Depends(get_auth_handler),
    token_payload = Security(AuthHandler.get_current_user)
):
    await user_service.logout(token_payload.sub)
    return {"message": "Successfully logged out"}

# User management endpoints
@app.get("/users/me", response_model=UserDTO)
async def get_current_user_profile(
    user_service: UserService = Depends(get_user_service),
    auth_handler: AuthHandler = Depends(get_auth_handler),
    token_payload = Security(AuthHandler.get_current_active_user)
):
    user = await user_service.get_user_by_id(token_payload.sub)
    if not user:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@app.put("/users/me", response_model=UserDTO)
async def update_current_user_profile(
    user_update: UserUpdateDTO,
    user_service: UserService = Depends(get_user_service),
    auth_handler: AuthHandler = Depends(get_auth_handler),
    token_payload = Security(AuthHandler.get_current_active_user)
):
    try:
        return await user_service.update_user(token_payload.sub, user_update)
    except ValueError as e:
        raise HTTPException(
            status_code=HTTP_409_CONFLICT,
            detail=str(e)
        )

@app.get("/users", response_model=List[UserDTO])
async def list_users(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    role: Optional[UserRole] = None,
    status: Optional[UserStatus] = None,
    user_service: UserService = Depends(get_user_service),
    auth_handler: AuthHandler = Depends(get_auth_handler),
    token_payload = Security(AuthHandler.get_current_admin_user)
):
    filters = {}
    if role:
        filters['role'] = role
    if status:
        filters['status'] = status
        
    return await user_service.list_users(offset=offset, limit=limit, filters=filters)

@app.get("/users/{user_id}", response_model=UserDTO)
async def get_user(
    user_id: UUID,
    user_service: UserService = Depends(get_user_service),
    auth_handler: AuthHandler = Depends(get_auth_handler),
    token_payload = Security(AuthHandler.get_current_admin_user)
):
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@app.put("/users/{user_id}", response_model=UserDTO)
async def update_user(
    user_id: UUID,
    user_update: UserUpdateDTO,
    user_service: UserService = Depends(get_user_service),
    auth_handler: AuthHandler = Depends(get_auth_handler),
    token_payload = Security(AuthHandler.get_current_admin_user)
):
    try:
        return await user_service.update_user(user_id, user_update)
    except ValueError as e:
        raise HTTPException(
            status_code=HTTP_409_CONFLICT,
            detail=str(e)
        )

@app.delete("/users/{user_id}")
async def delete_user(
    user_id: UUID,
    user_service: UserService = Depends(get_user_service),
    auth_handler: AuthHandler = Depends(get_auth_handler),
    token_payload = Security(AuthHandler.get_current_admin_user)
):
    if not await user_service.delete_user(user_id):
        raise HTTPException(
            status_code=HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return {"message": "User successfully deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)