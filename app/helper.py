from datetime import datetime
import time
from sqlalchemy import Case
from sqlmodel import select
from app.database import Session, engine
from app.models import Cluster, Deployment, DeploymentStatus
from app.clients.celery import celery_control


# Priority mapping for deployment scheduling
# Higher numbers represent higher priority levels
PRIORITY_MAP = {
    "low": 0,
    "medium": 1,
    "high": 2
}
# medium priority is the default when priority is unspecified
DEFAULT_PRIORITY_VALUE = 1


def get_priority_case():
    """Return a Case expression for priority ordering"""
    return Case(
        PRIORITY_MAP,
        value=Deployment.priority,
        else_=DEFAULT_PRIORITY_VALUE
    )


def get_priority_value(priority: str):
    """
    Convert a priority to its numeric value for comparison.

    This handles different formats of priority values:
    - String values ("high", "medium", "low")
    - Enum values (DeploymentPriority.HIGH)
    - None values (defaults to medium priority)

    Returns the numeric priority value for comparison operations.
    """
    if priority is None:
        return DEFAULT_PRIORITY_VALUE

    # Convert to string if it's not already
    if not isinstance(priority, str):
        priority = str(priority)

    # Handle enum representation
    if "." in priority:
        parts = priority.split(".")
        if len(parts) > 1:
            priority = parts[1].split(":")[0]

    priority_lower = priority.lower()
    return PRIORITY_MAP.get(priority_lower, DEFAULT_PRIORITY_VALUE)


def get_cluster_resource_utilization():
    """
    Calculate and return current resource utilization for all clusters.

    This function:
    1. Retrieves all clusters from the database
    2. For each cluster, finds all running and completed deployments
    3. Calculates total resource usage (CPU, RAM, GPU)
    4. Returns a structured dictionary with utilization data

    The resulting data is used for:
    - Making deployment decisions
    - Resource monitoring
    - Historical data collection

    Returns:
        dict: A dictionary with cluster_id as keys and resource information as values
    """
    result = {}

    with Session(engine) as session:
        # Get all clusters
        clusters = session.exec(select(Cluster)).all()

        for cluster in clusters:
            # Query deployments that are RUNNING or COMPLETED for this cluster
            statement = select(Deployment).where(
                (Deployment.cluster_id == cluster.id) &
                (Deployment.status.in_(
                    [DeploymentStatus.RUNNING, DeploymentStatus.COMPLETED]))
            )
            deployments = session.exec(statement).all()

            # Calculate used resources
            used_cpu = sum(d.requested_cpu for d in deployments)
            used_ram = sum(d.requested_ram for d in deployments)
            used_gpu = sum(d.requested_gpu for d in deployments)

            # Add to result dictionary
            result[cluster.id] = {
                "total_resources": {
                    "cpu": cluster.cpu,
                    "ram": cluster.ram,
                    "gpu": cluster.gpu
                },
                "used_resources": {
                    "cpu": used_cpu,
                    "ram": used_ram,
                    "gpu": used_gpu
                }
            }

    return result


def find_lower_priority_running_deployments(priority: str):
    """
    Find deployments with lower priority than the given one that are currently running.

    This function is critical for the preemption system, which allows higher priority
    deployments to take resources from lower priority ones when resources are scarce.

    The function:
    1. Gets all running deployments
    2. Filters them by priority (lower than the input priority)
    3. Sorts them by priority (lowest first) for optimal preemption

    Returns:
        List of Deployment objects with lower priority than the input priority
    """
    # Get the numeric value of the input priority
    input_priority_value = get_priority_value(priority)
    print(f"Input priority: {priority}, value: {input_priority_value}")

    with Session(engine) as session:
        # Get all running deployments
        all_running = session.exec(select(Deployment).where(
            Deployment.status == DeploymentStatus.RUNNING
        )).all()

        print(f"All running deployments ({len(all_running)}):")

        # Filter for lower priority deployments in Python
        result = []
        for d in all_running:
            priority_val = get_priority_value(d.priority)
            print(
                f"  ID: {d.id}, Priority: {d.priority}, Value: {priority_val}")

            # Only include if strictly lower priority
            if priority_val < input_priority_value:
                result.append(d)

        # Sort by priority (lowest first)
        result.sort(key=lambda d: get_priority_value(d.priority))

        print(f"Found {len(result)} lower priority deployments")
        for d in result:
            priority_val = get_priority_value(d.priority)
            print(
                f"  ID: {d.id}, Priority: {d.priority}, Value: {priority_val}")

        return result


def check_deployment_resources(deployment: Deployment, cluster_resources: dict):
    """
    Check if there are enough resources for a deployment.

    This is the core function for determining if a deployment can run immediately
    or needs to be queued/preempted. It compares the deployment's resource
    requirements with the cluster's available resources.

    Args:
        deployment: Deployment object with resource requirements
        cluster_resources: Resource information dictionary for the target cluster

    Returns:
        tuple: (has_resources, available_cpu, available_ram, available_gpu)
    """
    if not cluster_resources:
        return False, 0, 0, 0

    # Calculate available resources
    available_cpu = cluster_resources["total_resources"]["cpu"] - \
        cluster_resources["used_resources"]["cpu"]
    available_ram = cluster_resources["total_resources"]["ram"] - \
        cluster_resources["used_resources"]["ram"]
    available_gpu = cluster_resources["total_resources"]["gpu"] - \
        cluster_resources["used_resources"]["gpu"]

    # Check if we have enough resources
    cpu_needed = deployment.requested_cpu
    ram_needed = deployment.requested_ram
    gpu_needed = deployment.requested_gpu

    has_resources = (available_cpu >= cpu_needed and
                     available_ram >= ram_needed and
                     available_gpu >= gpu_needed)

    return has_resources, available_cpu, available_ram, available_gpu


def try_preemption(deployment: Deployment, available_cpu: int, available_ram: int, available_gpu: int):
    """
    Try to preempt lower priority deployments to free resources.

    This function implements the preemption algorithm:
    1. Find lower priority deployments that could be stopped
    2. Calculate how many resources would be freed by stopping them
    3. Determine if enough resources could be freed to run the new deployment

    The algorithm is greedy, taking the lowest priority deployments first
    until enough resources are available.

    Args:
        deployment: Deployment that needs resources
        available_cpu: Currently available CPU
        available_ram: Currently available RAM
        available_gpu: Currently available GPU

    Returns:
        tuple: (preemption_success, preemptible_deployments)
    """
    # Get resource requirements
    cpu_needed = deployment.requested_cpu
    ram_needed = deployment.requested_ram
    gpu_needed = deployment.requested_gpu

    # Find lower priority deployments
    lower_priority_deployments = find_lower_priority_running_deployments(
        deployment.priority)

    # Calculate resources that could be freed by preemption
    potential_cpu = available_cpu
    potential_ram = available_ram
    potential_gpu = available_gpu

    preemptible_deployments = []

    # Find deployments we could preempt to free enough resources
    for lpd in lower_priority_deployments:
        potential_cpu += lpd.requested_cpu
        potential_ram += lpd.requested_ram
        potential_gpu += lpd.requested_gpu
        preemptible_deployments.append(lpd)

        # Check if we have enough resources after this preemption
        if (potential_cpu >= cpu_needed and
            potential_ram >= ram_needed and
                potential_gpu >= gpu_needed):
            break

    # Check if preempting would give us enough resources
    preemption_success = (potential_cpu >= cpu_needed and
                          potential_ram >= ram_needed and
                          potential_gpu >= gpu_needed)

    return preemption_success, preemptible_deployments


def execute_preemption(preemptible_deployments: list[Deployment], session: Session):
    """
    Preempt deployments to free resources.

    This function actually performs the preemption:
    1. Sends revoke signals to the Celery tasks to stop them
    2. Updates the database status of preempted deployments
    3. Tracks preemption counts for analysis

    The preemption is forceful (terminate=True) to free resources immediately.

    Args:
        preemptible_deployments: List of deployments to preempt
        session: SQLModel session
    """
    print(
        f"Preempting {len(preemptible_deployments)} deployments to free resources...")

    # Preempt deployments
    for lpd in preemptible_deployments:
        # Stop the deployment task
        celery_control.revoke(lpd.id, terminate=True)

        # Update its status
        lpd.status = DeploymentStatus.PREEMPTED
        lpd.was_preempted = True
        lpd.preempted_count += 1
        session.add(lpd)

    session.commit()


def execute_deployment(deployment: Deployment, session: Session, simulation: bool = True):
    """
    Execute the deployment (or simulate it).

    In production, this would launch the actual container/workload.
    For development, it simulates the deployment with timeouts.

    The function handles:
    1. Actual deployment execution
    2. Status updates
    3. Error handling and retries

    Args:
        deployment: Deployment to execute
        session: SQLModel session
        simulation: Whether to run a simulation instead of the actual deployment

    Returns:
        str: Message about deployment completion
    """
    try:
        if simulation:
            # Simulate deployment
            n = 10
            for i in range(n):
                print(f"Deploying {deployment.id}... {i+1}/{n}")
                time.sleep(20)  # Simulating work
        else:
            # Actual deployment logic would go here
            pass

        # Mark as completed
        deployment.status = DeploymentStatus.COMPLETED
        deployment.completed_at = datetime.now()  # Set completion timestamp
        session.add(deployment)
        session.commit()

        return "Deployment completed."

    except Exception as e:
        return handle_deployment_failure(deployment, session, e)


def handle_deployment_failure(deployment: Deployment, session: Session, exception: Exception):
    """
    Handle a deployment failure.
    """
    from app.celery_worker import process_deployment  # Import here to avoid circular imports

    deployment.status = DeploymentStatus.FAILED
    deployment.failure_reason = str(exception)
    deployment.attempts += 1

    if deployment.attempts < deployment.max_attempts:
        # Retry the deployment
        session.add(deployment)
        session.commit()

        process_deployment.apply_async(
            args=[deployment.id],
            countdown=10,  # Wait 10 seconds before retry
            task_id=f"{deployment.id}-retry-{deployment.attempts}"
        )

        return f"Deployment failed, scheduling retry {deployment.attempts}/{deployment.max_attempts}"
    else:
        session.add(deployment)
        session.commit()
        return f"Deployment failed after {deployment.attempts} attempts: {str(exception)}"
