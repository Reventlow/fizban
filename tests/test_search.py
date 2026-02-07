"""Tests for semantic search module."""

from unittest import mock

import numpy as np

from fizban.config import Config
from fizban.db import ChunkRecord, DocumentRecord
from fizban.search import SearchResult, semantic_search


class TestSearchResult:
    """Test SearchResult dataclass."""

    def test_search_result_fields(self):
        result = SearchResult(
            chunk_id=1, document_id=2, document_path="/repo/doc.md",
            document_title="Doc", repo="/repo", chunk_content="text",
            chunk_index=0, distance=0.5,
        )
        assert result.chunk_id == 1
        assert result.document_id == 2
        assert result.distance == 0.5


class TestSemanticSearch:
    """Test semantic_search function with mocked dependencies."""

    def _make_config(self):
        cfg = Config()
        cfg.db_path = "/tmp/test_search.db"
        return cfg

    @mock.patch("fizban.search.get_vector_backend")
    @mock.patch("fizban.search.EmbeddingModel")
    @mock.patch("fizban.search.Database")
    def test_search_returns_results(self, MockDatabase, MockEmbeddings, MockVector):
        cfg = self._make_config()

        # Set up mock embeddings
        mock_emb_instance = MockEmbeddings.return_value
        mock_emb_instance.encode_query.return_value = np.zeros(384)

        # Set up mock vector backend
        mock_vec_instance = MockVector.return_value
        mock_vec_instance.search.return_value = [(10, 0.1), (20, 0.2)]

        # Set up mock database
        mock_db_instance = MockDatabase.return_value
        mock_db_instance.get_chunk.side_effect = lambda cid: {
            10: ChunkRecord(id=10, document_id=1, chunk_index=0, content="chunk A", start_char=0, end_char=7),
            20: ChunkRecord(id=20, document_id=2, chunk_index=0, content="chunk B", start_char=0, end_char=7),
        }.get(cid)
        mock_db_instance.get_document.side_effect = lambda did: {
            1: DocumentRecord(id=1, repo="/repo", path="/repo/a.md", title="Doc A",
                              content="full A", content_hash="h1", last_modified=1.0, indexed_at=1.0),
            2: DocumentRecord(id=2, repo="/repo", path="/repo/b.md", title="Doc B",
                              content="full B", content_hash="h2", last_modified=2.0, indexed_at=2.0),
        }.get(did)

        results = semantic_search("test query", config=cfg, limit=5)

        assert len(results) == 2
        assert isinstance(results[0], SearchResult)
        assert results[0].chunk_id == 10
        assert results[0].document_title == "Doc A"
        assert results[0].distance == 0.1
        assert results[1].chunk_id == 20
        assert results[1].distance == 0.2

    @mock.patch("fizban.search.get_vector_backend")
    @mock.patch("fizban.search.EmbeddingModel")
    @mock.patch("fizban.search.Database")
    def test_search_skips_missing_chunks(self, MockDatabase, MockEmbeddings, MockVector):
        cfg = self._make_config()

        mock_emb_instance = MockEmbeddings.return_value
        mock_emb_instance.encode_query.return_value = np.zeros(384)

        mock_vec_instance = MockVector.return_value
        mock_vec_instance.search.return_value = [(10, 0.1), (999, 0.2)]

        mock_db_instance = MockDatabase.return_value
        mock_db_instance.get_chunk.side_effect = lambda cid: (
            ChunkRecord(id=10, document_id=1, chunk_index=0, content="chunk", start_char=0, end_char=5)
            if cid == 10 else None
        )
        mock_db_instance.get_document.return_value = DocumentRecord(
            id=1, repo="/repo", path="/repo/a.md", title="Doc A",
            content="full", content_hash="h", last_modified=1.0, indexed_at=1.0,
        )

        results = semantic_search("query", config=cfg)
        assert len(results) == 1
        assert results[0].chunk_id == 10

    @mock.patch("fizban.search.get_vector_backend")
    @mock.patch("fizban.search.EmbeddingModel")
    @mock.patch("fizban.search.Database")
    def test_search_skips_missing_documents(self, MockDatabase, MockEmbeddings, MockVector):
        cfg = self._make_config()

        mock_emb_instance = MockEmbeddings.return_value
        mock_emb_instance.encode_query.return_value = np.zeros(384)

        mock_vec_instance = MockVector.return_value
        mock_vec_instance.search.return_value = [(10, 0.1)]

        mock_db_instance = MockDatabase.return_value
        mock_db_instance.get_chunk.return_value = ChunkRecord(
            id=10, document_id=999, chunk_index=0, content="orphan", start_char=0, end_char=6,
        )
        mock_db_instance.get_document.return_value = None

        results = semantic_search("query", config=cfg)
        assert len(results) == 0

    @mock.patch("fizban.search.get_vector_backend")
    @mock.patch("fizban.search.EmbeddingModel")
    @mock.patch("fizban.search.Database")
    def test_search_empty_results(self, MockDatabase, MockEmbeddings, MockVector):
        cfg = self._make_config()

        mock_emb_instance = MockEmbeddings.return_value
        mock_emb_instance.encode_query.return_value = np.zeros(384)

        mock_vec_instance = MockVector.return_value
        mock_vec_instance.search.return_value = []

        results = semantic_search("query", config=cfg)
        assert results == []

    @mock.patch("fizban.search.get_vector_backend")
    @mock.patch("fizban.search.EmbeddingModel")
    @mock.patch("fizban.search.Database")
    def test_search_passes_limit(self, MockDatabase, MockEmbeddings, MockVector):
        cfg = self._make_config()

        mock_emb_instance = MockEmbeddings.return_value
        mock_emb_instance.encode_query.return_value = np.zeros(384)

        mock_vec_instance = MockVector.return_value
        mock_vec_instance.search.return_value = []

        semantic_search("query", config=cfg, limit=3)

        mock_vec_instance.search.assert_called_once_with(mock.ANY, limit=3)
