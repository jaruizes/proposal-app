from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol

from docx import Document as DocxDocument
from pypdf import PdfReader


PDF_MEDIA_TYPE = "application/pdf"
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TEXT_MEDIA_TYPES = {"text/plain", "text/markdown", "text/x-markdown"}
SUPPORTED_UPLOAD_MEDIA_TYPES = TEXT_MEDIA_TYPES | {PDF_MEDIA_TYPE, DOCX_MEDIA_TYPE}


class DocumentParseError(RuntimeError):
    pass


@dataclass(frozen=True)
class ParsedDocument:
    content: str
    media_type: str
    metadata: dict[str, object]


class DocumentParser(Protocol):
    def parse(self, payload: bytes, *, filename: str, media_type: str) -> ParsedDocument: ...


class TextDocumentParser:
    def parse(self, payload: bytes, *, filename: str, media_type: str) -> ParsedDocument:
        if not payload:
            raise DocumentParseError("Uploaded text file is empty")
        for encoding in ("utf-8-sig", "utf-16", "latin-1"):
            try:
                text = payload.decode(encoding)
                return ParsedDocument(content=text, media_type=media_type if media_type in TEXT_MEDIA_TYPES else "text/plain", metadata={"parser": "text", "encoding": encoding})
            except UnicodeDecodeError:
                continue
        raise DocumentParseError("Unable to decode uploaded text file")


class PdfDocumentParser:
    def parse(self, payload: bytes, *, filename: str, media_type: str) -> ParsedDocument:
        if not payload:
            raise DocumentParseError("Uploaded PDF is empty")
        try:
            reader = PdfReader(BytesIO(payload))
            pages = [(page.extract_text() or "").strip() for page in reader.pages]
        except Exception as exc:
            raise DocumentParseError(f"Unable to parse PDF '{filename}': {exc}") from exc
        text = "\n\f\n".join(page for page in pages if page).strip()
        if not text:
            raise DocumentParseError("PDF contains no extractable text. Scanned/image-only PDFs require OCR, which is not enabled yet.")
        return ParsedDocument(content=text, media_type=PDF_MEDIA_TYPE, metadata={"parser": "pypdf", "pages": len(reader.pages), "page_boundaries": True})


class DocxDocumentParser:
    def parse(self, payload: bytes, *, filename: str, media_type: str) -> ParsedDocument:
        if not payload:
            raise DocumentParseError("Uploaded Word document is empty")
        try:
            document = DocxDocument(BytesIO(payload))
        except Exception as exc:
            raise DocumentParseError(f"Unable to parse Word document '{filename}': {exc}") from exc

        blocks: list[str] = []
        headings = 0
        for paragraph in document.paragraphs:
            text = paragraph.text.strip()
            if not text:
                continue
            style_name = paragraph.style.name if paragraph.style is not None else ""
            match = re.match(r"Heading\s+(\d+)", style_name, re.I)
            if match:
                level = min(max(int(match.group(1)), 1), 6)
                blocks.append(f"{'#' * level} {text}")
                headings += 1
            else:
                blocks.append(text)
        for table in document.tables:
            for row in table.rows:
                values = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                if any(values):
                    blocks.append(" | ".join(values))

        text = "\n\n".join(blocks).strip()
        if not text:
            raise DocumentParseError("Word document contains no extractable text")
        return ParsedDocument(content=text, media_type=DOCX_MEDIA_TYPE, metadata={"parser": "python-docx", "paragraphs": len(document.paragraphs), "tables": len(document.tables), "headings": headings})


class DocumentParserRegistry:
    def __init__(self) -> None:
        self._text = TextDocumentParser()
        self._pdf = PdfDocumentParser()
        self._docx = DocxDocumentParser()

    def resolve_media_type(self, *, filename: str, declared_media_type: str | None) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix == ".pdf": return PDF_MEDIA_TYPE
        if suffix == ".docx": return DOCX_MEDIA_TYPE
        if suffix == ".doc": raise DocumentParseError("Legacy .doc files are not supported; save the document as .docx first")
        if suffix in {".txt", ".text"}: return "text/plain"
        if suffix in {".md", ".markdown"}: return "text/markdown"
        if declared_media_type in SUPPORTED_UPLOAD_MEDIA_TYPES: return declared_media_type
        raise DocumentParseError(f"Unsupported file type '{suffix or declared_media_type or 'unknown'}'. Supported: PDF, DOCX, TXT and Markdown")

    def parse(self, payload: bytes, *, filename: str, declared_media_type: str | None = None) -> ParsedDocument:
        media_type = self.resolve_media_type(filename=filename, declared_media_type=declared_media_type)
        if media_type == PDF_MEDIA_TYPE: return self._pdf.parse(payload, filename=filename, media_type=media_type)
        if media_type == DOCX_MEDIA_TYPE: return self._docx.parse(payload, filename=filename, media_type=media_type)
        return self._text.parse(payload, filename=filename, media_type=media_type)
