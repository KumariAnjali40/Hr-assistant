import asyncio
import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.api import admin, chat, conversations
from app.config import settings
from app.db import engine
from app.logging import setup_logging
from app.rag.vectorstore import client as qdrant_client
from app.rag.vectorstore import ensure_collection
from app.services.redis import get_redis

log = structlog.get_logger()
is_prod = settings.env == "prod"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    try:
        await asyncio.to_thread(ensure_collection)
    except Exception as e:  # readiness probe will report it
        log.warning("qdrant_not_ready", error=str(e))
    yield
    await engine.dispose()


app = FastAPI(
    title="HR Assistant API",
    lifespan=lifespan,
    docs_url=None if is_prod else "/docs",
    redoc_url=None,
    openapi_url=None if is_prod else "/openapi.json",
)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"], allow_credentials=False,
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=rid, path=request.url.path, method=request.method)
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    log.info("request", status=response.status_code, ms=round((time.perf_counter() - start) * 1000))
    return response


app.include_router(chat.router)
app.include_router(conversations.router)
app.include_router(admin.router)
Instrumentator().instrument(app).expose(app, include_in_schema=False)  # /metrics for Prometheus


@app.get("/healthz")
async def healthz():
    """Liveness: process is up."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    """Readiness: dependencies reachable. Kubernetes only routes traffic when this is 200."""
    checks: dict[str, bool] = {}
    try:
        async with engine.connect() as c:
            await c.execute(text("select 1"))
        checks["postgres"] = True
    except Exception:
        checks["postgres"] = False
    try:
        checks["redis"] = bool(await get_redis().ping())
    except Exception:
        checks["redis"] = False
    try:
        await asyncio.to_thread(qdrant_client().get_collections)
        checks["qdrant"] = True
    except Exception:
        checks["qdrant"] = False
    return JSONResponse(checks, status_code=200 if all(checks.values()) else 503)
