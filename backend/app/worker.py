"""Celery worker: heavy ingestion runs here, never in the API process."""
import uuid

import redis
from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.models import PolicyDocument

celery_app = Celery("hr", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(task_acks_late=True, worker_prefetch_multiplier=1, task_time_limit=900)

_engine = create_engine(settings.database_url.replace("+asyncpg", "+psycopg2"), pool_pre_ping=True)


@celery_app.task(name="ingest_document")
def ingest_document(doc_id: str) -> None:
    from app.rag.ingest import ingest  # lazy: heavy imports

    with Session(_engine) as s:
        doc = s.get(PolicyDocument, uuid.UUID(doc_id))
        if doc is None:
            return
        doc.status = "processing"
        s.commit()
        try:
            doc.chunks = ingest(doc_id, doc.path, doc.name, doc.version, list(doc.allowed_roles))
            doc.status, doc.error = "active", None
            redis.Redis.from_url(settings.redis_url).incr("corpus_version")  # invalidate retrieval cache
        except Exception as e:  # surfaced in the admin UI
            doc.status, doc.error = "failed", str(e)[:500]
            raise
        finally:
            s.commit()
