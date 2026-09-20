---
name: define-solution
description: Execute phase 3 with Solution Architect owning solution.md, Delivery Manager owning delivery-plan.md, and Business Analyst coordinating/coherence-checking the offer.
---

# Fase 3 — Definición de solución y enfoque de ejecución

Input:

```text
workspace/<proposal>
```

Purpose: transform the approved strategy into a proposal-level solution and an unestimated high-level work breakdown before slide planning.

## Preconditions

Require:

```text
analysis.status: approved
strategy.status: approved
working/source-manifest.json
```

Read approved analysis/strategy artifacts.

## Base offer team and execution topology

Phase 3 is deliberately multi-role because it models a real offer team:

```text
Business Analyst / Offer Owner     # coordinator, main context
        ↓
Solution Architect                 # dedicated base-role context
        ↓ owns
solution.md
        ↓
Delivery Manager                   # dedicated base-role context
        ↓ owns
delivery-plan.md
        ↓
Business Analyst                   # coherence review in coordinator context
```

`solution-architect` and `delivery-manager` are **base-role agents**, not optional specialists and not counted against the specialist-consultation limit.

Execute them **sequentially, not in parallel**. The Delivery Manager must consume the architect's completed `solution.md`.

The Business Analyst coordinates but must not silently replace either owner's judgement.

## Source authority

Canonical principle:

```text
validated artifacts = orientation/context
original customer sources = authority
```

### Solution Architect review contract

The `solution-architect` role must receive:

```text
working/source-manifest.json
generated/analysis/opportunity-brief.md
generated/analysis/questions.md      # if present
generated/analysis/technology.md     # if present
generated/strategy/strategy.md
```

Before finalizing `solution.md`, inspect the **complete source inventory** and classify every source:

```text
REVIEW_IN_DEPTH | TARGETED_REVIEW | SKIP
```

Review original/native evidence directly whenever it may materially affect:

- functional requirements, processes, users or domain rules;
- data;
- integrations/interfaces/protocols;
- architecture/stack/platform;
- security/identity;
- NFRs such as availability, performance or scalability;
- operations/observability;
- deployment/infrastructure;
- legacy/migration/transition;
- diagrams/tables/visual relationships.

A document is not irrelevant merely because it is non-technical. Functional understanding is mandatory for valid architecture.

For a small corpus where most documents can change the solution, prefer full review of all. For large corpora, triage all and deeply review relevant/possibly relevant sources. Record skipped `DOC-nnn` sources and short reason in `solution.md`.

### Delivery Manager review contract

After `solution.md` exists, execute `delivery-manager` with:

```text
working/source-manifest.json
generated/analysis/opportunity-brief.md
generated/analysis/questions.md      # if present
generated/strategy/strategy.md
generated/solution/solution.md
```

The Delivery Manager also inspects the complete source inventory and directly reviews original/native sources that may materially affect:

- execution scope/work packages;
- functional decomposition;
- deliverables;
- dependencies/customer participation;
- access/environments/data prerequisites;
- methodology/governance;
- testing/acceptance;
- migration/transition/cutover;
- operational readiness/support;
- execution milestones/regulatory dates;
- third-party coordination.

It must not create the plan solely from `solution.md` or other summaries when original evidence could change delivery structure.

## Optional deep specialists

Optional specialists are additional to the three base roles. Typical examples:

```text
security/cryptography
AWS/Azure/GCP
OpenShift/Red Hat
network
SAP/mainframe
database/performance
data/AI
specific domain SME
```

The Solution Architect or Delivery Manager should normally be sufficient for proposal-level work. Consult an optional specialist only for a bounded question requiring deeper expertise.

Default maximum: **2 optional specialist consultations** in phase 3. If more seem necessary, stop and ask the human rather than creating fan-out.

For every consultation specify:

1. exact question(s);
2. approved artifacts needed;
3. relevant original customer sources/locators to inspect directly;
4. explicit out-of-scope;
5. concise expected result.

Optional specialists do not own canonical files or workflow state.

## No-estimation rule

Phase 3 must not produce:

- person-hours/person-days;
- story points/velocity;
- S/M/L or hidden sizing;
- team size/headcount/FTE/allocation;
- estimated weeks/months/duration;
- price/cost/margin;
- commercial commitment dates.

Customer-imposed dates/cadence may be recorded as `FACT`.

# A. `solution.md` — owner: Solution Architect

Write exactly:

```text
generated/solution/solution.md
```

Recommended structure:

```text
# Definición de solución
## 1. Resumen de la solución propuesta
## 2. Principios de solución
## 3. Arquitectura de solución
### 3.1 Arquitectura lógica
### 3.2 Componentes principales
### 3.3 Integraciones
### 3.4 Datos
### 3.5 Seguridad
### 3.6 Alta disponibilidad, resiliencia y continuidad
### 3.7 Observabilidad y operación
### 3.8 Despliegue e infraestructura
## 4. Tratamiento del legado y transición
## 5. Decisiones técnicas y trade-offs
## 6. Condicionantes de delivery
## 7. Riesgos de ejecución y mitigaciones actualizadas
## 8. Capacidades/perfiles necesarios a alto nivel
## 9. Decisiones, asunciones y TBDs pendientes
## 10. Elementos clave que deberán aparecer en la oferta
## 11. Revisión de fuentes realizada por el arquitecto
## 12. Consultas/validaciones de especialistas realizadas
```

For material technical statements distinguish when useful:

```text
FACT | PRINCIPLE | PROPOSAL | DECISION | ASSUMPTION
```

A `PROPOSAL` is not automatically a committed detailed-design decision.

Do not fabricate internal reusable assets. Do not claim a custom development has no third-party dependencies: normal framework/library dependencies exist unless evidence says otherwise; SBOM/dependency management should reflect that.

# B. `delivery-plan.md` — owner: Delivery Manager

Write exactly:

```text
generated/solution/delivery-plan.md
```

This is the delivery plan for materializing `solution.md`. It must explain how the solution should be delivered, not redefine the solution itself.

It answers questions such as:

```text
What delivery methodology or lifecycle is appropriate (waterfall, agile, hybrid or custom)?
Is an inception/discovery/landing phase needed before commitment or re-estimation?
What workstreams should exist and which can run in parallel?
What milestones, decision gates and integrated validation points are needed?
What dependencies, customer participation, governance and transition/cutover activities shape delivery?
```

Keep it unestimated: do not invent effort, staffing, duration, cost or price.

Choose the natural delivery structure and methodology. This may be waterfall, agile, hybrid or a custom model justified by the context. Typical shapes include:

```text
A. sequential phases/increments
B. parallel workstreams with increments
C. hybrid: common inception + parallel workstreams + integrated validation/cutover
D. discovery/inception first, followed by validation/re-estimation and then execution
```

Do not force sprints. If sprint-like units are used, they are planning units, not duration commitments.

Describe the selected delivery methodology and rationale first. Then, for each workstream/phase/increment include:

- stable ID/name;
- objective/outcome;
- scope included;
- high-level tasks;
- dependencies/prerequisites;
- outputs/deliverables when known;
- customer/third-party participation;
- high-level acceptance/exit condition;
- related risks/TBDs.

Each task contains at least:

```text
Task ID | Task name | Description
```

Consider when applicable: inception/discovery, validation and re-estimation gates, access/environments, architecture validation, platform/CI-CD, application foundation, frontend/UX, backend/domain, integrations, data/migration, security, observability/operations, testing/acceptance, deployment/cutover, documentation/training/handover, governance and transition to operations.

### Coverage check

Every major functional and technical capability in `solution.md` must map to work, including user-facing UI/frontend capabilities where required.

End with:

```text
solution capability → workstream(s)
```

# C. Business Analyst coherence review

After both files exist, the coordinator Business Analyst reviews them without creating another artifact.

Check:

- alignment with approved `strategy.md` and strategic story;
- scope/out-of-scope and human decisions preserved;
- customer requirements not silently changed;
- solution and delivery plan mutually consistent;
- all major capabilities covered by work;
- assumptions/TBDs aligned;
- optional specialist advice did not become unsupported promise;
- no estimate/commercial interest invented;
- artifacts are ready to feed later slide inventory/storytelling.

If correction is needed, route it back to the relevant owner and update that owner's canonical file.

## Completion

Complete only when:

1. upstream phases are approved;
2. Solution Architect inspected the full inventory and relevant original evidence;
3. `solution.md` exists;
4. Delivery Manager inspected the full inventory and relevant execution evidence after reading `solution.md`;
5. `delivery-plan.md` exists;
6. capability-to-work coverage is complete;
7. no estimate appears;
8. optional specialist consultations are bounded and recorded;
9. Business Analyst completed coherence review;
10. no slide planning started.

Set `solution.status: waiting_for_human` and STOP.
