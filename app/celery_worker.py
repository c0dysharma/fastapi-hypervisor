from app.clients.celery import celery
from app.models import Deployment, DeploymentStatus, ClusterResourceSnapshot
from app.helper import (
    get_cluster_resource_utilization,
    get_priority_case,
    check_deployment_resources,
    try_preemption,
    execute_preemption,
    execute_deployment
)
from app.clients.celery import celery_control
from app.database import engine, Session
from sqlalchemy import select, desc

# Configure periodic tasks that Celery Beat will schedule and run
# These tasks run automatically at specified intervals
celery.conf.beat_schedule = {
    'capture-resource-utilization': {
        'task': 'app.celery_worker.capture_resource_utilization',
        'schedule': 300.0,  # Every 5 minutes (300 seconds)
    },
}
celery.conf.timezone = 'UTC'  # Use UTC for consistent timestamps across environments


@celery.task
def test_task():
    """Simple task to verify Celery is working correctly."""
    return "Celery is working!"


@celery.task(bind=True)
def process_deployment(self, deployment_id: str):
    """
    Process a deployment request, handling resource allocation and execution.

    This is the main task that orchestrates the deployment workflow:
    1. Checks if there are sufficient cluster resources
    2. Attempts to preempt lower-priority deployments if needed
    3. Queues the deployment if resources aren't available
    4. Executes the deployment when resources are available
    5. Triggers checking of queued deployments after completion

    Args:
        deployment_id: The UUID of the deployment to process

    Returns:
        str: A message describing the result of the deployment process
    """
    with Session(engine) as session:
        # Retrieve the deployment from the database
        deployment = session.get(Deployment, deployment_id)
        if not deployment:
            return "Deployment not found."

        # Get current resource state for the target cluster
        cluster_resources = get_cluster_resource_utilization().get(deployment.cluster_id)
        if not cluster_resources:
            # Mark the deployment as failed if the cluster doesn't exist
            deployment.status = DeploymentStatus.FAILED
            deployment.failure_reason = "Cluster not found or no resources available"
            session.add(deployment)
            session.commit()
            return "Cluster not found."

        # Check if there are enough resources for immediate deployment
        has_resources, available_cpu, available_ram, available_gpu = check_deployment_resources(
            deployment, cluster_resources)

        if has_resources:
            # If resources are available, deploy immediately
            print(
                f"Sufficient resources available. Deploying {deployment_id}...")
            deployment.status = DeploymentStatus.RUNNING
            session.add(deployment)
            session.commit()

        else:
            # If resources aren't available, try preemption strategy
            # This attempts to free resources by stopping lower-priority deployments
            preemption_success, preemptible_deployments = try_preemption(
                deployment, available_cpu, available_ram, available_gpu)

            if preemption_success:
                # Execute preemption if enough lower-priority deployments were found
                execute_preemption(preemptible_deployments, session)

                # Now deploy our task since resources have been freed
                deployment.status = DeploymentStatus.RUNNING
                session.add(deployment)
                session.commit()

            else:
                # Queue the deployment if preemption wasn't possible/sufficient
                print(
                    f"Not enough resources even after potential preemption. Queueing {deployment_id}...")
                deployment.status = DeploymentStatus.QUEUED
                session.add(deployment)
                session.commit()
                return "Deployment queued due to insufficient resources."

        # Execute the deployment (or simulation in development)
        result = execute_deployment(deployment, session)

        # After successful deployment, check if any queued deployments can now run
        # This ensures efficient resource utilization by starting queued tasks
        # as soon as resources become available
        check_queued_deployments.apply_async()

        return result


@celery.task
def check_queued_deployments():
    """
    Check if any queued deployments can now be executed.

    This task is triggered:
    1. After a successful deployment completes
    2. After a deployment is canceled
    3. Periodically via Celery Beat

    It processes queued deployments in order of priority and creation time.
    """
    with Session(engine) as session:
        # Query for queued deployments, ordered by:
        # 1. Priority (high to low)
        # 2. Creation time (oldest first)
        statement = select(Deployment.id).where(
            Deployment.status == DeploymentStatus.QUEUED
        ).order_by(
            # Order by priority (high to low)
            desc(get_priority_case()),
            # Then by creation time (oldest first)
            Deployment.created_at
        )

        # Extract just the IDs from the query results
        deployment_ids = [id[0] for id in session.exec(statement).all()]

        print(f"Found {len(deployment_ids)} queued deployments to process")

        # Process each deployment in priority order
        for deployment_id in deployment_ids:
            # Schedule processing for this deployment
            # Using the deployment_id as the task_id ensures we can later
            # revoke this task if needed during preemption
            process_deployment.apply_async(
                args=[deployment_id],
                task_id=deployment_id  # Use the deployment_id directly as the task_id
            )
            print(f"Re-scheduling queued deployment {deployment_id}")


@celery.task
def capture_resource_utilization():
    """
    Capture current cluster resource utilization and store it in the database.

    This task runs periodically (every 5 minutes) to:
    1. Record the current resource state of all clusters
    2. Store utilization metrics for monitoring and analytics
    3. Enable historical trending and capacity planning

    The data can be used for:
    - Visualization dashboards
    - Resource optimization
    - Alerting on high utilization
    - Capacity planning
    """
    # Get the current resource utilization for all clusters
    cluster_resources = get_cluster_resource_utilization()

    with Session(engine) as session:
        # For each cluster, create a snapshot record
        for cluster_id, resources in cluster_resources.items():
            # Extract resource values from the utilization data
            total_cpu = resources["total_resources"]["cpu"]
            total_ram = resources["total_resources"]["ram"]
            total_gpu = resources["total_resources"]["gpu"]

            used_cpu = resources["used_resources"]["cpu"]
            used_ram = resources["used_resources"]["ram"]
            used_gpu = resources["used_resources"]["gpu"]

            # Calculate available resources (with safety floor at 0)
            available_cpu = max(0, total_cpu - used_cpu)
            available_ram = max(0, total_ram - used_ram)
            available_gpu = max(0, total_gpu - used_gpu)

            # Calculate utilization percentages with division-by-zero protection
            cpu_utilization = (used_cpu / total_cpu *
                               100) if total_cpu > 0 else 0
            ram_utilization = (used_ram / total_ram *
                               100) if total_ram > 0 else 0
            gpu_utilization = (used_gpu / total_gpu *
                               100) if total_gpu > 0 else 0

            # Create and save the resource snapshot in the database
            snapshot = ClusterResourceSnapshot(
                cluster_id=cluster_id,
                total_cpu=total_cpu,
                total_ram=total_ram,
                total_gpu=total_gpu,
                used_cpu=used_cpu,
                used_ram=used_ram,
                used_gpu=used_gpu,
                available_cpu=available_cpu,
                available_ram=available_ram,
                available_gpu=available_gpu,
                cpu_utilization=round(cpu_utilization, 2),
                ram_utilization=round(ram_utilization, 2),
                gpu_utilization=round(gpu_utilization, 2)
            )

            session.add(snapshot)

        # Commit all snapshots at once for better performance
        session.commit()

    return f"Captured resource utilization for {len(cluster_resources)} clusters"
