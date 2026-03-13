import logging
from app.jobs.celery_app import celery_app

logger = logging.getLogger("saib.jobs.health_check")

@celery_app.task(name="app.jobs.health_check_job.check_all_models")
def check_all_models():
    logger.info("health_check triggered (stub)")
    return {"status": "stub"}
