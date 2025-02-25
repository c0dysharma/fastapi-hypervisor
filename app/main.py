import sys
from fastapi import FastAPI
from contextlib import asynccontextmanager
from loguru import logger
from app.database import init_db
import os
from dotenv import load_dotenv
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

@app.get("/")
async def read_root():
    return {"message": "MLOps Hypervisor API is running!"}
