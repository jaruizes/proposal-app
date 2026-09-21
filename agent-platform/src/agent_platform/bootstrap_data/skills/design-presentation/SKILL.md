---
name: design-presentation
description: Produce the human-reviewable slide storyline from the approved proposal and optional reference presentations.
---

# Design Presentation Storyline

Owner: **Business Analyst / Offer Owner**

## Inputs

Primary authority:

- approved `proposal.md`;
- human presentation guidance, when supplied.

Optional style/story references:

- previous proposals/presentations retrieved from RAG.

Do not reread the complete RFP by default. Reopen upstream evidence only to verify a specific fact or requested visual.

## Goal

Transform the approved proposal into a presentation narrative, not a Markdown-to-slides transcription.

For every slide define:

- slide ID;
- exact concise title;
- purpose / primary message;
- content;
- visual-support intent;
- source/traceability where useful.

Keep section/subsection hierarchy clear and suitable for human iteration.

## Canonical output

`slides-plan.md`

No PPTX/Google Slides is created in this skill.
