from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.ssh import SSHConfig


class DeploymentRequest(BaseModel):
    model_id: str
    user_id: str
    api_name: str
    ssh_config: SSHConfig
    host_port: Optional[int] = None  # Changed from 2242 to None to enable auto-generated ports
    auto_restart: Optional[bool] = True
    huggingface_token: Optional[str] = None

class EndpointInfo(BaseModel):
    url: str
    status: Optional[str] = "unknown"

class ContainerDetails(BaseModel):
    id: str
    model: str
    hostPort: int
    containerPort: int = 2242
    image: Optional[str] = None
    container_name: Optional[str] = None
    deployment_id: Optional[str] = None  # Added to link container to deployment

class DeploymentStatus(BaseModel):
    deployment_id: str
    status: str
    progress: int
    estimated_time: Optional[str] = None
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    host_port: Optional[int] = None  # Added to track the port used
    
class DeploymentResponse(BaseModel):
    deployment_id: str
    status: str = "queued"
    container_id: Optional[str] = None
    machine_id: Optional[str] = None
    tunnel_url: Optional[str] = None
    endpoints: Optional[Dict[str, str]] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    monitor_url: Optional[str] = None
    host_port: Optional[int] = None  # Added to return the port used

class DeploymentListResponse(BaseModel):
    deployments: List[DeploymentResponse]
    total: int
    page: int = 1
    limit: int = 10
    next_page: Optional[str] = None
    
class DeploymentMetrics(BaseModel):
    cpu_usage: Optional[float] = None
    memory_usage: Optional[str] = None
    memory_percent: Optional[float] = None
    uptime: Optional[str] = None
    requests_served: Optional[int] = None
    average_response_time: Optional[float] = None
    last_accessed: Optional[datetime] = None
    
class DeploymentDetail(BaseModel):
    deployment_id: str
    user_id: str
    model_id: str
    api_name: str
    status: str
    container_details: Optional[ContainerDetails] = None
    machine_id: Optional[str] = None
    endpoints: Optional[Dict[str, str]] = None
    tunnel_url: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    deployment_duration: Optional[float] = None
    metrics: Optional[DeploymentMetrics] = None
    error: Optional[str] = None
    host_port: Optional[int] = None  # Added to display the port used    error: Optional[str] = None
    host_port: Optional[int] = None  # Added to display the port used