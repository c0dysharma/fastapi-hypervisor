import os
import sys
from dotenv import load_dotenv
from fastapi import FastAPI
from loguru import logger

# Importing all models to ensure they are registered with SQLModel
from app.models import *

# Importing routers for different API endpoints
from app.routes.user import router as user_router
from app.routes.organisation import router as organisation_router
from app.routes.organisation_member import router as organisation_member_router
from app.routes.cluster import router as cluster_router
from app.routes.deployment import router as deployment_router
from app.routes.resource import router as resource_router

# Load environment variables from a .env file
load_dotenv()

# Get the environment setting, default to "dev" if not set
ENV = os.getenv("env", "dev")

# Configure Loguru for logging
log_out_path = sys.stdout  # Default to standard output
if ENV != "dev":
    log_out_path = "app.log"  # Log to a file in non-dev environments

logger.remove()  # Remove the default logger
# Add a new logger with the specified output and level
logger.add(log_out_path, colorize=True, level="INFO")

# Create a FastAPI application instance
app = FastAPI()

# Include the routers for different API endpoints
app.include_router(user_router)
app.include_router(organisation_router)
app.include_router(organisation_member_router)
app.include_router(cluster_router)
app.include_router(deployment_router)
app.include_router(resource_router)

# Define a root endpoint for the API


@app.get("/")
async def read_root():
    return {"message": "MLOps Hypervisor API is running!"}
