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
  Entendimiento y calificación
  Business Analyst
  → opportunity-brief.md + optional questions.md / technology.md
      ↓ human GO / NO-GO

SOLUTION
  Propuesta de solución y plan de delivery
  Solution Architect + Delivery Manager + optional bounded specialists
  → solution.md + delivery-plan.md
      ↓ human approval

PROPOSAL
  Documento de oferta
  Business Analyst
  → proposal.md
      ↓ human approval
      ├─ deterministic DOCX/PDF materialization
      └─ finish when presentation is disabled

SLIDE_PLAN (optional)
  Hilo de presentación
  Business Analyst
  → slides-plan.md
      ↓ human approval

PRESENTATION (optional)
  Generación de presentación
  Business Analyst + deterministic Google Slides materialization
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

## Proposal generation

`compose-proposal` is adaptive but always owned by one Business Analyst AgentExecution.

Normal volume:

```text
build_context
  → one coherent proposal generation
  → proposal.md
```

Large volume or an incomplete/truncated single pass:

```text
build_context
  → deterministically select canonical artifacts per section
  → section-aware reference retrieval
  → bounded section drafting
  → issues-only review
  → targeted correction only where needed
  → deterministic assembly
  → one global review
  → proposal.md
```

Large-mode substeps are checkpointed in Valkey and reused across retries. Reference retrieval is constrained to `reference-offers` and explicitly marked non-factual.

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


## Declarative cognitive graph resolution

The business workflow engine never selects LangGraph nodes directly. Agent Platform resolves the internal graph from the persisted Skill definition:

```text
AgentExecutionRequest
        ↓
SkillRegistry
        ↓
constraints.execution.graph
        ↓
GraphRegistry
        ├── resilient-single
        ├── proposal
        ├── presentation-plan
        └── future registered graphs
```

`resilient-single` is the default and provides bounded truncation recovery for any skill, including newly added business processes. Specialized graphs are justified only when the task has a meaningful semantic decomposition that cannot be recovered safely by concise retry alone.

This keeps the platform open for workflows such as investment discovery, vendor assessment or architecture review without adding skill-specific conditionals to the central runtime.


## Standard AgentExecution protocol

Spring and Agent Platform communicate through a versioned, process-agnostic protocol. The transport never contains proposal-specific DTOs.

### Command

```text
AgentExecutionCommandV1
  schema_version
  message_type = agent.execution.command
  application
  execution_id
  request
    execution_id
    correlation_id
    agent_key
    skill_key
    objective
    model
    context
    constraints
    attachments[]
      name
      media_type
      content?   # small inline values only
      uri?       # preferred for large/binary resources
      metadata
```

### Event / result

```text
AgentExecutionEventV1
  schema_version
  message_type = agent.execution.event
  execution_id
  event_type
  source_event_type
  payload
    status
    artifacts[]
      type
      name?
      media_type
      content?
      uri?
      metadata
    usage
    model
    provider_request_id
    error?
```

Business semantics belong to the Skill and artifact content/metadata, not to the NATS envelope. New processes can therefore reuse the same protocol unchanged.

Large documents and binaries must be externalized and referenced by URI. NATS transports commands/events and lightweight descriptors, not document payloads.

Output validation is also platform-wide. The declared `constraints.output_format` is validated by the common runtime. Recoverable failures such as provider truncation or incomplete JSON/Markdown are retried according to the Skill execution policy before a terminal failure is emitted.
