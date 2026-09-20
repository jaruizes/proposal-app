# Architecture

ProposalFlow separates deterministic proposal workflow from cognitive agent capabilities.

## System context

```text
User
 ↓
Angular UI
 ↓ REST/SSE
Spring Boot ProposalFlow
 ├─ PostgreSQL application state
 ├─ NATS JetStream ───────────────→ Agent Platform
 ├─ Google Workspace MCP           ├─ LangGraph
 └─ Document Renderer              ├─ Anthropic
                                   ├─ PostgreSQL + pgvector
                                   └─ Valkey
```

Spring is the workflow and governance boundary. Agent Platform is the cognitive boundary. LangGraph is an internal Agent Platform runtime.

## Workflow

```text
ANALYSIS
  Entendimiento y cualificación
      ↓ human approval
STRATEGY
  Estrategia de respuesta
      ↓ human approval
SOLUTION
  Propuesta de solución y plan
      ↓ human approval
PROPOSAL
  Documento de oferta detallado
      ↓ human approval
      ├─ deterministic DOCX/PDF materialization
      └─ finish when presentation is disabled
SLIDE_PLAN (optional)
  Propuesta de presentación
      ↓ human approval
PRESENTATION (optional)
  Generación de presentación corporativa
```

## Evidence authority

Three different information classes are intentionally not mixed:

```text
Original current-offer sources
    = factual authority

Approved current-offer artifacts
    = compact, human-approved working context

Historical/reference RAG
    = non-factual structure/depth/style patterns
```

SOLUTION performs source triage before injecting original documents into expensive generation calls. If triage cannot be safely interpreted, the full source bundle is used.

## Proposal graph

`compose-proposal` uses LangGraph internally:

```text
build_context
  → plan_proposal
  → section-aware reference retrieval
  → parallel/bounded section drafting
  → section review
  → assembly
  → global review
  → optional targeted correction
```

Reference retrieval is constrained to `reference-offers` and explicitly marked non-factual.

## Messaging and APIs

- Angular → Spring: REST + SSE.
- Spring → Agent Platform execution: NATS JetStream commands/events.
- Spring → Agent Platform management/query: HTTP when appropriate.
- Spring → document-renderer: HTTP.
- Spring → Google Workspace: MCP stdio.

## Persistence boundaries

### ProposalFlow PostgreSQL

Owns offers, phase state, Markdown artifacts, agent execution telemetry, global template settings and materialized document metadata/binaries.

### Agent Platform PostgreSQL + pgvector

Owns cognitive platform persistence, LangGraph checkpoints, knowledge bases/documents/chunks, embeddings and retrieval metadata.

### Valkey

Non-authoritative cognitive/retrieval cache.

## Document rendering

```text
canonical Markdown
      ↓
python-docx
      ↓
DOCX
      ↓
LibreOffice headless
      ↓
PDF
```

The rendering service is deterministic and contains LibreOffice/fonts in its image. Temporary work uses ephemeral storage; durable documents are persisted by ProposalFlow.

## Templates

Global templates are optional:

- no DOCX template → new neutral DOCX;
- DOCX template → render using that template;
- no Slides template → new blank Google Slides deck;
- Slides template → copy original then edit the copy.

## Observability

OpenTelemetry spans/metrics cross service boundaries. The local stack includes Collector, Tempo, Jaeger, Prometheus and Grafana. Agent telemetry records token usage and provider request metadata; proposal RAG emits section-level retrieval diagnostics.

## Deployment model

Docker Compose is the local reference topology. Boundaries are designed to translate to Kubernetes:

- independent backend, agent-platform and document-renderer containers;
- externalizable PostgreSQL/pgvector, NATS and Valkey;
- non-root/read-only compatible renderer;
- no host/node LibreOffice dependency;
- health/readiness endpoints;
- stateless horizontal scaling for service components.

See [ADRs.md](ADRs.md) for the reasoning and alternatives behind these choices.
