from typing import Annotated, Optional, Dict
from app.database import get_session
from sqlmodel import Session
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.helper import get_cluster_resource_utilization

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]


class ResourceUsage(BaseModel):
    cpu: int
    ram: int
    gpu: int


class ClusterResources(BaseModel):
    total_resources: ResourceUsage
    used_resources: ResourceUsage


@router.get("/resources",
            response_model=Dict[str, ClusterResources],
            summary="Get resource utilization",
            description="Get current resource utilization for all clusters")
def get_resources():
    return get_cluster_resource_utilization()
