import os
from dotenv import load_dotenv
from celery import Celery
from celery.app.control import Control


load_dotenv()

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
celery = Celery(
    "mlops-hypervisor",
    backend=redis_url,
    broker=redis_url
)


celery_control = Control(app=celery)
