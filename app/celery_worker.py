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

# Set up the periodic task schedule
celery.conf.beat_schedule = {
    'capture-resource-utilization': {
        'task': 'app.celery_worker.capture_resource_utilization',
        'schedule': 20.0,  # Every 5 minutes (300 seconds)
    },
}
celery.conf.timezone = 'UTC'


@celery.task
def test_task():
    return "Celery is working!"


@celery.task(bind=True)
def process_deployment(self, deployment_id: str):
    """
    Process a deployment request, handling resource allocation and execution.
    """
    with Session(engine) as session:
        # Get the deployment
        deployment = session.get(Deployment, deployment_id)
        if not deployment:
            return "Deployment not found."

        # Get cluster resources
        cluster_resources = get_cluster_resource_utilization().get(deployment.cluster_id)
        if not cluster_resources:
            deployment.status = DeploymentStatus.FAILED
            deployment.failure_reason = "Cluster not found or no resources available"
            session.add(deployment)
            session.commit()
            return "Cluster not found."

        # Check resources
        has_resources, available_cpu, available_ram, available_gpu = check_deployment_resources(
            deployment, cluster_resources)

        if has_resources:
            # Deploy immediately if we have resources
            print(
                f"Sufficient resources available. Deploying {deployment_id}...")
            deployment.status = DeploymentStatus.RUNNING
            session.add(deployment)
            session.commit()

        else:
            # Try preemption if we don't have enough resources
            preemption_success, preemptible_deployments = try_preemption(
                deployment, available_cpu, available_ram, available_gpu)

            if preemption_success:
                # Execute preemption
                execute_preemption(preemptible_deployments, session)

                # Now deploy our task
                deployment.status = DeploymentStatus.RUNNING
                session.add(deployment)
                session.commit()

            else:
                # Queue if we can't free enough resources
                print(
                    f"Not enough resources even after potential preemption. Queueing {deployment_id}...")
                deployment.status = DeploymentStatus.QUEUED
                session.add(deployment)
                session.commit()
                return "Deployment queued due to insufficient resources."

        # Execute the deployment
        result = execute_deployment(deployment, session)

        # After successful deployment, check if any queued deployments can now run
        check_queued_deployments.apply_async()

        return result


@celery.task
def check_queued_deployments():
    """Check if any queued deployments can now be executed."""
    with Session(engine) as session:
        # First get IDs in the right order
        statement = select(Deployment.id).where(
            Deployment.status == DeploymentStatus.QUEUED
        ).order_by(
            # Order by priority (high to low)
            desc(get_priority_case()),
            # Then by creation time (oldest first)
            Deployment.created_at
        )

        deployment_ids = [id[0] for id in session.exec(statement).all()]

        print(f"Found {len(deployment_ids)} queued deployments to process")

        # Process each deployment
        for deployment_id in deployment_ids:
            # Schedule processing for this deployment using the deployment ID as the task ID
            process_deployment.apply_async(
                args=[deployment_id],
                task_id=deployment_id  # Use the deployment_id directly as the task_id
            )
            print(f"Re-scheduling queued deployment {deployment_id}")


@celery.task
def capture_resource_utilization():
    """
    Capture current cluster resource utilization and store it in the database.
    Runs every 5 minutes.
    """
    # Get the current resource utilization
    cluster_resources = get_cluster_resource_utilization()

    with Session(engine) as session:
        # For each cluster, create a snapshot record
        for cluster_id, resources in cluster_resources.items():
            # Get the total and used resources
            total_cpu = resources["total_resources"]["cpu"]
            total_ram = resources["total_resources"]["ram"]
            total_gpu = resources["total_resources"]["gpu"]

            used_cpu = resources["used_resources"]["cpu"]
            used_ram = resources["used_resources"]["ram"]
            used_gpu = resources["used_resources"]["gpu"]

            # Calculate available resources
            available_cpu = max(0, total_cpu - used_cpu)
            available_ram = max(0, total_ram - used_ram)
            available_gpu = max(0, total_gpu - used_gpu)

            # Calculate utilization percentages (avoid division by zero)
            cpu_utilization = (used_cpu / total_cpu *
                               100) if total_cpu > 0 else 0
            ram_utilization = (used_ram / total_ram *
                               100) if total_ram > 0 else 0
            gpu_utilization = (used_gpu / total_gpu *
                               100) if total_gpu > 0 else 0

            # Create and save the snapshot
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

        # Commit all snapshots at once
        session.commit()

    return f"Captured resource utilization for {len(cluster_resources)} clusters"
