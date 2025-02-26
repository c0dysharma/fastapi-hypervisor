import os
import sys
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from loguru import logger

from app.database import init_db
from app.routes.user import router as user_router
from app.routes.organisation import router as organisation_router
from app.routes.organisation_member import router as organisation_member_router

load_dotenv()

ENV = os.getenv("env", "dev")  # Default to "dev" if not set

# Configure Loguru
log_out_path = sys.stdout
if ENV != "dev":
    log_out_path = "app.log"

logger.remove()  # Remove the default logger
logger.add(log_out_path, colorize=True, level="INFO")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Initializing database...")
    init_db()  # Initialize database on startup
    yield
    print("Shutting down...")

app = FastAPI(lifespan=lifespan)

# Include the router
app.include_router(user_router)
app.include_router(organisation_router)
app.include_router(organisation_member_router)


@app.get("/")
async def read_root():
    return {"message": "MLOps Hypervisor API is running!"}
