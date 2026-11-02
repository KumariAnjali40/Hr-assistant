from langchain_ollama import OllamaEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models

from app.config import settings


def client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(model=settings.embed_model, base_url=settings.ollama_base_url)


def ensure_collection() -> None:
    """Idempotent. Payload indexes make the role/doc filters fast at scale."""
    c = client()
    name = settings.qdrant_collection
    if not c.collection_exists(name):
        c.create_collection(
            name, vectors_config=models.VectorParams(size=settings.embed_dim, distance=models.Distance.COSINE)
        )
    for field in ("metadata.allowed_roles", "metadata.doc_id", "metadata.policy_name"):
        try:
            c.create_payload_index(name, field_name=field, field_schema=models.PayloadSchemaType.KEYWORD)
        except Exception:
            pass  # already exists


def get_store() -> QdrantVectorStore:
    return QdrantVectorStore(client=client(), collection_name=settings.qdrant_collection, embedding=embeddings())


def delete_document_vectors(doc_id: str) -> None:
    client().delete(
        settings.qdrant_collection,
        points_selector=models.FilterSelector(
            filter=models.Filter(must=[models.FieldCondition(key="metadata.doc_id", match=models.MatchValue(value=doc_id))])
        ),
    )


def delete_other_versions(policy_name: str, keep_doc_id: str) -> None:
    """Remove superseded versions only AFTER the new one is fully indexed (zero-downtime update)."""
    client().delete(
        settings.qdrant_collection,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[models.FieldCondition(key="metadata.policy_name", match=models.MatchValue(value=policy_name))],
                must_not=[models.FieldCondition(key="metadata.doc_id", match=models.MatchValue(value=keep_doc_id))],
            )
        ),
    )
