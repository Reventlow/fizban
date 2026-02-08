"""Vector backend using sqlite-vss extension (fallback)."""

import json
import logging
import sqlite3

import numpy as np

from fizban.config import Config, get_config
from fizban.vector.base import VectorBackend

logger = logging.getLogger(__name__)


class SqliteVssBackend(VectorBackend):
    """Vector storage using the sqlite-vss extension.

    This is the fallback backend when sqlite-vec is not available.
    """

    def __init__(self, config: Config | None = None):
        self.config = config or get_config()
        self._conn: sqlite3.Connection | None = None
        self._dimension: int | None = None
        try:
            import sqlite_vss  # noqa: F401
        except ImportError:
            raise ImportError(
                "sqlite-vss is not installed. Install with: pip install sqlite-vss"
            )

    @property
    def conn(self) -> sqlite3.Connection:
        """Get or create the database connection with vss extension loaded."""
        if self._conn is None:
            import sqlite_vss

            self.config.ensure_db_dir()
            self._conn = sqlite3.connect(str(self.config.db_path))
            self._conn.enable_load_extension(True)
            sqlite_vss.load(self._conn)
            self._conn.enable_load_extension(False)
        return self._conn

    def init_index(self, dimension: int) -> None:
        """Create the vss virtual table if it doesn't exist."""
        self._dimension = dimension
        # sqlite-vss uses a different syntax
        self.conn.execute(
            f"""CREATE VIRTUAL TABLE IF NOT EXISTS vss_chunks USING vss0(
                embedding({dimension})
            )"""
        )
        # Also need a mapping table for chunk_id <-> rowid
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS vss_chunk_map (
                rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                chunk_id INTEGER NOT NULL UNIQUE
            )
        """)
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_vss_chunk_map ON vss_chunk_map(chunk_id)"
        )
        self.conn.commit()
        logger.info("Vector index initialized (sqlite-vss, dim=%d)", dimension)

    def add_vectors(self, ids: list[int], vectors: np.ndarray) -> None:
        """Add vectors to the vss0 table."""
        if len(ids) == 0:
            return
        for chunk_id, vector in zip(ids, vectors):
            # Remove existing entry if present
            existing = self.conn.execute(
                "SELECT rowid FROM vss_chunk_map WHERE chunk_id = ?", (chunk_id,)
            ).fetchone()
            if existing:
                self.conn.execute(
                    "DELETE FROM vss_chunks WHERE rowid = ?", (existing[0],)
                )
                self.conn.execute(
                    "DELETE FROM vss_chunk_map WHERE chunk_id = ?", (chunk_id,)
                )

            # Insert into map to get rowid
            cursor = self.conn.execute(
                "INSERT INTO vss_chunk_map (chunk_id) VALUES (?)", (chunk_id,)
            )
            row_id = cursor.lastrowid

            # Insert vector
            vec_json = json.dumps(vector.astype(float).tolist())
            self.conn.execute(
                "INSERT INTO vss_chunks (rowid, embedding) VALUES (?, ?)",
                (row_id, vec_json),
            )
        self.conn.commit()

    def delete_vectors(self, ids: list[int]) -> None:
        """Delete vectors by chunk ID."""
        if not ids:
            return
        for chunk_id in ids:
            existing = self.conn.execute(
                "SELECT rowid FROM vss_chunk_map WHERE chunk_id = ?", (chunk_id,)
            ).fetchone()
            if existing:
                self.conn.execute(
                    "DELETE FROM vss_chunks WHERE rowid = ?", (existing[0],)
                )
                self.conn.execute(
                    "DELETE FROM vss_chunk_map WHERE chunk_id = ?", (chunk_id,)
                )
        self.conn.commit()

    def search(
        self, query_vector: np.ndarray, limit: int = 10
    ) -> list[tuple[int, float]]:
        """Search for nearest neighbors using sqlite-vss."""
        vec_json = json.dumps(query_vector.astype(float).tolist())
        rows = self.conn.execute(
            """SELECT rowid, distance
               FROM vss_chunks
               WHERE vss_search(embedding, ?)
               LIMIT ?""",
            (vec_json, limit),
        ).fetchall()
        results = []
        for row_id, distance in rows:
            chunk_row = self.conn.execute(
                "SELECT chunk_id FROM vss_chunk_map WHERE rowid = ?", (row_id,)
            ).fetchone()
            if chunk_row:
                results.append((chunk_row[0], distance))
        return results

    def count(self) -> int:
        """Count vectors in the index."""
        try:
            row = self.conn.execute("SELECT COUNT(*) FROM vss_chunk_map").fetchone()
            return row[0]
        except sqlite3.OperationalError:
            return 0

    def clear(self) -> None:
        """Drop and recreate the vector tables."""
        try:
            self.conn.execute("DROP TABLE IF EXISTS vss_chunks")
            self.conn.execute("DROP TABLE IF EXISTS vss_chunk_map")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass
        if self._dimension:
            self.init_index(self._dimension)
