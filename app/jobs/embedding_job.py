import logging
from app.jobs.celery_app import celery_app

logger = logging.getLogger("saib.jobs.embedding")

@celery_app.task(name="app.jobs.embedding_job.embed_document", bind=True, max_retries=3)
def embed_document(self, document_id: str):
    logger.info("embed_document document_id=%s (stub)", document_id)
    return {"status": "stub", "document_id": document_id}
