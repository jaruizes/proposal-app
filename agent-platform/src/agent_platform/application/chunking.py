from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class ChunkingStrategyName(StrEnum):
    FIXED = "fixed"
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    PAGE = "page"
    HIERARCHICAL = "hierarchical"


@dataclass(frozen=True)
class ChunkCandidate:
    content: str
    start: int
    end: int
    metadata: dict[str, object] = field(default_factory=dict)
    embed: bool = True


class ChunkingStrategy(Protocol):
    name: ChunkingStrategyName

    def split(self, text: str) -> list[ChunkCandidate]: ...


def _validate_size(chunk_size: int, overlap: int) -> None:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")


class FixedChunker:
    name = ChunkingStrategyName.FIXED

    def __init__(self, *, chunk_size: int = 1200, overlap: int = 200) -> None:
        _validate_size(chunk_size, overlap)
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[ChunkCandidate]:
        if not text:
            return []
        chunks: list[ChunkCandidate] = []
        start = 0
        length = len(text)
        while start < length:
            hard_end = min(start + self.chunk_size, length)
            end = hard_end
            if hard_end < length:
                paragraph_break = text.rfind("\n\n", start + self.chunk_size // 2, hard_end)
                sentence_break = text.rfind(". ", start + self.chunk_size // 2, hard_end)
                if paragraph_break > start:
                    end = paragraph_break + 2
                elif sentence_break > start:
                    end = sentence_break + 2
            content = text[start:end].strip()
            if content:
                chunks.append(ChunkCandidate(content, start, end, {"chunking_strategy": "fixed-v1"}))
            if end >= length:
                break
            start = max(end - self.overlap, start + 1)
        return chunks


class ParagraphChunker:
    name = ChunkingStrategyName.PARAGRAPH

    def __init__(self, *, chunk_size: int = 1200, overlap: int = 200) -> None:
        _validate_size(chunk_size, overlap)
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[ChunkCandidate]:
        if not text:
            return []
        paragraphs = [(m.group(0).strip(), m.start(), m.end()) for m in re.finditer(r"[^\n].*?(?=\n\s*\n|\Z)", text, re.S) if m.group(0).strip()]
        chunks: list[ChunkCandidate] = []
        current: list[tuple[str, int, int]] = []
        current_len = 0

        def flush() -> None:
            nonlocal current, current_len
            if not current:
                return
            start, end = current[0][1], current[-1][2]
            chunks.append(ChunkCandidate("\n\n".join(item[0] for item in current), start, end, {"chunking_strategy": "paragraph-v1"}))
            current = []
            current_len = 0

        for content, start, end in paragraphs:
            if len(content) > self.chunk_size:
                flush()
                for candidate in FixedChunker(chunk_size=self.chunk_size, overlap=self.overlap).split(content):
                    chunks.append(ChunkCandidate(candidate.content, start + candidate.start, start + candidate.end, {"chunking_strategy": "paragraph-v1", "oversized_paragraph": True}))
                continue
            projected = current_len + (2 if current else 0) + len(content)
            if current and projected > self.chunk_size:
                flush()
            current.append((content, start, end))
            current_len += (2 if current_len else 0) + len(content)
        flush()
        return chunks


class HeadingAwareChunker:
    name = ChunkingStrategyName.HEADING

    def __init__(self, *, chunk_size: int = 1200, overlap: int = 200) -> None:
        _validate_size(chunk_size, overlap)
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[ChunkCandidate]:
        matches = list(re.finditer(r"(?m)^(#{1,6})\s+(.+?)\s*$", text))
        if not matches:
            return [ChunkCandidate(c.content, c.start, c.end, {**c.metadata, "chunking_strategy": "heading-v1", "heading": None}, c.embed) for c in ParagraphChunker(chunk_size=self.chunk_size, overlap=self.overlap).split(text)]
        chunks: list[ChunkCandidate] = []
        if matches[0].start() > 0 and text[:matches[0].start()].strip():
            prefix = text[:matches[0].start()]
            for candidate in FixedChunker(chunk_size=self.chunk_size, overlap=self.overlap).split(prefix):
                chunks.append(ChunkCandidate(candidate.content, candidate.start, candidate.end, {"chunking_strategy": "heading-v1", "heading": None}))
        for index, match in enumerate(matches):
            section_start = match.start()
            section_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            section = text[section_start:section_end].strip()
            heading = match.group(2).strip()
            level = len(match.group(1))
            for candidate in FixedChunker(chunk_size=self.chunk_size, overlap=self.overlap).split(section):
                chunks.append(ChunkCandidate(candidate.content, section_start + candidate.start, section_start + candidate.end, {"chunking_strategy": "heading-v1", "heading": heading, "heading_level": level}))
        return chunks


class PageAwareChunker:
    name = ChunkingStrategyName.PAGE

    def __init__(self, *, chunk_size: int = 1200, overlap: int = 200) -> None:
        _validate_size(chunk_size, overlap)
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> list[ChunkCandidate]:
        pages = text.split("\f")
        chunks: list[ChunkCandidate] = []
        cursor = 0
        for page_number, raw_page in enumerate(pages, start=1):
            leading = len(raw_page) - len(raw_page.lstrip())
            page = raw_page.strip()
            page_start = cursor + leading
            if page:
                for candidate in FixedChunker(chunk_size=self.chunk_size, overlap=self.overlap).split(page):
                    chunks.append(ChunkCandidate(candidate.content, page_start + candidate.start, page_start + candidate.end, {"chunking_strategy": "page-v1", "page": page_number}))
            cursor += len(raw_page) + (1 if page_number < len(pages) else 0)
        return chunks


class HierarchicalChunker:
    name = ChunkingStrategyName.HIERARCHICAL

    def __init__(self, *, parent_size: int = 6000, child_size: int = 1200, child_overlap: int = 200) -> None:
        _validate_size(parent_size, 0)
        _validate_size(child_size, child_overlap)
        if child_size >= parent_size:
            raise ValueError("child_size must be smaller than parent_size")
        self.parent_size = parent_size
        self.child_size = child_size
        self.child_overlap = child_overlap

    def split(self, text: str) -> list[ChunkCandidate]:
        parents = FixedChunker(chunk_size=self.parent_size, overlap=0).split(text)
        chunks: list[ChunkCandidate] = []
        for parent_index, parent in enumerate(parents):
            chunks.append(ChunkCandidate(parent.content, parent.start, parent.end, {"chunking_strategy": "hierarchical-v1", "hierarchy_level": "parent", "parent_index": parent_index}, embed=False))
            for child_index, child in enumerate(FixedChunker(chunk_size=self.child_size, overlap=self.child_overlap).split(parent.content)):
                chunks.append(ChunkCandidate(child.content, parent.start + child.start, parent.start + child.end, {"chunking_strategy": "hierarchical-v1", "hierarchy_level": "child", "parent_index": parent_index, "child_index": child_index}, embed=True))
        return chunks


def build_chunker(strategy: ChunkingStrategyName | str = ChunkingStrategyName.FIXED, *, chunk_size: int = 1200, overlap: int = 200, parent_size: int = 6000, child_size: int = 1200, child_overlap: int = 200) -> ChunkingStrategy:
    selected = ChunkingStrategyName(strategy)
    if selected is ChunkingStrategyName.FIXED:
        return FixedChunker(chunk_size=chunk_size, overlap=overlap)
    if selected is ChunkingStrategyName.PARAGRAPH:
        return ParagraphChunker(chunk_size=chunk_size, overlap=overlap)
    if selected is ChunkingStrategyName.HEADING:
        return HeadingAwareChunker(chunk_size=chunk_size, overlap=overlap)
    if selected is ChunkingStrategyName.PAGE:
        return PageAwareChunker(chunk_size=chunk_size, overlap=overlap)
    return HierarchicalChunker(parent_size=parent_size, child_size=child_size, child_overlap=child_overlap)
