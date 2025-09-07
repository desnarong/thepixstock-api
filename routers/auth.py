# ============================================================================
# AUTHENTICATION ROUTER
# ============================================================================
"""
Authentication router for the Event Photo Sales System.
Handles user authentication, registration, password management, and JWT tokens.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
import uuid

from models.user import (
    UserCreate, UserResponse, LoginRequest, LoginResponse,
    PasswordChangeRequest, PasswordResetRequest, PasswordResetConfirm,
    CustomerCreate, CustomerResponse, PhotographerCreate, PhotographerResponse,
    UserRole
)
from models.common import SuccessResponse, ErrorResponse, BaseResponse
from database.connection import get_db
from core.config import settings
from core.security import verify_password, get_password_hash, create_access_token
from core.dependencies import get_current_user, get_current_admin_user

# ============================================================================
# ROUTER SETUP
# ============================================================================
router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================
@router.post("/login", response_model=LoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db = Depends(get_db)
):
    """
    User login with username and password.
    Returns JWT access token and user information.
    """
    try:
        # Find user by username
        user = await db.fetchrow(
            "SELECT * FROM users WHERE username = $1 AND (role = 'admin' OR role = 'photographer')", 
            form_data.username
        )
        
        if not user or not verify_password(form_data.password, user['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user['username']}, 
            expires_delta=access_token_expires
        )
        
        # Update last login
        await db.execute(
            "UPDATE users SET last_login = $1 WHERE user_id = $2",
            datetime.utcnow(), user['user_id']
        )
        
        # Get user permissions based on role
        permissions = []
        if user['role'] == 'admin':
            permissions = ["admin:all", "events:all", "orders:all", "users:all"]
        elif user['role'] == 'photographer':
            permissions = ["events:read", "images:upload", "orders:read"]
        
        # Convert user record to response model
        user_response = UserResponse(
            user_id=user['user_id'],
            username=user['username'],
            role=user['role'],
            email=user.get('email'),
            status=user.get('status', 'active'),
            created_at=user['created_at'],
            updated_at=user.get('updated_at'),
            last_login=datetime.utcnow()
        )
        
        return LoginResponse(
            success=True,
            message="Login successful",
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_response,
            permissions=permissions
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )


@router.post("/register/customer", response_model=SuccessResponse)
async def register_customer(
    customer_data: CustomerCreate,
    db = Depends(get_db)
):
    """
    Register a new customer account.
    Creates both user and customer records.
    """
    try:
        # Check if email already exists
        existing_customer = await db.fetchrow(
            "SELECT customer_id FROM customers WHERE email = $1", 
            customer_data.email
        )
        if existing_customer:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )
        
        # Create user account
        user_id = str(uuid.uuid4())
        username = f"customer_{uuid.uuid4().hex[:8]}"
        
        if customer_data.password:
            password_hash = get_password_hash(customer_data.password)
        else:
            # Generate temporary password for guest checkout
            temp_password = uuid.uuid4().hex[:12]
            password_hash = get_password_hash(temp_password)
        
        await db.execute(
            "INSERT INTO users (user_id, username, password_hash, role) VALUES ($1, $2, $3, $4)",
            user_id, username, password_hash, UserRole.CUSTOMER.value
        )
        
        # Create customer record
        customer_id = str(uuid.uuid4())
        await db.execute(
            """INSERT INTO customers (customer_id, user_id, email, first_name, last_name, phone, marketing_consent) 
               VALUES ($1, $2, $3, $4, $5, $6, $7)""",
            customer_id, user_id, customer_data.email, customer_data.first_name, 
            customer_data.last_name, customer_data.phone, customer_data.marketing_consent
        )
        
        return SuccessResponse(
            success=True,
            message="Customer account created successfully",
            data={
                "customer_id": customer_id,
                "user_id": user_id,
                "username": username
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/register/photographer", response_model=SuccessResponse)
async def register_photographer(
    photographer_data: PhotographerCreate,
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Register a new photographer account (Admin only).
    Creates both user and photographer records.
    """
    try:
        # Check if username already exists
        existing_user = await db.fetchrow(
            "SELECT user_id FROM users WHERE username = $1", 
            photographer_data.username
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists"
            )
        
        # Check if email already exists
        existing_photographer = await db.fetchrow(
            "SELECT photographer_id FROM photographers WHERE email = $1", 
            photographer_data.email
        )
        if existing_photographer:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )
        
        # Create user account
        user_id = str(uuid.uuid4())
        password_hash = get_password_hash(photographer_data.password)
        
        await db.execute(
            "INSERT INTO users (user_id, username, password_hash, role) VALUES ($1, $2, $3, $4)",
            user_id, photographer_data.username, password_hash, UserRole.PHOTOGRAPHER.value
        )
        
        # Create photographer record
        photographer_id = str(uuid.uuid4())
        await db.execute(
            """INSERT INTO photographers 
               (photographer_id, user_id, commission_rate, bank_account, tax_id, phone, email, bio, portfolio_url, is_active) 
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
            photographer_id, user_id, photographer_data.commission_rate, photographer_data.bank_account,
            photographer_data.tax_id, photographer_data.phone, photographer_data.email,
            photographer_data.bio, photographer_data.portfolio_url, True
        )
        
        return SuccessResponse(
            success=True,
            message="Photographer account created successfully",
            data={
                "photographer_id": photographer_id,
                "user_id": user_id,
                "username": photographer_data.username
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Photographer registration failed: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user)
):
    """
    Get current authenticated user information.
    """
    return UserResponse(
        user_id=current_user['user_id'],
        username=current_user['username'],
        role=current_user['role'],
        email=current_user.get('email'),
        status=current_user.get('status', 'active'),
        created_at=current_user['created_at'],
        updated_at=current_user.get('updated_at'),
        last_login=current_user.get('last_login')
    )


@router.post("/change-password", response_model=SuccessResponse)
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Change user password.
    Requires current password for verification.
    """
    try:
        # Verify current password
        if not verify_password(password_data.current_password, current_user['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Update password
        new_password_hash = get_password_hash(password_data.new_password)
        await db.execute(
            "UPDATE users SET password_hash = $1, updated_at = $2 WHERE user_id = $3",
            new_password_hash, datetime.utcnow(), current_user['user_id']
        )
        
        return SuccessResponse(
            success=True,
            message="Password changed successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password change failed: {str(e)}"
        )


@router.post("/forgot-password", response_model=SuccessResponse)
async def forgot_password(
    request: PasswordResetRequest,
    db = Depends(get_db)
):
    """
    Request password reset.
    Sends reset token to user's email.
    """
    try:
        # Check if user exists with this email
        user = await db.fetchrow(
            """SELECT u.user_id, u.username 
               FROM users u 
               LEFT JOIN customers c ON u.user_id = c.user_id 
               LEFT JOIN photographers p ON u.user_id = p.user_id 
               WHERE c.email = $1 OR p.email = $1""",
            request.email
        )
        
        if not user:
            # Don't reveal if email exists or not for security
            return SuccessResponse(
                success=True,
                message="If an account with that email exists, a password reset link has been sent"
            )
        
        # Generate reset token (in production, store this in database with expiry)
        reset_token = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
        # Store reset token in database (you'll need to create this table)
        await db.execute(
            """INSERT INTO password_reset_tokens (user_id, token, expires_at) 
               VALUES ($1, $2, $3)
               ON CONFLICT (user_id) DO UPDATE SET 
               token = EXCLUDED.token, expires_at = EXCLUDED.expires_at""",
            user['user_id'], reset_token, expires_at
        )
        
        # TODO: Send email with reset link
        # send_password_reset_email(request.email, reset_token)
        
        return SuccessResponse(
            success=True,
            message="Password reset link has been sent to your email"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password reset request failed: {str(e)}"
        )


@router.post("/reset-password", response_model=SuccessResponse)
async def reset_password(
    reset_data: PasswordResetConfirm,
    db = Depends(get_db)
):
    """
    Reset password using reset token.
    """
    try:
        # Verify reset token
        token_record = await db.fetchrow(
            """SELECT user_id FROM password_reset_tokens 
               WHERE token = $1 AND expires_at > $2""",
            reset_data.token, datetime.utcnow()
        )
        
        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        
        # Update password
        new_password_hash = get_password_hash(reset_data.new_password)
        await db.execute(
            "UPDATE users SET password_hash = $1, updated_at = $2 WHERE user_id = $3",
            new_password_hash, datetime.utcnow(), token_record['user_id']
        )
        
        # Delete used token
        await db.execute(
            "DELETE FROM password_reset_tokens WHERE token = $1",
            reset_data.token
        )
        
        return SuccessResponse(
            success=True,
            message="Password has been reset successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password reset failed: {str(e)}"
        )


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    current_user: dict = Depends(get_current_user)
):
    """
    Logout user.
    In a stateless JWT system, this is mainly for logging purposes.
    """
    # In production, you might want to blacklist the token
    # or store it in a revoked tokens list
    
    return SuccessResponse(
        success=True,
        message="Logged out successfully"
    )


# ============================================================================
# TOKEN VALIDATION ENDPOINTS
# ============================================================================
@router.post("/verify-token", response_model=BaseResponse)
async def verify_token(
    token: str = Form(...),
    db = Depends(get_db)
):
    """
    Verify if a JWT token is valid.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # Check if user still exists
        user = await db.fetchrow("SELECT user_id FROM users WHERE username = $1", username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        return BaseResponse(
            success=True,
            message="Token is valid"
        )
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token verification failed: {str(e)}"
        )


@router.post("/refresh-token", response_model=LoginResponse)
async def refresh_token(
    current_user: dict = Depends(get_current_user)
):
    """
    Refresh JWT access token.
    """
    try:
        # Create new access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": current_user['username']}, 
            expires_delta=access_token_expires
        )
        
        # Get permissions
        permissions = []
        if current_user['role'] == 'admin':
            permissions = ["admin:all", "events:all", "orders:all", "users:all"]
        elif current_user['role'] == 'photographer':
            permissions = ["events:read", "images:upload", "orders:read"]
        
        user_response = UserResponse(
            user_id=current_user['user_id'],
            username=current_user['username'],
            role=current_user['role'],
            email=current_user.get('email'),
            status=current_user.get('status', 'active'),
            created_at=current_user['created_at'],
            updated_at=current_user.get('updated_at'),
            last_login=current_user.get('last_login')
        )
        
        return LoginResponse(
            success=True,
            message="Token refreshed successfully",
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_response,
            permissions=permissions
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}"
        )
