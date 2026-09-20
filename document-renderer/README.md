# Document Renderer

Deterministic document-rendering service used by ProposalFlow.

## Responsibilities

- `POST /v1/render/docx`: canonical Markdown → DOCX.
- `POST /v1/render/pdf`: canonical Markdown → DOCX → PDF.
- `GET /health/live` and `GET /health/ready`.

PDF is intentionally derived from the generated DOCX so Word and PDF share the same content/layout pipeline.

## Templates

The global ProposalFlow template setting supplies a template id.

- Empty template id: create a new neutral DOCX.
- `builtin-neutral`: also creates a new neutral DOCX for backward compatibility.
- Named template: load `templates/<template-id>.docx`.

Corporate templates can preserve styles, headers, footers and section configuration while body content is replaced by canonical proposal Markdown.

## LibreOffice

LibreOffice Writer, Fontconfig and open fonts are installed inside the image. Developers and Kubernetes nodes do not need LibreOffice installed.

Every PDF conversion uses a temporary isolated LibreOffice user profile. Renders are timeout-bounded and temporary files are deleted after the request.

## Container/runtime properties

- runs as UID 10001;
- compatible with read-only root filesystem;
- uses `/tmp` for ephemeral work;
- no PVC is required;
- intended to scale independently from Spring/Agent Platform.

The Docker Compose service applies `no-new-privileges`, drops Linux capabilities and mounts `/tmp` as tmpfs.
