"""Tool-driven source ingestion owned by Agent Platform.

Spring supplies only the Google Drive folder reference. Discovery, native Google API
reads and binary downloads happen through the platform ToolRegistry/MCP.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from langgraph.graph import END, StateGraph

from agent_platform.application.document_parsers import DocumentParseError, DocumentParserRegistry
from agent_platform.application.models import ModelResult, ModelUsage
from agent_platform.domain import AgentExecutionRequest, ToolCall


FOLDER_MIME = "application/vnd.google-apps.folder"
DOC_MIME = "application/vnd.google-apps.document"
SLIDES_MIME = "application/vnd.google-apps.presentation"
SHEETS_MIME = "application/vnd.google-apps.spreadsheet"


class SourceIngestionError(RuntimeError):
    pass


def _drive_id(value: str | None) -> str:
    raw = (value or "").strip()
    marker = "/folders/"
    if marker in raw:
        return raw.split(marker, 1)[1].split("?", 1)[0].split("/", 1)[0]
    return raw


def _folder_from_context(text: str) -> str:
    match = re.search(r"(?m)^Google Drive input folder:\s*(.+)$", text)
    return _drive_id(match.group(1).strip()) if match else ""


async def _tool_text(runtime, execution, tool_key: str, arguments: dict[str, Any]) -> str:
    if runtime._tools is None:
        raise SourceIngestionError("Agent Platform ToolRegistry is not configured")
    result = await runtime._tools.invoke(ToolCall(
        tool_key=tool_key,
        arguments=arguments,
        correlation_id=execution.correlation_id,
        metadata={"execution_id": str(execution.id), "graph": "source-ingestion"},
    ))
    await runtime._executions.add_event(execution.id, "tool.executed", {
        "tool": tool_key,
        "error": result.is_error,
    })
    if result.is_error:
        raise SourceIngestionError(result.error.message if result.error else f"{tool_key} failed")
    if result.structured_content is not None:
        return json.dumps(result.structured_content, ensure_ascii=False)
    return "\n".join(
        str(item.get("text", ""))
        for item in result.content
        if isinstance(item, dict) and item.get("type") == "text" and item.get("text")
    )


async def _list_files(runtime, execution, root_folder: str) -> list[dict[str, Any]]:
    queue: list[tuple[str, str]] = [(root_folder, "")]
    visited: set[str] = set()
    result: list[dict[str, Any]] = []
    while queue:
        folder_id, prefix = queue.pop(0)
        if folder_id in visited:
            continue
        visited.add(folder_id)
        raw = await _tool_text(runtime, execution, "drive_list_folder", {
            "folderId": folder_id,
            "pageSize": 1000,
        })
        try:
            children = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SourceIngestionError(f"drive_list_folder returned invalid JSON for {folder_id}") from exc
        if not isinstance(children, list):
            raise SourceIngestionError(f"drive_list_folder returned non-array for {folder_id}")
        for item in children:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            path = f"{prefix}/{name}".strip("/")
            if item.get("mimeType") == FOLDER_MIME:
                queue.append((str(item.get("id") or ""), path))
            else:
                enriched = dict(item)
                enriched["relativePath"] = path
                result.append(enriched)
    result.sort(key=lambda item: (str(item.get("relativePath") or ""), str(item.get("id") or "")))
    return result


def _source_hash(files: list[dict[str, Any]]) -> str:
    canonical = "".join(
        "\t".join([
            str(item.get("id") or ""),
            str(item.get("relativePath") or ""),
            str(item.get("mimeType") or ""),
            str(item.get("modifiedTime") or ""),
            str(item.get("size") or ""),
            str(item.get("md5Checksum") or ""),
            str(item.get("version") or ""),
        ]) + "\n"
        for item in files
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _safe_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name)


def _limit(value: str, maximum: int = 120_000) -> str:
    return value if len(value) <= maximum else value[:maximum] + "\n[representation truncated]"


async def _sheet_text(runtime, execution, spreadsheet_id: str, metadata: str, warnings: list[str], code: str) -> str:
    try:
        root = json.loads(metadata)
    except json.JSONDecodeError:
        return "[Unable to parse spreadsheet metadata]"
    blocks: list[str] = []
    for sheet in root.get("sheets", []) or []:
        title = str(((sheet.get("properties") or {}).get("title") or ""))
        if not title:
            continue
        try:
            values = await _tool_text(runtime, execution, "sheets_get_values", {
                "spreadsheetId": spreadsheet_id,
                "range": f"'{title.replace(chr(39), chr(39)*2)}'",
            })
            blocks.append(f"## Sheet: {title}\n{values}")
        except Exception as exc:
            warnings.append(f"{code} sheet {title}: {exc}")
    return "\n\n".join(blocks) or "[No readable sheet values found]"


async def _binary_text(runtime, execution, correlation_id, code: str, file: dict[str, Any], warnings: list[str]) -> tuple[str, str | None]:
    filename = str(file.get("name") or code)
    relative = f"workspace/{correlation_id}/sources/{code}-{_safe_name(filename)}"
    raw = await _tool_text(runtime, execution, "drive_download_file", {
        "fileId": str(file.get("id") or ""),
        "outputPath": relative,
        "overwrite": True,
    })
    try:
        output_path = str(json.loads(raw).get("outputPath") or relative)
    except json.JSONDecodeError:
        output_path = relative
    absolute = Path("/opt") / output_path
    try:
        payload = absolute.read_bytes()
        parsed = DocumentParserRegistry().parse(
            payload,
            filename=filename,
            declared_media_type=str(file.get("mimeType") or ""),
        )
        return parsed.content, output_path
    except (OSError, DocumentParseError) as exc:
        warnings.append(f"{code} {filename}: {exc}")
        return f"[Unable to extract binary source: {exc}]", output_path


def add_source_ingestion_nodes(builder: StateGraph, runtime, execution) -> None:
    async def ingest(state: dict) -> dict:
        request = AgentExecutionRequest.model_validate(state["request"])
        context = str(request.context.get("business_context") or "")
        folder_id = _folder_from_context(context)
        if not folder_id:
            raise SourceIngestionError("Google Drive input folder is missing")

        files = await _list_files(runtime, execution, folder_id)
        digest = _source_hash(files)
        entries: list[dict[str, Any]] = []
        warnings: list[str] = []
        textual = [
            "# Customer source corpus",
            "",
            "Original/native customer sources are authoritative. Extracted representations are auxiliary.",
        ]

        for index, file in enumerate(files, start=1):
            code = f"DOC-{index:03d}"
            file_id = str(file.get("id") or "")
            name = str(file.get("name") or "")
            mime = str(file.get("mimeType") or "")
            entry = {
                "id": code,
                "driveFileId": file_id,
                "name": name,
                "relativePath": file.get("relativePath") or name,
                "mimeType": mime,
                "sourceAuthority": "original_native",
                "modifiedTime": file.get("modifiedTime"),
                "size": file.get("size"),
                "md5Checksum": file.get("md5Checksum"),
                "version": file.get("version"),
                "webViewLink": file.get("webViewLink"),
                "status": "ready",
            }
            try:
                if mime == DOC_MIME:
                    extracted = await _tool_text(runtime, execution, "docs_get_document", {"documentId": file_id})
                    entry["representationKind"] = "google_native"
                elif mime == SLIDES_MIME:
                    extracted = await _tool_text(runtime, execution, "slides_get_presentation", {"presentationId": file_id})
                    entry["representationKind"] = "google_native"
                elif mime == SHEETS_MIME:
                    metadata = await _tool_text(runtime, execution, "sheets_get_spreadsheet", {"spreadsheetId": file_id})
                    values = await _sheet_text(runtime, execution, file_id, metadata, warnings, code)
                    extracted = metadata + "\n\n# Google Sheets values\n" + values
                    entry["representationKind"] = "google_native"
                else:
                    extracted, local_path = await _binary_text(
                        runtime, execution, request.correlation_id or execution.id, code, file, warnings
                    )
                    entry["representationKind"] = "binary"
                    if local_path:
                        entry["localPath"] = local_path
            except Exception as exc:
                extracted = f"[Unable to prepare representation: {exc}]"
                warnings.append(f"{code} {name}: {exc}")
                entry["status"] = "warning"

            entries.append(entry)
            textual.extend([
                "",
                f"## {code} — {entry['relativePath']}",
                f"MIME: {mime}",
                f"Drive ID: {file_id}",
                "Authority: original/native source",
                "",
                _limit(extracted),
            ])

        manifest = {
            "sourceType": "google_drive",
            "folderId": folder_id,
            "sourceHashAlgorithm": "SHA-256",
            "sourceHash": digest,
            "sourceCount": len(entries),
            "authorityPolicy": "Original/native customer sources are authoritative; extracted representations are auxiliary.",
            "sources": entries,
            "warnings": warnings,
        }
        report = (
            f"Google Drive ingestion completed: {len(entries)} documents, {len(warnings)} warnings. "
            f"Source hash: {digest}. MCP ownership: Agent Platform."
        )
        output = {
            "manifest": manifest,
            "textualContext": "\n".join(textual),
            "ingestionReport": report,
        }
        await runtime._executions.add_event(execution.id, "source.ingestion.completed", {
            "source_count": len(entries),
            "warnings": len(warnings),
            "source_hash": digest,
        })
        result = ModelResult(
            content=json.dumps(output, ensure_ascii=False),
            model=request.model or "tool-only",
            usage=ModelUsage(),
            metadata={"mcp_owned_by_agent_platform": True, "source_hash": digest},
        )
        return {"model_result": result.model_dump(mode="json")}

    builder.add_node("source_ingestion", ingest)
    builder.add_edge("build_context", "source_ingestion")
    builder.add_edge("source_ingestion", END)


__all__ = ["add_source_ingestion_nodes"]
