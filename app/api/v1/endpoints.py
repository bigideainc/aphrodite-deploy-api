from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional
import uuid
import logging
from datetime import datetime

from app.models.deployment import DeploymentRequest, DeploymentResponse
from app.services.deployment_service import deploy_model
from app.db.firebase import db

router = APIRouter()
logger = logging.getLogger("api-endpoints")

@router.post("/deploy", response_model=DeploymentResponse)
async def deploy(request: DeploymentRequest, background_tasks: BackgroundTasks):
    try:
        deployment_id = str(uuid.uuid4())
        
        deployment_data = {
            'deploymentId': deployment_id,
            'userId': request.user_id,
            'modelId': request.model_id,
            'apiName': request.api_name,
            'status': 'queued',
            'createdAt': datetime.now().isoformat()
        }
        
        if db:
            from firebase_admin import firestore
            deployment_data['createdAt'] = firestore.SERVER_TIMESTAMP
            db.collection('deployments').document(deployment_id).set(deployment_data)
        
        background_tasks.add_task(deploy_model, deployment_id, request)
        
        return DeploymentResponse(
            deployment_id=deployment_id,
            status="queued",
            created_at=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error in deploy endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/deployments/{deployment_id}", response_model=Dict[str, Any])
async def get_deployment(deployment_id: str):
    if not db:
        raise HTTPException(status_code=500, detail="Firebase not configured")
    
    doc = db.collection('deployments').document(deployment_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Deployment not found")
    
    return doc.to_dict()

@router.get("/deployments", response_model=List[Dict[str, Any]])
async def list_deployments(user_id: Optional[str] = None, limit: int = 10):
    if not db:
        raise HTTPException(status_code=500, detail="Firebase not configured")
    
    query = db.collection('deployments')
    if user_id:
        query = query.where('userId', '==', user_id)
    
    query = query.order_by('createdAt', direction='DESCENDING').limit(limit)
    deployments = [doc.to_dict() for doc in query.stream()]
    
    return deployments