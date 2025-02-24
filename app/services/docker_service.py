import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger("docker-service")

async def setup_deployment_files(ssh_client, deployment_id: str, host_port: int = 2242):
    """Setup deployment files in a unique directory for each deployment"""
    deployment_dir = f"~/aphrodite-deploy-{deployment_id}"
    logger.info(f"Setting up deployment directory at {deployment_dir}...")
    
    # Create unique directory
    ssh_client.exec_command(f"mkdir -p {deployment_dir}")
    
    dockerfile_content = """FROM python:3.10-slim

# Install git and curl
RUN apt-get update && \\
    apt-get install -y git curl && \\
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Clone aphrodite-engine repo
RUN git clone https://github.com/PygmalionAI/aphrodite-engine.git /app

# Set environment variables
ENV APHRODITE_TARGET_DEVICE=openvino
ENV APHRODITE_OPENVINO_KVCACHE_SPACE=8
ENV PIP_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu
ENV HF_HOME=/root/.cache/huggingface

# Create cache directory
RUN mkdir -p /root/.cache/huggingface/hub

# Install dependencies
RUN pip install --no-cache-dir -r requirements-openvino.txt && \\
    pip install --no-cache-dir -e .

# Copy the entrypoint script
COPY run_aphrodite.py /app/run_aphrodite.py
RUN chmod +x /app/run_aphrodite.py

# Expose the port used by the Aphrodite server
EXPOSE 2242

# Set entrypoint
ENTRYPOINT ["python", "/app/run_aphrodite.py"]"""
    
    stdin, stdout, stderr = ssh_client.exec_command(f"cat > {deployment_dir}/Dockerfile << 'EOF'\n{dockerfile_content}\nEOF")
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        raise Exception(f"Failed to create Dockerfile in {deployment_dir}")
    
    docker_compose_content = f"""version: '3.8'

services:
  aphrodite-engine:
    build:
      context: .
      dockerfile: Dockerfile
    image: aphrodite-engine-${{MODEL_ID:-gpt2}}
    container_name: aphrodite-${{MODEL_ID:-gpt2}}-${{DEPLOYMENT_ID}}
    ports:
      - "{host_port}:2242"
    environment:
      - MODEL_ID=${{MODEL_ID:-gpt2}}
      - HUGGINGFACE_TOKEN=${{HUGGINGFACE_TOKEN}}
      - APHRODITE_OPENVINO_KVCACHE_SPACE=8
      - HF_HOME=/root/.cache/huggingface
    volumes:
      - huggingface-cache:/root/.cache/huggingface
    restart: unless-stopped

volumes:
  huggingface-cache:
    name: huggingface-cache-${{DEPLOYMENT_ID}}"""
    
    stdin, stdout, stderr = ssh_client.exec_command(f"cat > {deployment_dir}/docker-compose.yml << 'EOF'\n{docker_compose_content}\nEOF")
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        raise Exception(f"Failed to create docker-compose.yml in {deployment_dir}")
    
    run_script_content = """#!/usr/bin/env python3
import os
import subprocess
import sys

def ensure_huggingface_cache_dir():
    hf_cache_dir = "/root/.cache/huggingface/hub"
    os.makedirs(hf_cache_dir, exist_ok=True)
    print(f"Ensured directory exists: {hf_cache_dir}")

def run_aphrodite():
    model_id = os.environ.get("MODEL_ID", "gpt2")
    cmd = ["aphrodite", "run", "--device", "openvino", "--host", "0.0.0.0", model_id]
    print("Running command:", " ".join(cmd))
    
    env = os.environ.copy()
    env["APHRODITE_OPENVINO_KVCACHE_SPACE"] = os.environ.get("APHRODITE_OPENVINO_KVCACHE_SPACE", "8")
    
    subprocess.check_call(cmd, env=env)

def main():
    huggingface_token = os.environ.get("HUGGINGFACE_TOKEN")
    if huggingface_token:
        os.environ["HUGGINGFACE_TOKEN"] = huggingface_token
        print("Hugging Face token is set.")
    
    print("Detected device: cpu (using OpenVINO backend)")
    ensure_huggingface_cache_dir()
    run_aphrodite()

if __name__ == "__main__":
    main()"""
    
    stdin, stdout, stderr = ssh_client.exec_command(f"cat > {deployment_dir}/run_aphrodite.py << 'EOF'\n{run_script_content}\nEOF")
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        raise Exception(f"Failed to create run_aphrodite.py in {deployment_dir}")
    
    ssh_client.exec_command(f"chmod +x {deployment_dir}/run_aphrodite.py")
    logger.info(f"Deployment files created successfully in {deployment_dir}")
    return deployment_dir

async def setup_container(ssh_client, model_id: str, user_id: str, 
                        host_port: int = 2242, huggingface_token: Optional[str] = None,
                        deployment_id: Optional[str] = None):
    """
    Setup and launch a container with persistent naming based on deployment_id
    """
    if not deployment_id:
        raise ValueError("deployment_id is required for container setup")
    
    # Create deployment directory with unique files
    deployment_dir = await setup_deployment_files(ssh_client, deployment_id, host_port)
    
    logger.info(f"Launching container for model {model_id} on port {host_port}...")
    
    # Sanitize model_id for Docker naming conventions
    original_model_id = model_id
    safe_model_id = model_id.lower().replace("/", "-")
    
    # Create unique and persistent names
    container_name = f"aphrodite-{safe_model_id}-{deployment_id}"
    image_name = f"aphrodite-engine-{safe_model_id}"
    
    env_vars = {
        "MODEL_ID": original_model_id,
        "HOST_PORT": str(host_port),
        "USER_ID": user_id,
        "DEPLOYMENT_ID": deployment_id,
        "HUGGINGFACE_TOKEN": huggingface_token or ""
    }
    
    # Launch the container using the unique deployment directory
    env_string = " ".join([f"{k}={v}" for k, v in env_vars.items()])
    launch_command = f"cd {deployment_dir} && {env_string} docker-compose up -d --build"
    
    stdin, stdout, stderr = ssh_client.exec_command(launch_command)
    exit_status = stdout.channel.recv_exit_status()
    stderr_output = stderr.read().decode('utf-8')
    
    if exit_status != 0 or "Error" in stderr_output:
        error_msg = f"Error launching container: {stderr_output}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    # Get the container ID
    stdin, stdout, stderr = ssh_client.exec_command(
        f"docker ps --filter name={container_name} --format '{{{{.ID}}}}'"
    )
    container_id = stdout.read().decode('utf-8').strip()
    
    if not container_id:
        error_msg = f"Failed to get container ID for {container_name}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    logger.info(f"Container {container_name} (ID: {container_id}) launched successfully on port {host_port}")
    return container_id

async def monitor_container_startup(ssh_client, container_id: str, host_port: int = 2242, timeout: int = 600):
    """
    Monitor container logs with improved endpoint extraction.
    Uses a longer timeout and better error handling.
    """
    logger.info(f"Monitoring container {container_id} startup with port {host_port}...")
    
    # First try with log following (real-time)
    log_command = f"docker logs -f {container_id}"
    stdin, stdout, stderr = ssh_client.exec_command(log_command)
    
    endpoints = {}
    startup_complete = False
    start_time = datetime.now()
    
    # Port patterns to check
    port_patterns = [
        f"http://0.0.0.0:{host_port}/",
        f"http://localhost:{host_port}/",
        r"http://0.0.0.0:\d+/",
        r"http://localhost:\d+/"
    ]
    
    while not startup_complete and (datetime.now() - start_time).total_seconds() < timeout:
        if stdout.channel.recv_ready():
            line = stdout.channel.recv(1024).decode('utf-8')
            
            # Check for base URL with dynamic port detection
            for pattern in port_patterns:
                if re.search(pattern, line):
                    # Extract actual port from the line
                    port_match = re.search(r"http://[^:]+:(\d+)/", line)
                    actual_port = port_match.group(1) if port_match else str(host_port)
                    endpoints["base_url"] = f"http://localhost:{actual_port}/"
                    break
            
            # Dynamic endpoint pattern dictionary
            endpoint_patterns = {
                "ui": r"Kobold Lite UI:\s+(http://[^:]+:(\d+)/?)",
                "docs": r"Documentation:\s+(http://[^:]+:(\d+)/redoc)",
                "completions": r"Completions API:\s+(http://[^:]+:(\d+)/v1/completions)",
                "chat": r"Chat API:\s+(http://[^:]+:(\d+)/v1/chat/completions)",
                "embeddings": r"Embeddings API:\s+(http://[^:]+:(\d+)/v1/embeddings)",
                "tokenization": r"Tokenization API:\s+(http://[^:]+:(\d+)/v1/tokenize)"
            }
            
            for key, pattern in endpoint_patterns.items():
                match = re.search(pattern, line)
                if match:
                    # Replace the host with localhost
                    endpoints[key] = match.group(1).replace("0.0.0.0", "localhost")
                    # Extract the actual port for default endpoints
                    if "actual_port" not in locals():
                        actual_port = match.group(2)
            
            if "Application startup complete" in line:
                startup_complete = True
                break
            
            # Also detect if all endpoints have been found
            if len(endpoints) >= 6:  # We expect 6 endpoints
                startup_complete = True
                break
        
        await asyncio.sleep(0.1)
    
    stdout.channel.close()
    
    # If we didn't get all endpoints, try fetching the entire log
    if not startup_complete or len(endpoints) < 6:
        logger.info("Trying to extract endpoints from complete logs...")
        stdin, stdout, stderr = ssh_client.exec_command(f"docker logs {container_id}")
        full_logs = stdout.read().decode('utf-8')
        
        # Try to detect the actual port first
        actual_port = str(host_port)
        for pattern in port_patterns:
            port_match = re.search(pattern, full_logs)
            if port_match:
                port_extract = re.search(r"http://[^:]+:(\d+)/", port_match.group(0))
                if port_extract:
                    actual_port = port_extract.group(1)
                    break
        
        # Set base_url if not already set
        if "base_url" not in endpoints:
            endpoints["base_url"] = f"http://localhost:{actual_port}/"
        
        # Try to find missing endpoints in the full logs
        for key, pattern in endpoint_patterns.items():
            if key not in endpoints:
                match = re.search(pattern, full_logs)
                if match:
                    endpoints[key] = match.group(1).replace("0.0.0.0", "localhost")
        
        if "Application startup complete" in full_logs:
            startup_complete = True
    
    # Last resort - if container is running but we don't have endpoints,
    # use default endpoints based on port
    if len(endpoints) == 0 or "base_url" not in endpoints:
        stdin, stdout, stderr = ssh_client.exec_command(f"docker inspect -f '{{{{.State.Running}}}}' {container_id}")
        is_running = stdout.read().decode('utf-8').strip() == "true"
        
        if is_running:
            # Try to find the actual mapped port
            stdin, stdout, stderr = ssh_client.exec_command(
                f"docker port {container_id} | grep -m 1 '0.0.0.0' | cut -d ':' -f 2"
            )
            detected_port = stdout.read().decode('utf-8').strip()
            actual_port = detected_port if detected_port else str(host_port)
            
            logger.warning(f"Using default endpoint configuration with port {actual_port}")
            endpoints = {
                "base_url": f"http://localhost:{actual_port}/",
                "ui": f"http://localhost:{actual_port}/",
                "docs": f"http://localhost:{actual_port}/redoc",
                "completions": f"http://localhost:{actual_port}/v1/completions",
                "chat": f"http://localhost:{actual_port}/v1/chat/completions",
                "embeddings": f"http://localhost:{actual_port}/v1/embeddings",
                "tokenization": f"http://localhost:{actual_port}/v1/tokenize"
            }
            startup_complete = True
    
    if not startup_complete:
        logger.warning(f"Container startup monitoring timed out after {timeout} seconds")
        
        # Check container status for debugging
        stdin, stdout, stderr = ssh_client.exec_command(f"docker inspect {container_id}")
        container_info = stdout.read().decode('utf-8')
        logger.info(f"Container inspection: {container_info[:500]}...")
    
    return endpoints