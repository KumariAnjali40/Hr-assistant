"""Offline ingestion: file -> text -> chunks -> embeddings -> Qdrant (with ACL metadata)."""
import uuid
from pathlib import Path

from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.vectorstore import delete_other_versions, ensure_collection, get_store

_NS = uuid.UUID("6f1d3a52-0000-4000-8000-000000000001")


def load_file(path: str):
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return PyPDFLoader(path).load()
    if ext == ".docx":
        return Docx2txtLoader(path).load()
    if ext in {".txt", ".md"}:
        return TextLoader(path, encoding="utf-8").load()
    raise ValueError(f"Unsupported file type: {ext}")


def ingest(doc_id: str, path: str, name: str, version: str, allowed_roles: list[str]) -> int:
    ensure_collection()
    pages = load_file(str(path))
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=900, chunk_overlap=150, separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = splitter.split_documents(pages)
    if not chunks:
        raise ValueError("No extractable text (scanned PDF? run OCR first).")
    ids = []
    for i, c in enumerate(chunks):
        c.metadata.update(
            {
                "doc_id": doc_id,
                "policy_name": name,
                "version": version,
                "allowed_roles": allowed_roles,
                "chunk_index": i,
                "page": c.metadata.get("page"),
            }
        )
        ids.append(str(uuid.uuid5(_NS, f"{doc_id}:{i}")))  # deterministic -> re-ingest is an upsert
    get_store().add_documents(chunks, ids=ids)
    delete_other_versions(name, doc_id)
    return len(chunks)
