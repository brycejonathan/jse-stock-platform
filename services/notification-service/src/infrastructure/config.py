from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Settings
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "JSE Stock Platform - Notification Service"
    DEBUG: bool = False
    
    # CORS Settings
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # MongoDB Settings
    MONGODB_URL: str
    MONGODB_DATABASE: str = "jse_stock_platform"
    
    # AWS Settings
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "us-east-1"
    
    # Email Settings
    SENDER_EMAIL: str
    
    # JWT Settings
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()