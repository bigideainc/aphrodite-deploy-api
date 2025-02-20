import paramiko
import asyncio
import logging
from typing import Optional

logger = logging.getLogger("ssh-service")

def connect_ssh(hostname: str, username: str, port: int = 22, 
                password: Optional[str] = None, key_filename: Optional[str] = None):
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    connect_kwargs = {
        'hostname': hostname,
        'username': username,
        'port': port
    }
    
    if password:
        connect_kwargs['password'] = password
    elif key_filename:
        connect_kwargs['key_filename'] = key_filename
    
    logger.info(f"Connecting to {hostname}...")
    ssh_client.connect(**connect_kwargs)
    return ssh_client

async def ensure_dependencies(ssh_client, password: Optional[str] = None):
    sudo_prefix = f"echo '{password}' | sudo -S " if password else "sudo "
    
    stdin, stdout, stderr = ssh_client.exec_command("which node")
    node_installed = stdout.channel.recv_exit_status() == 0
    
    stdin, stdout, stderr = ssh_client.exec_command("which lt")
    lt_installed = stdout.channel.recv_exit_status() == 0
    
    if not node_installed:
        logger.info("Installing Node.js...")
        stdin, stdout, stderr = ssh_client.exec_command(
            f"{sudo_prefix}apt-get update && {sudo_prefix}apt-get install -y nodejs npm"
        )
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            error_msg = stderr.read().decode('utf-8')
            raise Exception(f"Failed to install Node.js: {error_msg}")
        await asyncio.sleep(2)
    
    if not lt_installed:
        logger.info("Installing localtunnel...")
        stdin, stdout, stderr = ssh_client.exec_command(
            f"{sudo_prefix}npm install -g localtunnel"
        )
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            error_msg = stderr.read().decode('utf-8')
            raise Exception(f"Failed to install localtunnel: {error_msg}")
        await asyncio.sleep(2)
    
    logger.info("Dependencies check completed")