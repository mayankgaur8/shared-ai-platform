import logging
from app.jobs.celery_app import celery_app

logger = logging.getLogger("saib.jobs.usage_aggregation")

@celery_app.task(name="app.jobs.usage_aggregation_job.aggregate_usage")
def aggregate_usage():
    logger.info("usage_aggregation triggered (stub)")
    return {"status": "stub"}
