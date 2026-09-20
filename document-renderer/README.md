# Document Renderer

Deterministic proposal renderer used by ProposalFlow.

The container owns every native dependency required for rendering. A developer
only needs Docker/Compose; LibreOffice and fonts are installed in the image.

Current milestone:

- `POST /v1/render/docx`: canonical Markdown -> DOCX.
- `builtin-neutral`: default template requiring no binary asset.
- corporate templates: add `templates/<template-id>.docx` and rebuild the image.

The image already contains LibreOffice Writer and production-safe open fonts so
M6.4 can add DOCX -> PDF conversion without requiring LibreOffice on the host or
Kubernetes node.

The service runs as UID 10001, is compatible with a read-only root filesystem,
and uses `/tmp` as ephemeral working storage.
