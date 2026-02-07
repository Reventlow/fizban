"""Tests for indexer module helper functions."""

from pathlib import Path

from fizban.indexer import _identify_repo


class TestIdentifyRepo:
    """Test repo identification from file paths."""

    def test_match_first_repo(self):
        repos = ["/home/user/docs", "/home/user/infra"]
        result = _identify_repo(Path("/home/user/docs/guide.md"), repos)
        assert result == "/home/user/docs"

    def test_match_second_repo(self):
        repos = ["/home/user/docs", "/home/user/infra"]
        result = _identify_repo(Path("/home/user/infra/setup.md"), repos)
        assert result == "/home/user/infra"

    def test_nested_file_matches_repo(self):
        repos = ["/home/user/docs"]
        result = _identify_repo(Path("/home/user/docs/sub/deep/file.md"), repos)
        assert result == "/home/user/docs"

    def test_no_match_returns_parent_dir(self):
        repos = ["/home/user/docs"]
        result = _identify_repo(Path("/other/place/file.md"), repos)
        assert result == "/other/place"

    def test_empty_repos_returns_parent(self):
        result = _identify_repo(Path("/some/file.md"), [])
        assert result == "/some"
