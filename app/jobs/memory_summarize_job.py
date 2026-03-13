import logging
from app.jobs.celery_app import celery_app

logger = logging.getLogger("saib.jobs.memory_summarize")

@celery_app.task(name="app.jobs.memory_summarize_job.summarize_session")
def summarize_session(session_id: str):
    logger.info("summarize_session session_id=%s (stub)", session_id)
    return {"status": "stub", "session_id": session_id}
