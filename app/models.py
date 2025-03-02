from sqlalchemy import Case, event
from sqlmodel import SQLModel, Session
import uuid
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from enum import Enum
from datetime import datetime


class TimeStampModel(SQLModel):
    """
    Base model with timestamp fields.

    All models inheriting from this will automatically track:
    - When they were created
    - When they were last updated
    """
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = Field(default=None)


class User(TimeStampModel, table=True):
    """
    User model representing system users.

    Users can:
    - Belong to multiple organizations
    - Create and manage deployments
    - Authenticate with username/password
    """
    id: str = Field(default_factory=lambda: str(
        uuid.uuid4()), primary_key=True)
    # Indexed for fast lookups, must be unique
    username: str = Field(index=True, unique=True)
    password: str  # Stored as hashed value
    organisations: List["OrganisationMember"] = Relationship(
        back_populates="user")  # Many-to-many relationship with organizations
    deployments: List["Deployment"] = Relationship(
        back_populates="user")  # One-to-many relationship with deployments


class Cluster(TimeStampModel, table=True):
    """
    Cluster model representing compute resource clusters.

    Clusters:
    - Belong to one organization
    - Have defined resource capacities (CPU, RAM, GPU)
    - Track current resource utilization
    - Host multiple deployments
    """
    id: str = Field(default_factory=lambda: str(
        uuid.uuid4()), primary_key=True)
    # Foreign key to organization
    organisation_id: str = Field(foreign_key="organisation.id")
    organisation: "Organisation" = Relationship(
        back_populates="clusters")  # Many-to-one relationship with organization
    name: str  # Cluster name for identification

    # Total resource capacity
    cpu: int  # CPU cores available
    ram: int  # RAM in MB
    gpu: int  # GPU units available

    # Resource utilization tracking
    used_cpu: int = Field(default=0)  # Currently used CPU cores
    used_ram: int = Field(default=0)  # Currently used RAM in MB
    used_gpu: int = Field(default=0)  # Currently used GPU units

    # Relationship with deployments
    deployments: List["Deployment"] = Relationship(
        back_populates="cluster")  # One-to-many relationship with deployments


class Organisation(TimeStampModel, table=True):
    """
    Organization model representing groups of users.

    Organizations:
    - Have multiple members with different roles
    - Own multiple compute clusters
    - Use an invite code for member recruitment
    """
    id: str = Field(default_factory=lambda: str(
        uuid.uuid4()), primary_key=True)
    name: str  # Organization name
    invite_code: str  # Code used to invite new members
    members: List["OrganisationMember"] = Relationship(
        back_populates="organisation")  # One-to-many relationship with org members
    # One-to-many relationship with clusters
    clusters: List["Cluster"] = Relationship(back_populates="organisation")


class OrganisationMember(TimeStampModel, table=True):
    """
    Organization member model for many-to-many relationship between users and organizations.

    Represents:
    - A user's membership in an organization
    - Their role within that organization
    """
    id: str = Field(default_factory=lambda: str(
        uuid.uuid4()), primary_key=True)
    organisation_id: str = Field(
        foreign_key="organisation.id")  # Link to organization
    user_id: str = Field(foreign_key="user.id")  # Link to user
    # User's role in this organization (dev, admin, etc.)
    role: str = Field(default="dev")

    # Relationship references
    organisation: Optional[Organisation] = Relationship(
        back_populates="members")  # Many-to-one relationship with organization
    # Many-to-one relationship with user
    user: Optional[User] = Relationship(back_populates="organisations")


class DeploymentPriority(str, Enum):
    """
    Enum for deployment priority levels.

    Priority determines:
    - Order of execution when resources are limited
    - Which deployments can preempt others
    - Queue order when waiting for resources
    """
    HIGH = "high"    # Can preempt MEDIUM and LOW
    MEDIUM = "medium"  # Default priority, can preempt LOW
    LOW = "low"      # Lowest priority, may be preempted


class DeploymentStatus(str, Enum):
    """
    Enum representing the possible states of a deployment.

    The deployment lifecycle:
    - PENDING: Initial state before processing
    - QUEUED: Waiting for resources
    - RUNNING: Currently executing
    - PREEMPTED: Stopped to free resources for a higher priority task
    - FAILED: Execution failed
    - COMPLETED: Successfully finished
    """
    PENDING = "pending"     # Initial state
    QUEUED = "queued"       # Waiting for resources
    RUNNING = "running"     # Currently executing
    PREEMPTED = "preempted"  # Stopped to free resources
    FAILED = "failed"       # Execution failed
    COMPLETED = "completed"  # Successfully finished


class Deployment(TimeStampModel, table=True):
    """
    Deployment model representing a containerized workload.

    Deployments:
    - Request specific resource amounts
    - Have a priority level
    - Run on a specific cluster
    - Are created by a specific user
    - Track their execution state
    """
    id: str = Field(default_factory=lambda: str(
        uuid.uuid4()), primary_key=True)

    # Deployment metadata
    name: str  # Name of the deployment
    description: Optional[str] = None  # Optional description
    docker_image: str  # Docker image to deploy

    # Cluster association (single-cluster deployment)
    cluster_id: str = Field(foreign_key="cluster.id")  # Target cluster
    cluster: Optional[Cluster] = Relationship(
        back_populates="deployments")  # Link to cluster

    # User who created the deployment
    user_id: str = Field(foreign_key="user.id")  # Creator's user ID
    user: Optional[User] = Relationship(
        back_populates="deployments")  # Link to user

    # Priority level
    priority: DeploymentPriority = Field(
        default=DeploymentPriority.MEDIUM)  # Default to medium priority

    # Resource requirements
    requested_cpu: int  # Required CPU cores
    requested_ram: int  # Required RAM in MB
    requested_gpu: int  # Required GPU units

    # Deployment status
    status: DeploymentStatus = Field(
        default=DeploymentStatus.PENDING)  # Current execution state

    # Failure handling
    attempts: int = Field(default=0)  # Number of execution attempts
    max_attempts: int = Field(default=2)  # Max retry attempts (retry once)
    failure_reason: Optional[str] = None  # Reason for failure if applicable

    # Preemption tracking
    # Whether deployment was ever preempted
    was_preempted: bool = Field(default=False)
    preempted_count: int = Field(default=0)  # Number of times preempted

    # Timestamps
    # When the deployment started running
    started_at: Optional[datetime] = None
    # When the deployment completed/failed
    completed_at: Optional[datetime] = None


class ClusterResourceSnapshot(TimeStampModel, table=True):
    """
    Model to store historical cluster resource utilization data.

    Captures:
    - Total, used, and available resources at a point in time
    - Resource utilization percentages
    - Trends in resource usage over time

    Used for:
    - Monitoring and analytics
    - Capacity planning
    - Usage reporting
    """
    id: str = Field(default_factory=lambda: str(
        uuid.uuid4()), primary_key=True)

    # Cluster association
    # Which cluster this snapshot is for
    cluster_id: str = Field(foreign_key="cluster.id")
    cluster: Optional[Cluster] = Relationship()  # Link to cluster

    # Total resources
    total_cpu: int  # Total CPU cores in the cluster
    total_ram: int  # Total RAM in MB
    total_gpu: int  # Total GPU units

    # Used resources
    used_cpu: int  # CPU cores being used at snapshot time
    used_ram: int  # RAM in use at snapshot time
    used_gpu: int  # GPU units in use at snapshot time

    # Available resources (calculated)
    available_cpu: int  # CPU cores still available
    available_ram: int  # RAM still available
    available_gpu: int  # GPU units still available

    # Utilization percentages
    cpu_utilization: float  # Percentage of CPU used (0-100)
    ram_utilization: float  # Percentage of RAM used (0-100)
    gpu_utilization: float  # Percentage of GPU used (0-100)


# Add event listeners to update the updated_at field
@event.listens_for(Session, "before_flush")
def update_timestamps(session, flush_context, instances):
    """
    Update the updated_at timestamp for all modified entities.

    This SQLAlchemy event listener automatically sets the updated_at
    field to the current time whenever an entity is modified, ensuring
    accurate tracking of when records were last changed.
    """
    for instance in session.dirty:
        if isinstance(instance, TimeStampModel):
            if session.is_modified(instance):
                instance.updated_at = datetime.now()
