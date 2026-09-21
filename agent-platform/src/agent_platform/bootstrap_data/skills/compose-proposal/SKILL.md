---
name: compose-proposal
description: Compose the canonical detailed proposal document from approved offer artifacts and human proposal guidance. The proposal is authoritative for later derived presentation material.
---

# Fase 4 — Oferta detallada

Produce the canonical detailed commercial/technical response.

## Owner

Business Analyst / Offer Owner.

## Preconditions

Require approved analysis, strategy and solution phases. Use approved canonical artifacts as factual and decision authority.

## Inputs

- approved opportunity brief, questions and technology analysis when present;
- approved response strategy;
- approved solution and solution plan;
- human proposal guidance;
- relevant current-offer context supplied by the runtime.

## Proposal guidance

The human may configure ordered sections. Each section can include:

- `name`;
- `enabled`;
- `depth`: `SUMMARY`, `STANDARD` or `DETAILED`;
- `guidance`: authoritative instructions for that section.

Preserve enabled human sections and their order unless doing so would contradict approved upstream decisions. Complete each section using approved evidence. If guidance requests unsupported content, expose the gap instead of inventing it.

Depth semantics:

- `SUMMARY`: concise synthesis;
- `STANDARD`: normal explanatory depth;
- `DETAILED`: comprehensive treatment with explicit reasoning, traceability and tables/matrices where useful.

## Authority and safety

- Current-offer approved artifacts are the factual and decision authority.
- Never invent customer facts, prices, effort, staffing, dates, payment terms, legal conditions or contractual commitments.
- Preserve assumptions, open questions and unresolved aspects explicitly.
- Prefer high information density over filler.
- Develop acronyms on first relevant use.
- Use consistent customer and technical terminology.
- Make requirements-to-response and need-to-solution relationships explicit where useful.
- The proposal must stand on its own without the later slide deck.

Reference proposals retrieved from `reference-offers` are examples of structure, depth, terminology patterns and style only. They are explicitly NON-FACTUAL context: they never override current-offer artifacts and must never inject another customer's facts, technologies, commitments, dates, prices, staffing or claims into the current offer.

## Document qualities

The document should work for human evaluation and automated AI screening:

- explicit heading hierarchy;
- descriptive prose rather than slide fragments;
- traceable requirements and decisions;
- explicit scope, assumptions, risks and dependencies;
- detailed technical rationale where configured;
- tables and matrices where they improve extraction/comparison;
- no unsupported claims.

## Canonical output

When the LangGraph proposal workflow invokes this skill, its intermediate calls
request one section body or a compact JSON review. Follow the current stage instruction
for those calls. The workflow receives a compact, evidence-preserving Proposal Context
Pack built once from approved upstream artifacts; do not expect every original artifact
to be repeated in every section call.

Section review is issues-only: an acceptable draft is reused unchanged, and only sections
with material issues are regenerated. Successful intermediate model calls are durably
checkpointed by exact input fingerprint so retries can reuse completed work across new
outer execution IDs. Only the assembled result is the canonical proposal. Global review
must converge: it may trigger targeted corrections, but stylistic preferences or optional
improvements must not fail the entire phase.

Return ONLY the complete Markdown for:

`generated/proposal/proposal.md`

Do not generate DOCX, PDF, slides-plan, PPTX or Google Slides.

Start with a clear proposal title. Render configured enabled sections in order. End with a concise coverage/gaps section only when material unresolved information remains.

Set `proposal.status: waiting_for_human` and STOP.
