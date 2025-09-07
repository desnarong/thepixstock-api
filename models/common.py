# ============================================================================
# COMMON BASE MODELS
# ============================================================================
"""
Common base models and utilities used across the Event Photo Sales System.
Contains base classes, mixins, and common response structures.
"""

from datetime import datetime
from typing import Optional, Any, Dict, List, Generic, TypeVar
from pydantic import BaseModel, Field, UUID4, validator
from enum import Enum

# ============================================================================
# TYPE VARIABLES
# ============================================================================
T = TypeVar('T')

# ============================================================================
# BASE MIXINS
# ============================================================================
class UUIDMixin(BaseModel):
    """Mixin for models that use UUID as primary key."""
    id: UUID4 = Field(..., description="Unique identifier")

class TimestampMixin(BaseModel):
    """Mixin for models that track creation and update timestamps."""
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

class UserTrackingMixin(BaseModel):
    """Mixin for models that track which user created/modified them."""
    created_by: Optional[UUID4] = Field(None, description="User who created this record")
    updated_by: Optional[UUID4] = Field(None, description="User who last updated this record")

# ============================================================================
# ENUMS
# ============================================================================
class StatusEnum(str, Enum):
    """Base enum for status fields."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    DELETED = "deleted"

class SortOrder(str, Enum):
    """Enum for sort order in API queries."""
    ASC = "asc"
    DESC = "desc"

# ============================================================================
# PAGINATION MODELS
# ============================================================================
class PaginationParams(BaseModel):
    """Parameters for pagination requests."""
    page: int = Field(1, ge=1, description="Page number (1-based)")
    limit: int = Field(20, ge=1, le=100, description="Number of items per page")
    
    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.limit

class PaginationMeta(BaseModel):
    """Pagination metadata for responses."""
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")
    total: int = Field(..., description="Total number of items")
    pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")
    
    @validator('pages', always=True)
    def calculate_pages(cls, v, values):
        """Calculate total pages from total and limit."""
        total = values.get('total', 0)
        limit = values.get('limit', 1)
        return (total + limit - 1) // limit if total > 0 else 0
    
    @validator('has_next', always=True)
    def calculate_has_next(cls, v, values):
        """Calculate if there is a next page."""
        page = values.get('page', 1)
        pages = values.get('pages', 0)
        return page < pages
    
    @validator('has_prev', always=True)
    def calculate_has_prev(cls, v, values):
        """Calculate if there is a previous page."""
        page = values.get('page', 1)
        return page > 1

class PaginationResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""
    data: List[T] = Field(..., description="List of items")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")

# ============================================================================
# RESPONSE MODELS
# ============================================================================
class BaseResponse(BaseModel):
    """Base response model with common fields."""
    success: bool = Field(True, description="Whether the request was successful")
    message: Optional[str] = Field(None, description="Optional message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

class SuccessResponse(BaseResponse):
    """Standard success response."""
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")

class ErrorResponse(BaseResponse):
    """Standard error response."""
    success: bool = Field(False, description="Always false for error responses")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")

class MessageResponse(BaseResponse):
    """Simple message response."""
    pass

# ============================================================================
# SEARCH AND FILTER MODELS
# ============================================================================
class SearchParams(BaseModel):
    """Parameters for search requests."""
    query: Optional[str] = Field(None, min_length=1, max_length=255, description="Search query string")
    fields: Optional[List[str]] = Field(None, description="Fields to search in")

class DateRangeFilter(BaseModel):
    """Date range filter for queries."""
    start_date: Optional[datetime] = Field(None, description="Start date")
    end_date: Optional[datetime] = Field(None, description="End date")
    
    @validator('end_date')
    def end_after_start(cls, v, values):
        """Ensure end date is after start date."""
        start_date = values.get('start_date')
        if start_date and v and v < start_date:
            raise ValueError('end_date must be after start_date')
        return v

class SortParams(BaseModel):
    """Parameters for sorting results."""
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: SortOrder = Field(SortOrder.DESC, description="Sort order")

# ============================================================================
# FILE UPLOAD MODELS
# ============================================================================
class FileUploadResponse(BaseModel):
    """Response model for file uploads."""
    file_id: UUID4 = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME content type")
    url: Optional[str] = Field(None, description="Public URL if available")
    upload_timestamp: datetime = Field(default_factory=datetime.utcnow)

class FileMetadata(BaseModel):
    """File metadata information."""
    filename: str = Field(..., description="File name")
    file_size: int = Field(..., ge=0, description="File size in bytes")
    content_type: str = Field(..., description="MIME content type")
    file_hash: Optional[str] = Field(None, description="File hash for integrity checking")

# ============================================================================
# VALIDATION MODELS
# ============================================================================
class ValidationError(BaseModel):
    """Individual validation error."""
    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Error message")
    code: Optional[str] = Field(None, description="Error code")

class ValidationResponse(ErrorResponse):
    """Response for validation errors."""
    validation_errors: List[ValidationError] = Field(..., description="List of validation errors")

# ============================================================================
# STATISTICS MODELS
# ============================================================================
class CountResponse(BaseModel):
    """Simple count response."""
    count: int = Field(..., ge=0, description="Count value")
    label: Optional[str] = Field(None, description="Label for the count")

class PercentageResponse(BaseModel):
    """Percentage response."""
    value: float = Field(..., ge=0, le=100, description="Percentage value")
    total: int = Field(..., ge=0, description="Total count")
    label: Optional[str] = Field(None, description="Label for the percentage")

class StatsGroup(BaseModel):
    """Group of related statistics."""
    name: str = Field(..., description="Group name")
    stats: List[CountResponse] = Field(..., description="List of statistics")

# ============================================================================
# AUDIT MODELS
# ============================================================================
class AuditAction(str, Enum):
    """Enumeration of audit actions."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LOGIN = "login"
    LOGOUT = "logout"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    PAYMENT = "payment"

class AuditEntry(BaseModel):
    """Audit log entry."""
    action: AuditAction = Field(..., description="Action performed")
    resource_type: str = Field(..., description="Type of resource affected")
    resource_id: Optional[UUID4] = Field(None, description="ID of affected resource")
    user_id: Optional[UUID4] = Field(None, description="User who performed the action")
    ip_address: Optional[str] = Field(None, description="IP address of the user")
    user_agent: Optional[str] = Field(None, description="User agent string")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ============================================================================
# CONFIGURATION MODELS
# ============================================================================
class ConfigSetting(BaseModel):
    """System configuration setting."""
    key: str = Field(..., description="Setting key")
    value: Any = Field(..., description="Setting value")
    data_type: str = Field(..., description="Data type of the value")
    description: Optional[str] = Field(None, description="Setting description")
    is_public: bool = Field(False, description="Whether setting is publicly accessible")

class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Overall health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, str] = Field(..., description="Status of individual services")
    version: Optional[str] = Field(None, description="Application version")

# ============================================================================
# CURRENCY AND MONEY MODELS
# ============================================================================
class Currency(str, Enum):
    """Supported currencies."""
    THB = "THB"
    USD = "USD"
    EUR = "EUR"

class MoneyAmount(BaseModel):
    """Money amount with currency."""
    amount: float = Field(..., ge=0, description="Amount value")
    currency: Currency = Field(Currency.THB, description="Currency code")
    
    def __str__(self) -> str:
        """String representation of money amount."""
        return f"{self.amount:.2f} {self.currency.value}"

# ============================================================================
# NOTIFICATION MODELS
# ============================================================================
class NotificationType(str, Enum):
    """Types of notifications."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"

class NotificationBase(BaseModel):
    """Base notification model."""
    type: NotificationType = Field(..., description="Notification type")
    title: str = Field(..., max_length=255, description="Notification title")
    message: str = Field(..., description="Notification message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional notification data")

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def create_pagination_meta(page: int, limit: int, total: int) -> PaginationMeta:
    """Create pagination metadata."""
    return PaginationMeta(
        page=page,
        limit=limit,
        total=total,
        pages=(total + limit - 1) // limit if total > 0 else 0,
        has_next=page < ((total + limit - 1) // limit),
        has_prev=page > 1
    )

def create_success_response(data: Any = None, message: str = None) -> SuccessResponse:
    """Create a standard success response."""
    return SuccessResponse(
        data=data if data is not None else {},
        message=message
    )

def create_error_response(message: str, error_code: str = None, details: Dict[str, Any] = None) -> ErrorResponse:
    """Create a standard error response."""
    return ErrorResponse(
        message=message,
        error_code=error_code,
        details=details
    )
