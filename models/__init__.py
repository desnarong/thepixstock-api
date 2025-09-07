# ============================================================================
# MODELS PACKAGE INITIALIZATION
# ============================================================================
"""
Pydantic models for the Event Photo Sales System.

This package contains all the data models used throughout the application
for request/response validation, database schemas, and business logic.
"""

from .user import (
    UserCreate,
    UserResponse,
    UserUpdate,
    LoginRequest,
    LoginResponse
)

from .event import (
    EventCreate,
    EventResponse,
    EventUpdate,
    EventWithStats,
    EventListResponse
)

from .pricing import (
    PackageType,
    EventPricingCreate,
    EventPricingResponse,
    PricingTemplateCreate,
    PricingTemplateResponse
)

from .sales import (
    SalesStatus,
    EventSalesSettingsCreate,
    EventSalesSettingsResponse
)

from .customer import (
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
    CustomerListResponse
)

from .photographer import (
    PhotographerCreate,
    PhotographerResponse,
    PhotographerUpdate,
    CommissionCreate,
    CommissionResponse,
    PayoutCreate,
    PayoutResponse
)

from .cart import (
    CartSessionCreate,
    CartSessionResponse,
    CartItemAdd,
    CartItemResponse,
    CartResponse
)

from .order import (
    OrderStatus,
    OrderCreate,
    OrderResponse,
    OrderItemResponse,
    OrderListResponse,
    OrderStatsResponse
)

from .payment import (
    PaymentProcess,
    PaymentResponse,
    PaymentStatus,
    PaymentMethodResponse
)

from .download import (
    DownloadLinkResponse,
    DownloadTrackingResponse,
    DownloadStatsResponse
)

from .image import (
    ImageUpload,
    ImageResponse,
    ImageListResponse,
    WatermarkCreate,
    WatermarkResponse,
    ImageMetadata
)

from .analytics import (
    RevenueAnalyticsResponse,
    PopularImageResponse,
    CustomerAnalyticsResponse,
    SalesPerformanceResponse,
    DashboardStatsResponse
)

from .system import (
    SystemSettingResponse,
    SystemSettingUpdate,
    EmailTemplateCreate,
    EmailTemplateResponse,
    NotificationCreate,
    NotificationResponse
)

from .common import (
    PaginationResponse,
    BaseResponse,
    ErrorResponse,
    SuccessResponse,
    TimestampMixin,
    UUIDMixin
)

# Export all models for easy importing
__all__ = [
    # User models
    "UserCreate",
    "UserResponse", 
    "UserUpdate",
    "LoginRequest",
    "LoginResponse",
    
    # Event models
    "EventCreate",
    "EventResponse",
    "EventUpdate", 
    "EventWithStats",
    "EventListResponse",
    
    # Pricing models
    "PackageType",
    "EventPricingCreate",
    "EventPricingResponse",
    "PricingTemplateCreate", 
    "PricingTemplateResponse",
    
    # Sales models
    "SalesStatus",
    "EventSalesSettingsCreate",
    "EventSalesSettingsResponse",
    
    # Customer models
    "CustomerCreate",
    "CustomerResponse",
    "CustomerUpdate",
    "CustomerListResponse",
    
    # Photographer models
    "PhotographerCreate",
    "PhotographerResponse",
    "PhotographerUpdate",
    "CommissionCreate",
    "CommissionResponse", 
    "PayoutCreate",
    "PayoutResponse",
    
    # Cart models
    "CartSessionCreate",
    "CartSessionResponse",
    "CartItemAdd",
    "CartItemResponse",
    "CartResponse",
    
    # Order models
    "OrderStatus",
    "OrderCreate",
    "OrderResponse",
    "OrderItemResponse",
    "OrderListResponse",
    "OrderStatsResponse",
    
    # Payment models
    "PaymentProcess",
    "PaymentResponse",
    "PaymentStatus",
    "PaymentMethodResponse",
    
    # Download models
    "DownloadLinkResponse",
    "DownloadTrackingResponse", 
    "DownloadStatsResponse",
    
    # Image models
    "ImageUpload",
    "ImageResponse",
    "ImageListResponse",
    "WatermarkCreate",
    "WatermarkResponse",
    "ImageMetadata",
    
    # Analytics models
    "RevenueAnalyticsResponse",
    "PopularImageResponse",
    "CustomerAnalyticsResponse",
    "SalesPerformanceResponse",
    "DashboardStatsResponse",
    
    # System models
    "SystemSettingResponse",
    "SystemSettingUpdate",
    "EmailTemplateCreate",
    "EmailTemplateResponse",
    "NotificationCreate",
    "NotificationResponse",
    
    # Common models
    "PaginationResponse",
    "BaseResponse",
    "ErrorResponse", 
    "SuccessResponse",
    "TimestampMixin",
    "UUIDMixin"
]

# Version info
__version__ = "1.0.0"
__author__ = "Event Photo Sales System"
__description__ = "Pydantic models for Event Photo Sales System API"

# Model categories for documentation
MODEL_CATEGORIES = {
    "authentication": ["UserCreate", "UserResponse", "LoginRequest", "LoginResponse"],
    "events": ["EventCreate", "EventResponse", "EventUpdate", "EventWithStats"],
    "ecommerce": ["OrderCreate", "OrderResponse", "PaymentProcess", "CartResponse"],
    "media": ["ImageUpload", "ImageResponse", "WatermarkCreate", "WatermarkResponse"],
    "analytics": ["RevenueAnalyticsResponse", "DashboardStatsResponse", "SalesPerformanceResponse"],
    "system": ["SystemSettingResponse", "EmailTemplateCreate", "NotificationResponse"]
}

def get_models_by_category(category: str) -> list:
    """
    Get list of model names by category.
    
    Args:
        category: Category name (authentication, events, ecommerce, media, analytics, system)
        
    Returns:
        List of model class names in the category
    """
    return MODEL_CATEGORIES.get(category, [])

def get_all_categories() -> list:
    """
    Get list of all available model categories.
    
    Returns:
        List of category names
    """
    return list(MODEL_CATEGORIES.keys())

# Validation settings
VALIDATION_CONFIG = {
    "validate_assignment": True,
    "use_enum_values": True,
    "extra": "forbid",
    "str_strip_whitespace": True,
    "json_encoders": {
        # Custom JSON encoders can be added here
    }
}
