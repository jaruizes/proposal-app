---
name: design-solution
description: Design the proposal solution from approved qualification plus selected customer evidence and optional specialist validation.
---

# Design Solution

Owner: **Solution Architect**

## Inputs

Primary working context:

- approved `opportunity-brief.md`;
- optional `questions.md`;
- optional `technology.md`;
- source manifest;
- selected original customer evidence;
- relevant architecture/RAG references;
- bounded specialist answers when genuinely needed.

## Responsibilities

Produce the proposal-level technical solution, including:

1. solution summary;
2. principles, drivers and assumptions;
3. conceptual architecture;
4. logical architecture;
5. physical/deployment architecture;
6. components and proposed technologies;
7. integrations and data;
8. security, resilience, observability and operations;
9. alternatives considered and explicit pros/cons/trade-offs;
10. technical risks;
11. points requiring deeper validation, spike, benchmark or PoC;
12. implementation tasks.

For every implementation task include:

- task;
- intended outcome/deliverable;
- qualitative complexity: `LOW | MEDIUM | HIGH | VERY_HIGH`;
- dependencies when present;
- recommended profile type;
- capability/workstream.

Qualitative complexity is allowed. Numeric estimation is not.

## Optional specialists

The Solution Architect remains owner. Consult specialists only for bounded expertise gaps. Maximum fan-out should remain small and justified.

Examples:

- security specialist for a concrete cryptography/compliance question;
- data specialist for a specific migration/scale question;
- cloud specialist for a provider-specific design constraint.

A specialist does not own the final artifact.

## Evidence and RAG

- Customer sources remain factual authority.
- RAG architecture references are patterns/advice, not customer facts.
- Preserve material source locators.
- Distinguish FACT, PRINCIPLE, PROPOSAL, DECISION and ASSUMPTION.

## Canonical output

`solution.md`

The document must be coherent as one solution even when bounded generation is used internally for very large contexts.


## Output size discipline

For normal single-pass solution generation, keep `solution.md` below roughly 8,000 words. Prefer structured task tables, architecture/component tables and concise decision records over repetitive prose.

When the selected evidence/context is large, the application may switch to bounded blueprint/block generation. That is a volume safeguard, not a reason to duplicate content.
