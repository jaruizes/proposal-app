---
name: generate-presentation
description: Materialize the approved slides-plan.md into the final corporate presentation without changing the approved narrative.
---

# Generate Presentation

Owner: **Business Analyst / Offer Owner**

The Business Analyst owns the approved presentation content. The materialization layer applies the corporate template and may use a bounded visual-design specialist for layout/visual QA only.

## Preconditions

Require:

- approved `proposal.md`;
- approved `slides-plan.md`;
- presentation output configuration;
- optional corporate presentation template.

No standalone strategy artifact exists.

## Authority hierarchy

1. approved `slides-plan.md` — narrative, hierarchy, titles and content intent;
2. corporate template — visual/layout authority;
3. relevant previous presentations from RAG — style/pattern reference only;
4. upstream artifacts — clarification of an approved fact only.

## Rules

- Preserve approved section/subsection hierarchy and slide order.
- Preserve approved slide titles and primary messages.
- Do not invent new commercial/technical commitments.
- Do not rewrite content merely to fit a layout.
- Prefer template-compatible layout adjustments, line breaks, geometry and bounded font changes.
- Never edit the corporate template itself; copy it first.
- Use previous presentations only as visual/style patterns, never as customer factual authority.
- Perform bounded visual QA on the generated deck.

## Outputs

- final Google Slides/PPTX-equivalent presentation;
- `presentation-build-report.md`;
- presentation metadata/URL.

The final presentation may be iterated by the human after generation.
