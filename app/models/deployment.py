from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

from app.models.ssh import SSHConfig

class DeploymentRequest(BaseModel):
    model_id: str
    user_id: str
    api_name: str
    ssh_config: SSHConfig
    host_port: Optional[int] = 2242
    auto_restart: Optional[bool] = True
    huggingface_token: Optional[str] = None

class EndpointInfo(BaseModel):
    url: str
    status: Optional[str] = "unknown"

class DeploymentResponse(BaseModel):
    deployment_id: str
    status: str = "queued"
    container_id: Optional[str] = None
    machine_id: Optional[str] = None
    tunnel_url: Optional[str] = None
    endpoints: Optional[Dict[str, str]] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())