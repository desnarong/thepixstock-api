# ============================================================================
# USER MODELS
# ============================================================================
"""
User-related models for the Event Photo Sales System.
Includes authentication, user management, customers, and photographers.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr, UUID4, validator
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
class UserRole(str, Enum):
    """User role enumeration."""
    ADMIN = "admin"
    PHOTOGRAPHER = "photographer"
    CUSTOMER = "customer"
    GUEST = "guest"

class UserStatus(str, Enum):
    """User status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"

# ============================================================================
# BASE USER MODELS
# ============================================================================
class UserBase(BaseModel):
    """Base user model with common fields."""
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    role: UserRole = Field(..., description="User role")
    
    @validator('username')
    def validate_username(cls, v):
        """Validate username format."""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username can only contain letters, numbers, hyphens, and underscores')
        return v.lower()

class UserCreate(UserBase):
    """Model for creating new users."""
    password: str = Field(..., min_length=8, max_length=128, description="User password")
    email: Optional[EmailStr] = Field(None, description="User email (optional for some roles)")
    
    @validator('password')
    def validate_password(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v

class UserUpdate(BaseModel):
    """Model for updating user information."""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    role: Optional[UserRole] = Field(None, description="User role")
    status: Optional[UserStatus] = Field(None, description="User status")
    email: Optional[EmailStr] = Field(None, description="User email")

class UserResponse(UUIDMixin, UserBase, TimestampMixin):
    """User response model (excludes sensitive information)."""
    user_id: UUID4 = Field(..., description="User ID")
    email: Optional[EmailStr] = Field(None, description="User email")
    status: UserStatus = Field(UserStatus.ACTIVE, description="User status")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    login_count: int = Field(0, description="Number of times user has logged in")
    
    class Config:
        orm_mode = True

class UserListResponse(PaginationResponse[UserResponse]):
    """Paginated user list response."""
    pass

# ============================================================================
# AUTHENTICATION MODELS
# ============================================================================
class LoginRequest(BaseModel):
    """Login request model."""
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")
    remember_me: bool = Field(False, description="Whether to remember the login")

class LoginResponse(BaseResponse):
    """Login response model."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: UserResponse = Field(..., description="User information")
    permissions: List[str] = Field([], description="User permissions")

class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str = Field(..., description="Refresh token")

class PasswordChangeRequest(BaseModel):
    """Password change request."""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")
    confirm_password: str = Field(..., description="Confirm new password")
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """Ensure passwords match."""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v

class PasswordResetRequest(BaseModel):
    """Password reset request."""
    email: EmailStr = Field(..., description="User email")

class PasswordResetConfirm(BaseModel):
    """Password reset confirmation."""
    token: str = Field(..., description="Reset token")
    new_password: str = Field(..., min_length=8, description="New password")
    confirm_password: str = Field(..., description="Confirm new password")
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """Ensure passwords match."""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v

# ============================================================================
# CUSTOMER MODELS
# ============================================================================
class CustomerBase(BaseModel):
    """Base customer model."""
    email: EmailStr = Field(..., description="Customer email")
    first_name: str = Field(..., min_length=1, max_length=100, description="First name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Last name")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")

class CustomerCreate(CustomerBase):
    """Model for creating new customers."""
    password: Optional[str] = Field(None, min_length=8, description="Password (optional for guest checkout)")
    marketing_consent: bool = Field(False, description="Consent to receive marketing emails")

class CustomerUpdate(BaseModel):
    """Model for updating customer information."""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=20)
    marketing_consent: Optional[bool] = Field(None)

class CustomerResponse(UUIDMixin, CustomerBase, TimestampMixin):
    """Customer response model."""
    customer_id: UUID4 = Field(..., description="Customer ID")
    user_id: UUID4 = Field(..., description="Associated user ID")
    username: Optional[str] = Field(None, description="Username")
    total_orders: int = Field(0, description="Total number of orders")
    total_spent: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total amount spent")
    last_order_date: Optional[datetime] = Field(None, description="Date of last order")
    marketing_consent: bool = Field(False, description="Marketing consent status")
    
    @property
    def full_name(self) -> str:
        """Get customer's full name."""
        return f"{self.first_name} {self.last_name}".strip()

class CustomerListResponse(PaginationResponse[CustomerResponse]):
    """Paginated customer list response."""
    pass

class CustomerStatsResponse(BaseModel):
    """Customer statistics response."""
    total_customers: int = Field(..., description="Total number of customers")
    new_customers_today: int = Field(..., description="New customers today")
    new_customers_this_month: int = Field(..., description="New customers this month")
    active_customers: int = Field(..., description="Active customers (made purchase in last 30 days)")
    top_customers: List[CustomerResponse] = Field(..., description="Top customers by spending")

# ============================================================================
# PHOTOGRAPHER MODELS
# ============================================================================
class PhotographerBase(BaseModel):
    """Base photographer model."""
    commission_rate: Decimal = Field(Decimal("30.00"), ge=0, le=100, description="Commission rate percentage")
    bank_account: Optional[str] = Field(None, max_length=50, description="Bank account number")
    tax_id: Optional[str] = Field(None, max_length=20, description="Tax ID number")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    email: EmailStr = Field(..., description="Photographer email")

class PhotographerCreate(PhotographerBase):
    """Model for creating new photographers."""
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=8, description="Password")
    bio: Optional[str] = Field(None, max_length=500, description="Photographer bio")
    portfolio_url: Optional[str] = Field(None, description="Portfolio website URL")

class PhotographerUpdate(BaseModel):
    """Model for updating photographer information."""
    commission_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    bank_account: Optional[str] = Field(None, max_length=50)
    tax_id: Optional[str] = Field(None, max_length=20)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = Field(None)
    bio: Optional[str] = Field(None, max_length=500)
    portfolio_url: Optional[str] = Field(None)
    is_active: Optional[bool] = Field(None, description="Whether photographer is active")

class PhotographerResponse(UUIDMixin, PhotographerBase, TimestampMixin):
    """Photographer response model."""
    photographer_id: UUID4 = Field(..., description="Photographer ID")
    user_id: UUID4 = Field(..., description="Associated user ID")
    username: str = Field(..., description="Username")
    bio: Optional[str] = Field(None, description="Photographer bio")
    portfolio_url: Optional[str] = Field(None, description="Portfolio website URL")
    is_active: bool = Field(True, description="Whether photographer is active")
    total_events: int = Field(0, description="Total events covered")
    total_images: int = Field(0, description="Total images uploaded")
    total_sales: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total sales")
    total_commission: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total commission earned")
    pending_commission: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Pending commission")
    rating: Optional[Decimal] = Field(None, ge=0, le=5, description="Average rating")
    
    class Config:
        orm_mode = True

class PhotographerListResponse(PaginationResponse[PhotographerResponse]):
    """Paginated photographer list response."""
    pass

class PhotographerStatsResponse(BaseModel):
    """Photographer statistics response."""
    total_photographers: int = Field(..., description="Total number of photographers")
    active_photographers: int = Field(..., description="Active photographers")
    top_photographers: List[PhotographerResponse] = Field(..., description="Top photographers by sales")
    total_commission_paid: MoneyAmount = Field(..., description="Total commission paid")
    pending_commission: MoneyAmount = Field(..., description="Total pending commission")

# ============================================================================
# COMMISSION MODELS
# ============================================================================
class CommissionStatus(str, Enum):
    """Commission status enumeration."""
    PENDING = "pending"
    PAID = "paid"
    HOLD = "hold"
    CANCELLED = "cancelled"

class CommissionCreate(BaseModel):
    """Model for creating commission records."""
    photographer_id: UUID4 = Field(..., description="Photographer ID")
    order_id: UUID4 = Field(..., description="Order ID")
    event_id: UUID4 = Field(..., description="Event ID")
    gross_amount: MoneyAmount = Field(..., description="Gross sales amount")
    commission_rate: Decimal = Field(..., ge=0, le=100, description="Commission rate percentage")

class CommissionResponse(UUIDMixin, TimestampMixin):
    """Commission response model."""
    commission_id: UUID4 = Field(..., description="Commission ID")
    photographer_id: UUID4 = Field(..., description="Photographer ID")
    photographer_name: str = Field(..., description="Photographer name")
    order_id: UUID4 = Field(..., description="Order ID")
    event_id: UUID4 = Field(..., description="Event ID")
    event_name: str = Field(..., description="Event name")
    gross_amount: MoneyAmount = Field(..., description="Gross sales amount")
    commission_rate: Decimal = Field(..., description="Commission rate percentage")
    commission_amount: MoneyAmount = Field(..., description="Commission amount")
    status: CommissionStatus = Field(..., description="Commission status")
    paid_at: Optional[datetime] = Field(None, description="Payment timestamp")
    notes: Optional[str] = Field(None, description="Additional notes")

class CommissionListResponse(PaginationResponse[CommissionResponse]):
    """Paginated commission list response."""
    pass

# ============================================================================
# PAYOUT MODELS
# ============================================================================
class PayoutStatus(str, Enum):
    """Payout status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class PayoutMethod(str, Enum):
    """Payout method enumeration."""
    BANK_TRANSFER = "bank_transfer"
    PAYPAL = "paypal"
    CHECK = "check"
    CASH = "cash"

class PayoutCreate(BaseModel):
    """Model for creating payouts."""
    photographer_id: UUID4 = Field(..., description="Photographer ID")
    payout_method: PayoutMethod = Field(..., description="Payout method")
    notes: Optional[str] = Field(None, max_length=500, description="Payout notes")

class PayoutResponse(UUIDMixin, TimestampMixin):
    """Payout response model."""
    payout_id: UUID4 = Field(..., description="Payout ID")
    photographer_id: UUID4 = Field(..., description="Photographer ID")
    photographer_name: str = Field(..., description="Photographer name")
    total_amount: MoneyAmount = Field(..., description="Total payout amount")
    commission_count: int = Field(..., description="Number of commissions included")
    payout_method: PayoutMethod = Field(..., description="Payout method")
    payout_reference: Optional[str] = Field(None, description="External reference number")
    status: PayoutStatus = Field(..., description="Payout status")
    payout_date: Optional[datetime] = Field(None, description="Date payout was processed")
    notes: Optional[str] = Field(None, description="Payout notes")

class PayoutListResponse(PaginationResponse[PayoutResponse]):
    """Paginated payout list response."""
    pass

# ============================================================================
# USER ACTIVITY MODELS
# ============================================================================
class UserActivityType(str, Enum):
    """User activity type enumeration."""
    LOGIN = "login"
    LOGOUT = "logout"
    UPLOAD = "upload"
    PURCHASE = "purchase"
    DOWNLOAD = "download"
    PROFILE_UPDATE = "profile_update"

class UserActivity(UUIDMixin, TimestampMixin):
    """User activity log entry."""
    user_id: UUID4 = Field(..., description="User ID")
    activity_type: UserActivityType = Field(..., description="Activity type")
    description: str = Field(..., description="Activity description")
    ip_address: Optional[str] = Field(None, description="IP address")
    user_agent: Optional[str] = Field(None, description="User agent")
    metadata: Optional[dict] = Field(None, description="Additional metadata")

# ============================================================================
# PERMISSION MODELS
# ============================================================================
class Permission(str, Enum):
    """System permissions."""
    # User management
    USER_READ = "user:read"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    
    # Event management
    EVENT_READ = "event:read"
    EVENT_CREATE = "event:create"
    EVENT_UPDATE = "event:update"
    EVENT_DELETE = "event:delete"
    
    # Image management
    IMAGE_READ = "image:read"
    IMAGE_UPLOAD = "image:upload"
    IMAGE_DELETE = "image:delete"
    
    # Order management
    ORDER_READ = "order:read"
    ORDER_CREATE = "order:create"
    ORDER_UPDATE = "order:update"
    
    # Financial
    FINANCE_READ = "finance:read"
    FINANCE_MANAGE = "finance:manage"
    
    # System administration
    ADMIN_PANEL = "admin:panel"
    SYSTEM_CONFIG = "system:config"

class RolePermissions(BaseModel):
    """Role-based permissions."""
    role: UserRole = Field(..., description="User role")
    permissions: List[Permission] = Field(..., description="List of permissions")

# Default role permissions
DEFAULT_ROLE_PERMISSIONS = {
    UserRole.ADMIN: [perm for perm in Permission],
    UserRole.PHOTOGRAPHER: [
        Permission.IMAGE_READ,
        Permission.IMAGE_UPLOAD,
        Permission.EVENT_READ,
        Permission.ORDER_READ,
        Permission.FINANCE_READ
    ],
    UserRole.CUSTOMER: [
        Permission.IMAGE_READ,
        Permission.ORDER_READ,
        Permission.ORDER_CREATE
    ],
    UserRole.GUEST: [
        Permission.IMAGE_READ
    ]
}
