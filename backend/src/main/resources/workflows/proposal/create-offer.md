# Create Offer — validated workflow contract

This file preserves the Proposal Copilot orchestration contract that was validated in `proposal-copilot/feat/optimize-tokens`. Runtime enforcement belongs to Java, not to an LLM supervisor.

## Base offer team and ownership

```text
Business Analyst / Offer Owner
Solution Architect
Delivery Manager
Presentation Builder
```

```text
analysis artifacts   → Business Analyst
strategy.md          → Business Analyst
solution.md          → Solution Architect
solution-plan.md     → Delivery Manager
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

Statuses:

```text
not_started | running | waiting_for_human | approved | invalidated | stale | failed
```

Dependency chain:

```text
sources → analysis → strategy → solution → slide_plan → presentation
```

A changed approved upstream artifact invalidates/stales every downstream phase.

## Human gates

Every enabled business phase ends in `waiting_for_human`. Never start the next phase without explicit human approval.

## Phase 1

Owner: Business Analyst. Execute `analyze-opportunity` directly with no subagents. End waiting for human.

## Phase 2

Require analysis approved. Owner: Business Analyst. Execute `build-strategy` directly with no subagents. End waiting for human.

## Phase 3

Require analysis + strategy approved. Execute sequentially:

```text
Solution Architect → solution.md
Delivery Manager   → solution-plan.md
Business Analyst   → coherence review
```

Both base roles inspect complete source inventory and materially relevant originals. Optional deep specialists are bounded consultations only. Default maximum: two. No effort/staffing/duration/price/cost/margin estimation. End waiting for human.

## Phase 4

Require upstream approved. Owner: Business Analyst. Execute `design-proposal` directly. Require exactly `slides-plan.md`. The approved plan must be hierarchical and explicit with SECTION/SUBSECTION titles and cover yes/no; slide IDs; exact title; optional visual headline; primary message; content; visual support; notes.

Hard copy rules:
- content-slide title target <=10 words, hard maximum 12;
- no visible generic cliente/customer wording;
- `max_slides` counts content slides only;
- structural cover intent explicit.

End waiting for human.

## Phase 5

Require slide_plan approved. Owner: Presentation Builder. The approved slide plan is frozen authority for hierarchy, exact titles, cover presence, content-slide order, messages/content/visual intent. Template is immutable: copy first and modify generated copy only. Agenda derives from top-level sections. Visual QA may change layout/font/textbox geometry but never rewrite approved copy. End waiting for human.

## Feedback routing

```text
visual/layout/style-only → phase 5
slide title/message/content/sequence/hierarchy → phase 4
solution issue → phase 3
strategy/scope issue → corresponding upstream phase
```

## No-estimation discipline

Never invent person-hours/days, story points, S/M/L, staffing/FTEs, duration, price, cost or margin. Customer-imposed facts may be preserved as facts.
