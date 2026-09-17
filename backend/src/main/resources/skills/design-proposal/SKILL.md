---
name: design-proposal
description: Execute phase 4 slide planning. The Business Analyst / Offer Owner produces the approved hierarchical presentation contract: sections, subsections, structural covers and content slides.
---

# Fase 4 — Planificación narrativa de la presentación

Input:

```text
workspace/<proposal>
```

This phase defines the approved presentation contract. It decides sections, subsections, structural section/subsection titles, content-slide order, exact slide titles, slide message/content and visual-support intent. It does not materialize Google Slides/PPTX.

## Preconditions

Require:

```text
analysis.status: approved
strategy.status: approved
solution.status: approved
```

Require `opportunity-brief.md`, `strategy.md`, `solution.md`, `solution-plan.md`; read `questions.md`, `technology.md` and `presentation-guidance.yaml` when present.

## Owner

```text
Business Analyst / Offer Owner
```

One coordinator context. No storytellers, slide designers, architects, delivery managers, reviewers, specialists, forks or parallel agents.

## Language

Use `presentation.language`; fall back to top-level `language` only when absent.

## Customer naming rule — visible copy

Never use generic nouns such as `cliente`, `el cliente`, `nuestro cliente`, `the client`, `the customer` in visible presentation copy: section/subsection titles, slide titles, visual headlines, bullets/body copy, callouts or diagram labels written by us.

When the organization must be named, use the actual configured/approved organization name (for example `Redeia` or `REINTEL`). Otherwise omit the reference entirely.

Examples:

```text
FORBIDDEN: Qué queda fuera de alcance, por decisión ya tomada por el cliente
BETTER: Qué queda fuera de alcance
```

```text
FORBIDDEN: Aspectos pendientes de confirmar con el cliente
BETTER: Aspectos pendientes de confirmar
```

## Context/source policy

Use approved offer artifacts as normal context. Do not reread the complete customer corpus by default. Reopen original evidence only to verify a material fact, recover a requested source visual, confirm an exact statement/number or resolve a specific contradiction.

## Optional human guidance

Optional `<opportunity>/presentation-guidance.yaml` may define sections, descriptions, `max_slides`, subsections and concrete requested slides.

When absent, the Business Analyst designs the hierarchy. When present, preserve human sections/subsections unless conflicting with approved upstream decisions; listed concrete slides are required by default unless `required: false`; complete missing narrative where needed; identify and justify AI-added sections/subsections/slides; never fabricate unsupported content.

## Hierarchical presentation contract — critical

`slides-plan.md` MUST be organized hierarchically:

```text
Presentation
  Section
    Section cover metadata
    Content slides
    Subsection
      Subsection cover metadata
      Content slides
```

A section/subsection is not merely a Markdown heading. Its title is an approved structural presentation title that phase 5 must materialize verbatim when the plan says its cover is enabled.

For every section include: Section ID, exact section title, purpose, cover yes/no, content slide count and max_slides when configured. For every subsection include the same equivalent metadata.

Section/subsection cover slides are structural slides and do not count toward `max_slides`, which applies to content slides. When human guidance defines a section/subsection, default section/subsection cover to yes unless explicitly suppressed.

## Slide-title contract — critical

Content-slide titles must be concise enough for corporate presentation layouts:

```text
target: <= 10 words
hard maximum: 12 words
```

Do not use a long sentence as a title merely because it captures the whole message. Move nuance to `Objetivo / mensaje principal` or body copy. Before completing phase 4, explicitly validate every title and rewrite any title exceeding 12 words.

## Visual headline

A separate display headline is optional. If useful define `Headline visual opcional`. Otherwise explicitly use `Headline visual opcional: No definido`. Phase 5 may not invent one later. A visual headline should normally be even shorter than the title and must follow the same no-`cliente/customer` rule.

## `max_slides` semantics

`max_slides` is a soft limit for content slides only. Prefer fewer slides when concise. More are allowed when genuinely necessary, but disclose configured max, proposed content slides, excess and reason.

## Narrative principles

- one primary message per content slide;
- customer-oriented story, not Markdown-to-slide conversion;
- progressively disclose technical depth;
- distinguish conceptual/logical vs physical architecture;
- synthesize workstreams instead of one slide per task;
- avoid unnecessary repetition;
- never fill `max_slides` mechanically;
- never invent estimates, staffing, dates, prices or commitments.

## Visual-support contract

For every content slide define whether visual support helps: architecture diagram, conceptual diagram, process/flow, workstream model, timeline/sequence without invented dates, table/matrix, customer-provided visual, generated illustration/iconography, chart based on approved data or none. Describe visual intent/content, not final coordinates/colors/fonts.

## Canonical output

Exactly:

```text
generated/presentation/slides-plan.md
```

Do not generate `slides-plan.json`, PPTX or Google Slides.

## Required hierarchy

Use globally sequential content slide IDs. Example:

```markdown
# SECTION-01 — Resumen ejecutivo
**Título exacto de sección:** Resumen ejecutivo
**Objetivo de la sección:** ...
**Portada de sección:** Sí
**Máximo indicado de slides de contenido:** 3
**Slides de contenido propuestas:** 3

## SLIDE-001
### Título de slide
Una plataforma abierta y alineada con Redeia
### Headline visual opcional
No definido
### Objetivo / mensaje principal
...
### Contenido
...
### Soporte visual
**Tipo:** ...
**Descripción:** ...
### Notas explicativas
...
### Trazabilidad / base
...

# SECTION-04 — ¿Qué proponemos?
## SUBSECTION-04.01 — Solución / Arquitectura conceptual y lógica
**Título exacto de subsección:** Solución / Arquitectura conceptual y lógica
**Portada de subsección:** Sí
```

## Final validation before output

Validate:
1. every content slide belongs to exactly one section or subsection;
2. every human section/subsection has an exact structural title;
3. hierarchy is unambiguous;
4. every content-slide title is <=12 words, preferably <=10;
5. no visible proposed copy contains generic `cliente/customer` terminology;
6. every slide has exact title, optional visual headline, primary message, content, visual support and notes when useful;
7. `max_slides` counts content slides only;
8. structural covers are counted separately;
9. no unsupported estimates/commitments appear.

At the end include a `Control final de narrativa` reporting title validation, zero visible cliente/customer occurrences, duplicities, omitted material messages and reason, deviations from human guidance, soft limits exceeded and upstream blockers/uncertainties.

Set `slide_plan.status: waiting_for_human` and STOP.
