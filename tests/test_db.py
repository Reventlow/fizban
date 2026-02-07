"""Tests for database module."""

import sqlite3
import time
from pathlib import Path

import pytest

from fizban.config import Config
from fizban.db import Database, DocumentRecord, ChunkRecord, ImageRecord, content_hash


@pytest.fixture
def db(tmp_path):
    """Create a Database with a temporary file-based SQLite database."""
    cfg = Config()
    cfg.db_path = tmp_path / "test.db"
    database = Database(cfg)
    database.init_db()
    yield database
    database.close()


class TestContentHash:
    """Test the content_hash utility function."""

    def test_deterministic(self):
        assert content_hash("hello") == content_hash("hello")

    def test_different_content_different_hash(self):
        assert content_hash("hello") != content_hash("world")

    def test_returns_hex_string(self):
        h = content_hash("test")
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex length

    def test_empty_string(self):
        h = content_hash("")
        assert isinstance(h, str)
        assert len(h) == 64


class TestDatabaseConnection:
    """Test database connection and initialization."""

    def test_init_db_creates_tables(self, db):
        # Verify tables exist by querying them
        tables = db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {row[0] for row in tables}
        assert "documents" in table_names
        assert "chunks" in table_names
        assert "images" in table_names

    def test_wal_mode_enabled(self, db):
        mode = db.conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"

    def test_foreign_keys_enabled(self, db):
        fk = db.conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1

    def test_close_and_reconnect(self, tmp_path):
        cfg = Config()
        cfg.db_path = tmp_path / "test.db"
        database = Database(cfg)
        database.init_db()
        database.close()
        assert database._conn is None
        # Reconnecting by accessing conn property
        _ = database.conn
        assert database._conn is not None
        database.close()


class TestDocumentOperations:
    """Test CRUD operations on documents."""

    def test_upsert_document_insert(self, db):
        doc_id = db.upsert_document(
            repo="/repo", path="/repo/file.md", title="Test",
            content="Hello", last_modified=1000.0,
        )
        assert isinstance(doc_id, int)
        assert doc_id > 0

    def test_upsert_document_returns_record(self, db):
        doc_id = db.upsert_document(
            repo="/repo", path="/repo/file.md", title="Test",
            content="Hello", last_modified=1000.0,
        )
        doc = db.get_document(doc_id)
        assert doc is not None
        assert isinstance(doc, DocumentRecord)
        assert doc.repo == "/repo"
        assert doc.path == "/repo/file.md"
        assert doc.title == "Test"
        assert doc.content == "Hello"

    def test_upsert_document_update_on_conflict(self, db):
        doc_id1 = db.upsert_document(
            repo="/repo", path="/repo/file.md", title="V1",
            content="Version 1", last_modified=1000.0,
        )
        doc_id2 = db.upsert_document(
            repo="/repo", path="/repo/file.md", title="V2",
            content="Version 2", last_modified=2000.0,
        )
        assert doc_id1 == doc_id2
        doc = db.get_document(doc_id2)
        assert doc.title == "V2"
        assert doc.content == "Version 2"

    def test_get_document_nonexistent(self, db):
        assert db.get_document(999) is None

    def test_get_document_by_path(self, db):
        db.upsert_document(
            repo="/repo", path="/repo/file.md", title="Test",
            content="Hello", last_modified=1000.0,
        )
        doc = db.get_document_by_path("/repo/file.md")
        assert doc is not None
        assert doc.title == "Test"

    def test_get_document_by_path_nonexistent(self, db):
        assert db.get_document_by_path("/no/such/file.md") is None

    def test_list_documents_all(self, db):
        db.upsert_document("/repo1", "/repo1/a.md", "A", "aaa", 1.0)
        db.upsert_document("/repo2", "/repo2/b.md", "B", "bbb", 2.0)
        docs = db.list_documents()
        assert len(docs) == 2

    def test_list_documents_filtered_by_repo(self, db):
        db.upsert_document("/repo1", "/repo1/a.md", "A", "aaa", 1.0)
        db.upsert_document("/repo2", "/repo2/b.md", "B", "bbb", 2.0)
        docs = db.list_documents(repo="/repo1")
        assert len(docs) == 1
        assert docs[0].repo == "/repo1"

    def test_list_documents_empty(self, db):
        docs = db.list_documents()
        assert docs == []

    def test_delete_document(self, db):
        doc_id = db.upsert_document("/repo", "/repo/f.md", "T", "c", 1.0)
        db.delete_document(doc_id)
        assert db.get_document(doc_id) is None

    def test_delete_document_cascades_chunks(self, db):
        doc_id = db.upsert_document("/repo", "/repo/f.md", "T", "c", 1.0)
        db.insert_chunks(doc_id, [(0, "chunk0", 0, 6)])
        db.delete_document(doc_id)
        chunks = db.get_chunks(doc_id)
        assert chunks == []

    def test_delete_document_cascades_images(self, db):
        doc_id = db.upsert_document("/repo", "/repo/f.md", "T", "c", 1.0)
        db.insert_images(doc_id, [("img.png", "/repo/img.png", "alt")])
        db.delete_document(doc_id)
        images = db.get_images(doc_id)
        assert images == []

    def test_get_content_hash(self, db):
        db.upsert_document("/repo", "/repo/f.md", "T", "content", 1.0)
        h = db.get_content_hash("/repo/f.md")
        assert h == content_hash("content")

    def test_get_content_hash_nonexistent(self, db):
        assert db.get_content_hash("/no/such/file.md") is None

    def test_get_all_paths(self, db):
        db.upsert_document("/repo", "/repo/a.md", "A", "aaa", 1.0)
        db.upsert_document("/repo", "/repo/b.md", "B", "bbb", 2.0)
        db.upsert_document("/other", "/other/c.md", "C", "ccc", 3.0)
        all_paths = db.get_all_paths()
        assert all_paths == {"/repo/a.md", "/repo/b.md", "/other/c.md"}

    def test_get_all_paths_filtered_by_repo(self, db):
        db.upsert_document("/repo", "/repo/a.md", "A", "aaa", 1.0)
        db.upsert_document("/other", "/other/c.md", "C", "ccc", 3.0)
        paths = db.get_all_paths(repo="/repo")
        assert paths == {"/repo/a.md"}


class TestChunkOperations:
    """Test CRUD operations on chunks."""

    def test_insert_chunks(self, db):
        doc_id = db.upsert_document("/repo", "/repo/f.md", "T", "content", 1.0)
        chunk_ids = db.insert_chunks(doc_id, [
            (0, "first chunk", 0, 11),
            (1, "second chunk", 11, 23),
        ])
        assert len(chunk_ids) == 2
        assert all(isinstance(cid, int) for cid in chunk_ids)

    def test_get_chunks_returns_ordered(self, db):
        doc_id = db.upsert_document("/repo", "/repo/f.md", "T", "content", 1.0)
        db.insert_chunks(doc_id, [
            (0, "first", 0, 5),
            (1, "second", 5, 11),
            (2, "third", 11, 16),
        ])
        chunks = db.get_chunks(doc_id)
        assert len(chunks) == 3
        assert chunks[0].chunk_index == 0
        assert chunks[1].chunk_index == 1
        assert chunks[2].chunk_index == 2

    def test_insert_chunks_replaces_existing(self, db):
        doc_id = db.upsert_document("/repo", "/repo/f.md", "T", "content", 1.0)
        db.insert_chunks(doc_id, [(0, "old chunk", 0, 9)])
        db.insert_chunks(doc_id, [(0, "new chunk", 0, 9)])
        chunks = db.get_chunks(doc_id)
        assert len(chunks) == 1
        assert chunks[0].content == "new chunk"

    def test_get_chunk_by_id(self, db):
        doc_id = db.upsert_document("/repo", "/repo/f.md", "T", "content", 1.0)
        chunk_ids = db.insert_chunks(doc_id, [(0, "the chunk", 0, 9)])
        chunk = db.get_chunk(chunk_ids[0])
        assert chunk is not None
        assert isinstance(chunk, ChunkRecord)
        assert chunk.content == "the chunk"
        assert chunk.document_id == doc_id

    def test_get_chunk_nonexistent(self, db):
        assert db.get_chunk(999) is None

    def test_get_chunks_empty(self, db):
        doc_id = db.upsert_document("/repo", "/repo/f.md", "T", "content", 1.0)
        chunks = db.get_chunks(doc_id)
        assert chunks == []


class TestImageOperations:
    """Test CRUD operations on images."""

    def test_insert_images(self, db):
        doc_id = db.upsert_document("/repo", "/repo/f.md", "T", "content", 1.0)
        db.insert_images(doc_id, [
            ("img.png", "/repo/img.png", "Alt text"),
            ("photo.jpg", "/repo/photo.jpg", ""),
        ])
        images = db.get_images(doc_id)
        assert len(images) == 2

    def test_insert_images_replaces_existing(self, db):
        doc_id = db.upsert_document("/repo", "/repo/f.md", "T", "content", 1.0)
        db.insert_images(doc_id, [("old.png", "/repo/old.png", "old")])
        db.insert_images(doc_id, [("new.png", "/repo/new.png", "new")])
        images = db.get_images(doc_id)
        assert len(images) == 1
        assert images[0].original_path == "new.png"

    def test_get_images_returns_image_records(self, db):
        doc_id = db.upsert_document("/repo", "/repo/f.md", "T", "content", 1.0)
        db.insert_images(doc_id, [("img.png", "/repo/img.png", "Alt")])
        images = db.get_images(doc_id)
        assert len(images) == 1
        img = images[0]
        assert isinstance(img, ImageRecord)
        assert img.original_path == "img.png"
        assert img.absolute_path == "/repo/img.png"
        assert img.alt_text == "Alt"

    def test_get_images_empty(self, db):
        doc_id = db.upsert_document("/repo", "/repo/f.md", "T", "content", 1.0)
        images = db.get_images(doc_id)
        assert images == []


class TestStats:
    """Test database statistics."""

    def test_stats_empty_db(self, db):
        stats = db.stats()
        assert stats["documents"] == 0
        assert stats["chunks"] == 0
        assert stats["images"] == 0
        assert stats["repos"] == []

    def test_stats_with_data(self, db):
        doc_id = db.upsert_document("/repo", "/repo/f.md", "T", "content", 1.0)
        db.insert_chunks(doc_id, [(0, "chunk", 0, 5)])
        db.insert_images(doc_id, [("i.png", "/repo/i.png", "")])
        stats = db.stats()
        assert stats["documents"] == 1
        assert stats["chunks"] == 1
        assert stats["images"] == 1
        assert stats["repos"] == ["/repo"]

    def test_stats_includes_db_path(self, db):
        stats = db.stats()
        assert "db_path" in stats
        assert isinstance(stats["db_path"], str)
