# ProposalFlow

ProposalFlow is an end-to-end proposal-generation application built on top of an independent Agent Platform.

The system is designed around a small number of **business phases and accountable roles**, not around one agent invocation per artifact. The Spring Boot application owns the deterministic workflow and human gates; the Agent Platform owns cognitive execution, RAG, skills, checkpoints, caching and model-provider integration.

The main deliverable is a customer-facing proposal document. Presentation generation is optional.

---

## Business workflow

ProposalFlow implements five business phases:

```text
1. Entendimiento y calificación
   Business Analyst
      │
      ├── opportunity-brief.md
      ├── questions.md       optional
      └── technology.md      optional
      │
      ▼
   HUMAN GO / NO-GO
      │
      └── GO
          ▼
2. Propuesta de solución y plan de delivery
   Solution Architect + Delivery Manager
      │
      ├── optional bounded specialists
      ├── solution.md
      └── delivery-plan.md
      │
      ▼
   HUMAN APPROVAL
      │
      ▼
3. Documento de oferta
   Business Analyst
      │
      ├── proposal.md
      ├── proposal.docx
      └── proposal.pdf
      │
      ▼
   HUMAN APPROVAL
      │
      ├── FIN
      │
      └── optional presentation
          ▼
4. Hilo de presentación
   Business Analyst
      │
      └── slides-plan.md
      │
      ▼
   HUMAN APPROVAL
      │
      ▼
5. Generación de presentación
   Business Analyst + deterministic materialization
      │
      └── corporate Google Slides / PPTX-equivalent deck
```

Phases 4 and 5 are optional. If presentation generation is disabled, approval of phase 3 completes the workflow.

### Human decision ownership

AI produces analysis and decision support. It does **not** make the commercial GO/NO-GO decision.

The first human gate is therefore:

```text
Entendimiento y calificación
          ↓
       GO / NO-GO
```

A human business owner decides whether the organization should continue investing in the response.

---

# 1. Entendimiento y calificación

**Owner:** Business Analyst / Offer Owner  
**Skill:** `qualify-opportunity`

This phase merges the previous “Entendimiento y cualificación” and “Estrategia de respuesta” phases.

The Business Analyst performs **one primary reasoning pass** over the customer input corpus. The goal is to understand and qualify the opportunity before any technical solution is designed.

The analysis should answer, whenever the customer evidence supports it:

- What does the customer want?
- Why does the customer want it?
- What business/technical outcomes are expected?
- What is in scope?
- What is explicitly or implicitly outside scope?
- Which dates relate to the bid process?
- Which dates/timing constraints relate to project execution?
- Which dependencies and acceptance conditions are already known?
- Which technologies/products/architectures are mandated, preferred or simply mentioned?
- Which questions remain open?
- Which initial execution risks are already visible?
- Which assumptions can reasonably be made while questions remain open?
- What response strategy/positioning should guide the proposal?
- Which evidence-backed value-add ideas complement the requested scope?

The phase also provides decision support for the human GO/NO-GO gate.

## Outputs

One Business Analyst execution produces up to three canonical artifacts:

### `opportunity-brief.md`

Required. It contains the complete approved understanding of the opportunity, including:

- executive opportunity summary;
- customer needs and drivers;
- expected objectives/outcomes;
- scope IN;
- scope OUT;
- known constraints/dependencies;
- bid/process timing;
- known project timing;
- assumptions;
- initial risks;
- response strategy/positioning;
- potential value-add;
- explicit gaps;
- evidence/source locators;
- GO/NO-GO decision-support factors.

The former standalone `strategy.md` no longer exists. Response strategy belongs in the opportunity brief.

### `questions.md`

Optional.

Contains only material questions that need customer/human clarification. If there are no real open questions, the artifact is not created.

### `technology.md`

Optional.

Contains technologies, products, architectural constraints or technology-related requirements explicitly stated by the customer. It is **not** the proposed solution.

## Efficiency rule

The same Business Analyst does not reread the same source corpus three times to create three files.

```text
customer evidence
       ↓
one BA reasoning execution
       ↓
structured result
   ┌───┼──────────────┐
   ▼   ▼              ▼
brief questions? technology?
```

---

# 2. Propuesta de solución y plan de delivery

This phase contains two clearly separated responsibilities.

## 2.1 Solution design

**Owner:** Solution Architect  
**Skill:** `design-solution`

Primary inputs:

- approved `opportunity-brief.md`;
- optional `questions.md`;
- optional `technology.md`;
- relevant original customer evidence;
- relevant RAG architecture/reference knowledge;
- bounded specialist answers when genuinely needed.

The Solution Architect owns `solution.md`.

### `solution.md` content

The canonical solution document covers:

1. solution summary;
2. principles, design drivers and assumptions;
3. conceptual architecture;
4. logical architecture;
5. physical/deployment architecture;
6. components and proposed technologies;
7. integrations and data;
8. security, resilience, observability and operations;
9. alternatives considered;
10. pros/cons and explicit trade-offs;
11. technical risks;
12. validation points such as spikes, benchmarks or PoCs;
13. implementation tasks;
14. evidence/TBD traceability.

For each implementation task the solution must include:

- task;
- expected outcome/deliverable;
- qualitative complexity;
- dependencies, when present;
- recommended profile type;
- capability/workstream.

Allowed qualitative complexity:

```text
LOW
MEDIUM
HIGH
VERY_HIGH
```

Numeric estimation is forbidden at this stage:

```text
NO person-days
NO hours
NO story points
NO team-size/FTE quantities
NO numeric duration
NO cost / price
```

### Original evidence and RAG

Approved artifacts are the normal working context.

Original customer sources remain factual authority and are reopened only when they materially affect solution correctness.

RAG sources such as architecture references are advisory/reference material. They never override current-customer facts.

### Optional specialists

The Solution Architect may request a **small bounded number** of specialist consultations when normal solution-architecture expertise is insufficient.

For example:

- security/cryptography;
- a concrete data/migration question;
- a provider-specific platform constraint.

Specialists answer bounded questions. They do not own the canonical solution.

### Adaptive generation

Normal-size solutions are generated by one Solution Architect execution.

Large contexts may use:

```text
selected evidence
      ↓
compact architect blueprint
      ↓
3 bounded blocks
      ↓
deterministic assembly
      ↓
solution.md
```

This prevents `max_tokens` failures without turning every solution into many independent agents.

---

## 2.2 Delivery planning

**Owner:** Delivery Manager  
**Skill:** `plan-delivery`

The Delivery Manager starts primarily from:

- approved `opportunity-brief.md`;
- approved `solution.md`, including implementation tasks, complexity, dependencies and profile types.

The Delivery Manager should not reread the complete RFP by default.

### `delivery-plan.md` content

The Delivery Manager defines:

- recommended delivery methodology/lifecycle;
- rationale;
- optional inception/discovery/landing phase;
- workstreams / lines of work;
- sequencing and dependencies;
- milestones;
- decision gates;
- integrated validation/acceptance;
- release/cutover;
- transition/handover;
- customer participation;
- third-party participation;
- governance model;
- governance roles;
- governance forums/ceremonies;
- delivery risks;
- TBDs.

The Delivery Manager does not redefine the technical solution and does not create numeric estimates.

The normal path is **one Delivery Manager execution**.

---

# 3. Documento de oferta

**Owner:** Business Analyst / Offer Owner  
**Skill:** `compose-proposal`

The Business Analyst does not solve the opportunity again in this phase.

The authoritative inputs already exist:

```text
opportunity-brief.md
solution.md
delivery-plan.md
```

Optional `questions.md` and `technology.md` remain available when relevant.

RAG reference offers may be used for:

- structure;
- tone;
- terminology;
- depth;
- proven narrative patterns.

Historical/reference offers are never factual authority for the current customer.

## Default mode: one agent execution

If the approved context fits safely within the configured threshold, one Business Analyst execution writes the complete `proposal.md`.

```text
approved artifacts
      ↓
Business Analyst
      ↓
complete proposal.md
```

The objective is a coherent customer-facing document with a single storyline and voice.

The proposal must not look like independently generated sections concatenated together.

## Large-volume fallback

Only when the input context is too large for a safe single-pass generation does the same Business Analyst AgentExecution switch to bounded internal generation:

```text
large approved context
        ↓
deterministic section-specific context
        ↓
section-aware reference retrieval
        ↓
bounded drafts
        ↓
issues-only reviews
        ↓
correct only affected sections
        ↓
one global consistency review
        ↓
proposal.md
```

Successful internal substeps are persisted in Valkey and reused across retries. Large-volume mode does not create a separate Business Analyst AgentExecution per section or for context selection.

The system does **not** regenerate already successful sections after a late failure when their input fingerprint is unchanged.

## Proposal cost protection

Large proposal generation has configurable safeguards:

```env
PROPOSAL_INPUT_TOKEN_BUDGET=250000
PROPOSAL_OUTPUT_TOKEN_BUDGET=30000
PROPOSAL_COST_BUDGET_USD=2.0
```

If the configured budget is reached, generation stops before continuing to burn model tokens.

## Canonical and materialized outputs

Canonical:

```text
proposal.md
```

After human approval:

```text
proposal.md
   ↓ deterministic renderer
proposal.docx
   ↓ LibreOffice
proposal.pdf
```

DOCX/PDF rendering does not use an LLM.

A proposal may finish here when no presentation is required.

---

# 4. Hilo de presentación

**Owner:** Business Analyst / Offer Owner  
**Skill:** `design-presentation`

Primary input:

- approved `proposal.md`.

Optional inputs:

- presentation guidance;
- previous presentations/offers from RAG for storyline/style patterns.

The complete RFP is not reread by default.

The Business Analyst turns the approved proposal into a presentation narrative.

Output:

```text
slides-plan.md
```

Each planned slide should define:

- slide ID;
- concise exact title;
- primary message/purpose;
- content;
- visual-support intent;
- traceability when useful.

The plan is human-reviewed before presentation materialization starts.

---

# 5. Generación de presentación

**Owner:** Business Analyst / Offer Owner  
**Skill:** `generate-presentation`

The Business Analyst owns the approved presentation content. The materialization layer applies the corporate template and the Business Analyst performs bounded visual QA against the generated deck.

Authority order:

1. approved `slides-plan.md`;
2. corporate template;
3. reference presentations from RAG for style/patterns;
4. upstream artifacts for clarification only.

The system:

- copies the corporate template rather than editing it;
- materializes the approved hierarchy/content;
- performs bounded visual QA;
- preserves approved titles/messages;
- avoids rewriting content merely to fit a layout.

Outputs include the final Google Slides/PPTX-equivalent presentation and a presentation build report.

---

# Active agent and skill model

ProposalFlow intentionally keeps the base team small.

| Agent | Active skills | Responsibility |
|---|---|---|
| `business-analyst` | `qualify-opportunity`, `compose-proposal`, `design-presentation`, `generate-presentation` | Business qualification, strategy, proposal narrative and presentation |
| `solution-architect` | `design-solution` | End-to-end solution design |
| `delivery-manager` | `plan-delivery` | Delivery approach and governance |
| `security-specialist` | `design-solution` | Optional bounded specialist consultation |

The governing rules are:

```text
artifact != agent
skill != mandatory separate model invocation
more complexity != more agents
```

### Expected execution shape

For a normal-size offer without optional specialists, the intended cognitive execution shape is deliberately small:

| Business phase | Typical AgentExecutions | Notes |
|---|---:|---|
| Entendimiento y calificación | 1 | One Business Analyst execution produces brief + optional questions/technology |
| Solución y delivery | 3 | Architect source triage, architect solution, Delivery Manager plan |
| Documento de oferta | 1 | One Business Analyst AgentExecution; large mode may use multiple internal model substeps |
| Hilo de presentación | 1 | Only when presentation is requested |
| Generación de presentación | 1–4 | Initial Business Analyst materialization plan plus bounded visual-QA iterations |

Optional solution specialists add at most two bounded executions. A large solution may also use a compact blueprint plus three bounded architect drafting executions. Those are exceptions driven by volume or specialist need, not the default.


Prefer:

```text
better context engineering
+ structured outputs
+ selective retrieval
+ bounded generation only when necessary
```

over unnecessary agent fan-out.

---

# Canonical artifacts

```text
opportunity-brief.md
questions.md              optional
technology.md             optional
solution.md
delivery-plan.md
proposal.md
slides-plan.md            optional
presentation metadata     optional
```

There is no standalone `strategy.md`.

Markdown artifacts are versioned, inspectable and human-reviewable.

---

# Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│ Angular UI                                                  │
│ offers · gates · artifacts · RAG · templates · telemetry   │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST + SSE
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ Spring Boot backend                                         │
│ deterministic workflow owner                                │
│ phase state · human gates · artifacts · source ingestion    │
│ command/event correlation · document materialization        │
└───────────────┬──────────────────────────────┬──────────────┘
                │ NATS JetStream               │ HTTP/MCP
                ▼                              ▼
┌──────────────────────────────┐      ┌───────────────────────┐
│ Agent Platform               │      │ Render / Workspace     │
│ FastAPI + LangGraph          │      │ DOCX/PDF + Slides      │
│ agents · skills · RAG        │      │ Google Workspace MCP   │
│ checkpoints · Valkey cache   │      └───────────────────────┘
│ provider integrations        │
└───────────────┬──────────────┘
                │
                ├─ PostgreSQL + pgvector
                ├─ Valkey
                └─ Anthropic
```

## True command/event execution

NATS execution is asynchronous end to end.

```text
Spring
  ├─ persist RUNNING
  ├─ publish execution.requested
  └─ return immediately

Agent Platform
  └─ work for as long as needed

NATS
  └─ execution.completed / execution.failed

Spring
  ├─ persist terminal result
  └─ resume phase from durable checkpoints
```

There is no workflow-duration timeout in the NATS path.

Provider/API operations may still have their own bounded technical timeouts.

---

# Retry and durability model

Agent tasks have stable checkpoint keys and input fingerprints.

A completed step is reusable only when all relevant inputs are unchanged:

- model;
- prompt;
- context;
- attachments;
- output contract;
- human refinement.

For large proposal generation, internal substeps are additionally checkpointed in Valkey.

This means a late failure should resume near the failure point instead of paying again for the entire workflow.

---

# RAG and source authority

Authority hierarchy:

```text
current customer sources
        ↓
approved current-offer artifacts
        ↓
RAG references / prior offers
```

Current-customer sources are factual authority.

Approved artifacts are compact working context.

RAG content is used as reference knowledge or style/pattern guidance according to the skill. Historical proposals never introduce customer facts into the current offer.

Default knowledge bases include:

- `reference-offers`;
- `architecture-references`;
- `corporate-roles`;
- `corporate-capabilities`;
- `accelerators`;
- `case-studies`.

---

# Observability and cost

Every AgentExecution exposes:

- agent;
- phase;
- objective;
- status;
- model;
- duration;
- input tokens;
- output tokens;
- prompt-cache read tokens;
- prompt-cache write tokens;
- estimated model cost;
- provider request ID;
- errors.

Large proposal executions additionally expose per-substep usage:

- draft;
- review;
- correction;
- global review;
- checkpoint reuse.

The stack exports OpenTelemetry traces and Prometheus metrics to the local observability environment.

Anthropic prompt caching is enabled for stable agent/skill instructions and reusable proposal context.

---

# Main components

## Frontend

- Angular 20.
- Offer workflow and human gates.
- Artifact preview/raw Markdown.
- Refinement/retry actions.
- RAG/knowledge administration.
- Template configuration.
- Per-agent token/cache/cost observability.
- DOCX/PDF download.
- Presentation workflow.

## Backend

- Java 21 / Spring Boot 3.5.
- PostgreSQL + Flyway.
- Deterministic five-phase business workflow.
- Source ingestion.
- NATS command/event execution.
- Durable phase resume.
- Versioned artifacts.
- Google Workspace MCP integration.
- deterministic DOCX/PDF materialization.

## Reusable cognitive execution policy

Agent Platform does not hard-code business skills into the LangGraph runtime. Every skill declares its cognitive execution policy in `manifest.json`:

```json
{
  "constraints": {
    "execution": {
      "graph": "resilient-single",
      "truncation": {
        "max_attempts": 3,
        "shrink_factors": [1.0, 0.65, 0.40],
        "min_output_tokens": 700
      }
    }
  }
}
```

The built-in graph strategies are:

| Graph | Use |
|---|---|
| `resilient-single` | Default for any bounded current or future skill. One cognitive task with checkpoint/cache support and automatic compact retries on provider truncation. |
| `proposal` | Semantic decomposition for large proposal documents. |
| `presentation-plan` | Semantic decomposition for large presentation storylines. |

A new workflow step therefore does **not** require changing `LangGraphAgentRuntime`. A new skill such as `find-investments` can initially use `resilient-single`. If its cognitive process later needs planning, loops, specialist delegation or tool-driven research, implement and register a graph such as `investment-research` and reference it declaratively from the skill.

The rule is:

```text
business phase / human gate       -> Spring workflow
one cognitive execution           -> Agent Platform
internal cognitive topology       -> graph selected by Skill
provider max_tokens recovery      -> common resilient runtime policy
```

Specialized graphs may add semantic splitting, soft budgets and graceful quality degradation, but they remain behind the same `AgentExecutionRequest -> AgentExecutionResult` contract.

## Agent Platform

- Python/FastAPI.
- LangGraph runtime.
- agent/skill registries.
- Anthropic provider.
- PostgreSQL LangGraph checkpoints.
- pgvector knowledge/RAG.
- Valkey caches/checkpoints.
- hybrid retrieval.
- ontology signals.
- OpenTelemetry.

## Document Renderer

- Markdown → DOCX using `python-docx`.
- DOCX → PDF using LibreOffice headless.
- No LLM involved in rendering.

---

# Local development

## Prerequisites

Using Docker Compose, the host only needs:

- Docker + Docker Compose;
- an Anthropic API key for real model execution;
- Google OAuth credentials when Drive/Slides integration is used.

## Configure

```bash
cp .env.example .env
```

At minimum:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

## Start

```bash
docker compose up -d --build
```

## Main local endpoints

| Component | URL / port |
|---|---|
| ProposalFlow UI | http://localhost:4200 |
| Spring backend | http://localhost:8080 |
| Agent Platform | http://localhost:8000 |
| Agent Platform API docs | http://localhost:8000/docs |
| Document Renderer | http://localhost:8090 |
| Application PostgreSQL | localhost:5432 |
| Agent/RAG PostgreSQL | localhost:5433 |
| NATS | localhost:4222 |
| NATS monitoring | http://localhost:8222 |
| Valkey | localhost:6379 |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Tempo | http://localhost:3200 |
| Jaeger | http://localhost:16686 |

---

# First clean end-to-end run

1. Start/rebuild the stack.
2. Configure optional corporate templates.
3. Create a new offer and provide the input source folder.
4. Let **Entendimiento y calificación** finish.
5. Review `opportunity-brief.md`, optional `questions.md` and optional `technology.md`.
6. Make the human GO/NO-GO decision.
7. If GO, approve the phase.
8. Review and approve **Propuesta de solución y plan de delivery**.
9. Review and approve **Documento de oferta**.
10. Download the materialized DOCX/PDF.
11. Stop here when no presentation is required.
12. Otherwise approve/iterate **Hilo de presentación**.
13. Generate and inspect the final corporate presentation.

For a clean database, ProposalFlow creates only the five current business phases. No compatibility migration from the previous six-phase workflow is required for a fresh run.

---

# Repository layout

```text
.
├── frontend/
├── backend/
├── agent-platform/
├── document-renderer/
├── mcp/google-workspace/
├── observability/
├── docs/
├── docker-compose.yml
└── .env.example
```

Additional architecture detail is available under `docs/`.
