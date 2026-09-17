from agent_platform.application.chunking import (
    ChunkingStrategyName,
    HeadingAwareChunker,
    HierarchicalChunker,
    PageAwareChunker,
    ParagraphChunker,
    build_chunker,
)


def test_fixed_is_default_strategy():
    chunker = build_chunker(chunk_size=40, overlap=5)
    assert chunker.name is ChunkingStrategyName.FIXED
    chunks = chunker.split("A sentence. " * 20)
    assert len(chunks) > 1
    assert all(chunk.metadata["chunking_strategy"] == "fixed-v1" for chunk in chunks)


def test_paragraph_strategy_preserves_paragraph_boundaries():
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    chunks = ParagraphChunker(chunk_size=35, overlap=5).split(text)
    assert len(chunks) >= 2
    assert all(chunk.metadata["chunking_strategy"] == "paragraph-v1" for chunk in chunks)


def test_heading_strategy_records_heading_metadata():
    text = "# Architecture\n\nOpenShift and GitOps.\n\n## Security\n\nVault and policies."
    chunks = HeadingAwareChunker(chunk_size=80, overlap=10).split(text)
    headings = {chunk.metadata.get("heading") for chunk in chunks}
    assert "Architecture" in headings
    assert "Security" in headings


def test_page_strategy_never_crosses_pdf_page_marker():
    chunks = PageAwareChunker(chunk_size=100, overlap=10).split("Page one text.\n\f\nPage two text.")
    assert {chunk.metadata["page"] for chunk in chunks} == {1, 2}
    assert all("Page one" not in chunk.content or "Page two" not in chunk.content for chunk in chunks)


def test_hierarchical_strategy_creates_parent_and_child_levels():
    chunks = HierarchicalChunker(parent_size=100, child_size=35, child_overlap=5).split("Architecture and platform engineering. " * 20)
    parents = [chunk for chunk in chunks if chunk.metadata["hierarchy_level"] == "parent"]
    children = [chunk for chunk in chunks if chunk.metadata["hierarchy_level"] == "child"]
    assert parents and children
    assert all(not chunk.embed for chunk in parents)
    assert all(chunk.embed for chunk in children)
    assert {chunk.metadata["parent_index"] for chunk in children}.issubset({chunk.metadata["parent_index"] for chunk in parents})
