"""Embedding generation using sentence-transformers."""

import logging
import numpy as np
from fizban.config import Config, get_config

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """Wrapper around sentence-transformers for generating embeddings.

    The model is loaded lazily on first use.
    """

    def __init__(self, config: Config | None = None):
        self.config = config or get_config()
        self._model = None

    @property
    def dimension(self) -> int:
        """Return the embedding dimension for the configured model."""
        # all-MiniLM-L6-v2 produces 384-dim vectors
        # Load model to get actual dimension if using a different model
        if self._model is not None:
            return self._model.get_sentence_embedding_dimension()
        # Default for all-MiniLM-L6-v2
        if "MiniLM-L6" in self.config.embedding_model:
            return 384
        # Must load model to determine dimension
        return self._ensure_model().get_sentence_embedding_dimension()

    def _ensure_model(self):
        """Load the model if not already loaded."""
        if self._model is None:
            logger.info("Loading embedding model: %s", self.config.embedding_model)
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.config.embedding_model)
            logger.info("Model loaded (dimension=%d)", self._model.get_sentence_embedding_dimension())
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        """Encode a list of texts into embeddings.

        Args:
            texts: List of text strings to encode.

        Returns:
            numpy array of shape (len(texts), dimension).
        """
        if not texts:
            return np.array([]).reshape(0, self.dimension)
        model = self._ensure_model()
        embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        return embeddings

    def encode_query(self, query: str) -> np.ndarray:
        """Encode a single query text.

        Args:
            query: Search query string.

        Returns:
            numpy array of shape (dimension,).
        """
        result = self.encode([query])
        return result[0]
