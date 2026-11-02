import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import KNOWN_ROLES, User, require_role
from app.config import settings
from app.db import get_session
from app.models import PolicyDocument
from app.rag.vectorstore import delete_document_vectors
from app.services.audit import audit
from app.services.redis import bump_corpus_version

router = APIRouter(prefix="/api/admin", tags=["admin"])
ALLOWED_EXT = {".pdf", ".docx", ".txt", ".md"}


def _celery():
    from app.worker import celery_app  # lazy: keeps API start-up light

    return celery_app


@router.post("/policies", status_code=202)
async def upload_policy(
    file: UploadFile,
    name: str = Form(..., max_length=200),
    version: str = Form(..., max_length=32),
    allowed_roles: str = Form("employee,manager,hr"),
    user: User = Depends(require_role("hr")),
    session: AsyncSession = Depends(get_session),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Allowed file types: {', '.join(sorted(ALLOWED_EXT))}")
    roles = [r.strip() for r in allowed_roles.split(",") if r.strip()]
    if not roles or not set(roles) <= KNOWN_ROLES:
        raise HTTPException(400, f"allowed_roles must be a subset of {sorted(KNOWN_ROLES)}")

    doc_id = uuid.uuid4()
    dest = Path(settings.upload_dir) / f"{doc_id}{ext}"  # server-generated name: no path traversal
    dest.parent.mkdir(parents=True, exist_ok=True)
    size, too_big = 0, False
    with dest.open("wb") as f:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > settings.max_upload_mb << 20:
                too_big = True
                break
            f.write(chunk)
    if too_big:
        dest.unlink(missing_ok=True)
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB")

    session.add(
        PolicyDocument(
            id=doc_id, name=name, version=version, allowed_roles=roles,
            filename=file.filename or dest.name, path=str(dest), uploaded_by=user.id,
        )
    )
    audit(session, user.id, "policy_upload", doc_id=str(doc_id), name=name, version=version, roles=roles)
    await session.commit()
    _celery().send_task("ingest_document", args=[str(doc_id)])  # async: API returns immediately
    return {"id": str(doc_id), "status": "pending"}


@router.get("/policies")
async def list_policies(user: User = Depends(require_role("hr")), session: AsyncSession = Depends(get_session)):
    rows = await session.scalars(select(PolicyDocument).order_by(PolicyDocument.created_at.desc()))
    return [
        {"id": str(d.id), "name": d.name, "version": d.version, "roles": d.allowed_roles,
         "status": d.status, "chunks": d.chunks, "error": d.error, "filename": d.filename}
        for d in rows
    ]


@router.delete("/policies/{doc_id}", status_code=204)
async def delete_policy(doc_id: uuid.UUID, user: User = Depends(require_role("hr")), session: AsyncSession = Depends(get_session)):
    doc = await session.get(PolicyDocument, doc_id)
    if not doc:
        raise HTTPException(404, "Not found")
    await asyncio.to_thread(delete_document_vectors, str(doc_id))
    Path(doc.path).unlink(missing_ok=True)
    audit(session, user.id, "policy_delete", doc_id=str(doc_id), name=doc.name)
    await session.delete(doc)
    await session.commit()
    await bump_corpus_version()  # invalidates cached retrievals
