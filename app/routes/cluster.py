from datetime import datetime
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models import Cluster


router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


class ClusterInput(BaseModel):
    name: str
    organisation_id: str
    cpu: int
    ram: int
    gpu: int


class ClusterResponse(BaseModel):
    id: str
    name: str
    organisation_id: str
    cpu: int
    ram: int
    gpu: int


class DetailedClusterResponse(BaseModel):
    id: str
    name: str
    organisation_id: str
    cpu: int
    ram: int
    gpu: int
    used_cpu: int
    used_ram: int
    used_gpu: int
    created_at: datetime
    updated_at: Optional[datetime] = None


@router.get("/clusters",
            response_model=List[DetailedClusterResponse],
            summary="Get all clusters",
            description="Retrieve a list of all compute clusters")
def get_clusters(session: SessionDep):
    cluster = session.exec(select(Cluster)).all()
    return cluster


@router.get("/clusters/{id}",
            response_model=DetailedClusterResponse,
            summary="Get cluster by ID",
            description="Retrieve details of a specific cluster by its ID")
def get_cluster(id: str, session: SessionDep):
    cluster = session.get(Cluster, id)

    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    return cluster


@router.post("/clusters",
             response_model=ClusterResponse,
             summary="Create cluster",
             description="Create a new compute cluster with specified resources")
def create_luster(args: ClusterInput, session: SessionDep):
    cluster = Cluster(name=args.name, cpu=args.cpu, ram=args.ram,
                      gpu=args.gpu, organisation_id=args.organisation_id)
    session.add(cluster)
    session.commit()
    session.refresh(cluster)

    return ClusterResponse(
        id=cluster.id,
        name=cluster.name,
        organisation_id=cluster.organisation_id,
        cpu=cluster.cpu,
        gpu=cluster.gpu,
        ram=cluster.ram
    )
