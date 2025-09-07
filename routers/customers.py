# ============================================================================
# CUSTOMERS ROUTER
# ============================================================================
"""
Customers router for the Event Photo Sales System.
Handles customer management, photographer administration, and user profiles.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
import uuid

from models.user import (
    CustomerCreate, CustomerResponse, CustomerUpdate, CustomerListResponse,
    PhotographerCreate, PhotographerResponse, PhotographerUpdate, PhotographerListResponse,
    UserResponse, UserCreate, UserUpdate, UserRole
)
from models.order import OrderListResponse
from models.common import SuccessResponse, PaginationParams
from database.connection import get_db
from core.dependencies import get_current_user, get_current_admin_user
from core.security import get_password_hash

# ============================================================================
# ROUTER SETUP
# ============================================================================
router = APIRouter()

# ============================================================================
# CUSTOMER MANAGEMENT ENDPOINTS
# ============================================================================
@router.get("/", response_model=CustomerListResponse)
async def get_customers(
    pagination: PaginationParams = Depends(),
    search: Optional[str] = Query(None, description="Search customers by name or email"),
@router.get("/", response_model=CustomerListResponse)
async def get_customers(
    pagination: PaginationParams = Depends(),
    search: Optional[str] = Query(None, description="Search customers by name or email"),
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Get all customers with pagination and search (Admin only).
    """
    try:
        # Build query conditions
        conditions = []
        params = []
        param_count = 0
        
        if search:
            param_count += 1
            conditions.append(f"""(c.email ILIKE ${param_count} OR 
                                c.first_name ILIKE ${param_count} OR 
                                c.last_name ILIKE ${param_count} OR 
                                CONCAT(c.first_name, ' ', c.last_name) ILIKE ${param_count})""")
            params.append(f"%{search}%")
        
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        # Get total count
        count_query = f"""
            SELECT COUNT(*) FROM customers c
            JOIN users u ON c.user_id = u.user_id
            {where_clause}
        """
        total_count = await db.fetchval(count_query, *params)
        
        # Get customers with stats
        data_query = f"""
            SELECT c.*, u.username,
                   COALESCE(order_stats.total_orders, 0) as total_orders,
                   COALESCE(order_stats.total_spent, 0) as total_spent,
                   order_stats.last_order_date
            FROM customers c
            JOIN users u ON c.user_id = u.user_id
            LEFT JOIN (
                SELECT customer_id, 
                       COUNT(*) as total_orders,
                       SUM(total_amount) as total_spent,
                       MAX(created_at) as last_order_date
                FROM orders 
                WHERE order_status = 'paid'
                GROUP BY customer_id
            ) order_stats ON c.customer_id = order_stats.customer_id
            {where_clause}
            ORDER BY c.created_at DESC
            LIMIT ${param_count + 1} OFFSET ${param_count + 2}
        """
        params.extend([pagination.limit, pagination.offset])
        
        customers = await db.fetch(data_query, *params)
        
        # Convert to response models
        customer_responses = []
        for customer in customers:
            customer_response = CustomerResponse(
                customer_id=customer['customer_id'],
                user_id=customer['user_id'],
                username=customer['username'],
                email=customer['email'],
                first_name=customer['first_name'],
                last_name=customer['last_name'],
                phone=customer['phone'],
                total_orders=customer['total_orders'],
                total_spent={"amount": float(customer['total_spent'] or 0), "currency": "THB"},
                last_order_date=customer['last_order_date'],
                marketing_consent=customer.get('marketing_consent', False),
                created_at=customer['created_at'],
                updated_at=customer['updated_at']
            )
            customer_responses.append(customer_response)
        
        return CustomerListResponse(
            data=customer_responses,
            pagination={
                "page": pagination.page,
                "limit": pagination.limit,
                "total": total_count,
                "pages": (total_count + pagination.limit - 1) // pagination.limit,
                "has_next": pagination.page < ((total_count + pagination.limit - 1) // pagination.limit),
                "has_prev": pagination.page > 1
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get customers: {str(e)}"
        )


@router.post("/", response_model=SuccessResponse)
async def create_customer(
    customer: CustomerCreate,
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Create a new customer account (Admin only).
    """
    try:
        # Check if email already exists
        existing_customer = await db.fetchrow(
            "SELECT customer_id FROM customers WHERE email = $1", 
            customer.email
        )
        if existing_customer:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )
        
        # Create user account
        user_id = str(uuid.uuid4())
        username = f"customer_{uuid.uuid4().hex[:8]}"
        
        if customer.password:
            password_hash = get_password_hash(customer.password)
        else:
            # Generate temporary password
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
            customer_id, user_id, customer.email, customer.first_name, 
            customer.last_name, customer.phone, customer.marketing_consent
        )
        
        return SuccessResponse(
            success=True,
            message="Customer created successfully",
            data={
                "customer_id": customer_id,
                "user_id": user_id,
                "username": username,
                "temporary_password": temp_password if not customer.password else None
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create customer: {str(e)}"
        )


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get customer details.
    """
    try:
        # Get customer with stats
        customer = await db.fetchrow(
            """SELECT c.*, u.username,
                      COALESCE(order_stats.total_orders, 0) as total_orders,
                      COALESCE(order_stats.total_spent, 0) as total_spent,
                      order_stats.last_order_date
               FROM customers c
               JOIN users u ON c.user_id = u.user_id
               LEFT JOIN (
                   SELECT customer_id, 
                          COUNT(*) as total_orders,
                          SUM(total_amount) as total_spent,
                          MAX(created_at) as last_order_date
                   FROM orders 
                   WHERE order_status = 'paid'
                   GROUP BY customer_id
               ) order_stats ON c.customer_id = order_stats.customer_id
               WHERE c.customer_id = $1""",
            customer_id
        )
        
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )
        
        # Check access permissions
        if (current_user['role'] != 'admin' and 
            customer['user_id'] != current_user['user_id']):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        return CustomerResponse(
            customer_id=customer['customer_id'],
            user_id=customer['user_id'],
            username=customer['username'],
            email=customer['email'],
            first_name=customer['first_name'],
            last_name=customer['last_name'],
            phone=customer['phone'],
            total_orders=customer['total_orders'],
            total_spent={"amount": float(customer['total_spent'] or 0), "currency": "THB"},
            last_order_date=customer['last_order_date'],
            marketing_consent=customer.get('marketing_consent', False),
            created_at=customer['created_at'],
            updated_at=customer['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get customer: {str(e)}"
        )


@router.put("/{customer_id}", response_model=SuccessResponse)
async def update_customer(
    customer_id: str,
    customer_update: CustomerUpdate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Update customer information.
    """
    try:
        # Check if customer exists and user has permission
        customer = await db.fetchrow(
            "SELECT user_id FROM customers WHERE customer_id = $1", customer_id
        )
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found"
            )
        
        if (current_user['role'] != 'admin' and 
            customer['user_id'] != current_user['user_id']):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Build update query
        update_fields = []
        params = []
        param_count = 0
        
        for field, value in customer_update.dict(exclude_unset=True).items():
            if value is not None:
                param_count += 1
                update_fields.append(f"{field} = ${param_count}")
                params.append(value)
        
        if not update_fields:
            return SuccessResponse(
                success=True,
                message="No changes to update"
            )
        
        # Add updated_at
        param_count += 1
        update_fields.append(f"updated_at = ${param_count}")
        params.append(datetime.utcnow())
        
        # Add customer_id for WHERE clause
        param_count += 1
        params.append(customer_id)
        
        query = f"UPDATE customers SET {', '.join(update_fields)} WHERE customer_id = ${param_count}"
        await db.execute(query, *params)
        
        return SuccessResponse(
            success=True,
            message="Customer updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update customer: {str(e)}"
        )


@router.get("/{customer_id}/orders", response_model=OrderListResponse)
async def get_customer_orders(
    customer_id: str,
    pagination: PaginationParams = Depends(),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get customer's order history.
    """
    try:
        # Check access permissions
        if current_user['role'] != 'admin':
            customer = await db.fetchrow(
                "SELECT user_id FROM customers WHERE customer_id = $1", customer_id
            )
            if not customer or customer['user_id'] != current_user['user_id']:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
        
        # Get total count
        total_count = await db.fetchval(
            "SELECT COUNT(*) FROM orders WHERE customer_id = $1", customer_id
        )
        
        # Get orders
        orders = await db.fetch(
            """SELECT o.*, e.name as event_name
               FROM orders o
               LEFT JOIN events e ON o.event_id = e.event_id
               WHERE o.customer_id = $1
               ORDER BY o.created_at DESC
               LIMIT $2 OFFSET $3""",
            customer_id, pagination.limit, pagination.offset
        )
        
        # Convert to response models (simplified for this example)
        order_responses = []
        for order in orders:
            order_responses.append({
                "order_id": str(order['order_id']),
                "order_number": order['order_number'],
                "event_name": order['event_name'],
                "package_type": order['package_type'],
                "total_amount": {"amount": float(order['total_amount']), "currency": order['currency']},
                "status": order['order_status'],
                "created_at": order['created_at']
            })
        
        return OrderListResponse(
            data=order_responses,
            pagination={
                "page": pagination.page,
                "limit": pagination.limit,
                "total": total_count,
                "pages": (total_count + pagination.limit - 1) // pagination.limit,
                "has_next": pagination.page < ((total_count + pagination.limit - 1) // pagination.limit),
                "has_prev": pagination.page > 1
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get customer orders: {str(e)}"
        )


# ============================================================================
# PHOTOGRAPHER MANAGEMENT ENDPOINTS
# ============================================================================
@router.get("/photographers", response_model=PhotographerListResponse)
async def get_photographers(
    pagination: PaginationParams = Depends(),
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Get all photographers (Admin only).
    """
    try:
        # Get total count
        total_count = await db.fetchval("SELECT COUNT(*) FROM photographers")
        
        # Get photographers with stats
        photographers = await db.fetch(
            """SELECT p.*, u.username,
                      COALESCE(event_stats.total_events, 0) as total_events,
                      COALESCE(image_stats.total_images, 0) as total_images,
                      COALESCE(commission_stats.total_commission, 0) as total_commission,
                      COALESCE(commission_stats.pending_commission, 0) as pending_commission
               FROM photographers p
               JOIN users u ON p.user_id = u.user_id
               LEFT JOIN (
                   SELECT ea.photographer_id, COUNT(DISTINCT ea.event_id) as total_events
                   FROM event_assignments ea
                   GROUP BY ea.photographer_id
               ) event_stats ON p.photographer_id = event_stats.photographer_id
               LEFT JOIN (
                   SELECT i.uploaded_by, COUNT(*) as total_images
                   FROM images i
                   JOIN users u ON i.uploaded_by = u.user_id
                   WHERE u.role = 'photographer'
                   GROUP BY i.uploaded_by
               ) image_stats ON p.user_id = image_stats.uploaded_by
               LEFT JOIN (
                   SELECT pc.photographer_id,
                          SUM(pc.commission_amount) as total_commission,
                          SUM(CASE WHEN pc.status = 'pending' THEN pc.commission_amount ELSE 0 END) as pending_commission
                   FROM photographer_commissions pc
                   GROUP BY pc.photographer_id
               ) commission_stats ON p.photographer_id = commission_stats.photographer_id
               ORDER BY p.created_at DESC
               LIMIT $1 OFFSET $2""",
            pagination.limit, pagination.offset
        )
        
        # Convert to response models
        photographer_responses = []
        for photographer in photographers:
            photographer_response = PhotographerResponse(
                photographer_id=photographer['photographer_id'],
                user_id=photographer['user_id'],
                username=photographer['username'],
                commission_rate=photographer['commission_rate'],
                bank_account=photographer['bank_account'],
                tax_id=photographer['tax_id'],
                phone=photographer['phone'],
                email=photographer['email'],
                bio=photographer.get('bio'),
                portfolio_url=photographer.get('portfolio_url'),
                is_active=photographer['is_active'],
                total_events=photographer['total_events'],
                total_images=photographer['total_images'],
                total_commission={"amount": float(photographer['total_commission'] or 0), "currency": "THB"},
                pending_commission={"amount": float(photographer['pending_commission'] or 0), "currency": "THB"},
                created_at=photographer['created_at'],
                updated_at=photographer['updated_at']
            )
            photographer_responses.append(photographer_response)
        
        return PhotographerListResponse(
            data=photographer_responses,
            pagination={
                "page": pagination.page,
                "limit": pagination.limit,
                "total": total_count,
                "pages": (total_count + pagination.limit - 1) // pagination.limit,
                "has_next": pagination.page < ((total_count + pagination.limit - 1) // pagination.limit),
                "has_prev": pagination.page > 1
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get photographers: {str(e)}"
        )


@router.post("/photographers", response_model=SuccessResponse)
async def create_photographer(
    photographer: PhotographerCreate,
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Create a new photographer account (Admin only).
    """
    try:
        # Check if username already exists
        existing_user = await db.fetchrow(
            "SELECT user_id FROM users WHERE username = $1", 
            photographer.username
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists"
            )
        
        # Check if email already exists
        existing_photographer = await db.fetchrow(
            "SELECT photographer_id FROM photographers WHERE email = $1", 
            photographer.email
        )
        if existing_photographer:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )
        
        # Create user account
        user_id = str(uuid.uuid4())
        password_hash = get_password_hash(photographer.password)
        
        await db.execute(
            "INSERT INTO users (user_id, username, password_hash, role) VALUES ($1, $2, $3, $4)",
            user_id, photographer.username, password_hash, UserRole.PHOTOGRAPHER.value
        )
        
        # Create photographer record
        photographer_id = str(uuid.uuid4())
        await db.execute(
            """INSERT INTO photographers 
               (photographer_id, user_id, commission_rate, bank_account, tax_id, phone, email, bio, portfolio_url, is_active) 
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
            photographer_id, user_id, photographer.commission_rate, photographer.bank_account,
            photographer.tax_id, photographer.phone, photographer.email,
            photographer.bio, photographer.portfolio_url, True
        )
        
        return SuccessResponse(
            success=True,
            message="Photographer created successfully",
            data={
                "photographer_id": photographer_id,
                "user_id": user_id,
                "username": photographer.username
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create photographer: {str(e)}"
        )


@router.get("/photographers/{photographer_id}", response_model=PhotographerResponse)
async def get_photographer(
    photographer_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get photographer details.
    """
    try:
        # Get photographer with stats
        photographer = await db.fetchrow(
            """SELECT p.*, u.username,
                      COALESCE(event_stats.total_events, 0) as total_events,
                      COALESCE(image_stats.total_images, 0) as total_images,
                      COALESCE(commission_stats.total_commission, 0) as total_commission,
                      COALESCE(commission_stats.pending_commission, 0) as pending_commission
               FROM photographers p
               JOIN users u ON p.user_id = u.user_id
               LEFT JOIN (
                   SELECT ea.photographer_id, COUNT(DISTINCT ea.event_id) as total_events
                   FROM event_assignments ea
                   GROUP BY ea.photographer_id
               ) event_stats ON p.photographer_id = event_stats.photographer_id
               LEFT JOIN (
                   SELECT i.uploaded_by, COUNT(*) as total_images
                   FROM images i
                   WHERE i.uploaded_by = p.user_id
                   GROUP BY i.uploaded_by
               ) image_stats ON p.user_id = image_stats.uploaded_by
               LEFT JOIN (
                   SELECT pc.photographer_id,
                          SUM(pc.commission_amount) as total_commission,
                          SUM(CASE WHEN pc.status = 'pending' THEN pc.commission_amount ELSE 0 END) as pending_commission
                   FROM photographer_commissions pc
                   GROUP BY pc.photographer_id
               ) commission_stats ON p.photographer_id = commission_stats.photographer_id
               WHERE p.photographer_id = $1""",
            photographer_id
        )
        
        if not photographer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Photographer not found"
            )
        
        # Check access permissions
        if (current_user['role'] != 'admin' and 
            photographer['user_id'] != current_user['user_id']):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        return PhotographerResponse(
            photographer_id=photographer['photographer_id'],
            user_id=photographer['user_id'],
            username=photographer['username'],
            commission_rate=photographer['commission_rate'],
            bank_account=photographer['bank_account'],
            tax_id=photographer['tax_id'],
            phone=photographer['phone'],
            email=photographer['email'],
            bio=photographer.get('bio'),
            portfolio_url=photographer.get('portfolio_url'),
            is_active=photographer['is_active'],
            total_events=photographer['total_events'],
            total_images=photographer['total_images'],
            total_commission={"amount": float(photographer['total_commission'] or 0), "currency": "THB"},
            pending_commission={"amount": float(photographer['pending_commission'] or 0), "currency": "THB"},
            created_at=photographer['created_at'],
            updated_at=photographer['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get photographer: {str(e)}"
        )
