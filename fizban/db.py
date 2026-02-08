"""SQLite database management for Fizban."""

import hashlib
import logging
import sqlite3
import time
from dataclasses import dataclass

from fizban.config import Config, get_config

logger = logging.getLogger(__name__)


@dataclass
class DocumentRecord:
    """A document stored in the database."""

    id: int
    repo: str
    path: str
    title: str
    content: str
    content_hash: str
    last_modified: float
    indexed_at: float


@dataclass
class ChunkRecord:
    """A text chunk stored in the database."""

    id: int
    document_id: int
    chunk_index: int
    content: str
    start_char: int
    end_char: int


@dataclass
class ImageRecord:
    """An image reference stored in the database."""

    id: int
    document_id: int
    original_path: str
    absolute_path: str
    alt_text: str


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    title TEXT,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    last_modified REAL NOT NULL,
    indexed_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    original_path TEXT NOT NULL,
    absolute_path TEXT NOT NULL,
    alt_text TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_images_document ON images(document_id);
CREATE INDEX IF NOT EXISTS idx_documents_repo ON documents(repo);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash);
"""


def content_hash(content: str) -> str:
    """Compute a SHA-256 hash of content for change detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class Database:
    """SQLite database wrapper for Fizban."""

    def __init__(self, config: Config | None = None):
        self.config = config or get_config()
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Get or create the database connection."""
        if self._conn is None:
            self.config.ensure_db_dir()
            self._conn = sqlite3.connect(str(self.config.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def init_db(self) -> None:
        """Initialize the database schema."""
        self.conn.executescript(SCHEMA_SQL)
        logger.info("Database initialized at %s", self.config.db_path)

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # --- Document operations ---

    def upsert_document(
        self, repo: str, path: str, title: str, content: str, last_modified: float
    ) -> int:
        """Insert or update a document. Returns the document ID."""
        hash_val = content_hash(content)
        now = time.time()
        cursor = self.conn.execute(
            """INSERT INTO documents (repo, path, title, content, content_hash, last_modified, indexed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(path) DO UPDATE SET
                   repo=excluded.repo, title=excluded.title, content=excluded.content,
                   content_hash=excluded.content_hash, last_modified=excluded.last_modified,
                   indexed_at=excluded.indexed_at
               RETURNING id""",
            (repo, path, title, content, hash_val, last_modified, now),
        )
        row = cursor.fetchone()
        self.conn.commit()
        return row[0]

    def get_document(self, doc_id: int) -> DocumentRecord | None:
        """Fetch a document by ID."""
        row = self.conn.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if row is None:
            return None
        return DocumentRecord(**dict(row))

    def get_document_by_path(self, path: str) -> DocumentRecord | None:
        """Fetch a document by file path."""
        row = self.conn.execute(
            "SELECT * FROM documents WHERE path = ?", (path,)
        ).fetchone()
        if row is None:
            return None
        return DocumentRecord(**dict(row))

    def list_documents(self, repo: str | None = None) -> list[DocumentRecord]:
        """List all documents, optionally filtered by repo."""
        if repo:
            rows = self.conn.execute(
                "SELECT * FROM documents WHERE repo = ? ORDER BY path", (repo,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM documents ORDER BY path").fetchall()
        return [DocumentRecord(**dict(r)) for r in rows]

    def delete_document(self, doc_id: int) -> None:
        """Delete a document and its chunks/images (cascade)."""
        self.conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        self.conn.commit()

    def get_content_hash(self, path: str) -> str | None:
        """Get the content hash for a document by path."""
        row = self.conn.execute(
            "SELECT content_hash FROM documents WHERE path = ?", (path,)
        ).fetchone()
        return row[0] if row else None

    def get_all_paths(self, repo: str | None = None) -> set[str]:
        """Get all indexed document paths."""
        if repo:
            rows = self.conn.execute(
                "SELECT path FROM documents WHERE repo = ?", (repo,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT path FROM documents").fetchall()
        return {r[0] for r in rows}

    # --- Chunk operations ---

    def insert_chunks(
        self, document_id: int, chunks: list[tuple[int, str, int, int]]
    ) -> list[int]:
        """Insert chunks for a document. Each tuple: (chunk_index, content, start_char, end_char).
        Returns list of chunk IDs."""
        # Delete existing chunks for this document first
        self.conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        chunk_ids = []
        for chunk_index, content, start_char, end_char in chunks:
            cursor = self.conn.execute(
                "INSERT INTO chunks (document_id, chunk_index, content, start_char, end_char) VALUES (?, ?, ?, ?, ?) RETURNING id",
                (document_id, chunk_index, content, start_char, end_char),
            )
            chunk_ids.append(cursor.fetchone()[0])
        self.conn.commit()
        return chunk_ids

    def get_chunks(self, document_id: int) -> list[ChunkRecord]:
        """Get all chunks for a document."""
        rows = self.conn.execute(
            "SELECT * FROM chunks WHERE document_id = ? ORDER BY chunk_index",
            (document_id,),
        ).fetchall()
        return [ChunkRecord(**dict(r)) for r in rows]

    def get_chunk(self, chunk_id: int) -> ChunkRecord | None:
        """Get a single chunk by ID."""
        row = self.conn.execute(
            "SELECT * FROM chunks WHERE id = ?", (chunk_id,)
        ).fetchone()
        if row is None:
            return None
        return ChunkRecord(**dict(row))

    # --- Image operations ---

    def insert_images(
        self, document_id: int, images: list[tuple[str, str, str]]
    ) -> None:
        """Insert image references for a document. Each tuple: (original_path, absolute_path, alt_text)."""
        self.conn.execute("DELETE FROM images WHERE document_id = ?", (document_id,))
        for original_path, absolute_path, alt_text in images:
            self.conn.execute(
                "INSERT INTO images (document_id, original_path, absolute_path, alt_text) VALUES (?, ?, ?, ?)",
                (document_id, original_path, absolute_path, alt_text),
            )
        self.conn.commit()

    def get_images(self, document_id: int) -> list[ImageRecord]:
        """Get all image references for a document."""
        rows = self.conn.execute(
            "SELECT * FROM images WHERE document_id = ? ORDER BY id", (document_id,)
        ).fetchall()
        return [ImageRecord(**dict(r)) for r in rows]

    # --- Stats ---

    def stats(self) -> dict:
        """Get database statistics."""
        doc_count = self.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        chunk_count = self.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        image_count = self.conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
        repos = self.conn.execute("SELECT DISTINCT repo FROM documents").fetchall()
        return {
            "documents": doc_count,
            "chunks": chunk_count,
            "images": image_count,
            "repos": [r[0] for r in repos],
            "db_path": str(self.config.db_path),
        }
