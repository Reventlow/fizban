"""Tests for repository management module."""

import subprocess
from pathlib import Path
from unittest import mock

from fizban.config import Config
from fizban.repos import pull_all, scan_repo


class TestScanRepo:
    """Test markdown file discovery in repositories."""

    def test_scan_finds_markdown_files(self, tmp_path):
        (tmp_path / "doc.md").write_text("# Hello")
        (tmp_path / "readme.md").write_text("# Readme")
        files = scan_repo(str(tmp_path))
        assert len(files) == 2
        assert all(f.suffix == ".md" for f in files)

    def test_scan_finds_nested_files(self, tmp_path):
        sub = tmp_path / "sub" / "deep"
        sub.mkdir(parents=True)
        (sub / "nested.md").write_text("# Nested")
        files = scan_repo(str(tmp_path))
        assert len(files) == 1
        assert files[0].name == "nested.md"

    def test_scan_ignores_non_markdown(self, tmp_path):
        (tmp_path / "doc.md").write_text("# Doc")
        (tmp_path / "script.py").write_text("print('hi')")
        (tmp_path / "data.json").write_text("{}")
        files = scan_repo(str(tmp_path))
        assert len(files) == 1
        assert files[0].name == "doc.md"

    def test_scan_nonexistent_path_returns_empty(self):
        files = scan_repo("/nonexistent/path/that/does/not/exist")
        assert files == []

    def test_scan_empty_directory(self, tmp_path):
        files = scan_repo(str(tmp_path))
        assert files == []

    def test_scan_returns_sorted(self, tmp_path):
        (tmp_path / "c.md").write_text("c")
        (tmp_path / "a.md").write_text("a")
        (tmp_path / "b.md").write_text("b")
        files = scan_repo(str(tmp_path))
        names = [f.name for f in files]
        assert names == sorted(names)

    def test_scan_returns_absolute_paths(self, tmp_path):
        (tmp_path / "doc.md").write_text("# Doc")
        files = scan_repo(str(tmp_path))
        assert all(f.is_absolute() for f in files)


class TestPullAll:
    """Test git pull operations across configured repos."""

    def test_pull_nonexistent_path(self, tmp_path):
        cfg = Config()
        cfg.repos = [str(tmp_path / "nonexistent")]
        results = pull_all(cfg)
        assert "error: path does not exist" in results[cfg.repos[0]]

    def test_pull_not_a_git_repo(self, tmp_path):
        cfg = Config()
        cfg.repos = [str(tmp_path)]
        results = pull_all(cfg)
        assert "skipped: not a git repo" in results[cfg.repos[0]]

    def test_pull_success(self, tmp_path):
        # Create a fake .git directory
        (tmp_path / ".git").mkdir()
        cfg = Config()
        cfg.repos = [str(tmp_path)]

        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Already up to date."

        with mock.patch("fizban.repos.subprocess.run", return_value=mock_result) as mock_run:
            results = pull_all(cfg)

        assert results[str(tmp_path)] == "ok"
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert call_args[0][0] == ["git", "-C", str(tmp_path), "pull", "--ff-only"]

    def test_pull_git_error(self, tmp_path):
        (tmp_path / ".git").mkdir()
        cfg = Config()
        cfg.repos = [str(tmp_path)]

        mock_result = mock.Mock()
        mock_result.returncode = 1
        mock_result.stderr = "fatal: not a git repository"

        with mock.patch("fizban.repos.subprocess.run", return_value=mock_result):
            results = pull_all(cfg)

        assert "error:" in results[str(tmp_path)]

    def test_pull_timeout(self, tmp_path):
        (tmp_path / ".git").mkdir()
        cfg = Config()
        cfg.repos = [str(tmp_path)]

        with mock.patch(
            "fizban.repos.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=60),
        ):
            results = pull_all(cfg)

        assert results[str(tmp_path)] == "error: timeout"

    def test_pull_multiple_repos(self, tmp_path):
        repo1 = tmp_path / "repo1"
        repo2 = tmp_path / "repo2"
        repo1.mkdir()
        repo2.mkdir()
        (repo1 / ".git").mkdir()
        (repo2 / ".git").mkdir()

        cfg = Config()
        cfg.repos = [str(repo1), str(repo2)]

        mock_result = mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Already up to date."

        with mock.patch("fizban.repos.subprocess.run", return_value=mock_result):
            results = pull_all(cfg)

        assert len(results) == 2
        assert results[str(repo1)] == "ok"
        assert results[str(repo2)] == "ok"

    def test_pull_empty_repos_list(self):
        cfg = Config()
        cfg.repos = []
        results = pull_all(cfg)
        assert results == {}
