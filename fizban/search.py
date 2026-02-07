"""Semantic search over indexed documents."""

import logging
from dataclasses import dataclass

from fizban.config import Config, get_config
from fizban.db import Database
from fizban.embeddings import EmbeddingModel
from fizban.vector import get_vector_backend

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single search result."""

    chunk_id: int
    document_id: int
    document_path: str
    document_title: str
    repo: str
    chunk_content: str
    chunk_index: int
    distance: float


def semantic_search(
    query: str,
    config: Config | None = None,
    limit: int = 10,
) -> list[SearchResult]:
    """Perform semantic search over the indexed documents.

    Args:
        query: Natural language search query.
        config: Optional configuration override.
        limit: Maximum number of results.

    Returns:
        List of SearchResult ordered by relevance (ascending distance).
    """
    config = config or get_config()
    db = Database(config)
    embeddings = EmbeddingModel(config)
    vector = get_vector_backend(config)

    # Encode the query
    query_embedding = embeddings.encode_query(query)

    # Search vectors
    hits = vector.search(query_embedding, limit=limit)

    results = []
    for chunk_id, distance in hits:
        chunk = db.get_chunk(chunk_id)
        if chunk is None:
            continue
        doc = db.get_document(chunk.document_id)
        if doc is None:
            continue
        results.append(SearchResult(
            chunk_id=chunk_id,
            document_id=doc.id,
            document_path=doc.path,
            document_title=doc.title,
            repo=doc.repo,
            chunk_content=chunk.content,
            chunk_index=chunk.chunk_index,
            distance=distance,
        ))

    return results
