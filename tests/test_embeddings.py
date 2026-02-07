"""Tests for embedding model module."""

from unittest import mock

import numpy as np
import pytest

from fizban.config import Config
from fizban.embeddings import EmbeddingModel


class TestEmbeddingModelDimension:
    """Test dimension detection logic."""

    def test_default_model_dimension_without_loading(self):
        """MiniLM-L6 returns 384 without loading the model."""
        cfg = Config()
        cfg.embedding_model = "all-MiniLM-L6-v2"
        model = EmbeddingModel(cfg)
        assert model.dimension == 384

    def test_model_not_loaded_for_known_dimension(self):
        """For known models, dimension should not trigger model loading."""
        cfg = Config()
        cfg.embedding_model = "all-MiniLM-L6-v2"
        model = EmbeddingModel(cfg)
        _ = model.dimension
        assert model._model is None

    def test_loaded_model_returns_actual_dimension(self):
        cfg = Config()
        model = EmbeddingModel(cfg)
        mock_model = mock.Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 768
        model._model = mock_model
        assert model.dimension == 768


class TestEmbeddingModelEncode:
    """Test encoding with mocked sentence-transformers."""

    @mock.patch("fizban.embeddings.SentenceTransformer", create=True)
    def test_encode_returns_numpy_array(self, MockST):
        mock_model = MockST.return_value
        mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3]])
        mock_model.get_sentence_embedding_dimension.return_value = 3

        with mock.patch.dict("sys.modules", {"sentence_transformers": mock.Mock(SentenceTransformer=MockST)}):
            cfg = Config()
            emb = EmbeddingModel(cfg)
            emb._model = mock_model
            result = emb.encode(["hello world"])

        assert isinstance(result, np.ndarray)
        assert result.shape == (1, 3)

    def test_encode_empty_list(self):
        cfg = Config()
        cfg.embedding_model = "all-MiniLM-L6-v2"
        emb = EmbeddingModel(cfg)
        result = emb.encode([])
        assert isinstance(result, np.ndarray)
        assert result.shape == (0, 384)

    def test_encode_query_returns_1d(self):
        cfg = Config()
        emb = EmbeddingModel(cfg)
        mock_model = mock.Mock()
        mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3]])
        mock_model.get_sentence_embedding_dimension.return_value = 3
        emb._model = mock_model

        result = emb.encode_query("test query")
        assert result.shape == (3,)
