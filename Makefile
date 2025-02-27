# Load environment variables from .env
include .env
export $(shell sed 's/=.*//' .env)

# Declare phony targets
.PHONY: run run-prod install update-requirements celery-worker celery-beat migrations migrate

# =============== 🚀 FASTAPI SERVER ===============
run:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-prod:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --log-level info

# =============== 🐍 VIRTUAL ENV ===============
install:
	python -m venv venv && source venv/bin/activate && pip install -r requirements.txt

# =============== 📦 DEPENDENCIES ===============
update-requirements:
	pip freeze > requirements.txt

# =============== 🔄 CELERY WORKER ===============
celery-worker:
	celery -A app.celery_worker worker --loglevel=info

celery-beat:
	celery -A app.celery_worker beat --loglevel=info

# =============== 🗃️ DATABASE MIGRATIONS ===============
migrations:
	alembic revision --autogenerate

migrate:
	alembic upgrade head