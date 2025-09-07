# ============================================================================
# ROUTERS PACKAGE INITIALIZATION
# ============================================================================
"""
API routers package for the Event Photo Sales System.

This package contains all the FastAPI routers organized by domain/functionality.
Each router handles a specific area of the application.
"""

from fastapi import APIRouter
from .auth import router as auth_router
from .events import router as events_router
from .orders import router as orders_router
from .customers import router as customers_router
from .analytics import router as analytics_router

# ============================================================================
# MAIN API ROUTER
# ============================================================================
api_router = APIRouter(prefix="/api/v1")

# Include all sub-routers
api_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["Authentication"]
)

api_router.include_router(
    events_router,
    prefix="/events",
    tags=["Events"]
)

api_router.include_router(
    orders_router,
    prefix="/orders",
    tags=["Orders"]
)

api_router.include_router(
    customers_router,
    prefix="/customers",
    tags=["Customers"]
)

api_router.include_router(
    analytics_router,
    prefix="/analytics",
    tags=["Analytics"]
)

# ============================================================================
# ROUTER METADATA
# ============================================================================
ROUTER_INFO = {
    "auth": {
        "description": "Authentication and user management endpoints",
        "endpoints_count": 8,
        "requires_auth": False
    },
    "events": {
        "description": "Event management, pricing, and image handling",
        "endpoints_count": 15,
        "requires_auth": True
    },
    "orders": {
        "description": "Order processing, cart management, and fulfillment",
        "endpoints_count": 12,
        "requires_auth": True
    },
    "customers": {
        "description": "Customer management and photographer administration",
        "endpoints_count": 10,
        "requires_auth": True
    },
    "analytics": {
        "description": "Business intelligence and reporting endpoints",
        "endpoints_count": 8,
        "requires_auth": True
    }
}

def get_router_info(router_name: str = None):
    """
    Get information about available routers.
    
    Args:
        router_name: Specific router name, or None for all routers
        
    Returns:
        Router information dictionary
    """
    if router_name:
        return ROUTER_INFO.get(router_name)
    return ROUTER_INFO

def get_all_tags():
    """Get all router tags for OpenAPI documentation."""
    return [
        {
            "name": "Authentication",
            "description": "User authentication, login, and token management"
        },
        {
            "name": "Events", 
            "description": "Event creation, management, pricing, and image handling"
        },
        {
            "name": "Orders",
            "description": "Shopping cart, order processing, and digital fulfillment"
        },
        {
            "name": "Customers",
            "description": "Customer management, photographers, and user administration"
        },
        {
            "name": "Analytics",
            "description": "Business intelligence, reports, and performance metrics"
        }
    ]

# Export everything
__all__ = [
    "api_router",
    "auth_router", 
    "events_router",
    "orders_router", 
    "customers_router",
    "analytics_router",
    "get_router_info",
    "get_all_tags",
    "ROUTER_INFO"
]
