import os
from dotenv import load_dotenv
from celery import Celery

load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
celery = Celery(
    "mlops-hypervisor",
    backend=redis_url,
    broker=redis_url
)

@celery.task
def test_task():
    return "Celery is working!"
