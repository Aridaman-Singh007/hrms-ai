from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.parser import router as parser_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(parser_router, prefix="/parser")
