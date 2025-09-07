# ============================================================================
# ORDER MODELS
# ============================================================================
"""
Order-related models for the Event Photo Sales System.
Includes orders, order items, shopping cart, and fulfillment.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, UUID4, validator, EmailStr
from enum import Enum
from decimal import Decimal

from .common import (
    TimestampMixin, 
    UUIDMixin, 
    BaseResponse, 
    PaginationResponse,
    MoneyAmount
)
from .pricing import PackageType

# ============================================================================
# ENUMS
# ============================================================================
class OrderStatus(str, Enum):
    """Order status enumeration."""
    PENDING = "pending"
    PAID = "paid"
    PROCESSING = "processing"
    FULFILLED = "fulfilled"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    EXPIRED = "expired"

class FulfillmentStatus(str, Enum):
    """Fulfillment status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    DELIVERED = "delivered"
    FAILED = "failed"

class CartStatus(str, Enum):
    """Shopping cart status enumeration."""
    ACTIVE = "active"
    ABANDONED = "abandoned"
    CONVERTED = "converted"
    EXPIRED = "expired"

# ============================================================================
# SHOPPING CART MODELS
# ============================================================================
class CartSessionBase(BaseModel):
    """Base cart session model."""
    event_id: UUID4 = Field(..., description="Event ID")
    customer_email: Optional[EmailStr] = Field(None, description="Customer email")
    expires_at: Optional[datetime] = Field(None, description="Cart expiration time")

class CartSessionCreate(CartSessionBase):
    """Model for creating cart sessions."""
    customer_id: Optional[UUID4] = Field(None, description="Customer ID (if logged in)")

class CartSessionResponse(UUIDMixin, CartSessionBase, TimestampMixin):
    """Cart session response model."""
    session_id: UUID4 = Field(..., description="Cart session ID")
    customer_id: Optional[UUID4] = Field(None, description="Customer ID")
    status: CartStatus = Field(CartStatus.ACTIVE, description="Cart status")
    is_active: bool = Field(True, description="Whether cart is active")
    item_count: int = Field(0, description="Number of items in cart")
    total_value: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total cart value")
    
    @property
    def is_expired(self) -> bool:
        """Check if cart is expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    class Config:
        orm_mode = True

class CartItemAdd(BaseModel):
    """Model for adding items to cart."""
    image_id: UUID4 = Field(..., description="Image ID to add")

class CartItemResponse(UUIDMixin, TimestampMixin):
    """Cart item response model."""
    item_id: UUID4 = Field(..., description="Cart item ID")
    session_id: UUID4 = Field(..., description="Cart session ID")
    image_id: UUID4 = Field(..., description="Image ID")
    image_filename: Optional[str] = Field(None, description="Image filename")
    image_thumbnail_url: Optional[str] = Field(None, description="Image thumbnail URL")
    added_at: datetime = Field(..., description="When item was added")
    
    class Config:
        orm_mode = True

class CartResponse(BaseModel):
    """Complete cart response."""
    session: CartSessionResponse = Field(..., description="Cart session details")
    items: List[CartItemResponse] = Field([], description="Cart items")
    available_packages: List[Dict[str, Any]] = Field([], description="Available pricing packages")
    recommended_package: Optional[str] = Field(None, description="Recommended package type")
    estimated_total: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Estimated total cost")

# ============================================================================
# ORDER MODELS
# ============================================================================
class OrderBase(BaseModel):
    """Base order model."""
    event_id: UUID4 = Field(..., description="Event ID")
    package_type: PackageType = Field(..., description="Selected package type")
    total_amount: MoneyAmount = Field(..., description="Total order amount")
    currency: str = Field("THB", description="Order currency")

class OrderCreate(OrderBase):
    """Model for creating orders."""
    customer_id: Optional[UUID4] = Field(None, description="Customer ID")
    customer_email: Optional[EmailStr] = Field(None, description="Customer email for guest orders")
    image_ids: Optional[List[UUID4]] = Field(None, description="Selected image IDs (for single/package orders)")
    discount_code: Optional[str] = Field(None, description="Applied discount code")
    special_instructions: Optional[str] = Field(None, max_length=1000, description="Special instructions")
    
    @validator('image_ids')
    def validate_image_selection(cls, v, values):
        """Validate image selection based on package type."""
        package_type = values.get('package_type')
        
        if package_type == PackageType.SINGLE:
            if not v or len(v) != 1:
                raise ValueError('Single package requires exactly 1 image')
        elif package_type == PackageType.PACKAGE_4:
            if not v or len(v) != 4:
                raise ValueError('Package 4 requires exactly 4 images')
        elif package_type == PackageType.UNLIMITED:
            if v:
                raise ValueError('Unlimited package should not specify image IDs')
        
        return v

class OrderUpdate(BaseModel):
    """Model for updating orders."""
    status: Optional[OrderStatus] = Field(None, description="Order status")
    special_instructions: Optional[str] = Field(None, max_length=1000)
    internal_notes: Optional[str] = Field(None, max_length=2000, description="Internal admin notes")

class OrderResponse(UUIDMixin, OrderBase, TimestampMixin):
    """Order response model."""
    order_id: UUID4 = Field(..., description="Order ID")
    order_number: str = Field(..., description="Human-readable order number")
    customer_id: Optional[UUID4] = Field(None, description="Customer ID")
    customer_email: Optional[EmailStr] = Field(None, description="Customer email")
    customer_name: Optional[str] = Field(None, description="Customer name")
    event_name: Optional[str] = Field(None, description="Event name")
    status: OrderStatus = Field(OrderStatus.PENDING, description="Order status")
    fulfillment_status: FulfillmentStatus = Field(FulfillmentStatus.PENDING, description="Fulfillment status")
    
    # Pricing details
    subtotal: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Subtotal before discounts")
    discount_amount: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Discount amount")
    tax_amount: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Tax amount")
    
    # Payment info
    payment_method: Optional[str] = Field(None, description="Payment method used")
    payment_reference: Optional[str] = Field(None, description="Payment reference number")
    paid_at: Optional[datetime] = Field(None, description="Payment timestamp")
    
    # Additional info
    discount_code: Optional[str] = Field(None, description="Applied discount code")
    special_instructions: Optional[str] = Field(None, description="Customer instructions")
    internal_notes: Optional[str] = Field(None, description="Internal notes")
    
    # Fulfillment
    download_expires_at: Optional[datetime] = Field(None, description="Download expiry time")
    download_count: int = Field(0, description="Number of downloads")
    max_downloads: int = Field(3, description="Maximum allowed downloads")
    
    class Config:
        orm_mode = True

class OrderItemResponse(UUIDMixin, TimestampMixin):
    """Order item response model."""
    item_id: UUID4 = Field(..., description="Order item ID")
    order_id: UUID4 = Field(..., description="Order ID")
    image_id: UUID4 = Field(..., description="Image ID")
    image_filename: Optional[str] = Field(None, description="Image filename")
    image_thumbnail_url: Optional[str] = Field(None, description="Image thumbnail URL")
    unit_price: MoneyAmount = Field(..., description="Unit price for this item")
    
    class Config:
        orm_mode = True

class OrderDetailResponse(OrderResponse):
    """Detailed order response with items."""
    items: List[OrderItemResponse] = Field([], description="Order items")
    payment_history: List[Dict[str, Any]] = Field([], description="Payment history")
    status_history: List[Dict[str, Any]] = Field([], description="Status change history")

class OrderListResponse(PaginationResponse[OrderResponse]):
    """Paginated order list response."""
    pass

# ============================================================================
# ORDER STATISTICS MODELS
# ============================================================================
class OrderStatsResponse(BaseModel):
    """Order statistics response."""
    total_orders: int = Field(0, description="Total number of orders")
    pending_orders: int = Field(0, description="Pending orders")
    paid_orders: int = Field(0, description="Paid orders")
    failed_orders: int = Field(0, description="Failed orders")
    cancelled_orders: int = Field(0, description="Cancelled orders")
    
    total_revenue: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total revenue")
    avg_order_value: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Average order value")
    conversion_rate: Decimal = Field(Decimal("0"), description="Cart to order conversion rate")
    
    orders_by_package: List[Dict[str, Any]] = Field([], description="Orders breakdown by package type")
    orders_by_status: List[Dict[str, Any]] = Field([], description="Orders breakdown by status")
    daily_orders: List[Dict[str, Any]] = Field([], description="Daily order counts")

# ============================================================================
# FULFILLMENT MODELS
# ============================================================================
class FulfillmentRequest(BaseModel):
    """Request to fulfill an order."""
    order_id: UUID4 = Field(..., description="Order ID to fulfill")
    download_expiry_hours: Optional[int] = Field(None, ge=1, le=8760, description="Custom download expiry")
    custom_message: Optional[str] = Field(None, max_length=500, description="Custom message to customer")

class FulfillmentResponse(UUIDMixin, TimestampMixin):
    """Fulfillment response model."""
    fulfillment_id: UUID4 = Field(..., description="Fulfillment ID")
    order_id: UUID4 = Field(..., description="Order ID")
    status: FulfillmentStatus = Field(..., description="Fulfillment status")
    download_token: Optional[str] = Field(None, description="Download token")
    download_url: Optional[str] = Field(None, description="Download URL")
    expires_at: Optional[datetime] = Field(None, description="Download expiry time")
    max_downloads: int = Field(3, description="Maximum downloads allowed")
    download_count: int = Field(0, description="Current download count")
    fulfilled_at: Optional[datetime] = Field(None, description="Fulfillment timestamp")
    
    class Config:
        orm_mode = True

# ============================================================================
# ORDER SEARCH AND FILTER MODELS
# ============================================================================
class OrderSearchFilter(BaseModel):
    """Filter for order searches."""
    status: Optional[List[OrderStatus]] = Field(None, description="Filter by order status")
    fulfillment_status: Optional[List[FulfillmentStatus]] = Field(None, description="Filter by fulfillment status")
    event_ids: Optional[List[UUID4]] = Field(None, description="Filter by event IDs")
    customer_ids: Optional[List[UUID4]] = Field(None, description="Filter by customer IDs")
    package_types: Optional[List[PackageType]] = Field(None, description="Filter by package types")
    payment_methods: Optional[List[str]] = Field(None, description="Filter by payment methods")
    min_amount: Optional[MoneyAmount] = Field(None, description="Minimum order amount")
    max_amount: Optional[MoneyAmount] = Field(None, description="Maximum order amount")
    start_date: Optional[datetime] = Field(None, description="Orders from this date")
    end_date: Optional[datetime] = Field(None, description="Orders until this date")
    search_term: Optional[str] = Field(None, description="Search in order number, customer email, etc.")

class OrderSearchResponse(PaginationResponse[OrderResponse]):
    """Order search results."""
    filters_applied: OrderSearchFilter = Field(..., description="Applied filters")
    total_value: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total value of filtered orders")

# ============================================================================
# BULK ORDER OPERATIONS
# ============================================================================
class BulkOrderUpdate(BaseModel):
    """Model for bulk order updates."""
    order_ids: List[UUID4] = Field(..., min_items=1, max_items=100, description="Order IDs to update")
    status: Optional[OrderStatus] = Field(None, description="New status for all orders")
    fulfillment_status: Optional[FulfillmentStatus] = Field(None, description="New fulfillment status")
    internal_notes: Optional[str] = Field(None, max_length=2000, description="Notes to add")

class BulkOrderResponse(BaseModel):
    """Response for bulk order operations."""
    success_count: int = Field(..., description="Number of successfully updated orders")
    error_count: int = Field(..., description="Number of failed updates")
    errors: List[Dict[str, Any]] = Field([], description="Details of any errors")
    updated_orders: List[UUID4] = Field([], description="Successfully updated order IDs")

class BulkFulfillmentRequest(BaseModel):
    """Request for bulk fulfillment."""
    order_ids: List[UUID4] = Field(..., min_items=1, max_items=50, description="Order IDs to fulfill")
    download_expiry_hours: int = Field(72, ge=1, le=8760, description="Download expiry hours")
    send_notification: bool = Field(True, description="Whether to send email notifications")

# ============================================================================
# ORDER ANALYTICS MODELS
# ============================================================================
class OrderAnalyticsFilter(BaseModel):
    """Filter for order analytics."""
    start_date: Optional[datetime] = Field(None, description="Analysis start date")
    end_date: Optional[datetime] = Field(None, description="Analysis end date")
    event_ids: Optional[List[UUID4]] = Field(None, description="Specific events to analyze")
    customer_segments: Optional[List[str]] = Field(None, description="Customer segments")
    include_cancelled: bool = Field(False, description="Include cancelled orders")

class SalesMetrics(BaseModel):
    """Sales metrics model."""
    period: str = Field(..., description="Time period (day, week, month, etc.)")
    total_orders: int = Field(0, description="Total orders in period")
    total_revenue: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total revenue")
    avg_order_value: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Average order value")
    new_customers: int = Field(0, description="New customers in period")
    repeat_customers: int = Field(0, description="Repeat customers")

class OrderAnalyticsResponse(BaseModel):
    """Order analytics response."""
    summary: OrderStatsResponse = Field(..., description="Overall summary")
    sales_trends: List[SalesMetrics] = Field([], description="Sales trends over time")
    top_events: List[Dict[str, Any]] = Field([], description="Top performing events")
    customer_insights: Dict[str, Any] = Field({}, description="Customer behavior insights")
    package_performance: List[Dict[str, Any]] = Field([], description="Package type performance")
    seasonal_patterns: List[Dict[str, Any]] = Field([], description="Seasonal sales patterns")

# ============================================================================
# ORDER EXPORT MODELS
# ============================================================================
class OrderExportFormat(str, Enum):
    """Export format options."""
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"
    JSON = "json"

class OrderExportRequest(BaseModel):
    """Request for order export."""
    format: OrderExportFormat = Field(..., description="Export format")
    filters: Optional[OrderSearchFilter] = Field(None, description="Export filters")
    include_items: bool = Field(True, description="Include order items")
    include_customer_info: bool = Field(True, description="Include customer information")
    date_range_start: Optional[datetime] = Field(None, description="Start date for export")
    date_range_end: Optional[datetime] = Field(None, description="End date for export")

class OrderExportResponse(BaseModel):
    """Response for order export."""
    export_id: UUID4 = Field(..., description="Export job ID")
    status: str = Field("processing", description="Export status")
    download_url: Optional[str] = Field(None, description="Download URL when ready")
    expires_at: Optional[datetime] = Field(None, description="Download link expiry")
    record_count: Optional[int] = Field(None, description="Number of records exported")
    file_size: Optional[int] = Field(None, description="File size in bytes")

# ============================================================================
# ORDER WORKFLOW MODELS
# ============================================================================
class OrderWorkflowStep(BaseModel):
    """Order workflow step."""
    step_name: str = Field(..., description="Step name")
    step_order: int = Field(..., description="Step order in workflow")
    required_status: OrderStatus = Field(..., description="Required order status")
    action_type: str = Field(..., description="Type of action to perform")
    is_automatic: bool = Field(False, description="Whether step is automatic")
    conditions: Optional[Dict[str, Any]] = Field(None, description="Step conditions")

class OrderWorkflowResponse(UUIDMixin, TimestampMixin):
    """Order workflow response."""
    workflow_id: UUID4 = Field(..., description="Workflow ID")
    workflow_name: str = Field(..., description="Workflow name")
    description: Optional[str] = Field(None, description="Workflow description")
    steps: List[OrderWorkflowStep] = Field([], description="Workflow steps")
    is_active: bool = Field(True, description="Whether workflow is active")
    applies_to: List[str] = Field([], description="What this workflow applies to")
    
    class Config:
        orm_mode = True

# ============================================================================
# ORDER VALIDATION MODELS
# ============================================================================
class OrderValidationRule(BaseModel):
    """Order validation rule."""
    rule_name: str = Field(..., description="Rule name")
    rule_type: str = Field(..., description="Rule type")
    validation_logic: str = Field(..., description="Validation logic")
    error_message: str = Field(..., description="Error message if validation fails")
    is_active: bool = Field(True, description="Whether rule is active")

class OrderValidationRequest(BaseModel):
    """Request for order validation."""
    order_data: OrderCreate = Field(..., description="Order data to validate")
    skip_inventory_check: bool = Field(False, description="Skip inventory validation")

class OrderValidationError(BaseModel):
    """Order validation error."""
    field: str = Field(..., description="Field with error")
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Error message")
    suggested_fix: Optional[str] = Field(None, description="Suggested fix")

class OrderValidationResponse(BaseModel):
    """Order validation response."""
    is_valid: bool = Field(..., description="Whether order is valid")
    errors: List[OrderValidationError] = Field([], description="Validation errors")
    warnings: List[str] = Field([], description="Validation warnings")
    estimated_total: Optional[MoneyAmount] = Field(None, description="Estimated order total")
    validated_at: datetime = Field(default_factory=datetime.utcnow)

# ============================================================================
# ORDER NOTIFICATION MODELS
# ============================================================================
class OrderNotificationType(str, Enum):
    """Order notification types."""
    ORDER_CREATED = "order_created"
    ORDER_PAID = "order_paid"
    ORDER_FULFILLED = "order_fulfilled"
    ORDER_CANCELLED = "order_cancelled"
    DOWNLOAD_READY = "download_ready"
    DOWNLOAD_EXPIRES_SOON = "download_expires_soon"

class OrderNotificationRequest(BaseModel):
    """Request to send order notification."""
    order_id: UUID4 = Field(..., description="Order ID")
    notification_type: OrderNotificationType = Field(..., description="Notification type")
    custom_message: Optional[str] = Field(None, description="Custom message to include")
    send_to_admin: bool = Field(False, description="Also send to admin")

class OrderNotificationResponse(BaseModel):
    """Order notification response."""
    notification_id: UUID4 = Field(..., description="Notification ID")
    order_id: UUID4 = Field(..., description="Order ID")
    notification_type: OrderNotificationType = Field(..., description="Notification type")
    recipient_email: str = Field(..., description="Recipient email")
    sent_at: Optional[datetime] = Field(None, description="When notification was sent")
    status: str = Field("pending", description="Notification status")
    error_message: Optional[str] = Field(None, description="Error message if failed")

# ============================================================================
# ORDER REVIEW MODELS
# ============================================================================
class OrderReviewCreate(BaseModel):
    """Model for creating order reviews."""
    order_id: UUID4 = Field(..., description="Order ID")
    rating: int = Field(..., ge=1, le=5, description="Rating (1-5 stars)")
    review_text: Optional[str] = Field(None, max_length=2000, description="Review text")
    recommend_to_others: bool = Field(True, description="Would recommend to others")

class OrderReviewResponse(UUIDMixin, TimestampMixin):
    """Order review response model."""
    review_id: UUID4 = Field(..., description="Review ID")
    order_id: UUID4 = Field(..., description="Order ID")
    customer_id: UUID4 = Field(..., description="Customer ID")
    customer_name: Optional[str] = Field(None, description="Customer name")
    event_id: UUID4 = Field(..., description="Event ID")
    event_name: Optional[str] = Field(None, description="Event name")
    rating: int = Field(..., description="Rating (1-5 stars)")
    review_text: Optional[str] = Field(None, description="Review text")
    recommend_to_others: bool = Field(..., description="Would recommend to others")
    is_verified: bool = Field(True, description="Whether review is from verified purchase")
    is_public: bool = Field(True, description="Whether review is publicly visible")
    helpful_votes: int = Field(0, description="Number of helpful votes")
    
    class Config:
        orm_mode = True

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def generate_order_number(order_id: UUID4) -> str:
    """Generate human-readable order number."""
    # Take first 8 characters of UUID and add timestamp
    timestamp = datetime.utcnow().strftime("%y%m%d")
    uuid_part = str(order_id).replace("-", "")[:8].upper()
    return f"ORD-{timestamp}-{uuid_part}"

def calculate_order_total(
    subtotal: MoneyAmount, 
    discount_amount: MoneyAmount, 
    tax_rate: Decimal = Decimal("0")
) -> MoneyAmount:
    """Calculate order total with discounts and taxes."""
    discounted_amount = subtotal.amount - discount_amount.amount
    tax_amount = discounted_amount * tax_rate
    total_amount = discounted_amount + tax_amount
    
    return MoneyAmount(amount=total_amount, currency=subtotal.currency)

def validate_order_items(
    package_type: PackageType, 
    image_ids: Optional[List[UUID4]]
) -> bool:
    """Validate order items against package type."""
    if package_type == PackageType.SINGLE:
        return image_ids is not None and len(image_ids) == 1
    elif package_type == PackageType.PACKAGE_4:
        return image_ids is not None and len(image_ids) == 4
    elif package_type == PackageType.UNLIMITED:
        return image_ids is None or len(image_ids) == 0
    return True
