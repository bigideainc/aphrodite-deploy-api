import asyncio
import logging
import os
import re

logger = logging.getLogger("tunnel-service")

async def verify_localtunnel_installation(ssh_client, password=None):
    """Verify and fix localtunnel installation if needed"""
    stdin, stdout, stderr = ssh_client.exec_command("which lt")
    exit_status = stdout.channel.recv_exit_status()
    
    if exit_status != 0:
        logger.warning("Localtunnel not found, attempting to install globally...")
        sudo_prefix = f"echo '{password}' | sudo -S " if password else "sudo "
        
        # Make sure npm is installed
        stdin, stdout, stderr = ssh_client.exec_command("which npm")
        if stdout.channel.recv_exit_status() != 0:
            logger.warning("npm not found, installing nodejs and npm...")
            install_cmd = f"{sudo_prefix}apt-get update && {sudo_prefix}apt-get install -y nodejs npm"
            stdin, stdout, stderr = ssh_client.exec_command(install_cmd)
            if stdout.channel.recv_exit_status() != 0:
                logger.error("Failed to install nodejs and npm")
                return False
            await asyncio.sleep(2)
        
        # Install localtunnel globally
        install_cmd = f"{sudo_prefix}npm install -g localtunnel"
        stdin, stdout, stderr = ssh_client.exec_command(install_cmd)
        if stdout.channel.recv_exit_status() != 0:
            logger.error("Failed to install localtunnel")
            return False
        await asyncio.sleep(2)
    
    return True

async def setup_tunnel(ssh_client, host_port: int, subdomain: str, password=None, deployment_id: str = None):
    """Set up localtunnel with deployment-specific management"""
    logger.info(f"Setting up tunnel with subdomain: {subdomain}...")
    
    if not deployment_id:
        deployment_id = subdomain.split('-')[-1]  # Fallback to extract from subdomain
    
    # Create deployment-specific directory
    tunnel_dir = f"~/tunnel-{deployment_id}"
    ssh_client.exec_command(f"mkdir -p {tunnel_dir}")
    
    # Verify and fix lt installation
    lt_installed = await verify_localtunnel_installation(ssh_client, password)
    if not lt_installed:
        logger.error("Failed to verify localtunnel installation")
        return None
    
    # Kill any existing tunnel for this specific port
    ssh_client.exec_command(f"pkill -f 'lt --port {host_port}' || true")
    
    # Start tunnel with deployment-specific logging
    tunnel_log = f"{tunnel_dir}/tunnel.log"
    tunnel_pid = f"{tunnel_dir}/tunnel.pid"
    tunnel_command = f"""
    cd {tunnel_dir} && 
    lt --port {host_port} --subdomain {subdomain} > {tunnel_log} 2>&1 & 
    echo $! > {tunnel_pid}
    """
    
    stdin, stdout, stderr = ssh_client.exec_command(tunnel_command)
    if stdout.channel.recv_exit_status() != 0:
        logger.error("Failed to start tunnel process")
        return None
    
    # Wait for tunnel to start and get URL
    max_retries = 3
    for attempt in range(max_retries):
        await asyncio.sleep(5)  # Give tunnel time to start
        
        # Check if process is running
        stdin, stdout, stderr = ssh_client.exec_command(f"cat {tunnel_pid} && ps -p $(cat {tunnel_pid})")
        if stdout.channel.recv_exit_status() != 0:
            logger.warning(f"Tunnel process not running on attempt {attempt + 1}")
            continue
        
        # Check tunnel log for URL
        stdin, stdout, stderr = ssh_client.exec_command(f"cat {tunnel_log}")
        log_content = stdout.read().decode('utf-8')
        
        url_match = re.search(r'your url is: (https://[^\s]+)', log_content)
        if url_match:
            tunnel_url = url_match.group(1)
            logger.info(f"Tunnel URL for deployment {deployment_id}: {tunnel_url}")
            
            # Verify tunnel is responding
            check_cmd = f"curl -s -o /dev/null -w '%{{http_code}}' {tunnel_url}"
            stdin, stdout, stderr = ssh_client.exec_command(check_cmd)
            status_code = stdout.read().decode('utf-8').strip()
            
            if status_code.startswith('2') or status_code.startswith('3'):
                return tunnel_url
            else:
                logger.warning(f"Tunnel URL returned status {status_code}")
        
        if attempt < max_retries - 1:
            # Kill existing tunnel and retry
            ssh_client.exec_command(f"pkill -f 'lt --port {host_port}' || true")
            await asyncio.sleep(2)
    
    logger.error(f"Failed to establish tunnel for deployment {deployment_id} after {max_retries} attempts")
    return None