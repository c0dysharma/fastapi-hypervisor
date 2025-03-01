from typing import Annotated, Optional
from app.database import get_session
from sqlmodel import Session
from fastapi import APIRouter, Depends, HTTPException

from app.helper import get_cluster_resource_utilization

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/resources")
def get_resources():
    return get_cluster_resource_utilization()
