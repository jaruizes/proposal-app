---
name: ingest-sources
description: Discover and prepare proposal source documents from local or Google Drive input, producing a canonical source manifest plus auxiliary textual/visual representations for multimodal analysis.
---

# Ingest Sources

Input:

```text
workspace/<proposal>
```

This is a technical preparation step before `analysis`. It does not perform semantic opportunity analysis and is not a human-checkpoint phase.

## Normative reference

Read and obey:

```text
docs/document-ingestion.md
```

## Configuration

Read `<opportunity>/offer-config.yaml`:

```yaml
input:
  type: local | google_drive
```

For `local`, resolve `input.path` relative to the opportunity directory.

For `google_drive`, require `input.folder_id`.

## Working structure

Ensure:

```text
<opportunity>/working/sources
<opportunity>/working/extracted
<opportunity>/working/rendered
```

Write canonical inventory to:

```text
<opportunity>/working/source-manifest.json
```

The original/native document remains authoritative. `extracted/` and `rendered/` are auxiliary representations.

## Local source discovery

Use:

```bash
uv run python tools/source_manifest.py local <input-path> <opportunity>/working/source-manifest.json
```

This assigns stable `DOC-nnn` IDs and records source metadata/hash.

For PDF/DOCX/PPTX/XLSX, create auxiliary searchable text:

```bash
uv run python tools/extract_documents.py <input-path> <opportunity>/working/extracted
```

For Office files (DOCX/PPTX/XLSX), also attempt a PDF visual rendering:

```bash
uv run python tools/render_documents.py <input-path> <opportunity>/working/rendered
```

This helper uses LibreOffice/`soffice` when installed. If it is not available or a file cannot be rendered, do not abort ingestion automatically; record/surface the warning so `analysis` knows visual inspection may be incomplete.

Original PDF files do not need conversion solely for multimodal analysis: inspect the original PDF itself.

## Google Drive source discovery

1. call `drive_list_folder` with the configured folder ID;
2. sort deterministically by file name + Drive file ID;
3. assign `DOC-nnn` IDs in that order;
4. record `driveFileId`, MIME type, modified time, checksum/size/web link where available;
5. write `source-manifest.json`;
6. update deterministic manifest hash with:

```bash
uv run python tools/source_manifest.py hash <opportunity>/working/source-manifest.json
```

### Google-native files

- Google Docs → `docs_get_document` as primary structural representation; inspect embedded visual information when material.
- Google Slides → `slides_get_presentation`; use `slides_get_thumbnail` for slides containing meaningful diagrams/layout/visual relationships.
- Google Sheets → `sheets_get_spreadsheet` + `sheets_get_values`; if charts/visual layout are materially relevant, use a richer/exported representation when available rather than relying on values alone.

Do not reduce Google-native content to Markdown before analysis when native APIs expose richer structure.

### Binary Drive files

For PDF/DOCX/PPTX/XLSX:

1. download with `drive_download_file` to deterministic `working/sources/` paths;
2. preserve downloaded original;
3. generate auxiliary text using `tools/extract_documents.py` where useful;
4. for downloaded DOCX/PPTX/XLSX, attempt visual PDF rendering using `tools/render_documents.py` against the downloaded-source directory;
5. preserve rendering warnings for phase-1 analysis;
6. never treat extracted Markdown as more authoritative than the original.

Use `drive_export_file` selectively when it provides a richer representation; do not export everything universally.

## Unsupported or unreadable sources

Include unsupported sources in the manifest with an appropriate status and surface them in the preparation summary.

Do not abort the whole opportunity unless the unreadable/unsupported source is clearly essential to meaningful qualification.

## Change detection

Compare previous/current manifests using stable identity/content fields and manifest hash.

If source material changed after analysis, report that `analysis` and downstream state must be invalidated.

## Completion

Return a concise preparation summary:

- source type;
- number of documents;
- supported/unsupported counts;
- changed sources;
- manifest hash/path;
- text extraction warnings;
- visual rendering warnings;
- which Office files received rendered PDF representations.

Do not perform semantic customer/opportunity analysis in this skill.
