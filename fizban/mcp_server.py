"""MCP server for Fizban documentation knowledge base."""

import json
import logging

from mcp.server.fastmcp import FastMCP

from fizban import __version__
from fizban.config import get_config

logger = logging.getLogger(__name__)

mcp = FastMCP("fizban")


@mcp.tool()
def repos_pull_all() -> str:
    """Pull latest changes from all configured documentation repos."""
    try:
        from fizban.repos import pull_all

        results = pull_all()
        return json.dumps(results, indent=2)
    except Exception as e:
        logger.exception("repos_pull_all failed")
        return json.dumps({"error": "Internal error. Check server logs for details."})


@mcp.tool()
def index_rebuild() -> str:
    """Full rebuild of the search index. Re-indexes all documents from scratch."""
    try:
        from fizban.indexer import rebuild_index

        stats = rebuild_index()
        return json.dumps(stats, indent=2)
    except Exception as e:
        logger.exception("index_rebuild failed")
        return json.dumps({"error": "Internal error. Check server logs for details."})


@mcp.tool()
def index_update() -> str:
    """Incremental index update. Only processes changed or new files, removes deleted ones."""
    try:
        from fizban.indexer import update_index

        stats = update_index()
        return json.dumps(stats, indent=2)
    except Exception as e:
        logger.exception("index_update failed")
        return json.dumps({"error": "Internal error. Check server logs for details."})


@mcp.tool()
def search_semantic(query: str, limit: int = 10, distance_threshold: float | None = None) -> str:
    """Semantic search over indexed documentation.

    Args:
        query: Natural language search query.
        limit: Maximum number of results (default: 10).
        distance_threshold: Maximum distance for results (lower = stricter).
            Results above this are excluded. Default from config (0.85).
    """
    limit = min(limit, 100)
    try:
        from fizban.search import semantic_search

        results = semantic_search(query, limit=limit, distance_threshold=distance_threshold)
        if not results:
            return json.dumps({
                "results": [],
                "message": "No results found within the distance threshold. "
                           "The query may not match any indexed documentation. "
                           "Try rephrasing or use a higher distance_threshold.",
            })
        return json.dumps(
            [
                {
                    "chunk_id": r.chunk_id,
                    "document_id": r.document_id,
                    "path": r.document_path,
                    "title": r.document_title,
                    "repo": r.repo,
                    "content": r.chunk_content,
                    "distance": round(r.distance, 4),
                }
                for r in results
            ],
            indent=2,
        )
    except Exception as e:
        logger.exception("search_semantic failed")
        return json.dumps({"error": "Internal error. Check server logs for details."})


@mcp.tool()
def docs_fetch(path: str) -> str:
    """Fetch full document content by file path.

    Args:
        path: Absolute path to the document.
    """
    try:
        config = get_config()
        # Validate that path is within a configured repo
        if not any(path.startswith(repo) for repo in config.repos):
            return json.dumps({"error": "Path is not within a configured repository."})

        from fizban.db import Database

        db = Database()
        try:
            doc = db.get_document_by_path(path)
            if doc is None:
                return json.dumps({"error": "Document not found."})

            images = db.get_images(doc.id)
            return json.dumps(
                {
                    "id": doc.id,
                    "path": doc.path,
                    "title": doc.title,
                    "repo": doc.repo,
                    "content": doc.content,
                    "images": [
                        {"original": img.original_path, "absolute": img.absolute_path, "alt": img.alt_text}
                        for img in images
                    ],
                },
                indent=2,
            )
        finally:
            db.close()
    except Exception as e:
        logger.exception("docs_fetch failed")
        return json.dumps({"error": "Internal error. Check server logs for details."})


@mcp.tool()
def docs_fetch_by_hit(chunk_id: int) -> str:
    """Fetch a full document from a search hit's chunk ID.

    Args:
        chunk_id: The chunk_id from a search result.
    """
    try:
        from fizban.db import Database

        db = Database()
        try:
            chunk = db.get_chunk(chunk_id)
            if chunk is None:
                return json.dumps({"error": "Chunk not found."})

            doc = db.get_document(chunk.document_id)
            if doc is None:
                return json.dumps({"error": "Document not found for chunk."})

            images = db.get_images(doc.id)
            return json.dumps(
                {
                    "id": doc.id,
                    "path": doc.path,
                    "title": doc.title,
                    "repo": doc.repo,
                    "content": doc.content,
                    "hit_chunk": {
                        "chunk_id": chunk.id,
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                    },
                    "images": [
                        {"original": img.original_path, "absolute": img.absolute_path, "alt": img.alt_text}
                        for img in images
                    ],
                },
                indent=2,
            )
        finally:
            db.close()
    except Exception as e:
        logger.exception("docs_fetch_by_hit failed")
        return json.dumps({"error": "Internal error. Check server logs for details."})


@mcp.tool()
def system_status() -> str:
    """Get Fizban system status: database stats, config, and health info."""
    try:
        from pathlib import Path
        from fizban.db import Database
        from fizban.vector import get_vector_backend

        home = str(Path.home())
        def redact_path(p: str) -> str:
            """Replace the home directory prefix with ~/."""
            if p.startswith(home):
                return "~/" + p[len(home):].lstrip("/")
            return Path(p).name

        config = get_config()
        db = Database(config)

        try:
            db_stats = db.stats()
        except Exception as e:
            logger.exception("system_status: db.stats() failed")
            db_stats = {"error": "Unable to retrieve database stats."}

        try:
            vector = get_vector_backend(config)
            vector_count = vector.count()
        except Exception as e:
            logger.exception("system_status: vector count failed")
            vector_count = "error: unable to retrieve vector count"

        try:
            return json.dumps(
                {
                    "version": __version__,
                    "config": {
                        "db_path": redact_path(str(config.db_path)),
                        "vector_backend": config.vector_backend,
                        "embedding_model": config.embedding_model,
                        "chunk_size": config.chunk_size,
                        "repos": [redact_path(r) for r in config.repos],
                    },
                    "database": db_stats,
                    "vector_count": vector_count,
                },
                indent=2,
            )
        finally:
            db.close()
    except Exception as e:
        logger.exception("system_status failed")
        return json.dumps({"error": "Internal error. Check server logs for details."})


def serve() -> None:
    """Start the MCP server using stdio transport."""
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting Fizban MCP server v%s", __version__)
    mcp.run(transport="stdio")
