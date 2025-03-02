# fastapi-hypervisor

A powerful resource management system for handling multiple deployments across clusters with priority-based scheduling, preemption capabilities, and efficient resource allocation.

## Introduction

fastapi-hypervisor helps you manage multiple deployments in compute clusters with advanced features:

- **Priority-based scheduling**: High priority workloads get resources first
- **Preemptive resource allocation**: Critical tasks can preempt lower priority ones
- **Resource monitoring**: Track CPU, RAM, and GPU utilization across clusters
- **Queue management**: Automatically schedule pending deployments as resources become available
- **Resilience**: Automatic retry for failed deployments and manual retry capabilities

## Setup Guide

### Prerequisites

- Python 3.11+
- Redis server (for Celery task queue)

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/c0dysharma/fastapi-hypervisor.git
   cd fastapi-hypervisor
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Configuration

Create a `.env` file in the project root with the following variables:

```
env=dev
DATABASE_URL=sqlite:///./mlops.db
REDIS_URL=redis://localhost:6379
```

### Database Setup

Initialize and migrate the database:

```bash
make migrations
make migrate
```

If you don't have make available, you can run:

```bash
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

## Running the Application

### Development Server

Start the FastAPI development server:

```bash
make run
```

Or manually:

```bash
uvicorn app.main:app --reload
```

### Production Server

For production deployment:

```bash
make run-prod
```

Or manually:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Background Workers

Start the Celery worker to process deployments:

```bash
make celery-worker
```

Start the Celery beat scheduler for periodic tasks:

```bash
make celery-beat
```

Manually:

```bash
celery -A app.celery_worker worker --loglevel=info
celery -A app.celery_worker beat --loglevel=info
```

## API Documentation

Once running, access the API documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Features

- **User & Organization Management**: Create and manage users and organizations
- **Cluster Management**: Define compute clusters with resource capacities
- **Priority-based Scheduling**: Automatically prioritize critical workloads
- **Resource Monitoring**: Track and visualize resource utilization
- **Deployment Lifecycle Management**: Handle the full lifecycle of deployment jobs

## Architecture

The system consists of:

1. **FastAPI Backend**: RESTful API for client interactions
2. **SQLModel Database**: Store users, organizations, clusters, and deployments
3. **Celery Workers**: Handle long-running deployment tasks
4. **Redis**: Message broker for Celery tasks
5. **Resource Monitor**: Track and record cluster utilization

## License

[MIT License](LICENSE)
