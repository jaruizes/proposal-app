---
name: ingest-sources
description: Discover and prepare Google Drive proposal sources through Agent Platform MCP tools.
---

# Ingest Sources

This is one technical AgentExecution owned by Agent Platform. Spring supplies the input folder reference but never calls Google Workspace MCP directly.

## Responsibilities

The `source-ingestion` graph:

1. recursively discovers Drive sources with `drive_list_folder`;
2. records stable source metadata and a deterministic SHA-256 source hash;
3. reads Google-native Docs, Slides and Sheets through MCP;
4. downloads supported binary sources into Agent Platform workspace scratch storage;
5. extracts PDF/DOCX/PPTX/XLSX/TXT/Markdown text inside Agent Platform;
6. returns the canonical source bundle.

Original/native customer documents remain authoritative. Extracted text is auxiliary.

## Output contract

Return one complete JSON object:

```json
{
  "manifest": {
    "sourceType": "google_drive",
    "folderId": "...",
    "sourceHash": "...",
    "sourceCount": 0,
    "sources": [],
    "warnings": []
  },
  "textualContext": "# Customer source corpus\n...",
  "ingestionReport": "..."
}
```

Do not perform opportunity qualification or solution design in this skill.
