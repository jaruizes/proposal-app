---
name: generate-presentation
description: Materialize the approved slides-plan.md into the final corporate presentation without changing the approved narrative.
---

# Generate Presentation

Owner: **Business Analyst / Offer Owner**

The Business Analyst owns the approved presentation content. The deterministic application layer applies the corporate template and executes bounded operation plans.

## Preconditions

Require:

- approved `slides-plan.md`;
- presentation output configuration;
- optional corporate presentation template.

## Authority hierarchy

1. approved `slides-plan.md` — narrative, hierarchy, titles and content intent;
2. corporate template — visual/layout authority;
3. relevant previous presentations from RAG — style/pattern reference only.

## Execution model

Presentation materialization is **chunked and checkpointable**.

- The application splits the frozen slide plan into small, structurally valid chunks.
- Each chunk is a standard `AgentExecution` using the same process-agnostic Spring ↔ Agent Platform protocol.
- A chunk must materialize only its assigned slides.
- Completed chunks are checkpointed and reused after retries.
- All cognitive planning finishes **before** the application creates/copies or mutates the target Google Slides file.
- The final side-effect phase applies the validated operation batches in order.
- Post-build QA is deterministic structural inspection; the current text-only transport must not claim visual thumbnail inspection.

## Rules

- Preserve approved section hierarchy, global slide order, titles and primary messages.
- Do not invent new commercial or technical commitments.
- Do not rewrite approved narrative copy.
- Never edit the corporate template itself; copy it first.
- Use `$PRESENTATION_ID` as the target placeholder in operation plans.
- Return only the declared JSON operation contract.
- Keep every chunk bounded; do not emit operations for slides outside the assigned chunk.

## Operation output contract

```json
{
  "operations": [
    {
      "tool": "slides_duplicate_slide|slides_delete_slide|slides_move_slides|slides_replace_text|slides_replace_element_text|slides_batch_update",
      "arguments": {}
    }
  ]
}
```

## Outputs

- final Google Slides/PPTX-equivalent presentation;
- `presentation-build-report.md`;
- presentation metadata/URL.
