"""Tests for text chunking."""

from fizban.indexer import chunk_text


class TestChunkText:
    def test_empty_text(self):
        assert chunk_text("") == []

    def test_short_text_single_chunk(self):
        text = "Hello, world!"
        chunks = chunk_text(text, chunk_size=100)
        assert len(chunks) == 1
        assert chunks[0] == (text, 0, len(text))

    def test_exact_chunk_size(self):
        text = "x" * 1000
        chunks = chunk_text(text, chunk_size=1000)
        assert len(chunks) == 1

    def test_multiple_chunks(self):
        text = "word " * 400  # 2000 chars
        chunks = chunk_text(text, chunk_size=500, chunk_overlap=100)
        assert len(chunks) > 1
        # Verify all text is covered
        full_text = ""
        prev_end = 0
        for content, start, end in chunks:
            assert content == text[start:end]
            assert start <= prev_end or start == 0  # Overlap or first chunk
            prev_end = end

    def test_overlap_exists(self):
        text = "a" * 2000
        chunks = chunk_text(text, chunk_size=1000, chunk_overlap=200)
        if len(chunks) >= 2:
            _, _, end1 = chunks[0]
            _, start2, _ = chunks[1]
            assert start2 < end1  # Overlap

    def test_chunks_cover_all_content(self):
        text = "The quick brown fox jumps over the lazy dog. " * 50
        chunks = chunk_text(text, chunk_size=200, chunk_overlap=50)
        # Every character should be in at least one chunk
        covered = set()
        for content, start, end in chunks:
            covered.update(range(start, end))
        assert covered == set(range(len(text)))

    def test_prefers_paragraph_breaks(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = chunk_text(text, chunk_size=30, chunk_overlap=5)
        # Should try to break at paragraph boundaries
        assert len(chunks) >= 2

    def test_no_empty_chunks(self):
        text = "Some content here. " * 100
        chunks = chunk_text(text, chunk_size=200, chunk_overlap=50)
        for content, start, end in chunks:
            assert len(content) > 0
            assert end > start
