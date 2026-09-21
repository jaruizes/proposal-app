# Architecture Decision Records

This document records the principal architecture decisions currently embodied in ProposalFlow / Proposal Agent Platform. It is a consolidated ADR log rather than a chronological set of separate files.

Statuses use **Accepted** for decisions currently implemented. A future change should update the relevant ADR rather than silently contradict it.

---

## ADR-001 — Separate deterministic application orchestration from the cognitive agent platform

**Status:** Accepted

### Problem / motivation

Proposal generation contains two very different classes of responsibility:

- deterministic business workflow: offer state, phase ordering, human approval, retries, artifacts and final deliverables;
- cognitive capabilities: LLM execution, agents, skills, RAG, memory, ontology and model-provider integration.

Putting both concerns in one service would make the business workflow dependent on whichever agent framework happens to be used.

### Decision

Keep Spring Boot as the deterministic ProposalFlow workflow owner and run an independent FastAPI Agent Platform for cognitive execution.

### Alternatives considered

- Put all orchestration in LangGraph.
- Put all cognitive logic directly in Spring.
- Use an external workflow/orchestration SaaS for both.

### Why this option

The application can evolve its business rules without coupling them to LangGraph, while Agent Platform can serve future applications. Human gates and artifact state remain explicit and deterministic.

### Consequences

There are additional service/network boundaries, but responsibilities are clearer and the cognitive runtime is replaceable.

---

## ADR-002 — Use hexagonal architecture in the Spring backend

**Status:** Accepted

### Problem / motivation

The backend integrates databases, NATS, MCP, Google Workspace, Agent Platform and document rendering. Business orchestration should not depend directly on those technologies.

### Decision

Use the dependency direction:

```text
infrastructure → business → domain
```

Domain defines models/ports, business implements use cases, infrastructure implements adapters.

### Alternatives considered

- Traditional controller/service/repository layering with framework types everywhere.
- Direct use of infrastructure clients from workflow code.

### Why this option

It preserves testability and lets adapters such as NATS, HTTP or rendering change without redesigning core workflow semantics.

### Consequences

More ports and mapping code are required.

---

## ADR-003 — Keep LangGraph behind Agent Platform contracts

**Status:** Accepted

### Problem / motivation

LangGraph is useful for graph execution, section-level proposal orchestration and checkpoints, but exposing LangGraph concepts as the public API would couple clients to one framework.

### Decision

Agent Platform exposes stable execution APIs and an `AgentRuntime` abstraction. LangGraph is an internal runtime implementation.

### Alternatives considered

- Spring calls LangGraph directly.
- Make LangGraph graph/thread ids the public contract.
- Keep only the original native runtime.

### Why this option

It provides LangGraph capabilities while retaining the ability to compare or replace runtimes without breaking clients.

### Consequences

Some execution state exists both at platform level and in LangGraph checkpoints; platform execution state/events remain the external source of truth.

---

## ADR-004 — Spring owns human gates and phase transitions

**Status:** Accepted

### Problem / motivation

AI output must be reviewed before downstream phases consume it. LLM-controlled transitions would make governance and reproducibility weak.

### Decision

Spring deterministically owns phase states and approvals. Agents produce artifacts but cannot approve or advance their own phase.

### Alternatives considered

- Fully autonomous agent workflow.
- Approval nodes implemented only inside LangGraph.

### Why this option

Human validation is a business requirement rather than a cognitive behavior. It must remain enforceable even if the model/runtime changes.

### Consequences

The application carries explicit workflow state and must coordinate async agent execution.

---

## ADR-005 — Use five business phases with a human GO/NO-GO gate and optional presentation

**Status:** Accepted

### Problem / motivation

The earlier six-phase flow separated opportunity understanding and response strategy even though both are normally owned by the same Business Analyst over the same evidence. That duplicated context and model calls.

### Decision

Use this fixed semantic workflow:

1. Entendimiento y calificación
2. Propuesta de solución y plan de delivery
3. Documento de oferta
4. Hilo de presentación
5. Generación de presentación

Phase 1 includes response strategy and produces decision support for a **human** GO/NO-GO gate. Phases 4 and 5 are optional. If presentation generation is disabled, approval of phase 3 completes the offer.

### Alternatives considered

- Keep understanding and response strategy as separate phases.
- Fully autonomous GO/NO-GO.
- Always generate slides.
- Allow arbitrary user-defined phase order.

### Why this option

It matches real proposal ownership, removes repeated Business Analyst reads of the same source corpus and keeps commercial decisions under human control.

### Consequences

There is no standalone `strategy.md`. Strategy is part of `opportunity-brief.md`. A clean database creates only the five current phases.

---

## ADR-006 — Use Markdown as the canonical cognitive artifact format

**Status:** Accepted

### Problem / motivation

Agent output needs to be reviewable, versionable, renderer-independent and easy to pass between phases.

### Decision

Store principal cognitive outputs as versioned Markdown artifacts.

### Alternatives considered

- Generate DOCX directly with the LLM.
- Store only rich HTML.
- Store arbitrary free-form text or JSON for every document.

### Why this option

Markdown is compact, diffable, human-readable and independent of final presentation technology.

### Consequences

A deterministic renderer is required for polished final documents.

---

## ADR-007 — Standardize Agent Platform output contracts

**Status:** Accepted

### Problem / motivation

Historically, callers had to repair or adapt different LLM output shapes, which pushed model-format concerns into Spring/UI code.

### Decision

Executions declare one of `markdown`, `optional_markdown`, `json` or `text`. Agent Platform normalizes and validates the result before completion.

### Alternatives considered

- Let each caller parse arbitrary responses.
- Put per-skill parsing logic only in Spring.

### Why this option

All runtimes/providers expose the same behavior and malformed output fails near its source.

### Consequences

Skills must declare accurate output contracts.

---

## ADR-008 — Use NATS JetStream for cognitive execution commands/events

**Status:** Accepted

### Problem / motivation

LLM executions are asynchronous, potentially long-running and should not tie up a synchronous Spring HTTP request.

### Decision

Use NATS JetStream for execution requests and execution events between Spring and Agent Platform. Keep HTTP for management/query APIs.

### Alternatives considered

- Synchronous REST only.
- Kafka.
- Database polling.

### Why this option

NATS is lightweight, supports durable messaging and fits command/event execution without introducing Kafka's operational weight for this use case.

### Consequences

The system has messaging infrastructure and must handle idempotency/timeouts/event correlation.

---

## ADR-009 — UI talks to Spring, not directly to the cognitive runtime

**Status:** Accepted

### Problem / motivation

The UI needs one coherent business boundary and must not bypass workflow rules.

### Decision

Angular uses Spring REST/SSE for offer workflow. Spring integrates Agent Platform.

### Alternatives considered

- Angular calls Agent Platform directly for executions.
- Browser connects directly to NATS.

### Why this option

It prevents clients from bypassing approvals, persistence rules and application authorization boundaries.

### Consequences

Spring acts as a facade for some Agent Platform management/query functionality.

---

## ADR-010 — Maintain two PostgreSQL databases

**Status:** Accepted

### Problem / motivation

Application transaction/state concerns and cognitive knowledge/vector/checkpoint concerns have different schemas and evolution rates.

### Decision

Use:
- regular PostgreSQL for ProposalFlow application state;
- PostgreSQL + pgvector for Agent Platform, knowledge/RAG and checkpoints.

Flyway manages the application schema; Alembic manages Agent Platform.

### Alternatives considered

- One shared database/schema.
- Separate specialized vector database.
- In-memory checkpoints.

### Why this option

It preserves service ownership while using familiar operational technology and pgvector for embeddings.

### Consequences

Two databases must be backed up/operated independently.

---

## ADR-011 — Use Valkey for Agent Platform cache

**Status:** Accepted

### Problem / motivation

Retrieval and cognitive results can benefit from cache without coupling cache state to persistent business data.

### Decision

Use Valkey through Redis-compatible APIs.

### Alternatives considered

- Redis.
- In-process cache only.
- PostgreSQL cache tables.

### Why this option

Valkey is lightweight, Redis-compatible and independently scalable.

### Consequences

Cached data is explicitly non-authoritative and must tolerate eviction.

---

## ADR-012 — Ingest source documents multimodally

**Status:** Accepted

### Problem / motivation

Proposal sources may contain tables, diagrams and layouts that plain text extraction can lose.

### Decision

Use native Google APIs where useful, download/export binaries where needed, extract text with Tika and create PDF visual representations for supported Office documents.

### Alternatives considered

- Text extraction only.
- OCR everything.
- Send every original file directly to the model.

### Why this option

It preserves rich evidence while keeping a normalized textual context for most reasoning.

### Consequences

Source ingestion is more complex and includes LibreOffice as a native dependency.

---

## ADR-013 — Package LibreOffice in service images

**Status:** Accepted

### Problem / motivation

Office-to-PDF conversion is required both during source ingestion and final document rendering. Requiring developers or Kubernetes nodes to install LibreOffice would reduce portability.

### Decision

Install LibreOffice and required open fonts inside the backend/document-renderer container images.

### Alternatives considered

- Install LibreOffice on every host/node.
- Use a hosted conversion API.
- Remove visual Office conversion.

### Why this option

Docker Compose and Kubernetes receive identical, self-contained behavior.

### Consequences

Images are larger and LibreOffice processes need timeouts/isolation.

---

## ADR-014 — Give each LibreOffice conversion an isolated temporary profile

**Status:** Accepted

### Problem / motivation

Concurrent headless LibreOffice processes can conflict through user-profile locks/state.

### Decision

Use a unique temporary `UserInstallation` profile per render/conversion and clean temporary data afterward.

### Alternatives considered

- Share the default profile.
- Run one persistent LibreOffice process.

### Why this option

It reduces lock/state leakage and makes individual conversions easier to terminate safely.

### Consequences

Each render creates small temporary directories and startup overhead.

---

## ADR-015 — Use approved artifacts as compact context but keep current-offer originals as factual authority

**Status:** Accepted

### Problem / motivation

Repeatedly sending full source documents is expensive, but relying only on summaries can hide technical constraints needed for solution design.

### Decision

Approved artifacts are compact working context. Original current-offer sources remain the factual authority and can be consulted again when required.

### Alternatives considered

- Never revisit originals after analysis.
- Always resend all originals to every phase.

### Why this option

It balances token cost with factual completeness.

### Consequences

Context selection must be explicit and observable.

---

## ADR-016 — Triage original sources before expensive solution-generation calls

**Status:** Accepted

### Problem / motivation

SOLUTION often needs original technical evidence, but large corpora make unconditional multimodal context expensive.

### Decision

First give the Solution Architect approved artifacts plus the source manifest. It classifies each source as `REVIEW_IN_DEPTH`, `TARGETED_REVIEW` or `SKIP`. Only selected originals are injected into subsequent solution calls.

If triage is invalid/unparseable, fall back to the full source bundle.

### Alternatives considered

- Always send the complete source bundle.
- Use only `technology.md`.
- Let Spring make a fixed filename/type-based selection.

### Why this option

The model can select evidence based on the actual problem, while fallback protects correctness.

### Consequences

There is an additional triage call, but expensive downstream context is reduced.

---

## ADR-017 — Bound specialist fan-out in solution design

**Status:** Accepted

### Problem / motivation

Unbounded agent delegation can multiply cost/latency without predictable quality gains.

### Decision

Solution triage can request at most two genuinely necessary specialist consultations.

### Alternatives considered

- No specialists.
- Unlimited autonomous delegation.
- Always invoke a fixed set of specialists.

### Why this option

Specialists remain available for hard topics while cost and orchestration remain bounded.

### Consequences

Some complex opportunities may need future configurable limits.

---

## ADR-018 — Treat historical reference proposals as non-factual RAG context

**Status:** Accepted

### Problem / motivation

Historical proposals are valuable examples but contain another customer's facts, commitments and technology.

### Decision

`reference-offers` retrieval may inform structure, depth, terminology patterns and style only. Prompts explicitly label retrieved references as non-factual.

### Alternatives considered

- Put reference proposals in the same factual context as current sources.
- Do not use historical proposals at all.

### Why this option

It captures reuse value without contaminating the current proposal with unsupported facts.

### Consequences

Retrieval context must clearly label provenance/authority.

---

## ADR-019 — Retrieve proposal references selectively in large-volume proposal mode

**Status:** Accepted

### Problem / motivation

Historical proposal examples can improve structure and depth, but retrieving references for every section is unnecessary when one coherent proposal call is sufficient.

### Decision

Normal-size proposals use one Business Analyst generation and at most a small whole-proposal reference lookup. Section-by-section `reference-offers` retrieval is activated only in large-volume bounded generation.

### Alternatives considered

- Always perform section-level retrieval.
- Feed complete historical proposals.
- Never use proposal references.

### Why this option

It preserves narrative coherence and lowers retrieval/context overhead for normal proposals while retaining targeted examples for large documents.

### Consequences

Retrieval diagnostics differ by mode; historical references remain explicitly non-factual in both modes.

---

## ADR-020 — Apply relevance gating before top-k retrieval results

**Status:** Accepted

### Problem / motivation

Rank fusion can always produce a "best" item even for meaningless queries. Returning exactly top-k regardless of relevance makes RAG misleading.

### Decision

Treat `top_k` as an upper bound after relevance filtering. Vector/keyword/graph candidates are gated using their component semantics rather than thresholding a reciprocal-rank-fusion score as if it were semantic similarity.

### Alternatives considered

- Always return k results.
- Threshold the final RRF score.
- Let the LLM ignore irrelevant chunks.

### Why this option

It allows zero-result retrieval and avoids pretending a rank-fusion score is semantic confidence.

### Consequences

Thresholds/policies need calibration and evaluation cases.

---

## ADR-021 — Use deterministic knowledge classification/enrichment where possible

**Status:** Accepted

### Problem / motivation

Basic document classification/metadata should not require an LLM call or introduce nondeterministic cost.

### Decision

The selected knowledge base is authoritative for document class; deterministic enrichment derives metadata such as language, keywords, headings and hashes.

### Alternatives considered

- LLM-classify every uploaded document.
- Require every metadata field manually.

### Why this option

It is cheap, reproducible and keeps human-selected knowledge-base intent authoritative.

### Consequences

Advanced semantic metadata may need future model-assisted enrichment.

---

## ADR-022 — Prefer one coherent proposal generation and fall back to bounded LangGraph generation only for large volume

**Status:** Accepted

### Problem / motivation

Always splitting a proposal into many model calls increases token cost and can produce a fragmented narrative. A single very large call, however, can truncate on large opportunities.

### Decision

`compose-proposal` always has one Business Analyst AgentExecution.

- **SINGLE mode:** one model generation writes the complete proposal when approved context fits the configured threshold.
- **SPLIT mode:** for large context, or when the single pass is structurally incomplete/truncated, the same AgentExecution compacts context once and uses bounded internal LangGraph substeps.

Split mode uses section-specific context, reference retrieval, issues-only review, targeted correction, deterministic assembly and one global review. Successful internal substeps are checkpointed in Valkey.

### Alternatives considered

- Always one huge generation.
- Always generate every section independently.
- Separate Business Analyst AgentExecutions for compaction and each section.

### Why this option

It makes narrative coherence and low execution count the default while retaining a safe escape hatch for very large documents.

### Consequences

The runtime must route dynamically by volume, validate single-pass completeness and maintain durable internal checkpoints for split mode.

---

## ADR-023 — Separate cognitive content from final document rendering

**Status:** Accepted

### Problem / motivation

Branding/layout changes should not require rerunning expensive LLM generation.

### Decision

LLMs produce canonical Markdown. A deterministic document renderer creates DOCX/PDF from approved content.

### Alternatives considered

- Ask the LLM to produce DOCX/HTML directly.
- Make Spring itself a full document layout engine.
- Generate only PDF.

### Why this option

Content and presentation evolve independently, and renders are reproducible.

### Consequences

The project owns a rendering service and template semantics.

---

## ADR-024 — Generate PDF from the generated DOCX

**Status:** Accepted

### Problem / motivation

Independent Markdown→DOCX and Markdown→PDF pipelines can produce visibly different deliverables.

### Decision

Render Markdown to DOCX first, then convert that DOCX to PDF with LibreOffice.

### Alternatives considered

- Markdown→HTML→PDF separately.
- Direct PDF library in parallel with DOCX.
- Only DOCX, no PDF.

### Why this option

DOCX and PDF represent the same layout/content pipeline.

### Consequences

PDF availability depends on successful DOCX generation and LibreOffice conversion.

---

## ADR-025 — Run document rendering as an independent service

**Status:** Accepted

### Problem / motivation

Document rendering has heavy native dependencies and different CPU/memory/scaling characteristics from the Spring application.

### Decision

Create a separate `document-renderer` service exposing deterministic rendering APIs.

### Alternatives considered

- Embed all rendering inside Spring.
- Invoke host-installed LibreOffice.
- Use Kubernetes Jobs for every render from day one.

### Why this option

The service can be independently containerized/scaled and works the same in Docker Compose or Kubernetes.

### Consequences

One additional service/API boundary exists.

---

## ADR-026 — Keep document-renderer stateless with ephemeral working storage

**Status:** Accepted

### Problem / motivation

Temporary Office/PDF files should not require persistent node storage and should not make pods stateful.

### Decision

Use `/tmp` ephemeral storage for jobs and return/persist results through the application. No renderer PVC is required.

### Alternatives considered

- Persistent filesystem/PVC for rendered files.
- Shared NFS.
- Store files permanently inside renderer pods.

### Why this option

It simplifies horizontal scaling and pod replacement.

### Consequences

All durable output must be persisted elsewhere before temp data is deleted.

---

## ADR-027 — Persist final materialized documents separately from Markdown artifacts

**Status:** Accepted

### Problem / motivation

Canonical content versions and visual render versions are not the same concept.

### Decision

Store materialized documents with both `contentVersion` and `renderVersion`, plus source hash, renderer version, template and binary content.

### Alternatives considered

- Store DOCX/PDF as ordinary artifacts with one version.
- Re-render every download.
- Store only external filesystem paths.

### Why this option

The system can distinguish content changes from template/renderer changes and reproduce/download historical output.

### Consequences

Binary data is stored in application PostgreSQL; large-scale deployment may later move binary content to object storage while keeping metadata/contracts.

---

## ADR-028 — Make materialization idempotent

**Status:** Accepted

### Problem / motivation

Retries, repeated clicks and async workflow execution should not create duplicate renders or waste CPU.

### Decision

Build a deterministic render key from source hash, template id, renderer version, materializer version and output type. Reuse an existing READY result with the same key.

### Alternatives considered

- Always create a new render version.
- Deduplicate only by proposal artifact version.

### Why this option

Template/renderer changes correctly create a new render while identical requests are free.

### Consequences

Renderer version must be exposed and included in identity.

---

## ADR-029 — Do not roll back proposal approval when rendering fails

**Status:** Accepted

### Problem / motivation

A DOCX/PDF renderer outage does not invalidate the human-approved proposal content.

### Decision

Proposal approval is authoritative and committed first. Document materialization runs asynchronously afterward and records independent `READY`/`FAILED` states.

### Alternatives considered

- Make approval transaction depend on successful PDF.
- Mark the proposal phase FAILED if PDF fails.

### Why this option

It separates business approval from derived-format infrastructure availability.

### Consequences

UI must expose render failures and retries separately.

---

## ADR-030 — Configure corporate templates globally, not per offer

**Status:** Accepted

### Problem / motivation

Corporate branding is a platform-level concern and requiring template ids on every offer creates repetitive configuration and blocks creation.

### Decision

Expose a global **Plantillas** area for:
- proposal DOCX template;
- Google Slides template.

Offers no longer require template fields.

### Alternatives considered

- Require template per offer.
- Hard-code templates in environment variables/images.
- Keep both global and per-offer overrides.

### Why this option

Most organizations use a common corporate standard, so global configuration is simpler and less error-prone.

### Consequences

Per-customer/per-offer overrides are not currently supported and would need an explicit future precedence rule.

---

## ADR-031 — Templates are optional and never a workflow prerequisite

**Status:** Accepted

### Problem / motivation

A user must be able to evaluate ProposalFlow without first creating corporate templates.

### Decision

If no DOCX template exists, create a new neutral document. If no Slides template exists, create a new blank Google Slides deck.

### Alternatives considered

- Fail when template is missing.
- Ship one mandatory built-in corporate template.

### Why this option

It minimizes setup friction and decouples content generation from branding availability.

### Consequences

Blank-mode output is less branded but functionally complete.

---

## ADR-032 — Never modify a Google Slides corporate template in place

**Status:** Accepted

### Problem / motivation

A shared corporate template is reusable source material and must not be corrupted by a proposal run.

### Decision

When a Slides template is configured, copy it first and apply all generated operations to the copy.

### Alternatives considered

- Edit then restore the template.
- Create a blank deck and manually reproduce template styling.

### Why this option

Copy-on-write is simple and protects the source template.

### Consequences

Google Drive accumulates generated copies as expected deliverables.

---

## ADR-033 — Materialize presentations through Google Workspace MCP

**Status:** Accepted

### Problem / motivation

Presentation generation needs stable, auditable tool calls and access to real Google Slides structures/thumbnails.

### Decision

Expose Drive/Slides operations through the local Google Workspace MCP server and let Spring's presentation adapter invoke those tools.

### Alternatives considered

- Direct Google API clients scattered through business code.
- Browser automation.
- Export PPTX locally and upload.

### Why this option

MCP centralizes tool schemas/authentication and is reusable by agent/tool workflows.

### Consequences

The backend packages/runs the MCP server and OAuth lifecycle must be configured.

---

## ADR-034 — Perform bounded visual QA on the real generated slide deck

**Status:** Accepted

### Problem / motivation

A structurally valid Slides API result can still contain clipping, overlap, density or template leftovers.

### Decision

Fetch thumbnails from the actual generated deck and allow a bounded number of corrective operations.

### Alternatives considered

- Trust the first operation plan.
- Render a separate local preview not tied to Google Slides.
- Unlimited autonomous fix loop.

### Why this option

QA evaluates the real artifact while bounding latency/cost.

### Consequences

Presentation generation performs extra tool/model calls.

---

## ADR-035 — Use global template settings persisted in the application database with environment fallback

**Status:** Accepted

### Problem / motivation

Runtime administrators need editable template configuration, while deployments may still need bootstrap defaults.

### Decision

Persist global template settings in PostgreSQL. If no global row exists yet, optional environment defaults can initialize behavior.

### Alternatives considered

- Environment variables only.
- Git-managed config only.
- A separate configuration service.

### Why this option

It gives UI manageability without losing deployment-time defaults.

### Consequences

Once persisted, database configuration is the operational source for template settings.

---

## ADR-036 — Expose artifact-level PDF export on demand

**Status:** Accepted

### Problem / motivation

Users may want a readable/printable version of intermediate Markdown artifacts while deciding whether to approve them.

### Decision

Add a PDF export action to the Markdown artifact viewer. The backend sends the selected artifact version through the deterministic renderer.

### Alternatives considered

- Persist PDF for every artifact automatically.
- Browser print-to-PDF only.
- Only export the final proposal.

### Why this option

It provides a useful validation aid without automatically storing/rendering every intermediate artifact.

### Consequences

Intermediate PDF export consumes renderer CPU but no model tokens.

---

## ADR-037 — Use OpenTelemetry as the cross-service observability standard

**Status:** Accepted

### Problem / motivation

The platform spans HTTP, NATS, MCP, LLM calls and retrieval. Troubleshooting and cost analysis require correlation.

### Decision

Instrument services with OpenTelemetry and export to the Collector, Tempo/Jaeger, Prometheus and Grafana.

### Alternatives considered

- Logs only.
- Vendor-specific APM.
- Separate tracing implementations per service.

### Why this option

OTel is vendor-neutral and covers distributed traces/metrics across the architecture.

### Consequences

Observability infrastructure is part of the local stack.

---

## ADR-038 — Persist token/provider execution telemetry

**Status:** Accepted

### Problem / motivation

Multi-agent/graph workflows can hide real cost and make optimization subjective.

### Decision

Record per-agent model, input/output tokens, duration, status, provider request id and errors; expose them in the UI.

### Alternatives considered

- Aggregate provider billing only.
- Log token counts without persistence.

### Why this option

Optimization decisions can be based on actual phase/agent consumption.

### Consequences

Telemetry schema evolves with provider capabilities.

---

## ADR-039 — Keep RAG retrieval diagnostics observable

**Status:** Accepted

### Problem / motivation

When reference material affects proposal writing, users/developers need to know which chunks were retrieved.

### Decision

Emit proposal section retrieval events containing query, section class, document/chunk identifiers, scores and candidate/relevance metadata, without duplicating full chunk bodies into observability events.

### Alternatives considered

- Opaque retrieval.
- Store full retrieved text in every telemetry event.

### Why this option

It gives useful provenance/debugging without unnecessary data duplication.

### Consequences

Diagnostics can expose document identifiers and should follow production access-control policies.

---

## ADR-040 — Docker Compose is the reference local environment, with Kubernetes-ready service boundaries

**Status:** Accepted

### Problem / motivation

Contributors should be able to run the complete system without installing infrastructure/native runtimes, while production may move to Kubernetes.

### Decision

Package application components in independent images and provide a complete Docker Compose topology. Keep services stateless where practical, expose health endpoints, avoid host-native LibreOffice dependencies and use external persistence.

### Alternatives considered

- Require all dependencies locally.
- Develop directly against Kubernetes only.
- Monolithic all-in-one container.

### Why this option

Compose gives low-friction local onboarding and maps cleanly to Deployments/Services/managed infrastructure later.

### Consequences

Production Kubernetes manifests/Helm are a separate deployment concern and are not implied by Compose itself.

---

## ADR-041 — Favor correctness over token savings when evidence selection is uncertain

**Status:** Accepted

### Problem / motivation

Context optimization can accidentally remove evidence required to produce a correct proposal.

### Decision

Use selection/triage to reduce context, but explicitly fall back to broader/full evidence when selection cannot be trusted.

### Alternatives considered

- Strict token cap even if evidence is omitted.
- Always use full context.

### Why this option

The platform optimizes cost without making cost reduction more important than proposal correctness.

### Consequences

Worst-case executions may still be expensive, and telemetry should be used to improve future retrieval/selection.
