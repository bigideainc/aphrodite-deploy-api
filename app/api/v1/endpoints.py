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
        
        # Return response including monitoring URL
        monitor_url = f"/api/v1/deployments/{deployment_id}/status"
        return DeploymentResponse(
            deployment_id=deployment_id,
            status="queued",
            created_at=datetime.now().isoformat(),
            monitor_url=monitor_url
        )
        
    except Exception as e:
        logger.error(f"Error in deploy endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/deployments/{deployment_id}", response_model=Dict[str, Any])
async def get_deployment(deployment_id: str):
    """
    Get raw deployment data
    """
    if not db:
        raise HTTPException(status_code=500, detail="Firebase not configured")
    
    doc = db.collection('deployments').document(deployment_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Deployment not found")
    
    return doc.to_dict()

@router.get("/deployments/{deployment_id}/status", response_model=Dict[str, Any])
async def get_deployment_status(deployment_id: str):
    """
    Get detailed deployment status with progress information
    """
    if not db:
        raise HTTPException(status_code=500, detail="Firebase not configured")
    
    doc = db.collection('deployments').document(deployment_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Deployment not found")
    
    deployment_data = doc.to_dict()
    status = deployment_data.get('status', 'unknown')
    
    # Calculate progress percentage based on status
    progress = 0
    if status == 'queued':
        progress = 5
    elif status == 'deploying':
        progress = 15
    elif status == 'starting':
        progress = 50
    elif status == 'active':
        progress = 100
    elif status == 'failed':
        progress = -1  # Error state
    
    # Determine estimated time remaining
    estimated_time = None
    if status == 'queued':
        estimated_time = "5-10 minutes"
    elif status == 'deploying':
        estimated_time = "4-8 minutes"
    elif status == 'starting':
        estimated_time = "1-3 minutes"
    
    # Prepare the detailed status response
    response = {
        'deployment_id': deployment_id,
        'status': status,
        'progress': progress,
        'estimated_time': estimated_time,
        'model_id': deployment_data.get('modelId'),
        'created_at': deployment_data.get('createdAt'),
        'container_id': deployment_data.get('containerId'),
        'machine_id': deployment_data.get('machineId'),
        'tunnel_url': deployment_data.get('tunnelUrl'),
        'endpoints': deployment_data.get('endpoints'),
    }
    
    # Add error information if failed
    if status == 'failed':
        response['error'] = deployment_data.get('error')
        response['failed_at'] = deployment_data.get('failedAt')
    
    # Add completion information if active
    if status == 'active':
        response['deployment_completed'] = deployment_data.get('deploymentCompleted')
        response['deployment_duration'] = deployment_data.get('deploymentDuration')
    
    return response

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

@router.delete("/deployments/{deployment_id}", response_model=Dict[str, Any])
async def delete_deployment(deployment_id: str):
    """
    Delete a deployment - stops the container and removes the deployment
    """
    if not db:
        raise HTTPException(status_code=500, detail="Firebase not configured")
    
    # Get deployment info
    doc = db.collection('deployments').document(deployment_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Deployment not found")
    
    deployment_data = doc.to_dict()
    
    # If the deployment has an active container, we should stop it
    # This would require implementing container stopping logic in a service
    # For now, we'll just mark it as deleted in the database
    
    from firebase_admin import firestore
    db.collection('deployments').document(deployment_id).update({
        'status': 'deleted',
        'deletedAt': firestore.SERVER_TIMESTAMP
    })
    
    return {
        'deployment_id': deployment_id,
        'status': 'deleted',
        'message': 'Deployment marked as deleted'
    }

@router.post("/deployments/{deployment_id}/stop", response_model=Dict[str, Any])
async def stop_deployment(deployment_id: str):
    """
    Stop a running deployment without deleting it
    """
    if not db:
        raise HTTPException(status_code=500, detail="Firebase not configured")
    
    # Get deployment info
    doc = db.collection('deployments').document(deployment_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Deployment not found")
    
    deployment_data = doc.to_dict()
    current_status = deployment_data.get('status')
    
    if current_status != 'active':
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot stop deployment in '{current_status}' status"
        )
    
    # Update status to stopped
    from firebase_admin import firestore
    db.collection('deployments').document(deployment_id).update({
        'status': 'stopped',
        'stoppedAt': firestore.SERVER_TIMESTAMP
    })
    
    return {
        'deployment_id': deployment_id,
        'status': 'stopped',
        'message': 'Deployment marked as stopped'
    }