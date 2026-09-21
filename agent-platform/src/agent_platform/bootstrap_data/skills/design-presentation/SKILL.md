---
name: design-presentation
description: Produce the human-reviewable slide storyline from the approved proposal and optional reference presentations.
---

# Design Presentation Storyline

Owner: **Business Analyst / Offer Owner**

## Inputs

Primary factual authority:

- approved `proposal.md`;
- human presentation guidance, when supplied.

Optional non-factual style/story references:

- previous proposals/presentations retrieved from RAG.

Do not reread the complete RFP or all upstream artifacts by default. Reopen upstream evidence only to verify a specific fact or requested visual.

## Goal

Transform the approved proposal into a concise presentation narrative, not a Markdown-to-slides transcription.

For every slide define:

- stable slide ID;
- exact concise title, maximum 12 words;
- purpose / primary message;
- concise slide-ready content;
- visual-support intent;
- source/traceability where useful.

Keep section/subsection hierarchy clear and suitable for human iteration.

## Size discipline

- normal substantial proposal: 10–24 slides;
- absolute maximum: 30 slides;
- maximum 5 slides per narrative section;
- slide content should normally stay below 70 words;
- prefer visual structure over copying paragraphs from `proposal.md`;
- do not add slides just to reproduce every proposal section verbatim.

Large proposals may be generated internally through a storyline plus bounded section-detail substeps. Those substeps belong to the same Business Analyst AgentExecution and are checkpointable.

## Canonical Markdown contract

Return `slides-plan.md` with this hierarchy:

```text
# <presentation title>

# SECTION-1 — <section title>

## SLIDE-1

### Título de slide
<maximum 12 words>

### Propósito / mensaje principal
<one primary message>

### Contenido
<concise slide-ready content>

### Intención visual
<visual/layout direction>

### Fuentes / trazabilidad
<proposal.md section/reference>
```

Repeat sequential `SECTION-n` and `SLIDE-n` identifiers.

Do not use generic `cliente/customer` wording anywhere in generated slide-plan copy. Use the real organization/context when supported.

## Canonical output

`slides-plan.md`

No PPTX/Google Slides is created in this skill.
