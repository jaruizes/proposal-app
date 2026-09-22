---
name: generate-presentation
description: Materialize approved slides-plan.md into the final corporate presentation through Agent Platform MCP tools.
---

# Generate Presentation

Owner: **Business Analyst / Offer Owner**

This skill is executed as **one AgentExecution**. Internal chunking, model calls, Google Workspace MCP calls and checkpoints are owned by Agent Platform/LangGraph and are invisible to the business workflow.

## Preconditions

Require:

- approved `slides-plan.md`;
- presentation output configuration;
- optional corporate presentation template ID.

## Execution graph

`presentation-materialization`:

1. read the approved slide plan and materialization configuration;
2. inspect the corporate template with the Agent Platform Google Workspace MCP provider;
3. choose bounded internal slide chunks;
4. generate operation plans per chunk with checkpoints and truncation recovery;
5. only after all planning succeeds, copy/create the target Google Slides file;
6. execute Slides/Drive MCP tools;
7. inspect the generated structure;
8. return the final presentation metadata/report as the execution artifact.

Spring must not split slides, interpret Google Slides operations or call MCP.

## Authority hierarchy

1. approved `slides-plan.md` — narrative, hierarchy, titles and content intent;
2. corporate template — visual/layout authority;
3. previous presentations from RAG — style reference only.

## Tool policy

The graph may use only the Google Workspace tools required for presentation materialization, including:

- `slides_get_presentation`;
- `slides_create_presentation`;
- `slides_duplicate_slide`;
- `slides_delete_slide`;
- `slides_move_slides`;
- `slides_replace_text`;
- `slides_replace_element_text`;
- `slides_batch_update`;
- `drive_copy_file`;
- `drive_move_file`.

The original template is never edited directly.

## Output

Return one complete JSON object:

```json
{
  "externalId": "...",
  "url": "https://docs.google.com/presentation/d/.../edit",
  "buildReport": {
    "templateId": "...",
    "renderingMode": "corporate-template|blank",
    "operationCount": 0,
    "chunks": 0,
    "structuralQa": "..."
  }
}
```

The number of internal chunks/model calls is an Agent Platform implementation detail, not a Spring workflow concern.
