#!/usr/bin/env python3
import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("API_PORT", 9090)),
        reload=os.getenv("DEBUG", "False").lower() == "true"
    )
