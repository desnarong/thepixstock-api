# ============================================================================
# EVENTS ROUTER
# ============================================================================
"""
Events router for the Event Photo Sales System.
Handles event management, pricing, images, and sales settings.
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
import uuid

from models.event import (
    EventCreate, EventResponse, EventUpdate, EventListResponse, EventWithStats,
    EventSalesSettingsCreate, EventSalesSettingsResponse, EventSalesSettingsUpdate,
    ImageUpload, ImageResponse, ImageListResponse, ImageUpdate,
    WatermarkCreate, WatermarkResponse, BulkWatermarkCreate,
    EventStatsResponse, EventAnalyticsFilter
)
from models.pricing import (
    EventPricingCreate, EventPricingResponse, EventPricingListResponse,
    PricingTemplateResponse, PackageType
)
from models.common import SuccessResponse, PaginationParams
from database.connection import get_db
from core.dependencies import get_current_user, get_current_admin_user
from core.file_storage import save_uploaded_file, generate_watermark
from services.image_processing import process_uploaded_image
from services.face_detection import detect_faces

# ============================================================================
# ROUTER SETUP
# ============================================================================
router = APIRouter()

# ============================================================================
# EVENT MANAGEMENT ENDPOINTS
# ============================================================================
@router.get("/", response_model=EventListResponse)
async def get_events(
    pagination: PaginationParams = Depends(),
    search: Optional[str] = Query(None, description="Search events by name"),
    status: Optional[str] = Query(None, description="Filter by event status"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get all events with pagination and filtering.
    """
    try:
        # Build query conditions
        conditions = []
        params = []
        param_count = 0
        
        if search:
            param_count += 1
            conditions.append(f"e.name ILIKE ${param_count}")
            params.append(f"%{search}%")
        
        if status:
            param_count += 1
            conditions.append(f"e.status = ${param_count}")
            params.append(status)
        
        if event_type:
            param_count += 1
            conditions.append(f"e.event_type = ${param_count}")
            params.append(event_type)
        
        # Non-admin users can only see their own events or public events
        if current_user['role'] != 'admin':
            param_count += 1
            conditions.append(f"(e.created_by = ${param_count} OR e.visibility = 'public')")
            params.append(current_user['user_id'])
        
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        # Get total count
        count_query = f"""
            SELECT COUNT(*) FROM events e
            LEFT JOIN users u ON e.created_by = u.user_id
            {where_clause}
        """
        total_count = await db.fetchval(count_query, *params)
        
        # Get events with stats
        data_query = f"""
            SELECT 
                e.*,
                u.username as created_by_username,
                COALESCE(img_stats.total_images, 0) as total_images,
                COALESCE(order_stats.total_orders, 0) as total_orders,
                COALESCE(order_stats.total_revenue, 0) as total_revenue,
                COALESCE(order_stats.unique_customers, 0) as unique_customers
            FROM events e
            LEFT JOIN users u ON e.created_by = u.user_id
            LEFT JOIN (
                SELECT event_id, COUNT(*) as total_images 
                FROM images 
                WHERE status = 'published'
                GROUP BY event_id
            ) img_stats ON e.event_id = img_stats.event_id
            LEFT JOIN (
                SELECT 
                    o.event_id,
                    COUNT(*) as total_orders,
                    SUM(o.total_amount) as total_revenue,
                    COUNT(DISTINCT o.customer_id) as unique_customers
                FROM orders o 
                WHERE o.order_status = 'paid'
                GROUP BY o.event_id
            ) order_stats ON e.event_id = order_stats.event_id
            {where_clause}
            ORDER BY e.created_at DESC
            LIMIT ${param_count + 1} OFFSET ${param_count + 2}
        """
        params.extend([pagination.limit, pagination.offset])
        
        events = await db.fetch(data_query, *params)
        
        # Convert to response models
        event_responses = []
        for event in events:
            event_response = EventResponse(
                event_id=event['event_id'],
                name=event['name'],
                description=event['description'],
                event_type=event['event_type'],
                event_date=event['event_date'],
                location=event['location'],
                visibility=event['visibility'],
                created_by=event['created_by'],
                created_by_username=event['created_by_username'],
                status=event['status'],
                tags=event['tags'] or [],
                max_images=event['max_images'],
                total_images=event['total_images'],
                total_orders=event['total_orders'],
                total_sales={"amount": float(event['total_revenue'] or 0), "currency": "THB"},
                unique_customers=event['unique_customers'],
                created_at=event['created_at'],
                updated_at=event['updated_at']
            )
            event_responses.append(event_response)
        
        return EventListResponse(
            data=event_responses,
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
            detail=f"Failed to get events: {str(e)}"
        )


@router.post("/", response_model=SuccessResponse)
async def create_event(
    event: EventCreate,
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Create a new event (Admin only).
    """
    try:
        event_id = str(uuid.uuid4())
        
        await db.execute(
            """INSERT INTO events 
               (event_id, name, description, event_type, event_date, location, visibility, 
                created_by, tags, max_images) 
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
            event_id, event.name, event.description, event.event_type.value,
            event.event_date, event.location, event.visibility.value,
            current_user['user_id'], event.tags or [], event.max_images
        )
        
        # Assign photographers if specified
        if event.photographer_ids:
            for photographer_id in event.photographer_ids:
                assignment_id = str(uuid.uuid4())
                await db.execute(
                    """INSERT INTO event_assignments (assignment_id, event_id, photographer_id, role) 
                       VALUES ($1, $2, $3, $4)""",
                    assignment_id, event_id, photographer_id, "photographer"
                )
        
        return SuccessResponse(
            success=True,
            message="Event created successfully",
            data={"event_id": event_id}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create event: {str(e)}"
        )


@router.get("/{event_id}", response_model=EventWithStats)
async def get_event(
    event_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get detailed event information with statistics.
    """
    try:
        # Get event with detailed stats
        event = await db.fetchrow(
            """SELECT 
                e.*,
                u.username as created_by_username,
                COALESCE(img_stats.total_images, 0) as total_images,
                COALESCE(order_stats.total_orders, 0) as total_orders,
                COALESCE(order_stats.total_revenue, 0) as total_revenue,
                COALESCE(order_stats.unique_customers, 0) as unique_customers,
                COALESCE(order_stats.avg_order_value, 0) as avg_order_value
            FROM events e
            LEFT JOIN users u ON e.created_by = u.user_id
            LEFT JOIN (
                SELECT event_id, COUNT(*) as total_images 
                FROM images 
                WHERE status = 'published'
                GROUP BY event_id
            ) img_stats ON e.event_id = img_stats.event_id
            LEFT JOIN (
                SELECT 
                    o.event_id,
                    COUNT(*) as total_orders,
                    SUM(o.total_amount) as total_revenue,
                    COUNT(DISTINCT o.customer_id) as unique_customers,
                    AVG(o.total_amount) as avg_order_value
                FROM orders o 
                WHERE o.order_status = 'paid'
                GROUP BY o.event_id
            ) order_stats ON e.event_id = order_stats.event_id
            WHERE e.event_id = $1""",
            event_id
        )
        
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )
        
        # Check access permissions
        if (current_user['role'] != 'admin' and 
            event['created_by'] != current_user['user_id'] and 
            event['visibility'] != 'public'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get sales breakdown by package
        sales_by_package = await db.fetch(
            """SELECT package_type, COUNT(*) as order_count, SUM(total_amount) as revenue
               FROM orders 
               WHERE event_id = $1 AND order_status = 'paid'
               GROUP BY package_type""",
            event_id
        )
        
        # Get daily sales for last 30 days
        daily_sales = await db.fetch(
            """SELECT DATE(created_at) as date, COUNT(*) as orders, SUM(total_amount) as revenue
               FROM orders 
               WHERE event_id = $1 AND order_status = 'paid' 
               AND created_at >= NOW() - INTERVAL '30 days'
               GROUP BY DATE(created_at)
               ORDER BY date""",
            event_id
        )
        
        # Get top selling images
        top_selling_images = await db.fetch(
            """SELECT i.id, i.filename, i.thumbnail_url, COUNT(oi.image_id) as purchase_count
               FROM images i
               JOIN order_items oi ON i.id = oi.image_id
               JOIN orders o ON oi.order_id = o.order_id
               WHERE i.event_id = $1 AND o.order_status = 'paid'
               GROUP BY i.id, i.filename, i.thumbnail_url
               ORDER BY purchase_count DESC
               LIMIT 10""",
            event_id
        )
        
        return EventWithStats(
            event_id=event['event_id'],
            name=event['name'],
            description=event['description'],
            event_type=event['event_type'],
            event_date=event['event_date'],
            location=event['location'],
            visibility=event['visibility'],
            created_by=event['created_by'],
            created_by_username=event['created_by_username'],
            status=event['status'],
            tags=event['tags'] or [],
            max_images=event['max_images'],
            total_images=event['total_images'],
            total_orders=event['total_orders'],
            total_sales={"amount": float(event['total_revenue'] or 0), "currency": "THB"},
            unique_customers=event['unique_customers'],
            avg_order_value={"amount": float(event['avg_order_value'] or 0), "currency": "THB"},
            sales_by_package=[
                {"package_type": s['package_type'], "order_count": s['order_count'], "revenue": float(s['revenue'])}
                for s in sales_by_package
            ],
            daily_sales=[
                {"date": s['date'].isoformat(), "orders": s['orders'], "revenue": float(s['revenue'])}
                for s in daily_sales
            ],
            top_selling_images=[
                {"image_id": str(img['id']), "filename": img['filename'], "thumbnail_url": img['thumbnail_url'], "purchase_count": img['purchase_count']}
                for img in top_selling_images
            ],
            created_at=event['created_at'],
            updated_at=event['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get event: {str(e)}"
        )


@router.put("/{event_id}", response_model=SuccessResponse)
async def update_event(
    event_id: str,
    event_update: EventUpdate,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Update event information.
    """
    try:
        # Check if event exists and user has permission
        event = await db.fetchrow("SELECT created_by FROM events WHERE event_id = $1", event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )
        
        if current_user['role'] != 'admin' and event['created_by'] != current_user['user_id']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Build update query
        update_fields = []
        params = []
        param_count = 0
        
        for field, value in event_update.dict(exclude_unset=True).items():
            if value is not None:
                param_count += 1
                if field in ['event_type', 'visibility', 'status']:
                    update_fields.append(f"{field} = ${param_count}")
                    params.append(value.value)
                else:
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
        
        # Add event_id for WHERE clause
        param_count += 1
        params.append(event_id)
        
        query = f"UPDATE events SET {', '.join(update_fields)} WHERE event_id = ${param_count}"
        await db.execute(query, *params)
        
        return SuccessResponse(
            success=True,
            message="Event updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update event: {str(e)}"
        )


@router.delete("/{event_id}", response_model=SuccessResponse)
async def delete_event(
    event_id: str,
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Delete event and all associated data (Admin only).
    """
    try:
        # Check if event exists
        event = await db.fetchrow("SELECT name FROM events WHERE event_id = $1", event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )
        
        # Delete in correct order to handle foreign key constraints
        await db.execute("DELETE FROM order_items WHERE order_id IN (SELECT order_id FROM orders WHERE event_id = $1)", event_id)
        await db.execute("DELETE FROM orders WHERE event_id = $1", event_id)
        await db.execute("DELETE FROM image_watermarks WHERE image_id IN (SELECT id FROM images WHERE event_id = $1)", event_id)
        await db.execute("DELETE FROM faces WHERE image_id IN (SELECT id FROM images WHERE event_id = $1)", event_id)
        await db.execute("DELETE FROM images WHERE event_id = $1", event_id)
        await db.execute("DELETE FROM event_pricing WHERE event_id = $1", event_id)
        await db.execute("DELETE FROM event_sales_settings WHERE event_id = $1", event_id)
        await db.execute("DELETE FROM events WHERE event_id = $1", event_id)
        
        return SuccessResponse(
            success=True,
            message="Event deleted successfully"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete event: {str(e)}"
        )


# ============================================================================
# EVENT PRICING ENDPOINTS
# ============================================================================
@router.get("/{event_id}/pricing", response_model=EventPricingListResponse)
async def get_event_pricing(
    event_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get pricing configuration for an event.
    """
    try:
        pricing = await db.fetch(
            """SELECT ep.*, e.name as event_name,
               COALESCE(order_stats.sales_count, 0) as sales_count,
               COALESCE(order_stats.total_revenue, 0) as total_revenue
               FROM event_pricing ep
               JOIN events e ON ep.event_id = e.event_id
               LEFT JOIN (
                   SELECT event_id, package_type, COUNT(*) as sales_count, SUM(total_amount) as total_revenue
                   FROM orders 
                   WHERE order_status = 'paid'
                   GROUP BY event_id, package_type
               ) order_stats ON ep.event_id = order_stats.event_id AND ep.package_type = order_stats.package_type
               WHERE ep.event_id = $1 
               ORDER BY 
                   CASE ep.package_type 
                       WHEN 'single' THEN 1 
                       WHEN 'package_4' THEN 2 
                       WHEN 'unlimited' THEN 3 
                       ELSE 4 
                   END""",
            event_id
        )
        
        pricing_responses = []
        for p in pricing:
            pricing_response = EventPricingResponse(
                pricing_id=p['pricing_id'],
                event_id=p['event_id'],
                event_name=p['event_name'],
                package_type=p['package_type'],
                price={"amount": float(p['price']), "currency": "THB"},
                description=p['description'],
                is_active=p['is_active'],
                max_images=p.get('max_images'),
                validity_days=p.get('validity_days'),
                sales_count=p['sales_count'],
                total_revenue={"amount": float(p['total_revenue'] or 0), "currency": "THB"},
                created_at=p['created_at'],
                updated_at=p['updated_at']
            )
            pricing_responses.append(pricing_response)
        
        return EventPricingListResponse(
            data=pricing_responses,
            pagination={
                "page": 1,
                "limit": len(pricing_responses),
                "total": len(pricing_responses),
                "pages": 1,
                "has_next": False,
                "has_prev": False
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get event pricing: {str(e)}"
        )


@router.post("/{event_id}/pricing", response_model=SuccessResponse)
async def set_event_pricing(
    event_id: str,
    pricing: List[EventPricingCreate],
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Set pricing configuration for an event (Admin only).
    """
    try:
        # Check if event exists
        event = await db.fetchrow("SELECT name FROM events WHERE event_id = $1", event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )
        
        # Clear existing pricing
        await db.execute("DELETE FROM event_pricing WHERE event_id = $1", event_id)
        
        # Insert new pricing
        for price_config in pricing:
            pricing_id = str(uuid.uuid4())
            await db.execute(
                """INSERT INTO event_pricing 
                   (pricing_id, event_id, package_type, price, description, is_active, max_images, validity_days) 
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                pricing_id, event_id, price_config.package_type.value, 
                price_config.price.amount, price_config.description, price_config.is_active,
                price_config.max_images, price_config.validity_days
            )
        
        return SuccessResponse(
            success=True,
            message="Pricing updated successfully",
            data={"event_id": event_id, "pricing_count": len(pricing)}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set event pricing: {str(e)}"
        )


# ============================================================================
# EVENT SALES SETTINGS ENDPOINTS
# ============================================================================
@router.get("/{event_id}/sales-settings", response_model=EventSalesSettingsResponse)
async def get_event_sales_settings(
    event_id: str,
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Get sales settings for an event (Admin only).
    """
    try:
        settings = await db.fetchrow(
            "SELECT * FROM event_sales_settings WHERE event_id = $1", event_id
        )
        
        if not settings:
            # Return default settings
            return EventSalesSettingsResponse(
                setting_id=str(uuid.uuid4()),
                event_id=event_id,
                sales_status="draft",
                sales_start_date=None,
                sales_end_date=None,
                watermark_enabled=True,
                preview_max_width=800,
                preview_max_height=600,
                download_link_expiry_hours=72,
                max_downloads_per_purchase=3,
                has_custom_settings=False,
                created_at=datetime.utcnow()
            )
        
        return EventSalesSettingsResponse(
            setting_id=settings['setting_id'],
            event_id=settings['event_id'],
            sales_status=settings['sales_status'],
            sales_start_date=settings['sales_start_date'],
            sales_end_date=settings['sales_end_date'],
            watermark_enabled=settings['watermark_enabled'],
            preview_max_width=settings['preview_max_width'],
            preview_max_height=settings['preview_max_height'],
            download_link_expiry_hours=settings['download_link_expiry_hours'],
            max_downloads_per_purchase=settings['max_downloads_per_purchase'],
            has_custom_settings=True,
            created_at=settings['created_at'],
            updated_at=settings['updated_at']
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sales settings: {str(e)}"
        )


@router.put("/{event_id}/sales-settings", response_model=SuccessResponse)
async def update_event_sales_settings(
    event_id: str,
    settings: EventSalesSettingsUpdate,
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Update sales settings for an event (Admin only).
    """
    try:
        # Check if event exists
        event = await db.fetchrow("SELECT name FROM events WHERE event_id = $1", event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )
        
        # Build update query
        update_fields = []
        params = []
        param_count = 0
        
        for field, value in settings.dict(exclude_unset=True).items():
            if value is not None:
                param_count += 1
                if field == 'sales_status':
                    update_fields.append(f"{field} = ${param_count}")
                    params.append(value.value)
                else:
                    update_fields.append(f"{field} = ${param_count}")
                    params.append(value)
        
        if update_fields:
            # Add updated_at
            param_count += 1
            update_fields.append(f"updated_at = ${param_count}")
            params.append(datetime.utcnow())
            
            # Add event_id for WHERE clause
            param_count += 1
            params.append(event_id)
            
            # Upsert settings
            setting_id = str(uuid.uuid4())
            await db.execute(
                f"""INSERT INTO event_sales_settings 
                   (setting_id, event_id, {', '.join(field.split(' = ')[0] for field in update_fields)})
                   VALUES ($1, $2, {', '.join(f'${i+3}' for i in range(len(update_fields)))})
                   ON CONFLICT (event_id) DO UPDATE SET
                   {', '.join(update_fields)}""",
                setting_id, event_id, *params[:-1]
            )
        
        return SuccessResponse(
            success=True,
            message="Sales settings updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update sales settings: {str(e)}"
        )


# ============================================================================
# IMAGE MANAGEMENT ENDPOINTS
# ============================================================================
@router.get("/{event_id}/images", response_model=ImageListResponse)
async def get_event_images(
    event_id: str,
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get images for an event with pagination.
    """
    try:
        # Build query conditions
        conditions = ["i.event_id = $1"]
        params = [event_id]
        param_count = 1
        
        if status_filter:
            param_count += 1
            conditions.append(f"i.status = ${param_count}")
            params.append(status_filter)
        
        where_clause = " WHERE " + " AND ".join(conditions)
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM images i{where_clause}"
        total_count = await db.fetchval(count_query, *params)
        
        # Get images with stats
        data_query = f"""
            SELECT 
                i.*,
                u.username as uploaded_by_username,
                COALESCE(purchase_stats.purchase_count, 0) as purchase_count,
                COALESCE(face_stats.face_count, 0) as face_count,
                CASE WHEN face_stats.face_count > 0 THEN true ELSE false END as has_faces
            FROM images i
            LEFT JOIN users u ON i.uploaded_by = u.user_id
            LEFT JOIN (
                SELECT oi.image_id, COUNT(*) as purchase_count
                FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id
                WHERE o.order_status = 'paid'
                GROUP BY oi.image_id
            ) purchase_stats ON i.id = purchase_stats.image_id
            LEFT JOIN (
                SELECT image_id, COUNT(*) as face_count
                FROM faces
                GROUP BY image_id
            ) face_stats ON i.id = face_stats.image_id
            {where_clause}
            ORDER BY i.timestamp DESC
            LIMIT ${param_count + 1} OFFSET ${param_count + 2}
        """
        params.extend([pagination.limit, pagination.offset])
        
        images = await db.fetch(data_query, *params)
        
        # Convert to response models
        image_responses = []
        for img in images:
            image_response = ImageResponse(
                image_id=img['id'],
                event_id=img['event_id'],
                filename=img['filename'],
                title=img.get('title'),
                description=img.get('description'),
                tags=img.get('tags', []),
                uploaded_by=img['uploaded_by'],
                uploaded_by_username=img['uploaded_by_username'],
                status=img['status'],
                file_size=img['file_size'],
                content_type=img['content_type'],
                width=img.get('width'),
                height=img.get('height'),
                consent_given=img['consent_given'],
                thumbnail_url=img['thumbnail_url'],
                preview_url=img.get('preview_url'),
                watermark_url=img.get('watermark_url'),
                purchase_count=img['purchase_count'],
                face_count=img['face_count'],
                has_faces=img['has_faces'],
                created_at=img['timestamp'],
                updated_at=img.get('updated_at')
            )
            image_responses.append(image_response)
        
        return ImageListResponse(
            data=image_responses,
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
            detail=f"Failed to get event images: {str(e)}"
        )


@router.post("/{event_id}/images", response_model=SuccessResponse)
async def upload_event_image(
    event_id: str,
    file: UploadFile = File(...),
    consent_given: bool = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Upload image to an event.
    """
    try:
        # Check if event exists and user has permission
        event = await db.fetchrow("SELECT created_by FROM events WHERE event_id = $1", event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )
        
        # Check upload permissions
        if (current_user['role'] != 'admin' and 
            event['created_by'] != current_user['user_id'] and
            current_user['role'] != 'photographer'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only image files are allowed"
            )
        
        image_id = str(uuid.uuid4())
        
        # Save file to storage
        file_info = await save_uploaded_file(file, event_id, image_id)
        
        # Process tags
        tag_list = []
        if tags:
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        
        # Save image record
        await db.execute(
            """INSERT INTO images 
               (id, event_id, filename, title, description, tags, uploaded_by, consent_given, 
                file_size, content_type, width, height, status) 
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)""",
            image_id, event_id, file_info['filename'], title, description, tag_list,
            current_user['user_id'], consent_given, file_info['file_size'], 
            file_info['content_type'], file_info.get('width'), file_info.get('height'), 'processing'
        )
        
        # Process image in background (generate thumbnails, detect faces if consent given)
        # This would typically be handled by a background task queue
        try:
            await process_uploaded_image(image_id, file_info, consent_given)
        except Exception as e:
            # Log error but don't fail the upload
            print(f"Image processing failed: {str(e)}")
        
        return SuccessResponse(
            success=True,
            message="Image uploaded successfully",
            data={"image_id": image_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload image: {str(e)}"
        )


# ============================================================================
# WATERMARK ENDPOINTS
# ============================================================================
@router.post("/{event_id}/watermarks/bulk", response_model=SuccessResponse)
async def bulk_generate_watermarks(
    event_id: str,
    request: BulkWatermarkCreate,
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Generate watermarks for multiple images in an event (Admin only).
    """
    try:
        # Check if event exists
        event = await db.fetchrow("SELECT name FROM events WHERE event_id = $1", event_id)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )
        
        # Get images to process
        if request.image_ids:
            images = await db.fetch(
                "SELECT id, filename FROM images WHERE event_id = $1 AND id = ANY($2)",
                event_id, request.image_ids
            )
        else:
            images = await db.fetch(
                "SELECT id, filename FROM images WHERE event_id = $1",
                event_id
            )
        
        processed_count = 0
        for image in images:
            try:
                # Check if watermark already exists
                if not request.force_regenerate:
                    existing = await db.fetchrow(
                        "SELECT watermark_id FROM image_watermarks WHERE image_id = $1",
                        image['id']
                    )
                    if existing:
                        continue
                
                # Create watermark record
                watermark_id = str(uuid.uuid4())
                await db.execute(
                    """INSERT INTO image_watermarks (watermark_id, image_id, processing_status) 
                       VALUES ($1, $2, $3)
                       ON CONFLICT (image_id) DO UPDATE SET 
                       processing_status = 'pending', updated_at = CURRENT_TIMESTAMP""",
                    watermark_id, image['id'], 'pending'
                )
                
                # Generate watermark (this would typically be a background task)
                await generate_watermark(image['id'], request.watermark_type)
                processed_count += 1
                
            except Exception as e:
                print(f"Failed to generate watermark for image {image['id']}: {str(e)}")
        
        return SuccessResponse(
            success=True,
            message=f"Watermark generation queued for {processed_count} images",
            data={
                "processed_count": processed_count,
                "total_images": len(images)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate watermarks: {str(e)}"
        )
