from sqlalchemy import Case, event
from sqlmodel import SQLModel, Session
import uuid
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from enum import Enum
from datetime import datetime


class TimeStampModel(SQLModel):
    """Base model with timestamp fields."""
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default=None)


class User(TimeStampModel, table=True):
    id: str = Field(default_factory=lambda: str(
        uuid.uuid4()), primary_key=True)
    username: str = Field(index=True, unique=True)
    password: str
    organisations: List["OrganisationMember"] = Relationship(
        back_populates="user")
    deployments: List["Deployment"] = Relationship(back_populates="user")


class Cluster(TimeStampModel, table=True):
    id: str = Field(default_factory=lambda: str(
        uuid.uuid4()), primary_key=True)
    organisation_id: str = Field(foreign_key="organisation.id")
    organisation: "Organisation" = Relationship(
        back_populates="clusters")
    name: str
    cpu: int
    ram: int
    gpu: int

    # Used resources
    used_cpu: int = Field(default=0)
    used_ram: int = Field(default=0)
    used_gpu: int = Field(default=0)
    deployments: List["Deployment"] = Relationship(back_populates="cluster")


class Organisation(TimeStampModel, table=True):
    id: str = Field(default_factory=lambda: str(
        uuid.uuid4()), primary_key=True)
    name: str
    invite_code: str
    members: List["OrganisationMember"] = Relationship(
        back_populates="organisation")
    clusters: List["Cluster"] = Relationship(back_populates="organisation")


class OrganisationMember(TimeStampModel, table=True):
    id: str = Field(default_factory=lambda: str(
        uuid.uuid4()), primary_key=True)
    organisation_id: str = Field(foreign_key="organisation.id")
    user_id: str = Field(foreign_key="user.id")
    role: str = Field(default="dev")
    organisation: Optional[Organisation] = Relationship(
        back_populates="members")
    user: Optional[User] = Relationship(back_populates="organisations")


class DeploymentPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DeploymentStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PREEMPTED = "preempted"
    FAILED = "failed"
    COMPLETED = "completed"


class Deployment(TimeStampModel, table=True):
    id: str = Field(default_factory=lambda: str(
        uuid.uuid4()), primary_key=True)

    # Deployment metadata
    name: str
    description: Optional[str] = None

    docker_image: str

    # Cluster association (single-cluster deployment)
    cluster_id: str = Field(foreign_key="cluster.id")
    cluster: Optional[Cluster] = Relationship(back_populates="deployments")

    # User who created the deployment
    user_id: str = Field(foreign_key="user.id")
    user: Optional[User] = Relationship(back_populates="deployments")

    # Priority level
    priority: DeploymentPriority = Field(default=DeploymentPriority.MEDIUM)

    # Resource requirements
    requested_cpu: int
    requested_ram: int
    requested_gpu: int

    # Deployment status
    status: DeploymentStatus = Field(default=DeploymentStatus.PENDING)

    # Failure handling
    attempts: int = Field(default=0)
    max_attempts: int = Field(default=2)  # As per requirement: retry once
    failure_reason: Optional[str] = None

    # Preemption tracking
    was_preempted: bool = Field(default=False)
    preempted_count: int = Field(default=0)

    # Timestamps
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ClusterResourceSnapshot(TimeStampModel, table=True):
    """Model to store historical cluster resource utilization data."""
    id: str = Field(default_factory=lambda: str(
        uuid.uuid4()), primary_key=True)

    # Cluster association
    cluster_id: str = Field(foreign_key="cluster.id")
    cluster: Optional[Cluster] = Relationship()

    # Total resources
    total_cpu: int
    total_ram: int
    total_gpu: int

    # Used resources
    used_cpu: int
    used_ram: int
    used_gpu: int

    # Available resources (calculated)
    available_cpu: int
    available_ram: int
    available_gpu: int

    # Utilization percentages
    cpu_utilization: float  # Percentage (0-100)
    ram_utilization: float
    gpu_utilization: float


# Add event listeners to update the updated_at field
@event.listens_for(Session, "before_flush")
def update_timestamps(session, flush_context, instances):
    """Update the updated_at timestamp for all modified entities."""
    for instance in session.dirty:
        if isinstance(instance, TimeStampModel):
            if session.is_modified(instance):
                instance.updated_at = datetime.now()
