import asyncio
import hashlib
import logging
from datetime import datetime

import firebase_admin
from firebase_admin import firestore

from app.db.firebase import db
from app.models.deployment import DeploymentRequest
from app.services.docker_service import (monitor_container_startup,
                                         setup_container)
from app.services.ssh_service import connect_ssh, ensure_dependencies
from app.services.tunnel_service import (setup_tunnel,
                                         verify_localtunnel_installation)

logger = logging.getLogger("deployment-service")

async def deploy_model(deployment_id: str, request: DeploymentRequest):
    """
    Background task to deploy the model with proper error handling and state management
    """
    start_time = datetime.now()
    
    # Generate a unique port for this deployment
    hash_object = hashlib.md5(deployment_id.encode())
    hash_int = int(hash_object.hexdigest(), 16)
    unique_port = 2242 + (hash_int % 60000)  # Range: 2242-62242 (avoiding system reserved ports)
    
    # Use the configured host port from request if available, otherwise use the unique port
    host_port = request.host_port or unique_port
    
    try:
        logger.info(f"Starting deployment {deployment_id} for model {request.model_id} on port {host_port}")
        
        # Update status to in-progress
        if db:
            db.collection('deployments').document(deployment_id).update({
                'status': 'deploying',
                'hostPort': host_port  # Store the port in the deployment document
            })
        
        # Connect to SSH
        ssh_client = None
        try:
            ssh_client = connect_ssh(
                hostname=request.ssh_config.host,
                username=request.ssh_config.username,
                port=request.ssh_config.port,
                password=request.ssh_config.password,
                key_filename=request.ssh_config.key_file
            )
            
            # Get machine ID
            stdin, stdout, stderr = ssh_client.exec_command("cat /etc/machine-id || hostname")
            machine_id = stdout.read().decode('utf-8').strip()
            logger.info(f"Machine ID: {machine_id}")
            
            # Update deployment with machine ID
            if db:
                db.collection('deployments').document(deployment_id).update({
                    'machineId': machine_id
                })
            
            # Ensure dependencies (Node.js, localtunnel)
            await ensure_dependencies(ssh_client, request.ssh_config.password)
            
            # Setup container with deployment_id for unique naming
            container_id = await setup_container(
                ssh_client=ssh_client,
                model_id=request.model_id,
                user_id=request.user_id,
                host_port=host_port,
                huggingface_token=request.huggingface_token,
                deployment_id=deployment_id  # Pass deployment_id for unique container naming
            )
            
            # Update deployment with container ID
            if db and container_id:
                db.collection('deployments').document(deployment_id).update({
                    'containerId': container_id,
                    'status': 'starting'
                })
            
            # Monitor container startup with dynamic port handling
            endpoints = await monitor_container_startup(
                ssh_client, 
                container_id, 
                host_port
            )
            
            # Verify localtunnel installation
            lt_installed = await verify_localtunnel_installation(
                ssh_client, 
                request.ssh_config.password
            )
            
            # Setup tunnel with improved error handling
            safe_api_name = request.api_name.lower().replace(" ", "-")
            subdomain = f"{safe_api_name}-{deployment_id[:8]}"  # Using part of deployment_id for uniqueness
            tunnel_url = await setup_tunnel(
                ssh_client, 
                host_port, 
                subdomain, 
                request.ssh_config.password
            )
            
            # Map local endpoints to tunnel URLs
            mapped_endpoints = {}
            for key, local_url in endpoints.items():
                if local_url and local_url.startswith("http://localhost"):
                    if tunnel_url:
                        # Extract the port and path from local URL
                        parts = local_url.split("localhost:")
                        if len(parts) >= 2:
                            port_and_path = parts[1]
                            # Extract path part after port
                            path_parts = port_and_path.split("/", 1)
                            if len(path_parts) > 1:
                                path = path_parts[1]
                                mapped_endpoints[key] = f"{tunnel_url.rstrip('/')}/{path}"
                            else:
                                mapped_endpoints[key] = tunnel_url
                        else:
                            mapped_endpoints[key] = tunnel_url
                    else:
                        # If tunnel setup failed, use the local URL
                        mapped_endpoints[key] = local_url
                else:
                    mapped_endpoints[key] = local_url
            
            # Prepare deployment data update
            deployment_data = {
                'userId': request.user_id,
                'modelId': request.model_id,
                'apiName': request.api_name,
                'containerId': container_id,
                'machineId': machine_id,
                'containerPort': host_port,  # Now using the unique host port
                'tunnelUrl': tunnel_url,
                'localEndpoints': endpoints,
                'endpoints': mapped_endpoints,
                'status': 'active',
            }
            
            # Update deployment in Firebase
            if db:
                deployment_data['updatedAt'] = firestore.SERVER_TIMESTAMP
                
                # Ensure we save detailed information about tunnel and endpoints
                if tunnel_url:
                    deployment_data['tunnelUrl'] = tunnel_url
                
                # Save both local and mapped endpoints for reference
                deployment_data['localEndpoints'] = endpoints
                deployment_data['endpoints'] = mapped_endpoints
                
                # Save container and model details
                deployment_data['containerDetails'] = {
                    'id': container_id,
                    'model': request.model_id,
                    'hostPort': host_port,  # Using the unique host port
                    'containerPort': 2242
                }
                
                # Additional metadata
                deployment_data['deploymentCompleted'] = firestore.SERVER_TIMESTAMP
                deployment_data['deploymentDuration'] = (datetime.now() - start_time).total_seconds()
                
                # Update the document
                db.collection('deployments').document(deployment_id).update(deployment_data)
                logger.info(f"Updated deployment {deployment_id} with complete details including tunnel URL: {tunnel_url}")
            
            logger.info(f"Deployment {deployment_id} completed successfully on port {host_port}")
            
        except Exception as e:
            error_msg = f"Deployment failed: {str(e)}"
            logger.error(error_msg)
            if db:
                error_data = {
                    'status': 'failed',
                    'error': error_msg,
                    'failedAt': firestore.SERVER_TIMESTAMP,
                    'deploymentDuration': (datetime.now() - start_time).total_seconds(),
                    'updatedAt': firestore.SERVER_TIMESTAMP
                }
                # If we have container info, add it
                if 'container_id' in locals() and container_id:
                    error_data['containerId'] = container_id
                    error_data['containerStatus'] = 'error'
                
                # If we have machine info, add it
                if 'machine_id' in locals() and machine_id:
                    error_data['machineId'] = machine_id
                
                db.collection('deployments').document(deployment_id).update(error_data)
        finally:
            if ssh_client:
                ssh_client.close()
            
    except Exception as e:
        logger.error(f"Unhandled error in deploy_model: {str(e)}")
        if db:
            db.collection('deployments').document(deployment_id).update({
                'status': 'failed',
                'error': f"Unhandled deployment error: {str(e)}",
                'failedAt': firestore.SERVER_TIMESTAMP,
                'deploymentDuration': (datetime.now() - start_time).total_seconds(),
                'updatedAt': firestore.SERVER_TIMESTAMP
            })