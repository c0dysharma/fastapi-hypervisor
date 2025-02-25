import os
from dotenv import load_dotenv
from sqlmodel import SQLModel, Session, create_engine

# Load environment variables from .env file
load_dotenv()

# Read database URL from .env
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./default.db")

# Create database engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def get_session():
    with Session(engine) as session:
        yield session

def init_db():
    SQLModel.metadata.create_all(engine)
