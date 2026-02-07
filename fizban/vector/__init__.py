"""Vector backend factory."""

from fizban.config import Config, get_config
from fizban.vector.base import VectorBackend


def get_vector_backend(config: Config | None = None) -> VectorBackend:
    """Create and return the configured vector backend.

    Tries the configured backend first, falls back to the other if unavailable.
    """
    config = config or get_config()
    backend_type = config.vector_backend.lower()

    if backend_type == "vec":
        try:
            from fizban.vector.vec_backend import SqliteVecBackend
            return SqliteVecBackend(config)
        except ImportError:
            import logging
            logging.getLogger(__name__).warning(
                "sqlite-vec not available, falling back to vss"
            )
            from fizban.vector.vss_backend import SqliteVssBackend
            return SqliteVssBackend(config)
    elif backend_type == "vss":
        try:
            from fizban.vector.vss_backend import SqliteVssBackend
            return SqliteVssBackend(config)
        except ImportError:
            import logging
            logging.getLogger(__name__).warning(
                "sqlite-vss not available, falling back to vec"
            )
            from fizban.vector.vec_backend import SqliteVecBackend
            return SqliteVecBackend(config)
    else:
        raise ValueError(f"Unknown vector backend: {backend_type!r}. Use 'vec' or 'vss'.")
