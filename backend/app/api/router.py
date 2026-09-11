from fastapi import APIRouter

from app.api.endpoints import conversions, health

api_router = APIRouter()
api_router.include_router(health.router, tags=["system"])
api_router.include_router(conversions.router, prefix="/conversions", tags=["conversions"])

