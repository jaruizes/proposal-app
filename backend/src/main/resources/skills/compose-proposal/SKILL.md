---
name: compose-proposal
description: Author the canonical proposal.md from approved qualification, solution and delivery artifacts with a single coherent narrative whenever volume allows.
---

# Compose Proposal

Owner: **Business Analyst / Offer Owner**

## Inputs

Primary factual/decision authority:

- approved `opportunity-brief.md`;
- optional `questions.md`;
- optional `technology.md`;
- approved `solution.md`;
- approved `delivery-plan.md`;
- human proposal guidance.

Optional RAG references:

- previous proposals or presentations for structure, terminology, tone and depth only.

Reference proposals are never factual authority for the current customer.

## Default execution mode: SINGLE

When the approved context is within the configured single-pass threshold, one Business Analyst model execution authors the complete proposal.

The document must:

- have one coherent narrative voice and storyline;
- move naturally from customer context and objectives to the proposed solution and delivery approach;
- avoid duplicated content between sections;
- preserve approved assumptions, risks and open points;
- use configured proposal sections as a structure contract, not as isolated mini-documents;
- never expose internal workflow, agent or context-pack terminology.

Do not create one independent agent execution per section in normal-size proposals.

## Large-volume mode: SPLIT

Only when context volume is too large for a safe coherent single generation, the SAME Business Analyst AgentExecution may use multiple internal model substeps:

1. compact approved artifacts once;
2. retrieve relevant reference patterns;
3. draft a small number of bounded sections/blocks;
4. use issues-only review;
5. correct only blocks with material issues;
6. assemble the canonical proposal;
7. perform one bounded global consistency review.

Successful internal substeps are checkpointed and reusable across retries. No extra Business Analyst AgentExecution is created merely to compact or split the proposal.

Even in split mode, the result must read as one authored document, not a Frankenstein concatenation.

## Quality rules

- Customer/current-offer artifacts are authoritative.
- Do not invent prices, numeric effort, staffing quantities, dates, contractual commitments or customer facts.
- Preserve explicit gaps instead of guessing.
- RAG references may inspire organization/style but may not introduce foreign facts.
- Avoid unnecessary repetition of the same architecture, risk or scope statement across sections.
- Do not turn every implementation task into a proposal subsection unless human guidance requires it.

## Output

Exactly one canonical artifact:

`proposal.md`

The application may deterministically materialize the approved Markdown into DOCX/PDF afterwards.
