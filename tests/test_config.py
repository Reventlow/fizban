"""Tests for configuration module."""

import os
from pathlib import Path
from unittest import mock

from fizban.config import Config, get_config, reset_config


class TestConfigDefaults:
    """Test that Config uses correct defaults when no env vars are set."""

    def test_default_db_path(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = Config()
        expected = Path.home() / ".local" / "share" / "fizban" / "fizban.db"
        assert cfg.db_path == expected

    def test_default_vector_backend(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = Config()
        assert cfg.vector_backend == "vec"

    def test_default_embedding_model(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = Config()
        assert cfg.embedding_model == "all-MiniLM-L6-v2"

    def test_default_chunk_size(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = Config()
        assert cfg.chunk_size == 1000

    def test_default_chunk_overlap(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = Config()
        assert cfg.chunk_overlap == 200

    def test_default_repos_is_list(self):
        cfg = Config()
        assert isinstance(cfg.repos, list)
        assert len(cfg.repos) == 3


class TestConfigEnvOverrides:
    """Test that env vars override default values."""

    def test_db_path_from_env(self):
        with mock.patch.dict(os.environ, {"FIZBAN_DB_PATH": "/tmp/test.db"}):
            cfg = Config()
        assert cfg.db_path == Path("/tmp/test.db")

    def test_vector_backend_from_env(self):
        with mock.patch.dict(os.environ, {"FIZBAN_VECTOR_BACKEND": "vss"}):
            cfg = Config()
        assert cfg.vector_backend == "vss"

    def test_embedding_model_from_env(self):
        with mock.patch.dict(os.environ, {"FIZBAN_EMBEDDING_MODEL": "custom-model"}):
            cfg = Config()
        assert cfg.embedding_model == "custom-model"

    def test_chunk_size_from_env(self):
        with mock.patch.dict(os.environ, {"FIZBAN_CHUNK_SIZE": "500"}):
            cfg = Config()
        assert cfg.chunk_size == 500

    def test_chunk_overlap_from_env(self):
        with mock.patch.dict(os.environ, {"FIZBAN_CHUNK_OVERLAP": "100"}):
            cfg = Config()
        assert cfg.chunk_overlap == 100


class TestConfigEnsureDbDir:
    """Test the ensure_db_dir method."""

    def test_ensure_db_dir_creates_parent(self, tmp_path):
        cfg = Config()
        cfg.db_path = tmp_path / "subdir" / "nested" / "fizban.db"
        cfg.ensure_db_dir()
        assert cfg.db_path.parent.exists()

    def test_ensure_db_dir_existing_dir_no_error(self, tmp_path):
        cfg = Config()
        cfg.db_path = tmp_path / "fizban.db"
        cfg.ensure_db_dir()  # Should not raise
        cfg.ensure_db_dir()  # Call again, still no error


class TestSingleton:
    """Test the get_config/reset_config singleton pattern."""

    def setup_method(self):
        reset_config()

    def teardown_method(self):
        reset_config()

    def test_get_config_returns_same_instance(self):
        cfg1 = get_config()
        cfg2 = get_config()
        assert cfg1 is cfg2

    def test_reset_config_clears_singleton(self):
        cfg1 = get_config()
        reset_config()
        cfg2 = get_config()
        assert cfg1 is not cfg2

    def test_get_config_returns_config_instance(self):
        cfg = get_config()
        assert isinstance(cfg, Config)
