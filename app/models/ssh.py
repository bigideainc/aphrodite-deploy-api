from pydantic import BaseModel
from typing import Optional

class SSHConfig(BaseModel):
    host: str
    username: str
    port: int = 22
    password: Optional[str] = None
    key_file: Optional[str] = None