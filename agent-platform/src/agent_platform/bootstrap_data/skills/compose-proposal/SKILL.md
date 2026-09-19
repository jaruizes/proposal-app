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

Reference proposals, when retrieval is enabled in a later milestone, are examples of structure, depth and style only. They never override or inject facts into the current offer.

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

Return ONLY the complete Markdown for:

`generated/proposal/proposal.md`

Do not generate DOCX, PDF, slides-plan, PPTX or Google Slides.

Start with a clear proposal title. Render configured enabled sections in order. End with a concise coverage/gaps section only when material unresolved information remains.

Set `proposal.status: waiting_for_human` and STOP.
