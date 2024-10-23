from typing import Any, Optional

class NotificationServiceException(Exception):
    def __init__(
        self,
        status_code: int,
        detail: str,
        internal_code: Optional[str] = None,
        data: Optional[dict] = None
    ):
        self.status_code = status_code
        self.detail = detail
        self.internal_code = internal_code
        self.data = data or {}
        super().__init__(detail)

class ValidationException(NotificationServiceException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=400,
            detail=detail,
            internal_code="VALIDATION_ERROR"
        )

class UnauthorizedException(NotificationServiceException):
    def __init__(self):
        super().__init__(
            status_code=401,
            detail="Invalid or expired authentication credentials",
            internal_code="UNAUTHORIZED"
        )

class ForbiddenException(NotificationServiceException):
    def __init__(self):
        super().__init__(
            status_code=403,
            detail="You don't have permission to perform this action",
            internal_code="FORBIDDEN"
        )

class NotFoundException(NotificationServiceException):
    def __init__(self, resource_type: str, resource_id: Any):
        super().__init__(
            status_code=404,
            detail=f"{resource_type} with id {resource_id} not found",
            internal_code="NOT_FOUND",
            data={"resource_type": resource_type, "resource_id": str(resource_id)}
        )

class NotificationDeliveryException(NotificationServiceException):
    def __init__(self, detail: str, provider: str):
        super().__init__(
            status_code=500,
            detail=detail,
            internal_code="NOTIFICATION_DELIVERY_ERROR",
            data={"provider": provider}
        )

class DatabaseException(NotificationServiceException):
    def __init__(self, operation: str, detail: str):
        super().__init__(
            status_code=500,
            detail=f"Database error during {operation}: {detail}",
            internal_code="DATABASE_ERROR",
            data={"operation": operation}
        )