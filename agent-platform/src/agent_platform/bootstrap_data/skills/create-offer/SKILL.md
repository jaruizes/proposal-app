---
name: create-offer
description: Orchestrate source ingestion, analysis, strategy, solution, hierarchical slide planning and final corporate presentation generation with persisted state and human checkpoints.
---

# Create Offer

Input:

```text
workspace/<proposal>
```

## Base offer team and ownership

```text
Business Analyst / Offer Owner
Solution Architect
Delivery Manager
Presentation Builder
```

Ownership:

```text
analysis artifacts   → Business Analyst
strategy.md          → Business Analyst
solution.md          → Solution Architect
delivery-plan.md     → Delivery Manager
slides-plan.md       → Business Analyst
final presentation   → Presentation Builder
overall offer coherence → Business Analyst
```

## Phase mapping

```text
source ingestion → ingest-sources
analysis         → analyze-opportunity
strategy         → build-strategy
solution         → define-solution
slide_plan       → design-proposal
presentation     → generate-presentation
```

## State

Canonical state:

```text
generated/workflow-state.yaml
```

Statuses:

```text
not_started | running | waiting_for_human | approved | invalidated | stale | failed
```

Dependency chain:

```text
sources → analysis → strategy → solution → slide_plan → presentation
```

A changed approved upstream artifact invalidates/stales every downstream phase.

## Phase 1 — analysis

Owner: Business Analyst / Offer Owner.

Run `analyze-opportunity` directly; no subagents. End `waiting_for_human` and STOP.

## Phase 2 — strategy

Require `analysis.status == approved`.

Owner: Business Analyst / Offer Owner.

Run `build-strategy` directly; require only `generated/strategy/strategy.md`. End `waiting_for_human` and STOP.

## Phase 3 — solution

Require analysis + strategy approved.

Sequential base-role execution:

```text
Solution Architect → solution.md
Delivery Manager   → delivery-plan.md
Business Analyst   → coherence review
```

Both base roles inspect complete source inventory and materially relevant originals. Optional deep specialists are bounded consultations only. No effort/staffing/duration/price/cost/margin estimation.

End `waiting_for_human` and STOP.

## Phase 4 — slide_plan

Require analysis + strategy + solution approved.

Owner: Business Analyst / Offer Owner.

Run `design-proposal` directly; no subagents.

Require exactly:

```text
generated/presentation/slides-plan.md
```

The approved plan MUST be hierarchical and explicit:

```text
SECTION
  exact section title
  section cover yes/no
  slides directly in section
  SUBSECTION
    exact subsection title
    subsection cover yes/no
    slides in subsection
```

Every content slide must have:

```text
ID
exact title
optional visual headline (or No definido)
primary message
content
visual support
notes when useful
```

Phase-4 hard copy rules:

- content-slide title target <=10 words, hard maximum 12 words;
- section/subsection titles are explicit approved structural titles;
- no visible proposed copy may use generic `cliente/customer` wording; use the real organization name when needed or omit the reference;
- `max_slides` counts content slides only; section/subsection covers are structural;
- no actual presentation is materialized.

Before setting `slide_plan.status: waiting_for_human`, validate:

```text
every slide belongs to one section/subsection
all titles <=12 words
zero visible cliente/customer occurrences
hierarchy unambiguous
structural cover intent explicit
```

STOP for human approval.

## Phase 5 — presentation

Require all upstream phases including `slide_plan` approved.

Owner: Presentation Builder.

Validate `presentation.template` and `presentation.output`, persist `presentation.status: running`, then invoke `generate-presentation`.

### Frozen slide-plan contract

The approved `slides-plan.md` is authoritative for:

- hierarchy;
- exact section/subsection titles;
- section/subsection cover presence;
- content-slide membership/order;
- exact slide titles;
- optional approved visual headlines;
- messages/content/visual intent.

The presentation phase may not rewrite these.

Section/subsection covers are materialized from the approved plan, not independently inferred from configuration.

`presentation.structural_slides` controls only global corporate slides outside that hierarchy (currently cover/agenda/closing).

The agenda derives from top-level approved sections; do not promote subsections unless explicitly requested.

### Fidelity requirements

For each content slide:

```text
same ID/order
exact title verbatim
title <=12 words
no invented visual headline
no generic cliente/customer visible copy
same approved message/content intent
```

If an approved plan violates these rules, return to phase 4 rather than silently fixing narrative copy in phase 5.

### Visual QA

Layout/font/textbox adjustments are allowed. Rewriting is not.

Auto-fix order:

```text
natural line breaks
→ textbox adjustment
→ small font reduction
→ alternate corporate layout
→ human review / return to phase 4
```

Avoid syllable/word fragmentation.

### Outputs

Require:

```text
generated/presentation/presentation.json
```

Expected during validation:

```text
generated/presentation/presentation-build-report.md
```

Report hierarchy fidelity, exact-title fidelity, content-vs-structural slide counts, automatic visual corrections and zero generic `cliente/customer` visible copy.

End `presentation.status: waiting_for_human` and STOP.

## Human feedback routing

```text
visual/layout/style-only → phase 5
slide title/message/content/sequence/hierarchy → phase 4
solution issue → phase 3
strategy/scope issue → corresponding upstream phase
```

## Language

Slide planning and presentation use `presentation.language`; fallback to top-level `language` only when absent.

## Model hints

```yaml
ai:
  task_models:
    opportunity_qualification: sonnet
    response_strategy: sonnet
    solution_architecture: sonnet
    delivery_planning: sonnet
    specialist_validation: sonnet
    slide_planning: sonnet
    presentation_generation: sonnet
    corporate_slide_design: sonnet
```

Never create contexts solely to force model routing.

## Normative references

Read and obey:

- `CLAUDE.md`
- `docs/process.md`
- `docs/document-ingestion.md`
- `docs/workflow-human-validation.md`
- `docs/roles-and-agents.md`
- `docs/google-slides-generation.md`

Do not expose hidden chain-of-thought.
