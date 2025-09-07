# ============================================================================
# ANALYTICS ROUTER
# ============================================================================
"""
Analytics router for the Event Photo Sales System.
Handles business intelligence, reporting, and performance metrics.
"""

from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from decimal import Decimal

from models.order import OrderStatsResponse
from models.pricing import PricingAnalyticsResponse, PackagePerformance
from models.event import EventAnalyticsFilter
from models.common import SuccessResponse, BaseResponse
from database.connection import get_db
from core.dependencies import get_current_admin_user

# ============================================================================
# ROUTER SETUP
# ============================================================================
router = APIRouter()

# ============================================================================
# DASHBOARD ANALYTICS ENDPOINTS
# ============================================================================
@router.get("/dashboard", response_model=dict)
async def get_dashboard_analytics(
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Get comprehensive dashboard analytics (Admin only).
    """
    try:
        # Revenue metrics
        revenue_today = await db.fetchval(
            "SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE order_status = 'paid' AND DATE(created_at) = CURRENT_DATE"
        )
        
        revenue_month = await db.fetchval(
            "SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE order_status = 'paid' AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)"
        )
        
        revenue_year = await db.fetchval(
            "SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE order_status = 'paid' AND DATE_TRUNC('year', created_at) = DATE_TRUNC('year', CURRENT_DATE)"
        )
        
        # Order metrics
        orders_today = await db.fetchval(
            "SELECT COUNT(*) FROM orders WHERE DATE(created_at) = CURRENT_DATE"
        )
        
        orders_month = await db.fetchval(
            "SELECT COUNT(*) FROM orders WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)"
        )
        
        pending_orders = await db.fetchval(
            "SELECT COUNT(*) FROM orders WHERE order_status = 'pending'"
        )
        
        # Customer metrics
        new_customers_today = await db.fetchval(
            "SELECT COUNT(*) FROM customers WHERE DATE(created_at) = CURRENT_DATE"
        )
        
        new_customers_month = await db.fetchval(
            "SELECT COUNT(*) FROM customers WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)"
        )
        
        total_customers = await db.fetchval("SELECT COUNT(*) FROM customers")
        
        # Event metrics
        active_events = await db.fetchval(
            "SELECT COUNT(*) FROM events WHERE status = 'live'"
        )
        
        total_events = await db.fetchval("SELECT COUNT(*) FROM events")
        
        # Image metrics
        total_images = await db.fetchval("SELECT COUNT(*) FROM images")
        
        images_uploaded_today = await db.fetchval(
            "SELECT COUNT(*) FROM images WHERE DATE(timestamp) = CURRENT_DATE"
        )
        
        # Cart metrics
        active_carts = await db.fetchval(
            "SELECT COUNT(*) FROM cart_sessions WHERE is_active = TRUE AND expires_at > NOW()"
        )
        
        abandoned_carts = await db.fetchval(
            "SELECT COUNT(*) FROM cart_sessions WHERE is_active = TRUE AND expires_at <= NOW()"
        )
        
        # Average order value
        avg_order_value = await db.fetchval(
            "SELECT COALESCE(AVG(total_amount), 0) FROM orders WHERE order_status = 'paid'"
        )
        
        # Conversion rate (orders/active carts)
        total_carts = await db.fetchval("SELECT COUNT(*) FROM cart_sessions")
        conversion_rate = (orders_month / total_carts * 100) if total_carts > 0 else 0
        
        # Top selling events (last 30 days)
        top_events = await db.fetch(
            """SELECT e.event_id, e.name, COUNT(o.order_id) as order_count, SUM(o.total_amount) as revenue
               FROM events e
               JOIN orders o ON e.event_id = o.event_id
               WHERE o.order_status = 'paid' AND o.created_at >= NOW() - INTERVAL '30 days'
               GROUP BY e.event_id, e.name
               ORDER BY revenue DESC
               LIMIT 5"""
        )
        
        # Package popularity
        package_stats = await db.fetch(
            """SELECT package_type, COUNT(*) as order_count, SUM(total_amount) as revenue
               FROM orders
               WHERE order_status = 'paid' AND created_at >= NOW() - INTERVAL '30 days'
               GROUP BY package_type
               ORDER BY order_count DESC"""
        )
        
        # Recent orders
        recent_orders = await db.fetch(
            """SELECT o.order_id, o.order_number, o.total_amount, o.package_type, o.created_at,
                      c.first_name, c.last_name, c.email, e.name as event_name
               FROM orders o
               LEFT JOIN customers c ON o.customer_id = c.customer_id
               LEFT JOIN events e ON o.event_id = e.event_id
               WHERE o.order_status = 'paid'
               ORDER BY o.created_at DESC
               LIMIT 10"""
        )
        
        # Daily revenue trend (last 7 days)
        daily_revenue = await db.fetch(
            """SELECT DATE(created_at) as date, COUNT(*) as orders, SUM(total_amount) as revenue
               FROM orders
               WHERE order_status = 'paid' AND created_at >= NOW() - INTERVAL '7 days'
               GROUP BY DATE(created_at)
               ORDER BY date"""
        )
        
        return {
            "revenue_metrics": {
            "cart_metrics": {
                "active": active_carts,
                "abandoned": abandoned_carts
            },
            "top_events": [
                {
                    "event_id": str(event['event_id']),
                    "name": event['name'],
                    "order_count": event['order_count'],
                    "revenue": float(event['revenue'])
                }
                for event in top_events
            ],
            "package_stats": [
                {
                    "package_type": stat['package_type'],
                    "order_count": stat['order_count'],
                    "revenue": float(stat['revenue'])
                }
                for stat in package_stats
            ],
            "recent_orders": [
                {
                    "order_id": str(order['order_id']),
                    "order_number": order['order_number'],
                    "customer_name": f"{order['first_name']} {order['last_name']}".strip() if order['first_name'] else None,
                    "customer_email": order['email'],
                    "event_name": order['event_name'],
                    "package_type": order['package_type'],
                    "total_amount": float(order['total_amount']),
                    "created_at": order['created_at']
                }
                for order in recent_orders
            ],
            "daily_revenue": [
                {
                    "date": revenue['date'].isoformat(),
                    "orders": revenue['orders'],
                    "revenue": float(revenue['revenue'])
                }
                for revenue in daily_revenue
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard analytics: {str(e)}"
        )


# ============================================================================
# REVENUE ANALYTICS ENDPOINTS
# ============================================================================
@router.get("/revenue", response_model=dict)
async def get_revenue_analytics(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    event_id: Optional[str] = Query(None, description="Filter by specific event"),
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Get detailed revenue analytics with filtering (Admin only).
    """
    try:
        # Build date filter
        conditions = ["o.order_status = 'paid'"]
        params = []
        param_count = 0
        
        if start_date:
            param_count += 1
            conditions.append(f"o.created_at >= ${param_count}")
            params.append(start_date)
        
        if end_date:
            param_count += 1
            conditions.append(f"o.created_at <= ${param_count}")
            params.append(end_date)
        
        if event_id:
            param_count += 1
            conditions.append(f"o.event_id = ${param_count}")
            params.append(event_id)
        
        where_clause = " WHERE " + " AND ".join(conditions)
        
        # Get revenue summary
        summary = await db.fetchrow(
            f"SELECT COUNT(*) as total_orders, SUM(total_amount) as total_revenue, AVG(total_amount) as avg_order_value FROM orders o{where_clause}",
            *params
        )
        
        # Get revenue by package type
        package_revenue = await db.fetch(
            f"""SELECT package_type, COUNT(*) as order_count, SUM(total_amount) as revenue
                FROM orders o{where_clause}
                GROUP BY package_type ORDER BY revenue DESC""",
            *params
        )
        
        # Get revenue by event
        event_revenue = await db.fetch(
            f"""SELECT o.event_id, e.name as event_name, COUNT(*) as order_count, SUM(o.total_amount) as revenue
                FROM orders o
                JOIN events e ON o.event_id = e.event_id
                {where_clause}
                GROUP BY o.event_id, e.name ORDER BY revenue DESC LIMIT 10""",
            *params
        )
        
        # Get daily revenue trend
        daily_revenue = await db.fetch(
            f"""SELECT DATE(created_at) as date, COUNT(*) as orders, SUM(total_amount) as revenue
                FROM orders o{where_clause}
                GROUP BY DATE(created_at) ORDER BY date""",
            *params
        )
        
        # Get monthly revenue trend
        monthly_revenue = await db.fetch(
            f"""SELECT DATE_TRUNC('month', created_at) as month, COUNT(*) as orders, SUM(total_amount) as revenue
                FROM orders o{where_clause}
                GROUP BY DATE_TRUNC('month', created_at) ORDER BY month""",
            *params
        )
        
        return {
            "summary": {
                "total_orders": summary['total_orders'] or 0,
                "total_revenue": float(summary['total_revenue'] or 0),
                "avg_order_value": float(summary['avg_order_value'] or 0)
            },
            "by_package_type": [
                {
                    "package_type": pr['package_type'],
                    "order_count": pr['order_count'],
                    "revenue": float(pr['revenue']),
                    "avg_value": float(pr['revenue'] / pr['order_count']) if pr['order_count'] > 0 else 0
                }
                for pr in package_revenue
            ],
            "by_event": [
                {
                    "event_id": str(er['event_id']),
                    "event_name": er['event_name'],
                    "order_count": er['order_count'],
                    "revenue": float(er['revenue'])
                }
                for er in event_revenue
            ],
            "daily_trends": [
                {
                    "date": dr['date'].isoformat(),
                    "orders": dr['orders'],
                    "revenue": float(dr['revenue'])
                }
                for dr in daily_revenue
            ],
            "monthly_trends": [
                {
                    "month": mr['month'].isoformat(),
                    "orders": mr['orders'],
                    "revenue": float(mr['revenue'])
                }
                for mr in monthly_revenue
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get revenue analytics: {str(e)}"
        )


# ============================================================================
# CUSTOMER ANALYTICS ENDPOINTS
# ============================================================================
@router.get("/customers", response_model=dict)
async def get_customer_analytics(
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Get customer behavior analytics (Admin only).
    """
    try:
        # Customer acquisition metrics
        new_customers_last_30_days = await db.fetchval(
            "SELECT COUNT(*) FROM customers WHERE created_at >= NOW() - INTERVAL '30 days'"
        )
        
        # Customer lifetime value
        customer_ltv = await db.fetch(
            """SELECT c.customer_id, c.email, c.first_name, c.last_name,
                      COUNT(o.order_id) as total_orders,
                      SUM(o.total_amount) as total_spent,
                      AVG(o.total_amount) as avg_order_value,
                      MIN(o.created_at) as first_order,
                      MAX(o.created_at) as last_order
               FROM customers c
               LEFT JOIN orders o ON c.customer_id = o.customer_id AND o.order_status = 'paid'
               GROUP BY c.customer_id, c.email, c.first_name, c.last_name
               HAVING COUNT(o.order_id) > 0
               ORDER BY total_spent DESC
               LIMIT 20"""
        )
        
        # Repeat customer rate
        repeat_customers = await db.fetchval(
            """SELECT COUNT(DISTINCT customer_id) 
               FROM (
                   SELECT customer_id, COUNT(*) as order_count
                   FROM orders 
                   WHERE order_status = 'paid'
                   GROUP BY customer_id
                   HAVING COUNT(*) > 1
               ) repeat_buyers"""
        )
        
        total_customers_with_orders = await db.fetchval(
            "SELECT COUNT(DISTINCT customer_id) FROM orders WHERE order_status = 'paid'"
        )
        
        repeat_rate = (repeat_customers / total_customers_with_orders * 100) if total_customers_with_orders > 0 else 0
        
        # Customer segmentation by purchase behavior
        customer_segments = await db.fetch(
            """SELECT 
                   CASE 
                       WHEN total_spent >= 2000 THEN 'High Value'
                       WHEN total_spent >= 500 THEN 'Medium Value'
                       WHEN total_spent > 0 THEN 'Low Value'
                       ELSE 'No Purchase'
                   END as segment,
                   COUNT(*) as customer_count,
                   AVG(total_spent) as avg_spent
               FROM (
                   SELECT c.customer_id, COALESCE(SUM(o.total_amount), 0) as total_spent
                   FROM customers c
                   LEFT JOIN orders o ON c.customer_id = o.customer_id AND o.order_status = 'paid'
                   GROUP BY c.customer_id
               ) customer_totals
               GROUP BY segment
               ORDER BY customer_count DESC"""
        )
        
        # Monthly customer acquisition
        monthly_acquisition = await db.fetch(
            """SELECT DATE_TRUNC('month', created_at) as month, COUNT(*) as new_customers
               FROM customers
               WHERE created_at >= NOW() - INTERVAL '12 months'
               GROUP BY DATE_TRUNC('month', created_at)
               ORDER BY month"""
        )
        
        return {
            "acquisition_metrics": {
                "new_customers_30_days": new_customers_last_30_days,
                "repeat_customer_rate": round(repeat_rate, 2)
            },
            "top_customers": [
                {
                    "customer_id": str(customer['customer_id']),
                    "name": f"{customer['first_name']} {customer['last_name']}".strip() if customer['first_name'] else None,
                    "email": customer['email'],
                    "total_orders": customer['total_orders'],
                    "total_spent": float(customer['total_spent'] or 0),
                    "avg_order_value": float(customer['avg_order_value'] or 0),
                    "first_order": customer['first_order'],
                    "last_order": customer['last_order']
                }
                for customer in customer_ltv
            ],
            "customer_segments": [
                {
                    "segment": segment['segment'],
                    "customer_count": segment['customer_count'],
                    "avg_spent": float(segment['avg_spent'] or 0)
                }
                for segment in customer_segments
            ],
            "monthly_acquisition": [
                {
                    "month": ma['month'].isoformat(),
                    "new_customers": ma['new_customers']
                }
                for ma in monthly_acquisition
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get customer analytics: {str(e)}"
        )


# ============================================================================
# EVENT PERFORMANCE ANALYTICS ENDPOINTS
# ============================================================================
@router.get("/events/performance", response_model=dict)
async def get_event_performance_analytics(
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Get event performance analytics (Admin only).
    """
    try:
        # Event performance metrics
        event_performance = await db.fetch(
            """SELECT e.event_id, e.name, e.event_type, e.created_at,
                      COUNT(DISTINCT i.id) as total_images,
                      COUNT(DISTINCT o.order_id) as total_orders,
                      COUNT(DISTINCT o.customer_id) as unique_customers,
                      COALESCE(SUM(o.total_amount), 0) as total_revenue,
                      COALESCE(AVG(o.total_amount), 0) as avg_order_value
               FROM events e
               LEFT JOIN images i ON e.event_id = i.event_id AND i.status = 'published'
               LEFT JOIN orders o ON e.event_id = o.event_id AND o.order_status = 'paid'
               GROUP BY e.event_id, e.name, e.event_type, e.created_at
               ORDER BY total_revenue DESC
               LIMIT 20"""
        )
        
        # Event type performance
        event_type_performance = await db.fetch(
            """SELECT e.event_type,
                      COUNT(DISTINCT e.event_id) as event_count,
                      COUNT(DISTINCT o.order_id) as total_orders,
                      COALESCE(SUM(o.total_amount), 0) as total_revenue,
                      COALESCE(AVG(o.total_amount), 0) as avg_order_value
               FROM events e
               LEFT JOIN orders o ON e.event_id = o.event_id AND o.order_status = 'paid'
               GROUP BY e.event_type
               ORDER BY total_revenue DESC"""
        )
        
        # Popular images across all events
        popular_images = await db.fetch(
            """SELECT i.id, i.filename, i.event_id, e.name as event_name,
                      COUNT(oi.image_id) as purchase_count
               FROM images i
               JOIN events e ON i.event_id = e.event_id
               LEFT JOIN order_items oi ON i.id = oi.image_id
               LEFT JOIN orders o ON oi.order_id = o.order_id AND o.order_status = 'paid'
               GROUP BY i.id, i.filename, i.event_id, e.name
               HAVING COUNT(oi.image_id) > 0
               ORDER BY purchase_count DESC
               LIMIT 10"""
        )
        
        # Conversion funnel
        total_events = await db.fetchval("SELECT COUNT(*) FROM events")
        events_with_images = await db.fetchval(
            "SELECT COUNT(DISTINCT event_id) FROM images WHERE status = 'published'"
        )
        events_with_sales = await db.fetchval(
            "SELECT COUNT(DISTINCT event_id) FROM orders WHERE order_status = 'paid'"
        )
        
        return {
            "event_performance": [
                {
                    "event_id": str(event['event_id']),
                    "name": event['name'],
                    "event_type": event['event_type'],
                    "created_at": event['created_at'],
                    "total_images": event['total_images'],
                    "total_orders": event['total_orders'],
                    "unique_customers": event['unique_customers'],
                    "total_revenue": float(event['total_revenue']),
                    "avg_order_value": float(event['avg_order_value']),
                    "revenue_per_image": float(event['total_revenue'] / event['total_images']) if event['total_images'] > 0 else 0
                }
                for event in event_performance
            ],
            "by_event_type": [
                {
                    "event_type": etp['event_type'],
                    "event_count": etp['event_count'],
                    "total_orders": etp['total_orders'],
                    "total_revenue": float(etp['total_revenue']),
                    "avg_order_value": float(etp['avg_order_value']),
                    "avg_revenue_per_event": float(etp['total_revenue'] / etp['event_count']) if etp['event_count'] > 0 else 0
                }
                for etp in event_type_performance
            ],
            "popular_images": [
                {
                    "image_id": str(img['id']),
                    "filename": img['filename'],
                    "event_id": str(img['event_id']),
                    "event_name": img['event_name'],
                    "purchase_count": img['purchase_count']
                }
                for img in popular_images
            ],
            "conversion_funnel": {
                "total_events": total_events,
                "events_with_images": events_with_images,
                "events_with_sales": events_with_sales,
                "image_conversion_rate": round((events_with_images / total_events * 100) if total_events > 0 else 0, 2),
                "sales_conversion_rate": round((events_with_sales / events_with_images * 100) if events_with_images > 0 else 0, 2)
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get event performance analytics: {str(e)}"
        )


# ============================================================================
# PHOTOGRAPHER PERFORMANCE ANALYTICS ENDPOINTS
# ============================================================================
@router.get("/photographers/performance", response_model=dict)
async def get_photographer_performance_analytics(
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Get photographer performance analytics (Admin only).
    """
    try:
        # Photographer performance metrics
        photographer_performance = await db.fetch(
            """SELECT p.photographer_id, p.user_id, u.username,
                      COUNT(DISTINCT ea.event_id) as events_covered,
                      COUNT(DISTINCT i.id) as images_uploaded,
                      COUNT(DISTINCT o.order_id) as sales_generated,
                      COALESCE(SUM(o.total_amount), 0) as total_sales_value,
                      COALESCE(SUM(pc.commission_amount), 0) as total_commission_earned,
                      COALESCE(AVG(o.total_amount), 0) as avg_order_value
               FROM photographers p
               JOIN users u ON p.user_id = u.user_id
               LEFT JOIN event_assignments ea ON p.photographer_id = ea.photographer_id
               LEFT JOIN images i ON p.user_id = i.uploaded_by
               LEFT JOIN order_items oi ON i.id = oi.image_id
               LEFT JOIN orders o ON oi.order_id = o.order_id AND o.order_status = 'paid'
               LEFT JOIN photographer_commissions pc ON p.photographer_id = pc.photographer_id
               WHERE p.is_active = TRUE
               GROUP BY p.photographer_id, p.user_id, u.username
               ORDER BY total_sales_value DESC"""
        )
        
        # Commission summary
        commission_summary = await db.fetchrow(
            """SELECT 
                   COUNT(DISTINCT photographer_id) as active_photographers,
                   SUM(CASE WHEN status = 'pending' THEN commission_amount ELSE 0 END) as pending_commissions,
                   SUM(CASE WHEN status = 'paid' THEN commission_amount ELSE 0 END) as paid_commissions,
                   AVG(commission_rate) as avg_commission_rate
               FROM photographer_commissions pc
               JOIN photographers p ON pc.photographer_id = p.photographer_id
               WHERE p.is_active = TRUE"""
        )
        
        # Monthly commission trends
        monthly_commissions = await db.fetch(
            """SELECT DATE_TRUNC('month', pc.created_at) as month,
                      COUNT(*) as commission_count,
                      SUM(commission_amount) as total_commissions
               FROM photographer_commissions pc
               WHERE pc.created_at >= NOW() - INTERVAL '12 months'
               GROUP BY DATE_TRUNC('month', pc.created_at)
               ORDER BY month"""
        )
        
        return {
            "photographer_performance": [
                {
                    "photographer_id": str(perf['photographer_id']),
                    "username": perf['username'],
                    "events_covered": perf['events_covered'],
                    "images_uploaded": perf['images_uploaded'],
                    "sales_generated": perf['sales_generated'],
                    "total_sales_value": float(perf['total_sales_value']),
                    "total_commission_earned": float(perf['total_commission_earned']),
                    "avg_order_value": float(perf['avg_order_value']),
                    "images_per_event": round(perf['images_uploaded'] / perf['events_covered'], 1) if perf['events_covered'] > 0 else 0,
                    "sales_per_event": round(perf['sales_generated'] / perf['events_covered'], 1) if perf['events_covered'] > 0 else 0
                }
                for perf in photographer_performance
            ],
            "commission_summary": {
                "active_photographers": commission_summary['active_photographers'] or 0,
                "pending_commissions": float(commission_summary['pending_commissions'] or 0),
                "paid_commissions": float(commission_summary['paid_commissions'] or 0),
                "avg_commission_rate": float(commission_summary['avg_commission_rate'] or 0)
            },
            "monthly_trends": [
                {
                    "month": mc['month'].isoformat(),
                    "commission_count": mc['commission_count'],
                    "total_commissions": float(mc['total_commissions'])
                }
                for mc in monthly_commissions
            ]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get photographer performance analytics: {str(e)}"
        )


# ============================================================================
# EXPORT ENDPOINTS
# ============================================================================
@router.post("/export/revenue", response_model=SuccessResponse)
async def export_revenue_report(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    format: str = Query("csv", description="Export format: csv, excel, pdf"),
    current_user: dict = Depends(get_current_admin_user),
    db = Depends(get_db)
):
    """
    Export revenue report in specified format (Admin only).
    """
    try:
        # This would typically generate a file and return a download link
        # For now, return a success message with placeholder data
        
        export_id = str(uuid.uuid4())
        
        # In a real implementation, you would:
        # 1. Generate the report in the background
        # 2. Store it in file storage
        # 3. Return a download link
        
        return SuccessResponse(
            success=True,
            message="Revenue report export initiated",
            data={
                "export_id": export_id,
                "status": "processing",
                "estimated_completion": "2 minutes",
                "download_url": f"/downloads/reports/{export_id}.{format}"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export revenue report: {str(e)}"
        )today": float(revenue_today),
                "month": float(revenue_month),
                "year": float(revenue_year)
            },
            "order_metrics": {
                "today": orders_today,
                "month": orders_month,
                "pending": pending_orders,
                "avg_order_value": float(avg_order_value),
                "conversion_rate": round(conversion_rate, 2)
            },
            "customer_metrics": {
                "new_today": new_customers_today,
                "new_month": new_customers_month,
                "total": total_customers
            },
            "event_metrics": {
                "active": active_events,
                "total": total_events
            },
            "image_metrics": {
                "total": total_images,
                "uploaded_today": images_uploaded_today
            },
            "cart_metrics": {
                "active": active_carts,
                "
