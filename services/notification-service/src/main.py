from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from infrastructure.config import Settings
from infrastructure.logging import setup_logging
from infrastructure.exceptions import NotificationServiceException
from application.routes import router as notification_router

app = FastAPI(title="JSE Stock Platform - Notification Service")

# Setup logging
logger = setup_logging()

# Load settings
settings = Settings()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(notification_router, prefix="/api/v1/notifications")

@app.exception_handler(NotificationServiceException)
async def notification_exception_handler(request: Request, exc: NotificationServiceException):
    logger.error(f"Error processing request: {exc.detail}", 
                extra={"path": request.url.path, "method": request.method})
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.on_event("startup")
async def startup_event():
    logger.info("Starting notification service")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down notification service")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)