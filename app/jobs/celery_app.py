"""
Celery application instance.
Broker and backend default to REDIS_URL when CELERY_BROKER_URL is not set.
"""
from celery import Celery
from app.config.settings import get_settings

settings = get_settings()

broker = settings.CELERY_BROKER_URL or settings.REDIS_URL
backend = settings.CELERY_RESULT_BACKEND or settings.REDIS_URL

celery_app = Celery(
    "saib",
    broker=broker,
    backend=backend,
    include=[
        "app.jobs.embedding_job",
        "app.jobs.usage_aggregation_job",
        "app.jobs.memory_summarize_job",
        "app.jobs.health_check_job",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "usage-aggregation-hourly": {
            "task": "app.jobs.usage_aggregation_job.aggregate_usage",
            "schedule": 3600.0,  # every hour
        },
        "model-health-check": {
            "task": "app.jobs.health_check_job.check_all_models",
            "schedule": 60.0,   # every minute
        },
    },
)
