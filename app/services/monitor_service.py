# app/services/monitor_service.py

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import httpx

# Import Firebase db from your existing initialization
from app.db.firebase import db

logger = logging.getLogger("monitor-service")

async def monitor_deployments():
    """
    Monitor all deployments that are in polling state
    and update their status in Firebase
    """
    logger.info("Starting deployment monitoring...")
    
    try:
        # Query all deployments that are in 'queued' or other non-final states and have isPolling=true
        monitor_ref = db.collection('monitor')
        query = monitor_ref.where('isPolling', '==', True)
        docs = query.stream()
        
        deployments = list(docs)
        if not deployments:
            logger.info("No deployments to monitor.")
            return
        
        logger.info(f"Found {len(deployments)} deployments to monitor.")
        
        # Process each deployment using asyncio
        tasks = []
        for doc in deployments:
            deployment = doc.to_dict()
            deployment_id = doc.id
            tasks.append(check_deployment_status(doc.reference, deployment_id, deployment))
        
        # Wait for all tasks to complete
        if tasks:
            await asyncio.gather(*tasks)
        
        logger.info("Deployment monitoring completed.")
        
    except Exception as e:
        logger.exception(f"Error in deployment monitoring: {str(e)}")


async def check_deployment_status(doc_ref, deployment_id: str, deployment: Dict[str, Any]):
    """
    Check the status of a single deployment and update its status in Firebase
    """
    logger.info(f"Checking status for deployment {deployment_id} ({deployment.get('modelId')})...")
    
    try:
        # Extract the deployment ID from the monitor URL
        monitor_url = deployment.get('monitorUrl')
        if not monitor_url:
            logger.error(f"Missing monitor URL for deployment {deployment_id}")
            await update_deployment_status(doc_ref, {
                'isPolling': False,
                'errorMessage': 'Missing monitor URL',
                'updatedAt': datetime.now().isoformat()
            })
            return
        
        # Extract the deployment ID from the URL
        import re
        url_match = re.search(r'/deployments/([^/]+)/status', monitor_url)
        if not url_match:
            logger.error(f"Invalid monitor URL format: {monitor_url}")
            await update_deployment_status(doc_ref, {
                'isPolling': False,
                'errorMessage': 'Invalid monitor URL format',
                'updatedAt': datetime.now().isoformat()
            })
            return
        
        api_deployment_id = url_match.group(1)
        
        # Make request to the deployment status endpoint
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'DeploymentMonitorService/1.0',  # Custom user agent
                'Cache-Control': 'no-cache'
            }
            
            logger.info(f"Requesting status from: {monitor_url}")
            response = await client.get(monitor_url, headers=headers)
            
            # Check if response is successful
            if response.status_code != 200:
                logger.error(f"Error response {response.status_code} for deployment {deployment_id}")
                await update_deployment_status(doc_ref, {
                    'lastErrorMessage': f"HTTP Error: {response.status_code}",
                    'updatedAt': datetime.now().isoformat()
                })
                return
            
            # Parse response data
            data = response.json()
            logger.info(f"Received status for deployment {deployment_id}: {data.get('status')}")
            
            # Prepare update data
            from firebase_admin import firestore
            update_data = {
                'status': data.get('status'),
                'progress': data.get('progress', 0),
                'updatedAt': firestore.SERVER_TIMESTAMP
            }
            
            # Add tunnel URL if it exists
            if 'tunnel_url' in data:
                update_data['tunnelUrl'] = data['tunnel_url']
            
            # Add endpoints if they exist
            if 'endpoints' in data:
                update_data['endpoints'] = data['endpoints']
            
            # Add deployment completion info if active
            if data.get('status') == 'active' and 'deployment_completed' in data:
                update_data['deploymentCompleted'] = data['deployment_completed']
                update_data['deploymentDuration'] = data['deployment_duration']
                update_data['isPolling'] = False  # Stop polling once active
            
            # If status is 'failed', stop polling
            if data.get('status') == 'failed':
                update_data['isPolling'] = False
                update_data['errorMessage'] = data.get('error', 'Deployment failed')
            
            # Update the document
            await update_deployment_status(doc_ref, update_data)
            
    except Exception as e:
        logger.exception(f"Error monitoring deployment {deployment_id}: {str(e)}")
        
        # Don't change polling status yet, will retry on next run
        await update_deployment_status(doc_ref, {
            'lastErrorMessage': str(e),
            'updatedAt': datetime.now().isoformat()
        })


async def update_deployment_status(doc_ref, update_data: Dict[str, Any]):
    """
    Update a deployment status in Firebase
    """
    try:
        doc_ref.update(update_data)
        logger.info(f"Updated deployment {doc_ref.id}")
    except Exception as e:
        logger.exception(f"Error updating deployment {doc_ref.id}: {str(e)}")


async def start_monitor_scheduler(interval_seconds=5):
    """
    Start a scheduler to monitor deployments at regular intervals
    """
    logger.info(f"Starting deployment monitor scheduler (interval: {interval_seconds}s)...")
    
    while True:
        try:
            await monitor_deployments()
        except Exception as e:
            logger.exception(f"Error in monitoring run: {str(e)}")
        
        # Sleep for the specified interval
        await asyncio.sleep(interval_seconds)