import asyncio
import logging
import re

logger = logging.getLogger("tunnel-service")

async def setup_tunnel(ssh_client, host_port: int, subdomain: str):
    logger.info(f"Setting up tunnel with subdomain: {subdomain}...")
    
    ssh_client.exec_command("pkill -f 'lt --port'")
    
    tunnel_command = f"nohup lt --port {host_port} --subdomain {subdomain} > ~/tunnel.log 2>&1 &"
    ssh_client.exec_command(tunnel_command)
    
    await asyncio.sleep(5)
    
    stdin, stdout, stderr = ssh_client.exec_command("cat ~/tunnel.log")
    log_content = stdout.read().decode('utf-8')
    
    url_match = re.search(r'your url is: (https://[^\s]+)', log_content)
    if url_match:
        tunnel_url = url_match.group(1)
        logger.info(f"Tunnel URL: {tunnel_url}")
        return tunnel_url
    else:
        logger.warning("Failed to extract tunnel URL from log")
        return None