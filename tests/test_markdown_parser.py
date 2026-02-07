"""Tests for markdown parser."""

from pathlib import Path

from fizban.markdown_parser import extract_images, extract_title, parse_markdown


class TestExtractTitle:
    def test_h1_title(self):
        assert extract_title("# My Title\n\nContent here") == "My Title"

    def test_h1_with_extra_spaces(self):
        assert extract_title("#   Spaced Title  \n") == "Spaced Title"

    def test_no_h1_uses_first_line(self):
        assert extract_title("Some content\nMore content") == "Some content"

    def test_empty_content(self):
        assert extract_title("") == "Untitled"

    def test_blank_lines_only(self):
        assert extract_title("\n\n\n") == "Untitled"

    def test_h2_not_matched_as_title(self):
        content = "## Subtitle\n# Real Title"
        assert extract_title(content) == "Real Title"


class TestExtractImages:
    def test_basic_image(self):
        content = "![Alt text](image.png)"
        images = extract_images(content, Path("/repo/docs/file.md"))
        assert len(images) == 1
        assert images[0].alt_text == "Alt text"
        assert images[0].original_path == "image.png"
        assert images[0].absolute_path == "/repo/docs/image.png"

    def test_relative_path(self):
        content = "![](../assets/photo.jpg)"
        images = extract_images(content, Path("/repo/docs/sub/file.md"))
        assert len(images) == 1
        assert images[0].absolute_path == "/repo/docs/assets/photo.jpg"

    def test_http_url_skipped(self):
        content = "![Logo](https://example.com/logo.png)"
        images = extract_images(content, Path("/repo/file.md"))
        assert len(images) == 0

    def test_data_url_skipped(self):
        content = "![](data:image/png;base64,abc123)"
        images = extract_images(content, Path("/repo/file.md"))
        assert len(images) == 0

    def test_image_with_title(self):
        content = '![Alt](image.png "My Title")'
        images = extract_images(content, Path("/repo/file.md"))
        assert len(images) == 1
        assert images[0].original_path == "image.png"

    def test_multiple_images(self):
        content = "![A](a.png)\nSome text\n![B](b.png)"
        images = extract_images(content, Path("/repo/file.md"))
        assert len(images) == 2
        assert images[0].alt_text == "A"
        assert images[1].alt_text == "B"

    def test_empty_alt_text(self):
        content = "![](diagram.svg)"
        images = extract_images(content, Path("/repo/file.md"))
        assert len(images) == 1
        assert images[0].alt_text == ""

    def test_nested_directory_image(self):
        content = "![](./images/screenshots/ui.png)"
        images = extract_images(content, Path("/repo/docs/guide.md"))
        assert len(images) == 1
        assert images[0].absolute_path == "/repo/docs/images/screenshots/ui.png"


class TestParseMarkdown:
    def test_full_parse(self):
        content = "# Guide\n\nSome text.\n\n![Diagram](img/arch.png)\n\nMore text."
        result = parse_markdown(content, Path("/repo/docs/guide.md"))
        assert result.title == "Guide"
        assert result.content == content
        assert len(result.images) == 1
        assert result.images[0].absolute_path == "/repo/docs/img/arch.png"

    def test_no_images(self):
        content = "# Plain\n\nJust text."
        result = parse_markdown(content, Path("/repo/file.md"))
        assert result.title == "Plain"
        assert len(result.images) == 0
