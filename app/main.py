from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio
from contextlib import asynccontextmanager

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.firebase import initialize_firebase
from app.services.monitor_service import start_monitor_scheduler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("aphrodite-api")

db = initialize_firebase()

# Global variable to store monitor task
monitor_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown events for the FastAPI application
    """
    # Start deployment monitor on application startup
    global monitor_task
    logger.info("Starting deployment monitor...")
    
    # Start monitoring in background
    monitor_task = asyncio.create_task(start_monitor_scheduler(interval_seconds=5))
    
    # Yield control back to FastAPI
    yield
    
    # Cleanup on shutdown
    logger.info("Stopping deployment monitor...")
    if monitor_task:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            logger.info("Monitor task cancelled successfully")

# Create the FastAPI application with lifespan
app = FastAPI(
    title="Aphrodite Engine Deployment API",
    description="API for deploying Aphrodite Engine models with OpenVINO",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

# If you're using an older version of FastAPI without lifespan support,
# use these event handlers instead:
"""
@app.on_event("startup")
async def startup_event():
    global monitor_task
    logger.info("Starting deployment monitor...")
    
    from app.services.monitor_service import start_monitor_scheduler
    monitor_task = asyncio.create_task(start_monitor_scheduler(interval_seconds=5))

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Stopping deployment monitor...")
    if monitor_task:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            logger.info("Monitor task cancelled successfully")
"""

@app.get("/")
async def root():
    return {
        "name": "Aphrodite Engine Deployment API",
        "version": "1.0.0",
        "status": "online"
    }

# Admin route for manual monitor triggering (useful for debugging)
@app.get("/admin/trigger-monitor")
async def trigger_monitor():
    """
    Manually trigger deployment monitoring (admin only)
    """
    from app.services.monitor_service import monitor_deployments
    
    # Create a task to run monitoring once
    task = asyncio.create_task(monitor_deployments())
    
    return {"message": "Deployment monitoring triggered"}