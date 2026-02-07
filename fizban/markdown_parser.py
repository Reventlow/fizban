"""Markdown parser with image extraction."""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ImageRef:
    """Reference to an image found in a markdown document."""

    original_path: str
    absolute_path: str
    alt_text: str


@dataclass
class ParsedDocument:
    """Result of parsing a markdown document."""

    title: str
    content: str
    images: list[ImageRef]


def extract_title(content: str) -> str:
    """Extract the first H1 heading from markdown content."""
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    # Fall back to first non-empty line
    for line in content.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:100]
    return "Untitled"


def extract_images(content: str, file_path: Path) -> list[ImageRef]:
    """Extract image references from markdown and resolve relative paths.

    Handles both ![alt](path) and ![alt](path "title") syntax.
    """
    images = []
    pattern = r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)'

    for match in re.finditer(pattern, content):
        alt_text = match.group(1)
        img_path = match.group(2)

        # Skip URLs
        if img_path.startswith(('http://', 'https://', 'data:')):
            continue

        # Resolve relative path against the markdown file's directory
        absolute_path = str((file_path.parent / img_path).resolve())

        images.append(ImageRef(
            original_path=img_path,
            absolute_path=absolute_path,
            alt_text=alt_text,
        ))

    return images


def parse_markdown(content: str, file_path: Path) -> ParsedDocument:
    """Parse a markdown document, extracting metadata and image references.

    Args:
        content: Raw markdown text.
        file_path: Absolute path to the markdown file (for resolving relative image paths).

    Returns:
        ParsedDocument with title, content, and image references.
    """
    title = extract_title(content)
    images = extract_images(content, file_path)
    return ParsedDocument(title=title, content=content, images=images)
