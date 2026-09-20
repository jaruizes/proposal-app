# ProposalFlow / Proposal Agent Platform

ProposalFlow is an end-to-end proposal-generation application built on top of an independent agent platform. It combines deterministic workflow orchestration, human approval gates, multimodal source ingestion, AI agents, reusable knowledge/RAG, document rendering, Google Workspace tooling and observability.

The project is deliberately split into two responsibilities:

- **ProposalFlow application (Angular + Spring Boot)** owns the business workflow, offer state, approvals, artifacts, source ingestion, document materialization and Google Workspace integration.
- **Agent Platform (FastAPI + LangGraph)** owns cognitive execution, agents, skills, memory, knowledge/RAG, ontology-aware retrieval, caching and model-provider integration.

The main deliverable is a detailed proposal document. Presentation generation is optional.

## Current workflow

The workflow order is fixed and every cognitive phase is human-gated:

```text
1. Entendimiento y cualificación
        ↓ approval
2. Estrategia de respuesta
        ↓ approval
3. Propuesta de solución y plan
        ↓ approval
4. Documento de oferta detallado
        ↓ approval
        ├─ proposal.docx
        ├─ proposal.pdf
        └─ finish if presentation is disabled

5. Propuesta de presentación              (optional)
        ↓ approval
6. Generación de presentación corporativa (optional)
```

The last two phases can be disabled per offer. When disabled, approving phase 4 completes the workflow after the DOCX/PDF materialization has been triggered.

### Canonical artifacts

The application keeps cognitive outputs as versioned Markdown artifacts. Typical files are:

```text
opportunity-brief.md
questions.md
technology.md
strategy.md
solution.md
solution-plan.md
proposal.md
slides-plan.md
```

Markdown remains the canonical, inspectable representation. Users can export any generated Markdown artifact to PDF from the artifact viewer.

The final proposal is additionally materialized as:

```text
proposal.md
    ↓ deterministic renderer
proposal.docx
    ↓ LibreOffice headless
proposal.pdf
```

DOCX/PDF rendering never calls an LLM.

## Architecture

```text
┌───────────────────────────────────────────────────────────────────────┐
│ Angular UI                                                            │
│ offers · approvals · artifacts · knowledge · templates · observability│
└───────────────────────────────┬───────────────────────────────────────┘
                                │ REST + SSE
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│ Spring Boot backend                                                   │
│                                                                       │
│ deterministic workflow owner                                         │
│ human gates · offer state · versioned artifacts                       │
│ source ingestion · source triage · Google Workspace MCP               │
│ proposal materialization · template settings                          │
└──────────────┬──────────────────────────┬─────────────────────────────┘
               │ NATS JetStream           │ HTTP
               │ cognitive execution      │ rendering
               ▼                          ▼
┌───────────────────────────────┐  ┌───────────────────────────────────┐
│ Agent Platform                │  │ Document Renderer                 │
│ FastAPI + LangGraph           │  │ Python + python-docx              │
│                               │  │ LibreOffice headless              │
│ Agents / Skills               │  │ Markdown → DOCX → PDF             │
│ RAG / Memory / Ontology       │  └───────────────────────────────────┘
│ Cache / Model providers       │
└──────────────┬────────────────┘
               │
               ├─ PostgreSQL + pgvector
               ├─ Valkey
               └─ Anthropic

Spring backend
    ├─ PostgreSQL (workflow/application state)
    ├─ Google Workspace MCP over stdio
    └─ NATS JetStream

Observability
    └─ OpenTelemetry → Collector → Tempo / Jaeger + Prometheus / Grafana
```

More detail is available in [docs/architecture.md](docs/architecture.md). Architectural decisions and their trade-offs are documented in [docs/ADRs.md](docs/ADRs.md).

## Main components

### Frontend

- Angular 20.
- Offer dashboard and workflow visualization.
- Human approval and refinement UI.
- Per-agent execution telemetry and token usage.
- Markdown preview/raw view.
- On-demand Markdown → PDF export.
- Final proposal DOCX/PDF status and download.
- Knowledge/RAG administration from the main application.
- Global corporate-template configuration.

### Spring Boot backend

- Java 21 / Spring Boot 3.5.
- Hexagonal dependency direction: `infrastructure → business → domain`.
- PostgreSQL + Flyway.
- Deterministic workflow and human gates.
- Source ingestion and multimodal preparation.
- NATS execution adapter to Agent Platform.
- Google Workspace MCP client.
- Final-document versioning/idempotency.
- REST API and SSE updates.

### Agent Platform

- Python/FastAPI.
- LangGraph runtime behind a stable platform API.
- Agent Registry and Skill Registry.
- Anthropic provider.
- PostgreSQL LangGraph checkpoints.
- PostgreSQL/pgvector knowledge store.
- Hybrid retrieval: vector + keyword + graph/ontology signals.
- Retrieval relevance gating.
- Memory and cache support.
- Valkey cache.
- NATS command/event transport.
- OpenTelemetry instrumentation.

### Document Renderer

- Independent FastAPI service.
- Markdown → DOCX with `python-docx`.
- DOCX → PDF with LibreOffice headless.
- LibreOffice and required fonts are installed **inside the image**.
- Non-root runtime.
- Read-only root filesystem compatible.
- Ephemeral `/tmp` working directory.
- No LibreOffice installation is required on the developer machine or Kubernetes node.

### Google Workspace MCP

The local MCP server wraps stable Google Drive, Slides, Docs and Sheets APIs. It is used for source access and final presentation materialization.

Important capabilities include:

- Drive discovery/download/export/copy/move.
- Slides creation from blank or corporate-template copy.
- Slides structure inspection and thumbnails.
- Slides batch updates and visual QA.
- Native Google Docs/Sheets reads.
- OAuth credentials remain outside the repository.

## Source ingestion and token strategy

Source documents are not treated as plain text only.

The backend can ingest Google-native documents and ordinary files, extract text with native APIs/Tika and create PDF visual representations when needed. Office-to-PDF conversion uses LibreOffice packaged in the backend image, so local hosts do not need LibreOffice.

### Analysis

The analysis phase is allowed to inspect the source corpus broadly because it builds the compact canonical understanding of the opportunity.

### Strategy

Strategy works primarily from approved artifacts rather than repeatedly injecting all raw documents.

### Solution

Solution must retain access to original customer evidence, but it does not blindly send every original source to every expensive model call.

The current flow is:

```text
approved artifacts
+ source manifest
        ↓
solution architect source triage
        ↓
REVIEW_IN_DEPTH / TARGETED_REVIEW / SKIP
        ↓
selected original customer sources
        ↓
specialists (max 2, only if needed)
        ↓
solution.md
        ↓
solution-plan.md
        ↓
coherence review
```

If triage cannot be interpreted safely, the implementation falls back to the full corpus rather than risk losing factual evidence.

The governing principle is:

```text
approved artifacts = compact working context
original current-offer sources = factual authority
reference proposals = non-factual structure/style patterns
```

## Proposal RAG

The Agent Platform exposes knowledge-base management and retrieval to the main UI.

Default knowledge bases include:

- `reference-offers`
- `architecture-references`
- `corporate-roles`
- `corporate-capabilities`
- `accelerators`
- `case-studies`

Documents can be uploaded as PDF, DOCX, TXT or Markdown and are parsed, enriched, chunked and embedded.

Supported retrieval modes include vector, keyword, graph and hybrid retrieval.

### Reference proposal isolation

Historical proposals are never treated as factual authority for a current offer.

During `compose-proposal` the LangGraph proposal flow retrieves references section by section from `reference-offers`. Retrieved chunks are explicitly injected as **NON-FACTUAL** patterns useful for structure, depth, terminology and style only.

The current-offer artifacts and original source material remain authoritative for facts, commitments, technology, customer data, dates, staffing and pricing.

Proposal retrieval emits per-section diagnostics so it is possible to inspect which document/chunk influenced the generation.

## Proposal generation graph

`compose-proposal` uses a dedicated LangGraph flow:

```text
build_context
    ↓
plan_proposal
    ↓
retrieve section references
    ↓
draft sections (bounded concurrency)
    ↓
review sections
    ↓
assemble proposal
    ↓
global consistency/coverage review
    ↓
optional targeted correction
```

The output remains one canonical `proposal.md`.

LangGraph is an internal runtime implementation detail. Spring and other clients depend on Agent Platform contracts, not on LangGraph APIs.

## Document materialization

When `proposal.md` is approved, Spring schedules deterministic materialization asynchronously.

Each materialized document stores:

- source artifact id;
- content version;
- render version;
- source SHA-256;
- template id;
- renderer version;
- render key;
- status (`PROCESSING`, `READY`, `FAILED`);
- error details;
- binary content.

The render key includes the source hash, template, renderer version, materializer version and target type. Repeating a render with identical inputs reuses the existing result.

DOCX and PDF failures are independent. A successful DOCX is preserved even if PDF conversion fails. Rendering failures do not roll back approval of the canonical proposal.

## Templates

Corporate templates are configured globally from **Plantillas** in the main UI, not per offer.

There are two independent settings:

- proposal DOCX template;
- Google Slides presentation template.

Both are optional.

### No document template configured

A new DOCX is created with neutral built-in styles and PDF is generated from that DOCX.

### No presentation template configured

A new blank Google Slides presentation is created and populated from the approved `slides-plan.md`.

### Template configured

- DOCX rendering loads the configured document template.
- Slides generation copies the configured Google Slides template before making any changes; the original is never edited.

Google Slides configuration accepts either a presentation ID or a normal Google Slides URL.

Environment variables `PROPOSAL_TEMPLATE_ID` and `GOOGLE_SLIDES_TEMPLATE_ID` can still provide bootstrap/default values when no global setting has yet been persisted.

## Presentation generation

Presentation is optional per offer.

When enabled:

1. `slides-plan.md` defines the approved narrative and slide hierarchy.
2. The presentation adapter either copies the global template or creates a blank deck.
3. The Presentation Builder generates bounded Google Slides operations.
4. The real deck is inspected via Slides thumbnails.
5. Visual QA can perform bounded corrective operations without rewriting approved narrative copy.

## Output contracts

Agent executions declare an output format:

- `markdown`
- `optional_markdown`
- `json`
- `text`

Agent Platform normalizes and validates outputs before completing the execution. Invalid output fails instead of forcing Spring/UI code to repair arbitrary LLM formatting.

This keeps the application contract stable regardless of whether the internal runtime is native or LangGraph.

## Local development

### Prerequisites

You need:

- Docker with Docker Compose;
- Node.js/npm only for the one-time Google OAuth setup;
- an Anthropic API key for real model execution;
- Google OAuth credentials if Google Drive/Slides integration is used.

You do **not** need Java, Python, PostgreSQL, NATS, Valkey, LibreOffice or pgvector installed on the host when using Docker Compose.

### 1. Configure environment

```bash
cp .env.example .env
```

At minimum for real AI execution:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

Corporate templates are optional and are normally configured later in the UI.

### 2. Google Workspace OAuth

Put the OAuth client credentials at:

```text
.secrets/google-oauth-credentials.json
```

Authenticate once on the host:

```bash
npm --prefix mcp/google-workspace install
npm --prefix mcp/google-workspace run auth
npm --prefix mcp/google-workspace run doctor
```

This creates:

```text
.secrets/google-token.json
```

Both files are gitignored and mounted read-only into the relevant containers.

### 3. Start the stack

```bash
docker compose up -d --build
```

### Local endpoints

| Component | URL / port |
|---|---|
| ProposalFlow UI | http://localhost:4200 |
| Spring backend | http://localhost:8080 |
| Agent Platform API | http://localhost:8000 |
| Agent Platform OpenAPI | http://localhost:8000/docs |
| Agent Platform Admin | http://localhost:8000/admin/ |
| Document Renderer | http://localhost:8090 |
| PostgreSQL (application) | localhost:5432 |
| PostgreSQL + pgvector (agents/RAG) | localhost:5433 |
| NATS | localhost:4222 |
| NATS monitoring | http://localhost:8222 |
| Valkey | localhost:6379 |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Tempo | http://localhost:3200 |
| Jaeger | http://localhost:16686 |

Grafana local credentials are `admin / admin`.

### Useful health checks

```bash
curl http://localhost:8080/actuator/health
curl http://localhost:8000/health/ready
curl http://localhost:8090/health/ready
```

## First end-to-end run

1. Start the stack and authenticate Google Workspace.
2. Open the UI at `http://localhost:4200`.
3. Optionally configure global DOCX/Slides templates under **Plantillas**.
4. Create an offer and provide the source Google Drive folder.
5. Choose whether presentation generation is required.
6. Review each generated Markdown artifact.
7. Use **PDF · Exportar** if you want a printable version of any artifact while validating it.
8. Refine and approve each phase.
9. Approving **Documento de oferta detallado** triggers `proposal.docx` and `proposal.pdf`.
10. Download the materialized files from the offer view.
11. If presentation was enabled, approve the presentation plan and let the system create the final deck.

## Docker / production direction

Docker Compose is the reference local topology, but service boundaries are intentionally compatible with Kubernetes deployment:

- backend, Agent Platform and document renderer have independent images;
- PostgreSQL/pgvector, NATS and Valkey are externalizable infrastructure dependencies;
- document renderer does not require a PVC and uses ephemeral working storage;
- LibreOffice is inside the renderer/backend images;
- renderer supports a read-only root filesystem and non-root UID;
- health/readiness endpoints are available;
- stateless services can be scaled independently;
- persisted application and knowledge state lives outside service containers.

For a production deployment, credentials should be supplied through Kubernetes Secrets or an external secret manager rather than repository files.

## Persistence

Two PostgreSQL databases intentionally separate application workflow state from cognitive/knowledge state.

### Application database

Stores:

- offers and phase status;
- versioned Markdown artifacts;
- agent execution telemetry;
- materialized DOCX/PDF versions;
- global template settings.

Flyway owns the schema.

### Agent Platform database

Uses PostgreSQL + pgvector for:

- agents/platform persistence;
- LangGraph checkpoints;
- knowledge bases/documents/chunks;
- embeddings and retrieval metadata;
- ontology/retrieval data.

Alembic owns this schema.

## Messaging

NATS JetStream is used for cognitive execution commands/events between Spring and Agent Platform.

The UI never talks directly to NATS or Agent Platform for workflow execution. Spring remains the deterministic owner and the application boundary.

HTTP remains appropriate for management/query operations such as knowledge administration and diagnostics.

## Observability

The stack includes:

- OpenTelemetry Collector;
- Tempo;
- Jaeger;
- Prometheus;
- Grafana.

The application records:

- HTTP/service traces;
- MCP tool spans;
- agent execution status;
- token input/output;
- provider request ids;
- duration/error details;
- proposal-RAG retrieval diagnostics.

This makes cost, latency and retrieval behavior inspectable instead of hidden inside agent calls.

## Testing

Backend:

```bash
docker compose exec backend ./mvnw test
```

If the Maven wrapper is not present in the image/worktree, run Maven inside the backend build environment or locally with Java 21/Maven.

Agent Platform:

```bash
docker compose exec agent-platform pytest
```

Focused retrieval/evaluation tests:

```bash
docker compose exec agent-platform pytest tests/application/test_retrieval.py
docker compose exec agent-platform pytest tests/evaluation
```

Document renderer:

```bash
docker compose exec document-renderer python -m unittest discover -s tests
```

## Repository layout

```text
.
├── frontend/                 Angular UI
├── backend/                  Spring Boot workflow/application backend
├── agent-platform/           FastAPI agent/cognitive platform
├── document-renderer/        deterministic Markdown/DOCX/PDF rendering
├── mcp/google-workspace/     Google Workspace MCP server
├── observability/            OTel, Tempo, Prometheus, Grafana configuration
├── docs/                     architecture and ADR documentation
├── docker-compose.yml        complete local topology
└── .env.example              environment defaults
```

## Security notes

- OAuth credentials/tokens are not committed.
- MCP file downloads are restricted to the workspace area.
- Document renderer runs non-root and is compatible with a read-only filesystem.
- Temporary rendering files are isolated and cleaned up.
- LibreOffice uses isolated temporary user profiles for conversions.
- Corporate source documents should be treated as confidential data; production deployments should add organization-appropriate encryption, retention, authorization and audit policies.

## Design documentation

- [Architecture](docs/architecture.md)
- [Architecture Decision Records](docs/ADRs.md)
- [Agent Platform](agent-platform/README.md)
- [Document Renderer](document-renderer/README.md)
- [Google Workspace MCP](mcp/google-workspace/README.md)
