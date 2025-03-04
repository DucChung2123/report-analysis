from fastapi import APIRouter
from .document_routes import router as document_router

# Main router that includes all other routers
router = APIRouter()

# Include document routes
router.include_router(document_router)