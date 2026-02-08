"""Markdown parser with image extraction."""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


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


def extract_images(content: str, file_path: Path, repo_root: Path | None = None) -> list[ImageRef]:
    """Extract image references from markdown and resolve relative paths.

    Handles both ![alt](path) and ![alt](path "title") syntax.
    Resolved paths are validated to stay within repo_root to prevent
    path traversal attacks (e.g. ../../etc/passwd).

    Args:
        content: Raw markdown text.
        file_path: Absolute path to the markdown file.
        repo_root: Root directory of the repository. If provided, images
            resolving outside this directory are skipped.
    """
    images = []
    pattern = r'!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)'

    # Resolve repo_root once for consistent comparison
    resolved_root = repo_root.resolve() if repo_root else None

    for match in re.finditer(pattern, content):
        alt_text = match.group(1)
        img_path = match.group(2)

        # Skip URLs
        if img_path.startswith(('http://', 'https://', 'data:')):
            continue

        # Resolve relative path against the markdown file's directory
        resolved = (file_path.parent / img_path).resolve()

        # Validate the resolved path stays within the repo boundary
        if resolved_root is not None:
            try:
                resolved.relative_to(resolved_root)
            except ValueError:
                logger.warning(
                    "Skipping image with path traversal outside repo: %s (resolved to %s)",
                    img_path, resolved,
                )
                continue

        images.append(ImageRef(
            original_path=img_path,
            absolute_path=str(resolved),
            alt_text=alt_text,
        ))

    return images


def parse_markdown(content: str, file_path: Path, repo_root: Path | None = None) -> ParsedDocument:
    """Parse a markdown document, extracting metadata and image references.

    Args:
        content: Raw markdown text.
        file_path: Absolute path to the markdown file (for resolving relative image paths).
        repo_root: Root directory of the repository (for sandboxing image paths).

    Returns:
        ParsedDocument with title, content, and image references.
    """
    title = extract_title(content)
    images = extract_images(content, file_path, repo_root=repo_root)
    return ParsedDocument(title=title, content=content, images=images)
