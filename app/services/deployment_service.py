import asyncio
import logging

from app.models.deployment import DeploymentRequest
from app.services.ssh_service import connect_ssh, ensure_dependencies
from app.services.docker_service import setup_container, monitor_container_startup
from app.services.tunnel_service import setup_tunnel
from app.db.firebase import db

logger = logging.getLogger("deployment-service")

async def deploy_model(deployment_id: str, request: DeploymentRequest):
    try:
        logger.info(f"Starting deployment {deployment_id} for model {request.model_id}")
        
        if db:
            from firebase_admin import firestore
            db.collection('deployments').document(deployment_id).update({
                'status': 'deploying'
            })
        
        ssh_client = None
        try:
            ssh_client = connect_ssh(
                hostname=request.ssh_config.host,
                username=request.ssh_config.username,
                port=request.ssh_config.port,
                password=request.ssh_config.password,
                key_filename=request.ssh_config.key_file
            )
            
            stdin, stdout, stderr = ssh_client.exec_command("cat /etc/machine-id || hostname")
            machine_id = stdout.read().decode('utf-8').strip()
            logger.info(f"Machine ID: {machine_id}")
            
            if db:
                db.collection('deployments').document(deployment_id).update({
                    'machineId': machine_id
                })
            
            await ensure_dependencies(ssh_client, request.ssh_config.password)
            
            container_id = await setup_container(
                ssh_client=ssh_client,
                model_id=request.model_id,
                user_id=request.user_id,
                host_port=request.host_port,
                huggingface_token=request.huggingface_token
            )
            
            if db and container_id:
                db.collection('deployments').document(deployment_id).update({
                    'containerId': container_id,
                    'status': 'starting'
                })
            
            endpoints = await monitor_container_startup(ssh_client, container_id)
            
            safe_api_name = request.api_name.lower().replace(" ", "-")
            subdomain = f"{safe_api_name}-{request.user_id}"
            tunnel_url = await setup_tunnel(ssh_client, request.host_port, subdomain)
            
            mapped_endpoints = {}
            for key, local_url in endpoints.items():
                if local_url and local_url.startswith("http://localhost"):
                    if tunnel_url:
                        path = local_url.split(':', 2)[2]
                        if path.startswith('/'):
                            path = path[1:]
                        mapped_endpoints[key] = f"{tunnel_url}/{path}"
                else:
                    mapped_endpoints[key] = local_url
            
            deployment_data = {
                'userId': request.user_id,
                'modelId': request.model_id,
                'apiName': request.api_name,
                'containerId': container_id,
                'machineId': machine_id,
                'containerPort': request.host_port,
                'tunnelUrl': tunnel_url,
                'endpoints': mapped_endpoints,
                'status': 'active',
            }
            
            if db:
                from firebase_admin import firestore
                deployment_data['updatedAt'] = firestore.SERVER_TIMESTAMP
                db.collection('deployments').document(deployment_id).update(deployment_data)
                logger.info(f"Updated deployment {deployment_id} with endpoints")
            
            logger.info(f"Deployment {deployment_id} completed successfully")
            
        except Exception as e:
            error_msg = f"Deployment failed: {str(e)}"
            logger.error(error_msg)
            if db:
                db.collection('deployments').document(deployment_id).update({
                    'status': 'failed',
                    'error': error_msg
                })
        finally:
            if ssh_client:
                ssh_client.close()
            
    except Exception as e:
        logger.error(f"Unhandled error in deploy_model: {str(e)}")
        if db:
            db.collection('deployments').document(deployment_id).update({
                'status': 'failed',
                'error': f"Unhandled error: {str(e)}"
            })