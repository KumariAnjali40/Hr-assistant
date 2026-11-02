import asyncio
import hashlib
import json
from dataclasses import asdict, dataclass

from qdrant_client import models

from app.config import settings
from app.rag.vectorstore import get_store
from app.services.redis import corpus_version, get_redis


@dataclass
class Chunk:
    policy_name: str
    version: str
    page: int | None
    text: str
    score: float
    doc_id: str


def build_filter(roles) -> models.Filter:
    """ACL enforced INSIDE the vector DB query: chunks the user may not see are never retrieved,
    so they can never reach the LLM context."""
    return models.Filter(
        must=[models.FieldCondition(key="metadata.allowed_roles", match=models.MatchAny(any=sorted(roles)))]
    )


def _search(query: str, roles, k: int, min_score: float) -> list[Chunk]:
    results = get_store().similarity_search_with_score(query, k=k, filter=build_filter(roles))
    out = []
    for doc, score in results:
        if score < min_score:
            continue
        m = doc.metadata
        out.append(
            Chunk(m.get("policy_name", "?"), str(m.get("version", "?")), m.get("page"), doc.page_content, float(score), m.get("doc_id", ""))
        )
    return out


async def retrieve(query: str, roles, k: int | None = None, min_score: float | None = None, use_cache: bool = True) -> list[Chunk]:
    k = k or settings.retrieval_k
    min_score = settings.retrieval_min_score if min_score is None else min_score
    key = None
    if use_cache:
        raw = json.dumps([query.strip().lower(), sorted(roles), k, min_score, await corpus_version()])
        key = "rag:" + hashlib.sha256(raw.encode()).hexdigest()
        if hit := await get_redis().get(key):
            return [Chunk(**c) for c in json.loads(hit)]
    chunks = await asyncio.to_thread(_search, query, roles, k, min_score)
    if key:
        await get_redis().set(key, json.dumps([asdict(c) for c in chunks]), ex=3600)
    return chunks
