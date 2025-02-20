from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.firebase import initialize_firebase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("aphrodite-api")

db = initialize_firebase()

app = FastAPI(
    title="Aphrodite Engine Deployment API",
    description="API for deploying Aphrodite Engine models with OpenVINO",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/")
async def root():
    return {
        "name": "Aphrodite Engine Deployment API",
        "version": "1.0.0",
        "status": "online"
    }