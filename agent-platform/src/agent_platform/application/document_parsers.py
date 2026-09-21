from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Protocol

from docx import Document as DocxDocument
from openpyxl import load_workbook
from pptx import Presentation as PptxPresentation
from pypdf import PdfReader


PDF_MEDIA_TYPE = "application/pdf"
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TEXT_MEDIA_TYPES = {"text/plain", "text/markdown", "text/x-markdown"}
SUPPORTED_UPLOAD_MEDIA_TYPES = TEXT_MEDIA_TYPES | {PDF_MEDIA_TYPE, DOCX_MEDIA_TYPE, PPTX_MEDIA_TYPE, XLSX_MEDIA_TYPE}


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


class PptxDocumentParser:
    def parse(self, payload: bytes, *, filename: str, media_type: str) -> ParsedDocument:
        try:
            presentation = PptxPresentation(BytesIO(payload))
        except Exception as exc:
            raise DocumentParseError(f"Unable to parse PowerPoint '{filename}': {exc}") from exc
        slides: list[str] = []
        for index, slide in enumerate(presentation.slides, start=1):
            texts: list[str] = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and str(shape.text).strip():
                    texts.append(str(shape.text).strip())
                if getattr(shape, "has_table", False):
                    for row in shape.table.rows:
                        values = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                        if any(values):
                            texts.append(" | ".join(values))
            if texts:
                slides.append(f"## Slide {index}\n\n" + "\n\n".join(texts))
        text = "\n\n".join(slides).strip()
        if not text:
            raise DocumentParseError("PowerPoint contains no extractable text")
        return ParsedDocument(content=text, media_type=PPTX_MEDIA_TYPE, metadata={"parser": "python-pptx", "slides": len(presentation.slides)})


class XlsxDocumentParser:
    def parse(self, payload: bytes, *, filename: str, media_type: str) -> ParsedDocument:
        try:
            workbook = load_workbook(BytesIO(payload), read_only=True, data_only=True)
        except Exception as exc:
            raise DocumentParseError(f"Unable to parse Excel workbook '{filename}': {exc}") from exc
        blocks: list[str] = []
        for sheet in workbook.worksheets:
            blocks.append(f"## Sheet: {sheet.title}")
            rows = 0
            for row in sheet.iter_rows(values_only=True):
                values = ["" if value is None else str(value) for value in row]
                if any(value.strip() for value in values):
                    blocks.append(" | ".join(values))
                    rows += 1
                if rows >= 2000:
                    blocks.append("[sheet truncated after 2000 non-empty rows]")
                    break
        text = "\n".join(blocks).strip()
        if not text:
            raise DocumentParseError("Excel workbook contains no extractable values")
        return ParsedDocument(content=text, media_type=XLSX_MEDIA_TYPE, metadata={"parser": "openpyxl", "sheets": len(workbook.sheetnames)})


class DocumentParserRegistry:
    def __init__(self) -> None:
        self._text = TextDocumentParser()
        self._pdf = PdfDocumentParser()
        self._docx = DocxDocumentParser()
        self._pptx = PptxDocumentParser()
        self._xlsx = XlsxDocumentParser()

    def resolve_media_type(self, *, filename: str, declared_media_type: str | None) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix == ".pdf": return PDF_MEDIA_TYPE
        if suffix == ".docx": return DOCX_MEDIA_TYPE
        if suffix == ".doc": raise DocumentParseError("Legacy .doc files are not supported; save the document as .docx first")
        if suffix == ".pptx": return PPTX_MEDIA_TYPE
        if suffix == ".xlsx": return XLSX_MEDIA_TYPE
        if suffix in {".txt", ".text"}: return "text/plain"
        if suffix in {".md", ".markdown"}: return "text/markdown"
        if declared_media_type in SUPPORTED_UPLOAD_MEDIA_TYPES: return declared_media_type
        raise DocumentParseError(f"Unsupported file type '{suffix or declared_media_type or 'unknown'}'. Supported: PDF, DOCX, TXT and Markdown")

    def parse(self, payload: bytes, *, filename: str, declared_media_type: str | None = None) -> ParsedDocument:
        media_type = self.resolve_media_type(filename=filename, declared_media_type=declared_media_type)
        if media_type == PDF_MEDIA_TYPE: return self._pdf.parse(payload, filename=filename, media_type=media_type)
        if media_type == DOCX_MEDIA_TYPE: return self._docx.parse(payload, filename=filename, media_type=media_type)
        if media_type == PPTX_MEDIA_TYPE: return self._pptx.parse(payload, filename=filename, media_type=media_type)
        if media_type == XLSX_MEDIA_TYPE: return self._xlsx.parse(payload, filename=filename, media_type=media_type)
        return self._text.parse(payload, filename=filename, media_type=media_type)
