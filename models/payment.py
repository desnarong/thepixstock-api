# ============================================================================
# PAYMENT MODELS
# ============================================================================
"""
Payment-related models for the Event Photo Sales System.
Includes payment processing, gateways, transactions, and refunds.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Union
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
class PaymentStatus(str, Enum):
    """Payment status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    EXPIRED = "expired"

class PaymentMethod(str, Enum):
    """Payment method enumeration."""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    BANK_TRANSFER = "bank_transfer"
    PROMPTPAY = "promptpay"
    TRUE_MONEY = "true_money"
    PAYPAL = "paypal"
    OMISE = "omise"
    STRIPE = "stripe"
    CASH = "cash"

class PaymentGateway(str, Enum):
    """Payment gateway enumeration."""
    OMISE = "omise"
    STRIPE = "stripe"
    PAYPAL = "paypal"
    BANK_TRANSFER = "bank_transfer"
    MANUAL = "manual"
    TEST = "test"

class RefundReason(str, Enum):
    """Refund reason enumeration."""
    CUSTOMER_REQUEST = "customer_request"
    DUPLICATE_PAYMENT = "duplicate_payment"
    FRAUD_PREVENTION = "fraud_prevention"
    TECHNICAL_ERROR = "technical_error"
    ORDER_CANCELLED = "order_cancelled"
    QUALITY_ISSUE = "quality_issue"
    OTHER = "other"

# ============================================================================
# PAYMENT PROCESSING MODELS
# ============================================================================
class PaymentProcessBase(BaseModel):
    """Base payment processing model."""
    order_id: UUID4 = Field(..., description="Order ID to process payment for")
    payment_method: PaymentMethod = Field(..., description="Selected payment method")
    amount: MoneyAmount = Field(..., description="Payment amount")

class PaymentProcess(PaymentProcessBase):
    """Model for processing payments."""
    payment_gateway: Optional[PaymentGateway] = Field(None, description="Preferred payment gateway")
    payment_token: Optional[str] = Field(None, description="Payment token from frontend")
    customer_ip: Optional[str] = Field(None, description="Customer IP address")
    return_url: Optional[str] = Field(None, description="Return URL after payment")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for notifications")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional payment metadata")

class PaymentResponse(UUIDMixin, TimestampMixin):
    """Payment response model."""
    payment_id: UUID4 = Field(..., description="Payment ID")
    order_id: UUID4 = Field(..., description="Order ID")
    payment_gateway: PaymentGateway = Field(..., description="Payment gateway used")
    gateway_transaction_id: Optional[str] = Field(None, description="Gateway transaction ID")
    payment_method: PaymentMethod = Field(..., description="Payment method used")
    amount: MoneyAmount = Field(..., description="Payment amount")
    status: PaymentStatus = Field(..., description="Payment status")
    
    # Gateway response data
    gateway_response: Optional[Dict[str, Any]] = Field(None, description="Raw gateway response")
    gateway_fee: Optional[MoneyAmount] = Field(None, description="Gateway processing fee")
    
    # Processing timestamps
    processed_at: Optional[datetime] = Field(None, description="When payment was processed")
    expires_at: Optional[datetime] = Field(None, description="When payment expires")
    
    # URLs and references
    payment_url: Optional[str] = Field(None, description="Payment URL for redirect")
    receipt_url: Optional[str] = Field(None, description="Receipt URL")
    
    # Error information
    error_code: Optional[str] = Field(None, description="Error code if payment failed")
    error_message: Optional[str] = Field(None, description="Error message if payment failed")
    
    class Config:
        orm_mode = True

class PaymentListResponse(PaginationResponse[PaymentResponse]):
    """Paginated payment list response."""
    pass

# ============================================================================
# PAYMENT METHOD MODELS
# ============================================================================
class PaymentMethodInfo(BaseModel):
    """Payment method information."""
    method: PaymentMethod = Field(..., description="Payment method")
    display_name: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="Method description")
    icon_url: Optional[str] = Field(None, description="Icon URL")
    is_available: bool = Field(True, description="Whether method is available")
    min_amount: Optional[MoneyAmount] = Field(None, description="Minimum payment amount")
    max_amount: Optional[MoneyAmount] = Field(None, description="Maximum payment amount")
    processing_fee: Optional[MoneyAmount] = Field(None, description="Processing fee")
    processing_time: Optional[str] = Field(None, description="Expected processing time")

class PaymentMethodResponse(BaseModel):
    """Available payment methods response."""
    available_methods: List[PaymentMethodInfo] = Field(..., description="Available payment methods")
    recommended_method: Optional[PaymentMethod] = Field(None, description="Recommended method")
    total_with_fees: Dict[str, MoneyAmount] = Field({}, description="Total amount including fees per method")

# ============================================================================
# PAYMENT WEBHOOK MODELS
# ============================================================================
class WebhookEventType(str, Enum):
    """Webhook event types."""
    PAYMENT_SUCCESS = "payment.success"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_CANCELLED = "payment.cancelled"
    REFUND_SUCCESS = "refund.success"
    REFUND_FAILED = "refund.failed"
    CHARGEBACK = "chargeback"

class PaymentWebhookData(BaseModel):
    """Payment webhook data."""
    event_type: WebhookEventType = Field(..., description="Webhook event type")
    payment_id: Optional[UUID4] = Field(None, description="Payment ID")
    gateway_transaction_id: str = Field(..., description="Gateway transaction ID")
    gateway: PaymentGateway = Field(..., description="Payment gateway")
    amount: MoneyAmount = Field(..., description="Payment amount")
    status: PaymentStatus = Field(..., description="Payment status")
    timestamp: datetime = Field(..., description="Event timestamp")
    raw_data: Dict[str, Any] = Field(..., description="Raw webhook data")

class WebhookValidationResponse(BaseModel):
    """Webhook validation response."""
    is_valid: bool = Field(..., description="Whether webhook is valid")
    signature_verified: bool = Field(..., description="Whether signature is verified")
    payment_found: bool = Field(..., description="Whether payment was found in system")
    status_updated: bool = Field(..., description="Whether payment status was updated")
    error_message: Optional[str] = Field(None, description="Error message if validation failed")

# ============================================================================
# REFUND MODELS
# ============================================================================
class RefundRequest(BaseModel):
    """Refund request model."""
    payment_id: UUID4 = Field(..., description="Payment ID to refund")
    amount: Optional[MoneyAmount] = Field(None, description="Refund amount (partial refund if specified)")
    reason: RefundReason = Field(..., description="Refund reason")
    notes: Optional[str] = Field(None, max_length=1000, description="Refund notes")
    notify_customer: bool = Field(True, description="Whether to notify customer")

class RefundResponse(UUIDMixin, TimestampMixin):
    """Refund response model."""
    refund_id: UUID4 = Field(..., description="Refund ID")
    payment_id: UUID4 = Field(..., description="Original payment ID")
    order_id: UUID4 = Field(..., description="Order ID")
    amount: MoneyAmount = Field(..., description="Refund amount")
    reason: RefundReason = Field(..., description="Refund reason")
    status: PaymentStatus = Field(..., description="Refund status")
    
    # Gateway information
    gateway_refund_id: Optional[str] = Field(None, description="Gateway refund ID")
    gateway_response: Optional[Dict[str, Any]] = Field(None, description="Gateway response")
    
    # Processing information
    processed_at: Optional[datetime] = Field(None, description="When refund was processed")
    processed_by: UUID4 = Field(..., description="User who processed the refund")
    
    # Additional info
    notes: Optional[str] = Field(None, description="Refund notes")
    customer_notified: bool = Field(False, description="Whether customer was notified")
    
    class Config:
        orm_mode = True

class RefundListResponse(PaginationResponse[RefundResponse]):
    """Paginated refund list response."""
    pass

# ============================================================================
# PAYMENT ANALYTICS MODELS
# ============================================================================
class PaymentAnalyticsFilter(BaseModel):
    """Filter for payment analytics."""
    start_date: Optional[datetime] = Field(None, description="Start date")
    end_date: Optional[datetime] = Field(None, description="End date")
    payment_methods: Optional[List[PaymentMethod]] = Field(None, description="Payment methods to include")
    payment_gateways: Optional[List[PaymentGateway]] = Field(None, description="Payment gateways to include")
    status: Optional[List[PaymentStatus]] = Field(None, description="Payment statuses to include")
    min_amount: Optional[MoneyAmount] = Field(None, description="Minimum payment amount")
    max_amount: Optional[MoneyAmount] = Field(None, description="Maximum payment amount")

class PaymentMethodStats(BaseModel):
    """Payment method statistics."""
    method: PaymentMethod = Field(..., description="Payment method")
    total_payments: int = Field(0, description="Total number of payments")
    total_amount: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total amount")
    success_rate: Decimal = Field(Decimal("0"), description="Success rate percentage")
    avg_amount: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Average payment amount")
    total_fees: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total processing fees")

class PaymentAnalyticsResponse(BaseModel):
    """Payment analytics response."""
    total_payments: int = Field(0, description="Total number of payments")
    total_amount: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total payment amount")
    successful_payments: int = Field(0, description="Number of successful payments")
    failed_payments: int = Field(0, description="Number of failed payments")
    success_rate: Decimal = Field(Decimal("0"), description="Overall success rate")
    total_refunds: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total refunded amount")
    total_fees: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total processing fees")
    
    # Breakdown by method
    by_method: List[PaymentMethodStats] = Field([], description="Statistics by payment method")
    
    # Trends
    daily_trends: List[Dict[str, Any]] = Field([], description="Daily payment trends")
    monthly_trends: List[Dict[str, Any]] = Field([], description="Monthly payment trends")
    
    # Performance metrics
    avg_processing_time: Optional[Decimal] = Field(None, description="Average processing time in seconds")
    peak_payment_hour: Optional[int] = Field(None, description="Peak payment hour (0-23)")

# ============================================================================
# PAYMENT SECURITY MODELS
# ============================================================================
class FraudDetectionRule(BaseModel):
    """Fraud detection rule."""
    rule_name: str = Field(..., description="Rule name")
    rule_type: str = Field(..., description="Rule type")
    conditions: Dict[str, Any] = Field(..., description="Rule conditions")
    action: str = Field(..., description="Action to take if rule matches")
    risk_score: int = Field(..., ge=1, le=100, description="Risk score (1-100)")
    is_active: bool = Field(True, description="Whether rule is active")

class PaymentRiskAssessment(BaseModel):
    """Payment risk assessment."""
    payment_id: UUID4 = Field(..., description="Payment ID")
    risk_score: int = Field(..., ge=0, le=100, description="Risk score (0-100)")
    risk_level: str = Field(..., description="Risk level (low, medium, high)")
    triggered_rules: List[str] = Field([], description="Names of triggered fraud rules")
    recommended_action: str = Field(..., description="Recommended action")
    assessment_reason: str = Field(..., description="Reason for the assessment")
    requires_review: bool = Field(False, description="Whether payment requires manual review")

class SecurityEvent(UUIDMixin, TimestampMixin):
    """Security event model."""
    event_id: UUID4 = Field(..., description="Event ID")
    event_type: str = Field(..., description="Event type")
    payment_id: Optional[UUID4] = Field(None, description="Related payment ID")
    severity: str = Field(..., description="Event severity")
    description: str = Field(..., description="Event description")
    user_ip: Optional[str] = Field(None, description="User IP address")
    user_agent: Optional[str] = Field(None, description="User agent")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional event metadata")
    resolved: bool = Field(False, description="Whether event has been resolved")
    resolved_by: Optional[UUID4] = Field(None, description="User who resolved the event")
    resolved_at: Optional[datetime] = Field(None, description="When event was resolved")

# ============================================================================
# PAYMENT RECONCILIATION MODELS
# ============================================================================
class ReconciliationPeriod(BaseModel):
    """Reconciliation period."""
    start_date: datetime = Field(..., description="Period start date")
    end_date: datetime = Field(..., description="Period end date")
    gateway: PaymentGateway = Field(..., description="Payment gateway")

class ReconciliationEntry(BaseModel):
    """Reconciliation entry."""
    payment_id: Optional[UUID4] = Field(None, description="Internal payment ID")
    gateway_transaction_id: str = Field(..., description="Gateway transaction ID")
    amount: MoneyAmount = Field(..., description="Transaction amount")
    status: PaymentStatus = Field(..., description="Transaction status")
    transaction_date: datetime = Field(..., description="Transaction date")
    reconciliation_status: str = Field(..., description="Reconciliation status")
    discrepancy: Optional[str] = Field(None, description="Discrepancy description")

class ReconciliationReport(UUIDMixin, TimestampMixin):
    """Reconciliation report."""
    report_id: UUID4 = Field(..., description="Report ID")
    period: ReconciliationPeriod = Field(..., description="Reconciliation period")
    total_transactions: int = Field(0, description="Total transactions in period")
    matched_transactions: int = Field(0, description="Successfully matched transactions")
    unmatched_transactions: int = Field(0, description="Unmatched transactions")
    discrepancies: List[ReconciliationEntry] = Field([], description="Transactions with discrepancies")
    total_amount: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Total amount")
    reconciled_amount: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Reconciled amount")
    variance_amount: MoneyAmount = Field(MoneyAmount(amount=0, currency="THB"), description="Variance amount")
    generated_by: UUID4 = Field(..., description="User who generated the report")

# ============================================================================
# PAYMENT GATEWAY CONFIGURATION
# ============================================================================
class GatewayConfig(BaseModel):
    """Payment gateway configuration."""
    gateway: PaymentGateway = Field(..., description="Payment gateway")
    is_enabled: bool = Field(True, description="Whether gateway is enabled")
    is_test_mode: bool = Field(False, description="Whether gateway is in test mode")
    supported_methods: List[PaymentMethod] = Field(..., description="Supported payment methods")
    min_amount: Optional[MoneyAmount] = Field(None, description="Minimum transaction amount")
    max_amount: Optional[MoneyAmount] = Field(None, description="Maximum transaction amount")
    processing_fee_percentage: Optional[Decimal] = Field(None, description="Processing fee percentage")
    processing_fee_fixed: Optional[MoneyAmount] = Field(None, description="Fixed processing fee")
    webhook_url: Optional[str] = Field(None, description="Webhook URL")
    return_url: Optional[str] = Field(None, description="Return URL")
    api_credentials: Dict[str, str] = Field({}, description="API credentials (encrypted)")
    additional_settings: Optional[Dict[str, Any]] = Field(None, description="Additional gateway settings")

class GatewayStatus(BaseModel):
    """Payment gateway status."""
    gateway: PaymentGateway = Field(..., description="Payment gateway")
    is_operational: bool = Field(..., description="Whether gateway is operational")
    last_check: datetime = Field(..., description="Last status check timestamp")
    response_time: Optional[Decimal] = Field(None, description="Average response time in seconds")
    error_rate: Optional[Decimal] = Field(None, description="Error rate percentage")
    last_error: Optional[str] = Field(None, description="Last error message")

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def calculate_processing_fee(
    amount: MoneyAmount, 
    fee_percentage: Optional[Decimal] = None, 
    fee_fixed: Optional[MoneyAmount] = None
) -> MoneyAmount:
    """Calculate processing fee for a payment."""
    total_fee = Decimal("0")
    
    if fee_percentage:
        total_fee += amount.amount * (fee_percentage / 100)
    
    if fee_fixed:
        total_fee += fee_fixed.amount
    
    return MoneyAmount(amount=total_fee, currency=amount.currency)

def validate_payment_amount(
    amount: MoneyAmount, 
    min_amount: Optional[MoneyAmount] = None, 
    max_amount: Optional[MoneyAmount] = None
) -> bool:
    """Validate payment amount against gateway limits."""
    if min_amount and amount.amount < min_amount.amount:
        return False
    
    if max_amount and amount.amount > max_amount.amount:
        return False
    
    return True

def get_payment_method_display_name(method: PaymentMethod) -> str:
    """Get display name for payment method."""
    display_names = {
        PaymentMethod.CREDIT_CARD: "Credit Card",
        PaymentMethod.DEBIT_CARD: "Debit Card",
        PaymentMethod.BANK_TRANSFER: "Bank Transfer",
        PaymentMethod.PROMPTPAY: "PromptPay",
        PaymentMethod.TRUE_MONEY: "TrueMoney Wallet",
        PaymentMethod.PAYPAL: "PayPal",
        PaymentMethod.OMISE: "Omise",
        PaymentMethod.STRIPE: "Stripe",
        PaymentMethod.CASH: "Cash"
    }
    return display_names.get(method, method.value.title())
