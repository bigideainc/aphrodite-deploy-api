# Aphrodite Deployment API

A deployment system for managing multiple instances of Aphrodite models using Docker containers and tunneling.

## System Overview

The system manages multiple model deployments with:
- Unique containers per deployment
- Isolated deployment directories
- Individual port assignments
- Dedicated tunnels per deployment

### Components

1. **Deployment Service**: Manages the overall deployment process
2. **Docker Service**: Handles container management
3. **Tunnel Service**: Manages ngrok/localtunnel connections
4. **Monitor Service**: Tracks deployment status

## Prerequisites

- Python 3.10+
- Docker
- Node.js and npm (for localtunnel)
- ngrok account (optional)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd aphrodite-deploy-api
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Unix
# or
.\venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Service

### Start the API Server

Start in background with nohup:
```bash
# Start the server
cd ~/tunnel_connect/aphrodite-deploy-api
source venv/bin/activate
nohup uvicorn app.main:app --reload --port 8070 > nohup.out 2>&1 &

# Check if it's running
ps aux | grep uvicorn
```

### Setup Tunneling

Using ngrok:
```bash
# Start ngrok in background
nohup ngrok http 8070 > ngrok.log 2>&1 &

# Get the public URL
tail -f ngrok.log
```

## Managing Deployments

### Deploy a New Model

Send a POST request to `/api/v1/deploy` with the configuration:
```json
{
    "model_id": "gpt2",
    "user_id": "user123",
    "api_name": "My API",
    "ssh_config": {
        "host": "your-server",
        "username": "your-username",
        "port": 22,
        "password": "your-password"
    }
}
```

### Monitor Deployments

Check deployment status:
```bash
# View API logs
tail -f nohup.out

# View running containers
docker ps

# View container logs
docker logs <container-id>
```

## Stopping Services

1. Stop the API server:
```bash
# Find the process
ps aux | grep uvicorn

# Kill it
kill <process-id>
```

2. Stop ngrok:
```bash
# Find the process
ps aux | grep ngrok

# Kill it
kill <process-id>
```

3. Stop specific containers:
```bash
# Stop a specific container
docker stop <container-id>

# Stop all Aphrodite containers
docker stop $(docker ps -q --filter name=aphrodite-)
```

## Directory Structure

Each deployment creates its own directory structure:
```
~/aphrodite-deploy-{deployment_id}/
  ├── Dockerfile
  ├── docker-compose.yml
  └── run_aphrodite.py

~/tunnel-{deployment_id}/
  ├── tunnel.log
  └── tunnel.pid
```

## Troubleshooting

1. Check API logs:
```bash
tail -f nohup.out
```

2. Check tunnel status:
```bash
tail -f ~/tunnel-*/tunnel.log
```

3. Check container status:
```bash
docker ps
docker logs <container-id>
```

4. Common issues:
   - Port conflicts: Check `docker ps` for port mappings
   - Tunnel connection: Check ngrok logs
   - Container startup: Check container logs

## Notes

- Each deployment gets a unique port in range 2242-62242
- Each container has its own unique name based on model and deployment ID
- Tunnels are managed individually per deployment
- Container and tunnel processes persist after terminal disconnect

## Support

For issues or questions, please check the logs first:
```bash
tail -f nohup.out  # API logs
tail -f ngrok.log  # Tunnel logs
docker logs <container-id>  # Container logs
```