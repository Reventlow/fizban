"""Abstract base class for vector storage backends."""

from abc import ABC, abstractmethod
import numpy as np


class VectorBackend(ABC):
    """Interface for vector storage and similarity search.

    All implementations store vectors keyed by chunk_id (integer)
    and support nearest-neighbor search.
    """

    @abstractmethod
    def init_index(self, dimension: int) -> None:
        """Create or initialize the vector index.

        Args:
            dimension: The dimensionality of the vectors (e.g., 384).
        """

    @abstractmethod
    def add_vectors(self, ids: list[int], vectors: np.ndarray) -> None:
        """Add vectors to the index.

        Args:
            ids: List of chunk IDs.
            vectors: numpy array of shape (len(ids), dimension).
        """

    @abstractmethod
    def delete_vectors(self, ids: list[int]) -> None:
        """Remove vectors by their chunk IDs."""

    @abstractmethod
    def search(self, query_vector: np.ndarray, limit: int = 10) -> list[tuple[int, float]]:
        """Find the nearest vectors to the query.

        Args:
            query_vector: numpy array of shape (dimension,).
            limit: Maximum number of results.

        Returns:
            List of (chunk_id, distance) tuples, ordered by ascending distance.
        """

    @abstractmethod
    def count(self) -> int:
        """Return the number of vectors in the index."""

    @abstractmethod
    def clear(self) -> None:
        """Remove all vectors from the index."""
