"""Vector search over document_chunks.

`org_id` is a required positional argument: there is no code path that can
search chunks without a tenant filter.
"""
import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Document, DocumentChunk
from app.models.enums import DocumentStatus


@dataclass
class RetrievedChunk:
    chunk_id: uuid.UUID
    doc_id: uuid.UUID
    document_name: str
    chunk_index: int
    content: str
    similarity: float


def search_similar(
    db: Session, org_id: uuid.UUID, query_embedding: list[float], top_k: int
) -> list[RetrievedChunk]:
    distance = DocumentChunk.embedding.cosine_distance(query_embedding)
    # pgvector >= 0.8: with a WHERE filter, HNSW would otherwise stop after
    # ef_search candidates and could return < top_k rows for a small tenant in
    # a large shared table. Iterative scan keeps searching until enough rows
    # pass the org filter. SET LOCAL only affects this transaction.
    db.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
    db.execute(text("SET LOCAL hnsw.ef_search = 100"))
    rows = db.execute(
        select(
            DocumentChunk.id,
            DocumentChunk.doc_id,
            Document.original_filename,
            DocumentChunk.chunk_index,
            DocumentChunk.content,
            (1 - distance).label("similarity"),
        )
        .join(Document, Document.id == DocumentChunk.doc_id)
        .where(
            DocumentChunk.org_id == org_id,
            Document.org_id == org_id,  # belt and braces
            Document.status == DocumentStatus.READY.value,
        )
        .order_by(distance)
        .limit(top_k)
    ).all()
    results = [
        RetrievedChunk(
            chunk_id=r.id,
            doc_id=r.doc_id,
            document_name=r.original_filename,
            chunk_index=r.chunk_index,
            content=r.content,
            similarity=float(r.similarity),
        )
        for r in rows
    ]
    # relaxed_order may return rows slightly out of order; re-sort exactly.
    results.sort(key=lambda c: c.similarity, reverse=True)
    return results
