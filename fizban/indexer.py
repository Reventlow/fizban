"""Document indexing with incremental update support."""

import logging
from pathlib import Path

from fizban.config import Config, get_config
from fizban.db import Database, content_hash
from fizban.embeddings import EmbeddingModel
from fizban.markdown_parser import parse_markdown
from fizban.repos import scan_repo
from fizban.vector import get_vector_backend
from fizban.vector.base import VectorBackend

logger = logging.getLogger(__name__)


def chunk_text(
    text: str, chunk_size: int = 1000, chunk_overlap: int = 200
) -> list[tuple[str, int, int]]:
    """Split text into overlapping chunks.

    Args:
        text: Text to split.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap between consecutive chunks.

    Returns:
        List of (chunk_content, start_char, end_char) tuples.
    """
    if not text:
        return []
    if len(text) <= chunk_size:
        return [(text, 0, len(text))]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))

        # Try to break at paragraph or sentence boundary
        if end < len(text):
            # Look for paragraph break
            newline_pos = text.rfind("\n\n", start, end)
            if newline_pos > start + chunk_size // 2:
                end = newline_pos + 2
            else:
                # Look for sentence break
                for sep in (". ", ".\n", "! ", "? "):
                    sep_pos = text.rfind(sep, start, end)
                    if sep_pos > start + chunk_size // 2:
                        end = sep_pos + len(sep)
                        break

        chunks.append((text[start:end], start, end))

        # Move start forward, accounting for overlap
        new_start = end - chunk_overlap
        # Ensure we always advance to avoid infinite loops
        if new_start <= start:
            new_start = end
        start = new_start
        if start >= len(text):
            break
        # Don't create tiny trailing chunks - append remainder to last chunk
        if len(text) - start < chunk_overlap:
            # Extend the last chunk to include the remaining text
            if chunks:
                last_content, last_start, last_end = chunks[-1]
                chunks[-1] = (text[last_start:], last_start, len(text))
            break

    return chunks


def _identify_repo(file_path: Path, repos: list[str]) -> str:
    """Determine which repo a file belongs to."""
    file_str = str(file_path)
    for repo in repos:
        if file_str.startswith(repo):
            return repo
    return str(file_path.parent)


def _index_file(
    file_path: Path,
    repo: str,
    db: Database,
    vector: VectorBackend,
    embeddings: EmbeddingModel,
    config: Config,
) -> bool:
    """Index a single markdown file.

    Returns True if the file was indexed (new or changed), False if skipped.
    """
    path_str = str(file_path)

    # Read file
    try:
        raw_content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error("Failed to read %s: %s", file_path, e)
        return False

    # Check if content has changed
    new_hash = content_hash(raw_content)
    existing_hash = db.get_content_hash(path_str)
    if existing_hash == new_hash:
        return False

    # Parse markdown (pass repo root to sandbox image path resolution)
    parsed = parse_markdown(raw_content, file_path, repo_root=Path(repo))

    # Upsert document
    last_modified = file_path.stat().st_mtime
    doc_id = db.upsert_document(
        repo, path_str, parsed.title, parsed.content, last_modified
    )

    # Delete old vectors for this document's chunks
    old_chunks = db.get_chunks(doc_id)
    if old_chunks:
        vector.delete_vectors([c.id for c in old_chunks])

    # Chunk text
    text_chunks = chunk_text(parsed.content, config.chunk_size, config.chunk_overlap)
    chunk_data = [
        (i, content, start, end) for i, (content, start, end) in enumerate(text_chunks)
    ]

    # Insert chunks into DB
    chunk_ids = db.insert_chunks(doc_id, chunk_data)

    # Generate and store embeddings
    if chunk_ids:
        texts = [content for _, content, _, _ in chunk_data]
        vectors = embeddings.encode(texts)
        vector.add_vectors(chunk_ids, vectors)

    # Store image references
    image_data = [
        (img.original_path, img.absolute_path, img.alt_text) for img in parsed.images
    ]
    db.insert_images(doc_id, image_data)

    logger.info(
        "Indexed %s (%d chunks, %d images)", path_str, len(chunk_ids), len(image_data)
    )
    return True


def rebuild_index(config: Config | None = None) -> dict:
    """Full rebuild: clear everything and re-index all repos.

    Returns:
        Stats dict with counts.
    """
    config = config or get_config()
    db = Database(config)
    db.init_db()
    embeddings = EmbeddingModel(config)
    vector = get_vector_backend(config)
    vector.init_index(embeddings.dimension)
    vector.clear()

    # Clear existing documents (cascades to chunks and images)
    for doc in db.list_documents():
        db.delete_document(doc.id)

    total_files = 0
    indexed = 0

    for repo_path in config.repos:
        md_files = scan_repo(repo_path)
        total_files += len(md_files)
        for file_path in md_files:
            if _index_file(file_path, repo_path, db, vector, embeddings, config):
                indexed += 1

    db.close()
    return {"total_files": total_files, "indexed": indexed}


def update_index(config: Config | None = None) -> dict:
    """Incremental update: only index changed files, remove deleted ones.

    Returns:
        Stats dict with counts.
    """
    config = config or get_config()
    db = Database(config)
    db.init_db()
    embeddings = EmbeddingModel(config)
    vector = get_vector_backend(config)
    vector.init_index(embeddings.dimension)

    total_files = 0
    indexed = 0
    removed = 0

    all_current_paths: set[str] = set()

    for repo_path in config.repos:
        md_files = scan_repo(repo_path)
        total_files += len(md_files)
        current_paths = {str(f) for f in md_files}
        all_current_paths.update(current_paths)

        # Index new/changed files
        for file_path in md_files:
            if _index_file(file_path, repo_path, db, vector, embeddings, config):
                indexed += 1

        # Remove deleted files for this repo
        indexed_paths = db.get_all_paths(repo_path)
        for path in indexed_paths - current_paths:
            doc = db.get_document_by_path(path)
            if doc:
                old_chunks = db.get_chunks(doc.id)
                if old_chunks:
                    vector.delete_vectors([c.id for c in old_chunks])
                db.delete_document(doc.id)
                removed += 1
                logger.info("Removed deleted file: %s", path)

    db.close()
    return {"total_files": total_files, "indexed": indexed, "removed": removed}
