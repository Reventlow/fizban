"""Configuration system for Fizban."""

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    """Fizban configuration loaded from environment variables."""

    db_path: Path = field(default_factory=lambda: Path(
        os.environ.get("FIZBAN_DB_PATH",
                       str(Path.home() / ".local" / "share" / "fizban" / "fizban.db"))
    ))
    vector_backend: str = field(default_factory=lambda:
        os.environ.get("FIZBAN_VECTOR_BACKEND", "vec")
    )
    embedding_model: str = field(default_factory=lambda:
        os.environ.get("FIZBAN_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    )
    chunk_size: int = field(default_factory=lambda:
        int(os.environ.get("FIZBAN_CHUNK_SIZE", "1000"))
    )
    chunk_overlap: int = field(default_factory=lambda:
        int(os.environ.get("FIZBAN_CHUNK_OVERLAP", "200"))
    )
    repos: list[str] = field(default_factory=lambda: [
        "/home/gorm/Documents/Fynbus_Guides",
        "/home/gorm/Documents/infrastructure",
        "/home/gorm/Documents/infrastructure-as-code",
    ])

    def ensure_db_dir(self) -> None:
        """Create the database directory if it doesn't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)


_config: Config | None = None


def get_config() -> Config:
    """Get or create the singleton configuration."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reset_config() -> None:
    """Reset the configuration singleton (useful for testing)."""
    global _config
    _config = None
