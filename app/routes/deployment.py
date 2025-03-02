from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models import Cluster, Deployment, DeploymentStatus
from app.celery_worker import process_deployment


router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


class DeploymentInput(BaseModel):
    name: str
    docker_image: str
    description: Optional[str] = None
    cluster_id: str
    user_id: str
    priority: Optional[str] = None

    requested_cpu: int
    requested_ram: int
    requested_gpu: int


@router.post("/deployments")
def create_deployment(args: DeploymentInput, session: SessionDep):
    cluster = session.exec(select(Cluster).where(
        Cluster.id == args.cluster_id)).first()
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")

    deployment = Deployment(
        name=args.name,
        docker_image=args.docker_image,
        description=args.description,
        cluster_id=cluster.id,
        user_id=args.user_id,
        priority=args.priority,
        requested_cpu=args.requested_cpu,
        requested_ram=args.requested_ram,
        requested_gpu=args.requested_gpu
    )
    session.add(deployment)
    session.commit()
    session.refresh(deployment)

    # queue the task for deployment
    process_deployment.apply_async(
        args=[deployment.id], task_id=deployment.id)

    result = {
        "id": deployment.id,
        "name": deployment.name,
        "description": deployment.description,
        "cluster_id": deployment.cluster_id,
        "user_id": deployment.user_id,
        "priority": deployment.priority,
        "requested_cpu": deployment.requested_cpu,
        "requested_ram": deployment.requested_ram,
        "requested_gpu": deployment.requested_gpu
    }

    return result


@router.get("/deployments")
def get_deployments(session: SessionDep):
    deployments = session.exec(select(Deployment)).all()

    return deployments


@router.get(f"/deployments/{id}")
def get_one_deployment(dep_id: str, session: SessionDep):
    deployment = session.exec(select(Deployment).where(
        Deployment.id == dep_id)).first()
    if not deployment:
        raise HTTPException(
            status_code=404, detail="deployment not found")

    return deployment


@router.get("/deployments/{dep_id}/retry")
def retry_deployment(dep_id: str, session: SessionDep):
    """
    Retry a deployment that was previously preempted, queued, or failed.

    This endpoint allows users to manually trigger a retry for deployments
    that didn't complete successfully. It will:
    1. Verify the deployment exists and is in a retryable state
    2. Reset necessary status fields
    3. Queue the deployment for execution

    Returns the updated deployment information.
    """
    # Find the deployment
    deployment = session.exec(select(Deployment).where(
        Deployment.id == dep_id)).first()

    if not deployment:
        raise HTTPException(
            status_code=404, detail="Deployment not found")

    # Check if deployment is in a retryable state
    retryable_statuses = [
        DeploymentStatus.PREEMPTED,
        DeploymentStatus.QUEUED,
        DeploymentStatus.FAILED
    ]

    if deployment.status not in retryable_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Only deployments with status {[s.value for s in retryable_statuses]} can be retried. Current status: {deployment.status}"
        )

    # Reset deployment status and counters as needed
    deployment.status = DeploymentStatus.PENDING
    deployment.attempts = 0  # Reset attempts counter
    deployment.failure_reason = None  # Clear any failure messages

    # Save changes
    session.add(deployment)
    session.commit()
    session.refresh(deployment)

    # Queue the task for deployment
    process_deployment.apply_async(
        args=[deployment.id], task_id=deployment.id)

    return {
        "id": deployment.id,
        "name": deployment.name,
        "status": deployment.status,
        "message": "Deployment queued for retry"
    }
