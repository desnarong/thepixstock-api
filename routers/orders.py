# ============================================================================
# ORDERS ROUTER
# ============================================================================
"""
Orders router for the Event Photo Sales System.
Handles shopping cart, order processing, payments, and fulfillment.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
import uuid

from models.order import (
    CartSessionCreate, CartSessionResponse, CartItemAdd, CartResponse,
    OrderCreate, OrderResponse, OrderDetailResponse, OrderListResponse,
    OrderUpdate, OrderStatsResponse, OrderSearchFilter, FulfillmentRequest,
    FulfillmentResponse, BulkOrderUpdate, BulkOrderResponse, OrderStatus
)
from models.payment import PaymentProcess, PaymentResponse
from models.common import SuccessResponse, PaginationParams
from database.connection import get_db
# ============================================================================
# ORDERS ROUTER
# ============================================================================
"""
Orders router for the Event Photo Sales System.
Handles shopping cart, order processing, payments, and fulfillment.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
import uuid

from models.order import (
    CartSessionCreate, CartSessionResponse, CartItemAdd, CartResponse,
    OrderCreate, OrderResponse, OrderDetailResponse, OrderListResponse,
    OrderUpdate, OrderStatsResponse, OrderSearchFilter, FulfillmentRequest,
    FulfillmentResponse, BulkOrderUpdate, BulkOrderResponse, OrderStatus
)
from models.payment import PaymentProcess, PaymentResponse
from models.common import SuccessResponse, PaginationParams
from database.connection import get_db
from core.dependencies import get_current_user, get_current_admin_user
from services.payment import process_payment, generate_download_link
from services.email import send_order_confirmation, send_download_ready_email

# ============================================================================
# ROUTER SETUP
# ============================================================================
router = APIRouter()

# ============================================================================
# SHOPPING CART ENDPOINTS
# ============================================================================
@router.post("/cart", response_model=CartSessionResponse)
async def create_cart_session(
    cart_data: CartSessionCreate,
    db = Depends(get_db)
):
    """
    Create a new shopping cart session.
    """
    try:
        # Check if event exists
        event = await db.fetchrow("SELECT name FROM events WHERE event_id = $1", cart_data.event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )
        
        # Find or create customer if email provided
        customer_id = None
        if cart_data.customer_email:
            customer = await db.fetchrow("SELECT customer_id FROM customers WHERE email = $1", cart_data.customer_email)
            if customer:
                customer_id = customer['customer_id']
        
        # Create cart session
        session_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        await db.execute(
            """INSERT INTO cart_sessions (session_id, customer_id, event_id, customer_email, expires_at) 
               VALUES ($1, $2, $3, $4, $5)""",
            session_id, customer_id, cart_data.event_id, cart_data.customer_email, expires_at
        )
        
        return CartSessionResponse(
            session_id=session_id,
            event_id=cart_data.event_id,
            customer_id=customer_id,
            customer_email=cart_data.customer_email,
            expires_at=expires_at,
            status="active",
            is_active=True,
            item_count=0,
            total_value={"amount": 0, "currency": "THB"},
            created_at=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create cart session: {str(e)}"
        )


@router.get("/cart/{session_id}", response_model=CartResponse)
async def get_cart(
    session_id: str,
    db = Depends(get_db)
):
    """
    Get cart contents and available packages.
    """
    try:
        # Get cart session
        session = await db.fetchrow(
            "SELECT * FROM cart_sessions WHERE session_id = $1", session_id
        )
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart session not found"
            )
        
        # Get cart items with image details
        items = await db.fetch(
            """SELECT ci.item_id, ci.image_id, ci.added_at,
                      i.filename, i.thumbnail_url, i.file_size
               FROM cart_items ci
               JOIN images i ON ci.image_id = i.id
               WHERE ci.session_id = $1
               ORDER BY ci.added_at DESC""",
            session_id
        )
        
        # Get available pricing packages for the event
        pricing = await db.fetch(
            "SELECT package_type, price FROM event_pricing WHERE event_id = $1 AND is_active = TRUE",
            session['event_id']
        )
        
        # Convert items to response format
        cart_items = []
        for item in items:
            cart_items.append({
                "item_id": str(item['item_id']),
                "image_id": str(item['image_id']),
                "filename": item['filename'],
                "thumbnail_url": item['thumbnail_url'],
                "file_size": item['file_size'],
                "added_at": item['added_at']
            })
        
        # Convert pricing to response format
        available_packages = []
        for p in pricing:
            available_packages.append({
                "package_type": p['package_type'],
                "price": {"amount": float(p['price']), "currency": "THB"}
            })
        
        # Determine recommended package
        item_count = len(items)
        recommended_package = None
        if item_count == 1:
            recommended_package = "single"
        elif item_count <= 4:
            recommended_package = "package_4"
        else:
            recommended_package = "unlimited"
        
        # Calculate estimated total based on recommended package
        estimated_total = {"amount": 0, "currency": "THB"}
        for package in available_packages:
            if package['package_type'] == recommended_package:
                estimated_total = package['price']
                break
        
        # Create session response
        session_response = CartSessionResponse(
            session_id=session['session_id'],
            event_id=session['event_id'],
            customer_id=session['customer_id'],
            customer_email=session['customer_email'],
            expires_at=session['expires_at'],
            status=session['status'],
            is_active=session['is_active'],
            item_count=len(items),
            total_value=estimated_total,
            created_at=session['created_at']
        )
        
        return CartResponse(
            session=session_response,
            items=cart_items,
            available_packages=available_packages,
            recommended_package=recommended_package,
            estimated_total=estimated_total
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get cart: {str(e)}"
        )


@router.post("/cart/{session_id}/items", response_model=SuccessResponse)
async def add_to_cart(
    session_id: str,
    item: CartItemAdd,
    db = Depends(get_db)
):
    """
    Add item to shopping cart.
    """
    try:
        # Verify cart session exists and is active
        session = await db.fetchrow(
            "SELECT * FROM cart_sessions WHERE session_id = $1 AND is_active = TRUE AND expires_at > NOW()",
            session_id
        )
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart session not found or expired"
            )
        
        # Check if image exists and belongs to the same event
        image = await db.fetchrow(
            "SELECT * FROM images WHERE id = $1 AND event_id = $2",
            item.image_id, session['event_id']
        )
        
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found in this event"
            )
        
        # Check if item already in cart
        existing_item = await db.fetchrow(
            "SELECT item_id FROM cart_items WHERE session_id = $1 AND image_id = $2",
            session_id, item.image_id
        )
        
        if existing_item:
            return SuccessResponse(
                success=True,
                message="Item already in cart"
            )
        
        # Add to cart
        item_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO cart_items (item_id, session_id, image_id) VALUES ($1, $2, $3)",
            item_id, session_id, item.image_id
        )
        
        # Get updated cart count
        cart_count = await db.fetchval(
            "SELECT COUNT(*) FROM cart_items WHERE session_id = $1", session_id
        )
        
        return SuccessResponse(
            success=True,
            message="Item added to cart",
            data={"cart_count": cart_count}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add item to cart: {str(e)}"
        )


@router.delete("/cart/{session_id}/items/{image_id}", response_model=SuccessResponse)
async def remove_from_cart(
    session_id: str,
    image_id: str,
    db = Depends(get_db)
):
    """
    Remove item from cart.
    """
    try:
        result = await db.execute(
            "DELETE FROM cart_items WHERE session_id = $1 AND image_id = $2",
            session_id, image_id
        )
        
        if result == "DELETE 0":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found in cart"
            )
        
        return SuccessResponse(
            success=True,
            message="Item removed from cart"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove item from cart: {str(e)}"
        )


# ============================================================================
# ORDER MANAGEMENT ENDPOINTS
# ============================================================================
@router.post("/", response_model=SuccessResponse)
async def create_order(
    order: OrderCreate,
    session_id: str = Query(..., description="Cart session ID"),
    db = Depends(get_db)
):
    """
    Create order from cart.
    """
    try:
        # Get cart session
        session = await db.fetchrow(
            "SELECT * FROM cart_sessions WHERE session_id = $1 AND is_active = TRUE",
            session_id
        )
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart session not found"
            )
        
        # Get pricing for the package
        pricing = await db.fetchrow(
            "SELECT price FROM event_pricing WHERE event_id = $1 AND package_type = $2 AND is_active = TRUE",
            order.event_id, order.package_type.value
        )
        
        if not pricing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pricing not found for this package"
            )
        
        # Validate image selection
        if order.package_type in ["single", "package_4"]:
            if not order.image_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Image selection required for this package"
                )
            
            max_images = 1 if order.package_type == "single" else 4
            if len(order.image_ids) > max_images:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Too many images selected for {order.package_type}"
                )
        
        # Create order
        order_id = str(uuid.uuid4())
        order_number = f"ORD-{datetime.utcnow().strftime('%y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        
        await db.execute(
            """INSERT INTO orders 
               (order_id, order_number, customer_id, customer_email, event_id, package_type, 
                total_amount, currency, subtotal, special_instructions, discount_code) 
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)""",
            order_id, order_number, session['customer_id'], session['customer_email'],
            order.event_id, order.package_type.value, pricing['price'], order.currency,
            pricing['price'], order.special_instructions, order.discount_code
        )
        
        # Create order items for specific image selections
        if order.image_ids:
            for image_id in order.image_ids:
                item_id = str(uuid.uuid4())
                unit_price = pricing['price'] / len(order.image_ids)
                await db.execute(
                    "INSERT INTO order_items (item_id, order_id, image_id, unit_price) VALUES ($1, $2, $3, $4)",
                    item_id, order_id, image_id, unit_price
                )
        
        # Mark cart as converted
        await db.execute(
            "UPDATE cart_sessions SET is_active = FALSE, status = 'converted' WHERE session_id = $1",
            session_id
        )
        
        return SuccessResponse(
            success=True,
            message="Order created successfully",
            data={
                "order_id": order_id,
                "order_number": order_number,
                "total_amount": float(pricing['price']),
                "currency": order.currency
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create order: {str(e)}"
        )


@router.get("/", response_model=OrderListResponse)
async def get_orders(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, alias="status"),
    event_id: Optional[str] = Query(None),
    customer_email: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Get all orders with filtering (Admin only).
    """
    try:
        # Build query conditions
        conditions = []
        params = []
        param_count = 0
        
        if status_filter:
            param_count += 1
            conditions.append(f"o.order_status = ${param_count}")
            params.append(status_filter)
        
        if event_id:
            param_count += 1
            conditions.append(f"o.event_id = ${param_count}")
            params.append(event_id)
        
        if customer_email:
            param_count += 1
            conditions.append(f"o.customer_email ILIKE ${param_count}")
            params.append(f"%{customer_email}%")
        
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM orders o{where_clause}"
        total_count = await db.fetchval(count_query, *params)
        
        # Get orders
        data_query = f"""
            SELECT o.*, c.first_name, c.last_name, e.name as event_name
            FROM orders o
            LEFT JOIN customers c ON o.customer_id = c.customer_id
            LEFT JOIN events e ON o.event_id = e.event_id
            {where_clause}
            ORDER BY o.created_at DESC
            LIMIT ${param_count + 1} OFFSET ${param_count + 2}
        """
        params.extend([pagination.limit, pagination.offset])
        
        orders = await db.fetch(data_query, *params)
        
        # Convert to response models
        order_responses = []
        for order in orders:
            customer_name = None
            if order['first_name'] and order['last_name']:
                customer_name = f"{order['first_name']} {order['last_name']}"
            
            order_response = OrderResponse(
                order_id=order['order_id'],
                order_number=order['order_number'],
                customer_id=order['customer_id'],
                customer_email=order['customer_email'],
                customer_name=customer_name,
                event_id=order['event_id'],
                event_name=order['event_name'],
                package_type=order['package_type'],
                total_amount={"amount": float(order['total_amount']), "currency": order['currency']},
                currency=order['currency'],
                status=order['order_status'],
                fulfillment_status=order['fulfillment_status'],
                subtotal={"amount": float(order['subtotal'] or 0), "currency": order['currency']},
                discount_amount={"amount": float(order['discount_amount'] or 0), "currency": order['currency']},
                tax_amount={"amount": float(order['tax_amount'] or 0), "currency": order['currency']},
                payment_method=order['payment_method'],
                payment_reference=order['payment_reference'],
                paid_at=order['paid_at'],
                discount_code=order['discount_code'],
                special_instructions=order['special_instructions'],
                internal_notes=order['internal_notes'],
                download_expires_at=order['download_expires_at'],
                download_count=order['download_count'] or 0,
                max_downloads=order['max_downloads'] or 3,
                created_at=order['created_at'],
                updated_at=order['updated_at']
            )
            order_responses.append(order_response)
        
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
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get orders: {str(e)}"
        )


@router.get("/{order_id}", response_model=OrderDetailResponse)
async def get_order(
    order_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get detailed order information.
    """
    try:
        # Get order with customer and event details
        order = await db.fetchrow(
            """SELECT o.*, c.first_name, c.last_name, e.name as event_name
               FROM orders o
               LEFT JOIN customers c ON o.customer_id = c.customer_id
               LEFT JOIN events e ON o.event_id = e.event_id
               WHERE o.order_id = $1""",
            order_id
        )
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        # Check access permissions
        if (current_user['role'] != 'admin' and 
            order['customer_id'] != current_user.get('customer_id')):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get order items
        items = await db.fetch(
            """SELECT oi.*, i.filename, i.thumbnail_url
               FROM order_items oi
               JOIN images i ON oi.image_id = i.id
               WHERE oi.order_id = $1""",
            order_id
        )
        
        # Get payment history
        payments = await db.fetch(
            "SELECT * FROM payments WHERE order_id = $1 ORDER BY created_at DESC",
            order_id
        )
        
        # Convert items to response format
        order_items = []
        for item in items:
            order_items.append({
                "item_id": str(item['item_id']),
                "order_id": str(item['order_id']),
                "image_id": str(item['image_id']),
                "filename": item['filename'],
                "thumbnail_url": item['thumbnail_url'],
                "unit_price": {"amount": float(item['unit_price']), "currency": order['currency']},
                "created_at": item['created_at']
            })
        
        # Convert payments to response format
        payment_history = []
        for payment in payments:
            payment_history.append({
                "payment_id": str(payment['payment_id']),
                "amount": {"amount": float(payment['amount']), "currency": payment['currency']},
                "status": payment['status'],
                "payment_gateway": payment['payment_gateway'],
                "processed_at": payment['processed_at'],
                "created_at": payment['created_at']
            })
        
        customer_name = None
        if order['first_name'] and order['last_name']:
            customer_name = f"{order['first_name']} {order['last_name']}"
        
        return OrderDetailResponse(
            order_id=order['order_id'],
            order_number=order['order_number'],
            customer_id=order['customer_id'],
            customer_email=order['customer_email'],
            customer_name=customer_name,
            event_id=order['event_id'],
            event_name=order['event_name'],
            package_type=order['package_type'],
            total_amount={"amount": float(order['total_amount']), "currency": order['currency']},
            currency=order['currency'],
            status=order['order_status'],
            fulfillment_status=order['fulfillment_status'],
            subtotal={"amount": float(order['subtotal'] or 0), "currency": order['currency']},
            discount_amount={"amount": float(order['discount_amount'] or 0), "currency": order['currency']},
            tax_amount={"amount": float(order['tax_amount'] or 0), "currency": order['currency']},
            payment_method=order['payment_method'],
            payment_reference=order['payment_reference'],
            paid_at=order['paid_at'],
            discount_code=order['discount_code'],
            special_instructions=order['special_instructions'],
            internal_notes=order['internal_notes'],
            download_expires_at=order['download_expires_at'],
            download_count=order['download_count'] or 0,
            max_downloads=order['max_downloads'] or 3,
            items=order_items,
            payment_history=payment_history,
            status_history=[],  # Would need status history table
            created_at=order['created_at'],
            updated_at=order['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get order: {str(e)}"
        )


# ============================================================================
# PAYMENT ENDPOINTS
# ============================================================================
@router.post("/{order_id}/payments", response_model=PaymentResponse)
async def process_order_payment(
    order_id: str,
    payment_data: PaymentProcess,
    db = Depends(get_db)
):
    """
    Process payment for an order.
    """
    try:
        # Get order details
        order = await db.fetchrow(
            "SELECT * FROM orders WHERE order_id = $1 AND order_status = 'pending'",
            order_id
        )
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found or already processed"
            )
        
        # Validate payment amount matches order total
        if payment_data.amount.amount != order['total_amount']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment amount does not match order total"
            )
        
        # Process payment using payment service
        payment_result = await process_payment(payment_data, order)
        
        if payment_result['status'] == 'success':
            # Update order status
            await db.execute(
                """UPDATE orders SET 
                   order_status = 'paid', 
                   payment_method = $2, 
                   payment_reference = $3, 
                   paid_at = CURRENT_TIMESTAMP,
                   updated_at = CURRENT_TIMESTAMP 
                   WHERE order_id = $1""",
                order_id, payment_data.payment_method.value, payment_result['payment_id']
            )
            
            # Generate download link
            download_token = await generate_download_link(order_id)
            
            # Send confirmation email
            try:
                await send_order_confirmation(order['customer_email'], order_id)
            except Exception as e:
                print(f"Failed to send confirmation email: {str(e)}")
        
        return PaymentResponse(
            payment_id=payment_result['payment_id'],
            order_id=order_id,
            payment_gateway=payment_result['gateway'],
            payment_method=payment_data.payment_method,
            amount=payment_data.amount,
            status=payment_result['status'],
            gateway_transaction_id=payment_result.get('gateway_transaction_id'),
            processed_at=payment_result.get('processed_at'),
            created_at=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process payment: {str(e)}"
        )


# ============================================================================
# FULFILLMENT ENDPOINTS
# ============================================================================
@router.post("/{order_id}/fulfill", response_model=FulfillmentResponse)
async def fulfill_order(
    order_id: str,
    fulfillment_request: FulfillmentRequest,
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Fulfill an order by generating download links (Admin only).
    """
    try:
        # Get order details
        order = await db.fetchrow(
            "SELECT * FROM orders WHERE order_id = $1 AND order_status = 'paid'",
            order_id
        )
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found or not paid"
            )
        
        # Generate download link
        download_token = await generate_download_link(
            order_id, 
            fulfillment_request.download_expiry_hours
        )
        
        # Update order fulfillment status
        await db.execute(
            """UPDATE orders SET 
               fulfillment_status = 'fulfilled',
               download_expires_at = $2,
               updated_at = CURRENT_TIMESTAMP 
               WHERE order_id = $1""",
            order_id, 
            datetime.utcnow() + timedelta(hours=fulfillment_request.download_expiry_hours or 72)
        )
        
        # Create fulfillment record
        fulfillment_id = str(uuid.uuid4())
        download_url = f"/downloads/{download_token}"
        
        await db.execute(
            """INSERT INTO fulfillments 
               (fulfillment_id, order_id, download_token, download_url, 
                expires_at, max_downloads, fulfilled_at, status) 
               VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP, 'ready')""",
            fulfillment_id, order_id, download_token, download_url,
            datetime.utcnow() + timedelta(hours=fulfillment_request.download_expiry_hours or 72),
            3
        )
        
        # Send download ready email
        try:
            await send_download_ready_email(
                order['customer_email'], 
                order_id, 
                download_url,
                fulfillment_request.custom_message
            )
        except Exception as e:
            print(f"Failed to send download ready email: {str(e)}")
        
        return FulfillmentResponse(
            fulfillment_id=fulfillment_id,
            order_id=order_id,
            status="ready",
            download_token=download_token,
            download_url=download_url,
            expires_at=datetime.utcnow() + timedelta(hours=fulfillment_request.download_expiry_hours or 72),
            max_downloads=3,
            download_count=0,
            fulfilled_at=datetime.utcnow(),
            created_at=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fulfill order: {str(e)}"
        )
