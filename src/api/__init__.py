# Makes the api directory a proper Python package
from fastapi import APIRouter

# Create a router that will be mounted to the main app
api_router = APIRouter()

# Import SSE router and include it
from .sse import router as sse_router
api_router.include_router(sse_router, tags=["events"])

# Import routes directly to register them with the api_router
from .routes import router as main_router
api_router.include_router(main_router, tags=["main"])

from .sse import notify_clients, shutdown_event