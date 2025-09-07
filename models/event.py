# ============================================================================
# EVENT MODELS
# ============================================================================
"""
Event-related models for the Event Photo Sales System.
Includes events, event settings, and image management.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, UUID4, validator, HttpUrl
from enum import Enum
from decimal import Decimal

from .common import (
    TimestampMixin, 
    UUIDMixin, 
    BaseResponse, 
    PaginationResponse,
    MoneyAmount,
    DateRangeFilter
)

# ============================================================================
# ENUMS
# ============================================================================
class EventStatus(str, Enum):
    """Event status enumeration."""
    DRAFT = "draft"
    PLANNING = "planning"
    LIVE = "live"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"

class EventType(str, Enum):
    """Event type enumeration."""
    WEDDING = "wedding"
    BIRTHDAY = "birthday"
    CORPORATE = "corporate"
    GRADUATION = "graduation"
    PARTY = "party"
    CONFERENCE = "conference"
    SPORTS = "sports"
    CONCERT = "concert"
    FESTIVAL = "festival"
    OTHER = "other"

class EventVisibility(str, Enum):
    """Event visibility enumeration."""
    PUBLIC = "public"
    PRIVATE = "private"
    UNLISTED = "unlisted"

class SalesStatus(str, Enum):
    """Sales status for events."""
    DRAFT = "draft"
    LIVE = "live" 
    CLOSED = "closed"
    SUSPENDED = "suspended"

# ============================================================================
# BASE EVENT MODELS
# ============================================================================
class EventBase(BaseModel):
    """Base event model with common fields."""
    name: str = Field(..., min_length=1, max_length=255, description="Event name")
    description: Optional[str] = Field(None, max_length=2000, description="Event description")
    event_type: EventType = Field(EventType.OTHER, description="Type of event")
    event_date: Optional[datetime] = Field(None, description="Date when event took place")
    location: Optional[str] = Field(None, max_length=500, description="Event location")
    visibility: EventVisibility = Field(EventVisibility.PRIVATE, description="Event visibility")

class EventCreate(EventBase):
    """Model for creating new events."""
    photographer_ids: Optional[List[UUID4]] = Field(None, description="Assigned photographer IDs")
    tags: Optional[List[str]] = Field(None, description="Event tags")
    max_images: Optional[int] = Field(None, ge=0, description="Maximum number of images allowed")
    
    @validator('tags')
    def validate_tags(cls, v):
        """Validate tags."""
        if v:
            # Limit number of tags
            if len(v) > 20:
                raise ValueError('Maximum 20 tags allowed')
            # Validate tag format
            for tag in v:
                if len(tag) > 50:
                    raise ValueError('Tag length cannot exceed 50 characters')
                if not tag.replace('-', '').replace('_', '').isalnum():
                    raise ValueError('Tags can only contain letters, numbers, hyphens, and underscores')
        return v

class EventUpdate(BaseModel):
    """Model for updating event information."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    event_type: Optional[EventType] = Field(None)
    event_date: Optional[datetime] = Field(None)
    location: Optional[str] = Field(None, max_length=500)
    visibility: Optional[EventVisibility] = Field(None)
    status: Optional[EventStatus] = Field(None)
    tags: Optional[List[str]] = Field(None)
    max_images: Optional[int] = Field(None, ge=0)

class EventResponse(UUIDMixin, EventBase, TimestampMixin):
    """Event response model."""
    event_id: UUID4 = Field(..., description="Event ID")
    created_by: UUID4 = Field(..., description="User who created the event")
    created_by_username: Optional[str] = Field(None, description="Username of creator")
    status: EventStatus = Field(EventStatus.DRAFT, description="Event status")
    tags: List[str] = Field([], description="Event tags")
    max_images: Optional[int] = Field(None, description="Maximum images allowed")
    
    # Statistics
    total_images: int = Field(0, description="Total number of images")
    total_sales: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total sales")
    total_orders: int = Field(0, description="Total number of orders")
    unique_customers: int = Field(0, description="Number of unique customers")
    
    # Assigned photographers
    photographers: List[Dict[str, Any]] = Field([], description="Assigned photographers")
    
    class Config:
        orm_mode = True

class EventWithStats(EventResponse):
    """Event response with detailed statistics."""
    sales_by_package: List[Dict[str, Any]] = Field([], description="Sales breakdown by package type")
    daily_sales: List[Dict[str, Any]] = Field([], description="Daily sales data")
    top_selling_images: List[Dict[str, Any]] = Field([], description="Top selling images")
    conversion_rate: Optional[Decimal] = Field(None, description="View to purchase conversion rate")
    avg_order_value: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Average order value")

class EventListResponse(PaginationResponse[EventResponse]):
    """Paginated event list response."""
    pass

# ============================================================================
# EVENT SALES SETTINGS MODELS
# ============================================================================
class EventSalesSettingsBase(BaseModel):
    """Base event sales settings model."""
    sales_status: SalesStatus = Field(SalesStatus.DRAFT, description="Sales status")
    sales_start_date: Optional[datetime] = Field(None, description="When sales begin")
    sales_end_date: Optional[datetime] = Field(None, description="When sales end")
    watermark_enabled: bool = Field(True, description="Enable watermarks on preview images")
    preview_max_width: int = Field(800, ge=100, le=2000, description="Maximum preview image width")
    preview_max_height: int = Field(600, ge=100, le=2000, description="Maximum preview image height")
    download_link_expiry_hours: int = Field(72, ge=1, le=8760, description="Download link expiry in hours")
    max_downloads_per_purchase: int = Field(3, ge=1, le=10, description="Maximum downloads per purchase")
    
    @validator('sales_end_date')
    def end_after_start(cls, v, values):
        """Ensure end date is after start date."""
        start_date = values.get('sales_start_date')
        if start_date and v and v <= start_date:
            raise ValueError('sales_end_date must be after sales_start_date')
        return v

class EventSalesSettingsCreate(EventSalesSettingsBase):
    """Model for creating event sales settings."""
    pass

class EventSalesSettingsUpdate(BaseModel):
    """Model for updating event sales settings."""
    sales_status: Optional[SalesStatus] = Field(None)
    sales_start_date: Optional[datetime] = Field(None)
    sales_end_date: Optional[datetime] = Field(None)
    watermark_enabled: Optional[bool] = Field(None)
    preview_max_width: Optional[int] = Field(None, ge=100, le=2000)
    preview_max_height: Optional[int] = Field(None, ge=100, le=2000)
    download_link_expiry_hours: Optional[int] = Field(None, ge=1, le=8760)
    max_downloads_per_purchase: Optional[int] = Field(None, ge=1, le=10)

class EventSalesSettingsResponse(UUIDMixin, EventSalesSettingsBase, TimestampMixin):
    """Event sales settings response model."""
    setting_id: UUID4 = Field(..., description="Settings ID")
    event_id: UUID4 = Field(..., description="Event ID")
    has_custom_settings: bool = Field(True, description="Whether event has custom settings")
    
    class Config:
        orm_mode = True

# ============================================================================
# IMAGE MODELS
# ============================================================================
class ImageStatus(str, Enum):
    """Image status enumeration."""
    UPLOADING = "uploading"
    PROCESSING = "processing"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    ARCHIVED = "archived"

class ImageBase(BaseModel):
    """Base image model."""
    filename: str = Field(..., description="Original filename")
    title: Optional[str] = Field(None, max_length=255, description="Image title")
    description: Optional[str] = Field(None, max_length=1000, description="Image description")
    tags: Optional[List[str]] = Field(None, description="Image tags")

class ImageUpload(BaseModel):
    """Model for image upload requests."""
    event_id: UUID4 = Field(..., description="Event ID")
    consent_given: bool = Field(..., description="Face processing consent")
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[str]] = Field(None)

class ImageUpdate(BaseModel):
    """Model for updating image information."""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    tags: Optional[List[str]] = Field(None)
    status: Optional[ImageStatus] = Field(None)

class ImageResponse(UUIDMixin, ImageBase, TimestampMixin):
    """Image response model."""
    image_id: UUID4 = Field(..., description="Image ID")
    event_id: UUID4 = Field(..., description="Event ID")
    uploaded_by: UUID4 = Field(..., description="User who uploaded the image")
    uploaded_by_username: Optional[str] = Field(None, description="Username of uploader")
    status: ImageStatus = Field(ImageStatus.PROCESSING, description="Image status")
    file_size: int = Field(0, description="File size in bytes")
    content_type: str = Field("", description="MIME content type")
    width: Optional[int] = Field(None, description="Image width in pixels")
    height: Optional[int] = Field(None, description="Image height in pixels")
    consent_given: bool = Field(False, description="Face processing consent")
    
    # URLs
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail URL")
    preview_url: Optional[str] = Field(None, description="Preview URL")
    watermark_url: Optional[str] = Field(None, description="Watermarked preview URL")
    download_url: Optional[str] = Field(None, description="Download URL (for purchased images)")
    
    # Statistics
    view_count: int = Field(0, description="Number of views")
    purchase_count: int = Field(0, description="Number of purchases")
    in_cart_count: int = Field(0, description="Number of times added to cart")
    
    # Face detection
    face_count: int = Field(0, description="Number of faces detected")
    has_faces: bool = Field(False, description="Whether image contains faces")
    
    class Config:
        orm_mode = True

class ImageListResponse(PaginationResponse[ImageResponse]):
    """Paginated image list response."""
    pass

class ImageMetadata(BaseModel):
    """Extended image metadata."""
    camera_make: Optional[str] = Field(None, description="Camera manufacturer")
    camera_model: Optional[str] = Field(None, description="Camera model")
    lens_model: Optional[str] = Field(None, description="Lens model")
    focal_length: Optional[str] = Field(None, description="Focal length")
    aperture: Optional[str] = Field(None, description="Aperture value")
    shutter_speed: Optional[str] = Field(None, description="Shutter speed")
    iso: Optional[int] = Field(None, description="ISO value")
    flash_used: Optional[bool] = Field(None, description="Whether flash was used")
    orientation: Optional[int] = Field(None, description="Image orientation")
    gps_latitude: Optional[Decimal] = Field(None, description="GPS latitude")
    gps_longitude: Optional[Decimal] = Field(None, description="GPS longitude")
    color_space: Optional[str] = Field(None, description="Color space")
    white_balance: Optional[str] = Field(None, description="White balance setting")

# ============================================================================
# WATERMARK MODELS
# ============================================================================
class WatermarkStatus(str, Enum):
    """Watermark processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class WatermarkCreate(BaseModel):
    """Model for creating watermarks."""
    image_id: UUID4 = Field(..., description="Image ID")
    watermark_type: str = Field("standard", description="Type of watermark to apply")
    opacity: Optional[Decimal] = Field(Decimal("0.5"), ge=0, le=1, description="Watermark opacity")
    position: str = Field("center", description="Watermark position")

class WatermarkResponse(UUIDMixin, TimestampMixin):
    """Watermark response model."""
    watermark_id: UUID4 = Field(..., description="Watermark ID")
    image_id: UUID4 = Field(..., description="Image ID")
    watermark_url: Optional[str] = Field(None, description="Watermarked image URL")
    preview_url: Optional[str] = Field(None, description="Preview image URL")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail URL")
    processing_status: WatermarkStatus = Field(WatermarkStatus.PENDING, description="Processing status")
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    
    class Config:
        orm_mode = True

# ============================================================================
# EVENT ASSIGNMENT MODELS
# ============================================================================
class EventAssignmentCreate(BaseModel):
    """Model for assigning photographers to events."""
    event_id: UUID4 = Field(..., description="Event ID")
    photographer_id: UUID4 = Field(..., description="Photographer ID")
    role: str = Field("photographer", description="Role in the event")
    permissions: List[str] = Field([], description="Specific permissions for this assignment")

class EventAssignmentResponse(UUIDMixin, TimestampMixin):
    """Event assignment response model."""
    assignment_id: UUID4 = Field(..., description="Assignment ID")
    event_id: UUID4 = Field(..., description="Event ID")
    event_name: str = Field(..., description="Event name")
    photographer_id: UUID4 = Field(..., description="Photographer ID")
    photographer_name: str = Field(..., description="Photographer name")
    role: str = Field(..., description="Role in the event")
    permissions: List[str] = Field([], description="Assigned permissions")
    is_active: bool = Field(True, description="Whether assignment is active")
    
    class Config:
        orm_mode = True

# ============================================================================
# EVENT STATISTICS MODELS
# ============================================================================
class EventStatsResponse(BaseModel):
    """Event statistics response model."""
    event_id: UUID4 = Field(..., description="Event ID")
    total_images: int = Field(0, description="Total images")
    approved_images: int = Field(0, description="Approved images")
    published_images: int = Field(0, description="Published images")
    total_views: int = Field(0, description="Total image views")
    unique_visitors: int = Field(0, description="Unique visitors")
    total_sales: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total sales")
    total_orders: int = Field(0, description="Total orders")
    conversion_rate: Decimal = Field(Decimal("0"), description="View to purchase conversion rate")
    avg_order_value: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Average order value")
    top_selling_images: List[ImageResponse] = Field([], description="Top selling images")
    sales_by_day: List[Dict[str, Any]] = Field([], description="Daily sales breakdown")
    sales_by_package: List[Dict[str, Any]] = Field([], description="Sales by package type")

class EventAnalyticsFilter(DateRangeFilter):
    """Filter for event analytics."""
    event_ids: Optional[List[UUID4]] = Field(None, description="Filter by specific events")
    photographer_ids: Optional[List[UUID4]] = Field(None, description="Filter by photographers")
    event_types: Optional[List[EventType]] = Field(None, description="Filter by event types")
    status: Optional[List[EventStatus]] = Field(None, description="Filter by event status")

# ============================================================================
# BULK OPERATIONS MODELS
# ============================================================================
class BulkImageUpdate(BaseModel):
    """Model for bulk image updates."""
    image_ids: List[UUID4] = Field(..., min_items=1, max_items=100, description="Image IDs to update")
    status: Optional[ImageStatus] = Field(None, description="New status for all images")
    tags: Optional[List[str]] = Field(None, description="Tags to add to all images")
    remove_tags: Optional[List[str]] = Field(None, description="Tags to remove from all images")

class BulkImageResponse(BaseModel):
    """Response for bulk image operations."""
    success_count: int = Field(..., description="Number of successfully updated images")
    error_count: int = Field(..., description="Number of failed updates")
    errors: List[Dict[str, Any]] = Field([], description="Details of any errors")

class BulkWatermarkCreate(BaseModel):
    """Model for bulk watermark generation."""
    event_id: UUID4 = Field(..., description="Event ID")
    image_ids: Optional[List[UUID4]] = Field(None, description="Specific image IDs (if None, all images)")
    watermark_type: str = Field("standard", description="Type of watermark")
    force_regenerate: bool = Field(False, description="Whether to regenerate existing watermarks")

# ============================================================================
# EVENT TEMPLATES MODELS
# ============================================================================
class EventTemplateCreate(BaseModel):
    """Model for creating event templates."""
    name: str = Field(..., min_length=1, max_length=255, description="Template name")
    description: Optional[str] = Field(None, max_length=1000, description="Template description")
    event_type: EventType = Field(..., description="Event type")
    default_settings: Dict[str, Any] = Field({}, description="Default event settings")
    pricing_template_id: Optional[UUID4] = Field(None, description="Default pricing template")

class EventTemplateResponse(UUIDMixin, TimestampMixin):
    """Event template response model."""
    template_id: UUID4 = Field(..., description="Template ID")
    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    event_type: EventType = Field(..., description="Event type")
    default_settings: Dict[str, Any] = Field({}, description="Default settings")
    pricing_template_id: Optional[UUID4] = Field(None, description="Pricing template ID")
    usage_count: int = Field(0, description="Number of times template was used")
    is_active: bool = Field(True, description="Whether template is active")
    created_by: UUID4 = Field(..., description="Creator user ID")
    
    class Config:
        orm_mode = True
