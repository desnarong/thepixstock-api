# ============================================================================
# PRICING MODELS
# ============================================================================
"""
Pricing-related models for the Event Photo Sales System.
Includes package types, pricing templates, and discount management.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, UUID4, validator
from enum import Enum
from decimal import Decimal

from .common import (
    TimestampMixin, 
    UUIDMixin, 
    BaseResponse, 
    PaginationResponse,
    MoneyAmount
)

# ============================================================================
# ENUMS
# ============================================================================
class PackageType(str, Enum):
    """Package type enumeration."""
    SINGLE = "single"
    PACKAGE_4 = "package_4"
    UNLIMITED = "unlimited"
    CUSTOM = "custom"

class DiscountType(str, Enum):
    """Discount type enumeration."""
    PERCENTAGE = "percentage"
    FIXED_AMOUNT = "fixed_amount"
    BUY_X_GET_Y = "buy_x_get_y"

class PricingStrategy(str, Enum):
    """Pricing strategy enumeration."""
    FIXED = "fixed"
    DYNAMIC = "dynamic"
    TIERED = "tiered"
    BUNDLE = "bundle"

# ============================================================================
# BASE PRICING MODELS
# ============================================================================
class PricingBase(BaseModel):
    """Base pricing model."""
    package_type: PackageType = Field(..., description="Package type")
    price: MoneyAmount = Field(..., description="Package price")
    description: Optional[str] = Field(None, max_length=500, description="Package description")
    is_active: bool = Field(True, description="Whether pricing is active")
    
    @validator('price')
    def validate_price(cls, v):
        """Validate price is positive."""
        if v.amount < 0:
            raise ValueError('Price must be positive')
        return v

class EventPricingCreate(PricingBase):
    """Model for creating event pricing."""
    event_id: UUID4 = Field(..., description="Event ID")
    max_images: Optional[int] = Field(None, ge=1, description="Maximum images for package (if applicable)")
    validity_days: Optional[int] = Field(None, ge=1, description="Package validity in days")
    
    @validator('max_images')
    def validate_max_images(cls, v, values):
        """Validate max_images based on package type."""
        package_type = values.get('package_type')
        if package_type == PackageType.SINGLE and v and v != 1:
            raise ValueError('Single package must have max_images = 1')
        elif package_type == PackageType.PACKAGE_4 and v and v != 4:
            raise ValueError('Package 4 must have max_images = 4')
        elif package_type == PackageType.UNLIMITED and v:
            raise ValueError('Unlimited package should not have max_images limit')
        return v

class EventPricingUpdate(BaseModel):
    """Model for updating event pricing."""
    price: Optional[MoneyAmount] = Field(None, description="Package price")
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = Field(None)
    max_images: Optional[int] = Field(None, ge=1)
    validity_days: Optional[int] = Field(None, ge=1)

class EventPricingResponse(UUIDMixin, PricingBase, TimestampMixin):
    """Event pricing response model."""
    pricing_id: UUID4 = Field(..., description="Pricing ID")
    event_id: UUID4 = Field(..., description="Event ID")
    event_name: Optional[str] = Field(None, description="Event name")
    max_images: Optional[int] = Field(None, description="Maximum images")
    validity_days: Optional[int] = Field(None, description="Validity in days")
    sales_count: int = Field(0, description="Number of sales for this package")
    total_revenue: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total revenue")
    
    class Config:
        orm_mode = True

class EventPricingListResponse(PaginationResponse[EventPricingResponse]):
    """Paginated event pricing list response."""
    pass

# ============================================================================
# PRICING TEMPLATE MODELS
# ============================================================================
class PricingTemplateBase(BaseModel):
    """Base pricing template model."""
    template_name: str = Field(..., min_length=1, max_length=100, description="Template name")
    description: Optional[str] = Field(None, max_length=500, description="Template description")
    is_default: bool = Field(False, description="Whether this is a default template")

class PricingTemplateCreate(PricingTemplateBase):
    """Model for creating pricing templates."""
    pricing_config: List[Dict[str, Any]] = Field(..., min_items=1, description="Pricing configuration")
    
    @validator('pricing_config')
    def validate_pricing_config(cls, v):
        """Validate pricing configuration."""
        required_fields = {'package_type', 'price', 'currency'}
        for config in v:
            if not all(field in config for field in required_fields):
                raise ValueError(f'Each pricing config must have: {required_fields}')
            if config['price'] < 0:
                raise ValueError('Price must be positive')
        return v

class PricingTemplateUpdate(BaseModel):
    """Model for updating pricing templates."""
    template_name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_default: Optional[bool] = Field(None)
    pricing_config: Optional[List[Dict[str, Any]]] = Field(None)

class PricingTemplateResponse(UUIDMixin, PricingTemplateBase, TimestampMixin):
    """Pricing template response model."""
    template_id: UUID4 = Field(..., description="Template ID")
    pricing_config: List[Dict[str, Any]] = Field(..., description="Pricing configuration")
    usage_count: int = Field(0, description="Number of events using this template")
    created_by: UUID4 = Field(..., description="Creator user ID")
    created_by_username: Optional[str] = Field(None, description="Creator username")
    
    class Config:
        orm_mode = True

class PricingTemplateListResponse(PaginationResponse[PricingTemplateResponse]):
    """Paginated pricing template list response."""
    pass

# ============================================================================
# DISCOUNT MODELS
# ============================================================================
class DiscountBase(BaseModel):
    """Base discount model."""
    code: str = Field(..., min_length=3, max_length=20, description="Discount code")
    discount_type: DiscountType = Field(..., description="Type of discount")
    value: Decimal = Field(..., ge=0, description="Discount value")
    description: Optional[str] = Field(None, max_length=500, description="Discount description")
    is_active: bool = Field(True, description="Whether discount is active")
    valid_from: Optional[datetime] = Field(None, description="Discount valid from date")
    valid_until: Optional[datetime] = Field(None, description="Discount valid until date")
    usage_limit: Optional[int] = Field(None, ge=1, description="Maximum number of uses")
    usage_limit_per_customer: Optional[int] = Field(None, ge=1, description="Max uses per customer")
    minimum_order_amount: Optional[MoneyAmount] = Field(None, description="Minimum order amount")
    
    @validator('code')
    def validate_code(cls, v):
        """Validate discount code format."""
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Discount code can only contain letters, numbers, hyphens, and underscores')
        return v.upper()
    
    @validator('value')
    def validate_value(cls, v, values):
        """Validate discount value based on type."""
        discount_type = values.get('discount_type')
        if discount_type == DiscountType.PERCENTAGE and v > 100:
            raise ValueError('Percentage discount cannot exceed 100%')
        return v
    
    @validator('valid_until')
    def validate_dates(cls, v, values):
        """Ensure valid_until is after valid_from."""
        valid_from = values.get('valid_from')
        if valid_from and v and v <= valid_from:
            raise ValueError('valid_until must be after valid_from')
        return v

class DiscountCreate(DiscountBase):
    """Model for creating discounts."""
    applicable_package_types: Optional[List[PackageType]] = Field(None, description="Applicable package types")
    applicable_event_ids: Optional[List[UUID4]] = Field(None, description="Applicable event IDs")

class DiscountUpdate(BaseModel):
    """Model for updating discounts."""
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = Field(None)
    valid_from: Optional[datetime] = Field(None)
    valid_until: Optional[datetime] = Field(None)
    usage_limit: Optional[int] = Field(None, ge=1)
    usage_limit_per_customer: Optional[int] = Field(None, ge=1)
    minimum_order_amount: Optional[MoneyAmount] = Field(None)

class DiscountResponse(UUIDMixin, DiscountBase, TimestampMixin):
    """Discount response model."""
    discount_id: UUID4 = Field(..., description="Discount ID")
    usage_count: int = Field(0, description="Number of times used")
    total_savings: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total savings provided")
    applicable_package_types: List[PackageType] = Field([], description="Applicable package types")
    applicable_event_ids: List[UUID4] = Field([], description="Applicable event IDs")
    created_by: UUID4 = Field(..., description="Creator user ID")
    
    @property
    def is_expired(self) -> bool:
        """Check if discount is expired."""
        if not self.valid_until:
            return False
        return datetime.utcnow() > self.valid_until
    
    @property
    def is_usage_limit_reached(self) -> bool:
        """Check if usage limit is reached."""
        if not self.usage_limit:
            return False
        return self.usage_count >= self.usage_limit
    
    class Config:
        orm_mode = True

class DiscountListResponse(PaginationResponse[DiscountResponse]):
    """Paginated discount list response."""
    pass

# ============================================================================
# DYNAMIC PRICING MODELS
# ============================================================================
class DynamicPricingRule(BaseModel):
    """Dynamic pricing rule."""
    rule_name: str = Field(..., description="Rule name")
    condition: str = Field(..., description="Condition (e.g., 'days_since_event > 30')")
    adjustment_type: DiscountType = Field(..., description="Type of price adjustment")
    adjustment_value: Decimal = Field(..., description="Adjustment value")
    priority: int = Field(1, ge=1, le=100, description="Rule priority (higher = more important)")
    is_active: bool = Field(True, description="Whether rule is active")

class DynamicPricingResponse(UUIDMixin, TimestampMixin):
    """Dynamic pricing response."""
    pricing_id: UUID4 = Field(..., description="Pricing ID")
    event_id: UUID4 = Field(..., description="Event ID")
    package_type: PackageType = Field(..., description="Package type")
    base_price: MoneyAmount = Field(..., description="Base price")
    current_price: MoneyAmount = Field(..., description="Current dynamic price")
    applied_rules: List[str] = Field([], description="Names of applied rules")
    last_updated: datetime = Field(..., description="Last price update")

# ============================================================================
# PRICING CALCULATION MODELS
# ============================================================================
class PriceCalculationRequest(BaseModel):
    """Request for price calculation."""
    event_id: UUID4 = Field(..., description="Event ID")
    package_type: PackageType = Field(..., description="Package type")
    image_ids: Optional[List[UUID4]] = Field(None, description="Specific image IDs (for custom packages)")
    discount_code: Optional[str] = Field(None, description="Discount code to apply")
    customer_id: Optional[UUID4] = Field(None, description="Customer ID for personalized pricing")

class PriceBreakdown(BaseModel):
    """Detailed price breakdown."""
    base_price: MoneyAmount = Field(..., description="Base package price")
    discount_amount: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Discount amount")
    tax_amount: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Tax amount")
    final_price: MoneyAmount = Field(..., description="Final price after discounts and taxes")
    savings: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total savings")

class PriceCalculationResponse(BaseModel):
    """Response for price calculation."""
    event_id: UUID4 = Field(..., description="Event ID")
    package_type: PackageType = Field(..., description="Package type")
    image_count: int = Field(0, description="Number of images included")
    breakdown: PriceBreakdown = Field(..., description="Price breakdown")
    applied_discount: Optional[DiscountResponse] = Field(None, description="Applied discount details")
    valid_until: Optional[datetime] = Field(None, description="Price validity")
    calculation_timestamp: datetime = Field(default_factory=datetime.utcnow)

# ============================================================================
# BULK PRICING MODELS
# ============================================================================
class BulkPricingUpdate(BaseModel):
    """Model for bulk pricing updates."""
    event_ids: List[UUID4] = Field(..., min_items=1, max_items=50, description="Event IDs to update")
    pricing_template_id: Optional[UUID4] = Field(None, description="Pricing template to apply")
    adjustment_type: DiscountType = Field(..., description="Type of adjustment")
    adjustment_value: Decimal = Field(..., description="Adjustment value")
    package_types: Optional[List[PackageType]] = Field(None, description="Package types to update")

class BulkPricingResponse(BaseModel):
    """Response for bulk pricing operations."""
    success_count: int = Field(..., description="Number of successfully updated pricings")
    error_count: int = Field(..., description="Number of failed updates")
    errors: List[Dict[str, Any]] = Field([], description="Details of any errors")
    updated_events: List[UUID4] = Field([], description="Successfully updated event IDs")

# ============================================================================
# PRICING ANALYTICS MODELS
# ============================================================================
class PricingAnalyticsFilter(BaseModel):
    """Filter for pricing analytics."""
    start_date: Optional[datetime] = Field(None, description="Start date")
    end_date: Optional[datetime] = Field(None, description="End date")
    event_ids: Optional[List[UUID4]] = Field(None, description="Specific events")
    package_types: Optional[List[PackageType]] = Field(None, description="Package types")
    include_discounts: bool = Field(True, description="Include discount analysis")

class PackagePerformance(BaseModel):
    """Package performance metrics."""
    package_type: PackageType = Field(..., description="Package type")
    total_sales: int = Field(0, description="Total number of sales")
    total_revenue: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total revenue")
    avg_price: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Average selling price")
    conversion_rate: Decimal = Field(Decimal("0"), description="Conversion rate")
    market_share: Decimal = Field(Decimal("0"), description="Market share percentage")

class PricingAnalyticsResponse(BaseModel):
    """Pricing analytics response."""
    total_revenue: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total revenue")
    total_orders: int = Field(0, description="Total number of orders")
    avg_order_value: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Average order value")
    package_performance: List[PackagePerformance] = Field([], description="Performance by package type")
    discount_usage: Dict[str, Any] = Field({}, description="Discount usage statistics")
    price_trends: List[Dict[str, Any]] = Field([], description="Price trend data")
    optimization_suggestions: List[str] = Field([], description="Pricing optimization suggestions")

# ============================================================================
# PRICING VALIDATION MODELS
# ============================================================================
class PricingValidationRule(BaseModel):
    """Pricing validation rule."""
    rule_name: str = Field(..., description="Rule name")
    rule_type: str = Field(..., description="Rule type (min_price, max_discount, etc.)")
    threshold_value: Decimal = Field(..., description="Threshold value")
    is_active: bool = Field(True, description="Whether rule is active")

class PricingValidationRequest(BaseModel):
    """Request for pricing validation."""
    event_id: UUID4 = Field(..., description="Event ID")
    pricing_config: List[Dict[str, Any]] = Field(..., description="Pricing configuration to validate")

class PricingValidationError(BaseModel):
    """Pricing validation error."""
    package_type: PackageType = Field(..., description="Package type with error")
    error_code: str = Field(..., description="Error code")
    error_message: str = Field(..., description="Error message")
    suggested_fix: Optional[str] = Field(None, description="Suggested fix")

class PricingValidationResponse(BaseModel):
    """Pricing validation response."""
    is_valid: bool = Field(..., description="Whether pricing is valid")
    errors: List[PricingValidationError] = Field([], description="Validation errors")
    warnings: List[str] = Field([], description="Validation warnings")
    validated_at: datetime = Field(default_factory=datetime.utcnow)

# ============================================================================
# COMMISSION PRICING MODELS
# ============================================================================
class CommissionTier(BaseModel):
    """Commission tier model."""
    tier_name: str = Field(..., description="Tier name")
    min_sales: int = Field(0, ge=0, description="Minimum sales for this tier")
    max_sales: Optional[int] = Field(None, description="Maximum sales for this tier")
    commission_rate: Decimal = Field(..., ge=0, le=100, description="Commission rate percentage")

class CommissionStructure(UUIDMixin, TimestampMixin):
    """Commission structure model."""
    structure_id: UUID4 = Field(..., description="Structure ID")
    structure_name: str = Field(..., description="Structure name")
    description: Optional[str] = Field(None, description="Structure description")
    tiers: List[CommissionTier] = Field(..., description="Commission tiers")
    default_rate: Decimal = Field(Decimal("30.00"), description="Default commission rate")
    is_active: bool = Field(True, description="Whether structure is active")
    applies_to: List[str] = Field([], description="What this structure applies to")

# ============================================================================
# PRICING COMPARISON MODELS
# ============================================================================
class CompetitorPricing(BaseModel):
    """Competitor pricing information."""
    competitor_name: str = Field(..., description="Competitor name")
    package_type: PackageType = Field(..., description="Package type")
    price: MoneyAmount = Field(..., description="Competitor price")
    features: List[str] = Field([], description="Package features")
    last_updated: datetime = Field(..., description="Last update timestamp")

class PricingComparison(BaseModel):
    """Pricing comparison analysis."""
    our_pricing: EventPricingResponse = Field(..., description="Our pricing")
    competitor_pricing: List[CompetitorPricing] = Field([], description="Competitor pricing")
    market_position: str = Field(..., description="Our market position (premium, competitive, budget)")
    recommendations: List[str] = Field([], description="Pricing recommendations")

# ============================================================================
# SEASONAL PRICING MODELS
# ============================================================================
class SeasonalPricingRule(BaseModel):
    """Seasonal pricing rule."""
    rule_name: str = Field(..., description="Rule name")
    start_date: datetime = Field(..., description="Season start date")
    end_date: datetime = Field(..., description="Season end date")
    adjustment_type: DiscountType = Field(..., description="Adjustment type")
    adjustment_value: Decimal = Field(..., description="Adjustment value")
    applicable_packages: List[PackageType] = Field(..., description="Applicable package types")
    recurring_yearly: bool = Field(False, description="Whether rule repeats yearly")

class SeasonalPricingResponse(UUIDMixin, TimestampMixin):
    """Seasonal pricing response."""
    rule_id: UUID4 = Field(..., description="Rule ID")
    rule_name: str = Field(..., description="Rule name")
    start_date: datetime = Field(..., description="Start date")
    end_date: datetime = Field(..., description="End date")
    adjustment_type: DiscountType = Field(..., description="Adjustment type")
    adjustment_value: Decimal = Field(..., description="Adjustment value")
    applicable_packages: List[PackageType] = Field(..., description="Applicable packages")
    recurring_yearly: bool = Field(..., description="Recurring yearly")
    is_active: bool = Field(True, description="Whether rule is active")
    usage_count: int = Field(0, description="Number of times applied")

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def calculate_discount_amount(
    base_price: MoneyAmount, 
    discount_type: DiscountType, 
    discount_value: Decimal
) -> MoneyAmount:
    """Calculate discount amount."""
    if discount_type == DiscountType.PERCENTAGE:
        discount_amount = base_price.amount * (discount_value / 100)
    elif discount_type == DiscountType.FIXED_AMOUNT:
        discount_amount = min(discount_value, base_price.amount)
    else:
        discount_amount = Decimal("0")
    
    return MoneyAmount(amount=discount_amount, currency=base_price.currency)

def validate_package_pricing(package_type: PackageType, price: MoneyAmount) -> bool:
    """Validate if package pricing makes sense."""
    # Basic validation rules
    if price.amount <= 0:
        return False
    
    # Package-specific validation could be added here
    return True
