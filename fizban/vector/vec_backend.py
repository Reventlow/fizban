"""Vector backend using sqlite-vec extension."""

import logging
import sqlite3
import struct

import numpy as np

from fizban.config import Config, get_config
from fizban.vector.base import VectorBackend

logger = logging.getLogger(__name__)


def _serialize_f32(vector: np.ndarray) -> bytes:
    """Serialize a float32 numpy array to bytes for sqlite-vec."""
    return struct.pack(f"{len(vector)}f", *vector.astype(np.float32))


class SqliteVecBackend(VectorBackend):
    """Vector storage using the sqlite-vec extension.

    Uses a virtual table (vec0) for storing and searching vectors.
    """

    def __init__(self, config: Config | None = None):
        self.config = config or get_config()
        self._conn: sqlite3.Connection | None = None
        self._dimension: int | None = None
        # Verify sqlite-vec is available
        try:
            import sqlite_vec  # noqa: F401
        except ImportError:
            raise ImportError(
                "sqlite-vec is not installed. Install with: pip install sqlite-vec"
            )

    @property
    def conn(self) -> sqlite3.Connection:
        """Get or create the database connection with vec extension loaded."""
        if self._conn is None:
            import sqlite_vec

            self.config.ensure_db_dir()
            self._conn = sqlite3.connect(str(self.config.db_path))
            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
            self._conn.enable_load_extension(False)
        return self._conn

    def init_index(self, dimension: int) -> None:
        """Create the vec0 virtual table if it doesn't exist."""
        self._dimension = dimension
        self.conn.execute(
            f"""CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
                chunk_id INTEGER PRIMARY KEY,
                embedding float[{dimension}]
            )"""
        )
        self.conn.commit()
        logger.info("Vector index initialized (sqlite-vec, dim=%d)", dimension)

    def add_vectors(self, ids: list[int], vectors: np.ndarray) -> None:
        """Add vectors to the vec0 table."""
        if len(ids) == 0:
            return
        for chunk_id, vector in zip(ids, vectors):
            self.conn.execute(
                "INSERT OR REPLACE INTO vec_chunks (chunk_id, embedding) VALUES (?, ?)",
                (chunk_id, _serialize_f32(vector)),
            )
        self.conn.commit()

    def delete_vectors(self, ids: list[int]) -> None:
        """Delete vectors by chunk ID."""
        if not ids:
            return
        placeholders = ",".join("?" for _ in ids)
        self.conn.execute(f"DELETE FROM vec_chunks WHERE chunk_id IN ({placeholders})", ids)
        self.conn.commit()

    def search(self, query_vector: np.ndarray, limit: int = 10) -> list[tuple[int, float]]:
        """Search for nearest neighbors using sqlite-vec."""
        rows = self.conn.execute(
            """SELECT chunk_id, distance
               FROM vec_chunks
               WHERE embedding MATCH ?
               ORDER BY distance
               LIMIT ?""",
            (_serialize_f32(query_vector), limit),
        ).fetchall()
        return [(row[0], row[1]) for row in rows]

    def count(self) -> int:
        """Count vectors in the index."""
        try:
            row = self.conn.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()
            return row[0]
        except sqlite3.OperationalError:
            return 0

    def clear(self) -> None:
        """Drop and recreate the vector table."""
        try:
            self.conn.execute("DROP TABLE IF EXISTS vec_chunks")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass
        if self._dimension:
            self.init_index(self._dimension)
