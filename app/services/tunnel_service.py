import asyncio
import logging
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
        
        # Verify installation
        stdin, stdout, stderr = ssh_client.exec_command("which lt")
        if stdout.channel.recv_exit_status() != 0:
            logger.error("Localtunnel installation verification failed")
            return False
    
    return True

async def setup_tunnel(ssh_client, host_port: int, subdomain: str, password=None):
    """Set up localtunnel with better error handling and fallback options"""
    logger.info(f"Setting up tunnel with subdomain: {subdomain}...")
    
    # Verify and fix lt installation
    lt_installed = await verify_localtunnel_installation(ssh_client, password)
    if not lt_installed:
        # Fallback to direct IP address if tunnel can't be set up
        stdin, stdout, stderr = ssh_client.exec_command("curl -s ifconfig.me || curl -s icanhazip.com || hostname -I | awk '{print $1}'")
        public_ip = stdout.read().decode('utf-8').strip()
        if public_ip:
            logger.info(f"Using direct IP address as fallback: {public_ip}")
            return f"http://{public_ip}:{host_port}"
        else:
            logger.error("Failed to get public IP address")
            return None
    
    # Kill any existing localtunnel processes
    ssh_client.exec_command("pkill -f 'lt --port' || true")
    
    # Try with subdomain
    tunnel_command = f"nohup lt --port {host_port} --subdomain {subdomain} > ~/tunnel.log 2>&1 &"
    ssh_client.exec_command(tunnel_command)
    
    # Give localtunnel time to start
    await asyncio.sleep(8)
    
    # Check if tunnel was created successfully
    stdin, stdout, stderr = ssh_client.exec_command("cat ~/tunnel.log")
    log_content = stdout.read().decode('utf-8')
    
    url_match = re.search(r'your url is: (https://[^\s]+)', log_content)
    if url_match:
        tunnel_url = url_match.group(1)
        logger.info(f"Tunnel URL: {tunnel_url}")
        return tunnel_url
    
    # If subdomain fails, try without specifying subdomain
    logger.warning("Failed to create tunnel with specified subdomain, trying without subdomain...")
    ssh_client.exec_command("pkill -f 'lt --port' || true")
    tunnel_command = f"nohup lt --port {host_port} > ~/tunnel2.log 2>&1 &"
    ssh_client.exec_command(tunnel_command)
    
    await asyncio.sleep(8)
    
    stdin, stdout, stderr = ssh_client.exec_command("cat ~/tunnel2.log")
    log_content = stdout.read().decode('utf-8')
    
    url_match = re.search(r'your url is: (https://[^\s]+)', log_content)
    if url_match:
        tunnel_url = url_match.group(1)
        logger.info(f"Tunnel URL (without subdomain): {tunnel_url}")
        return tunnel_url
        
    # Last resort: direct IP
    logger.warning("Failed to extract tunnel URL from log, using direct IP address as fallback")
    stdin, stdout, stderr = ssh_client.exec_command("curl -s ifconfig.me || curl -s icanhazip.com || hostname -I | awk '{print $1}'")
    public_ip = stdout.read().decode('utf-8').strip()
    if public_ip:
        logger.info(f"Using direct IP address as fallback: {public_ip}")
        return f"http://{public_ip}:{host_port}"
    
    logger.error("All tunnel creation attempts failed")
    return None