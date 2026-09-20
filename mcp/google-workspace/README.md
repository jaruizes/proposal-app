# Google Workspace MCP

Local stdio MCP built on stable Google Workspace APIs.

## Tools

Drive:

- `drive_search_files`
- `drive_list_folder`
- `drive_get_file`
- `drive_download_file`
- `drive_export_file`
- `drive_copy_file`
- `drive_create_folder`
- `drive_move_file`

Slides:

- `slides_create_presentation`
- `slides_get_presentation`
- `slides_get_thumbnail`
- `slides_duplicate_slide`
- `slides_delete_slide`
- `slides_move_slides`
- `slides_replace_text`
- `slides_replace_element_text`
- `slides_batch_update`

Docs:

- `docs_get_document`
- `docs_create_document`
- `docs_batch_update`

Sheets:

- `sheets_get_spreadsheet`
- `sheets_get_values`
- `sheets_update_values`

## Source-ingestion safety

`drive_download_file` downloads non-Google-native files such as PDF, DOCX, PPTX and XLSX.

`drive_export_file` exports Google-native files to a requested MIME type when an export is actually needed. Prefer native Docs/Slides/Sheets APIs when they expose richer structure.

Both tools only write under the repository `workspace/` tree. They refuse destinations outside that boundary and do not overwrite existing files unless `overwrite=true` is explicitly passed.

## Setup

```bash
npm install
npm run build
npm run auth
npm run doctor
```
