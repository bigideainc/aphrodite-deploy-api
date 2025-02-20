from fastapi import APIRouter
from app.api.v1.endpoints import router as deploy_router

api_router = APIRouter()

api_router.include_router(deploy_router, prefix="/v1", tags=["deployments"])