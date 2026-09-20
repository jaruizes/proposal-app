---
name: design-proposal
description: Execute phase 4 slide planning. The Business Analyst / Offer Owner produces the approved hierarchical presentation contract: sections, subsections, structural covers and content slides.
---

# Fase 5 — Planificación narrativa de la presentación

Input:

```text
workspace/<proposal>
```

This phase defines the **approved presentation contract**. It decides:

- sections;
- subsections;
- structural section/subsection titles;
- content-slide order;
- exact slide titles;
- slide message/content;
- visual-support intent.

It does not materialize Google Slides/PPTX.

## Preconditions

Require:

```text
analysis.status: approved
strategy.status: approved
solution.status: approved
proposal.status: approved
```

Require:

```text
generated/analysis/opportunity-brief.md
generated/strategy/strategy.md
generated/solution/solution.md
generated/solution/delivery-plan.md
generated/proposal/proposal.md
```

Read when present:

```text
generated/analysis/questions.md
generated/analysis/technology.md
presentation-guidance.yaml
```

## Owner

```text
Business Analyst / Offer Owner
```

One coordinator context. No storytellers, slide designers, architects, delivery managers, reviewers, specialists, forks or parallel agents.

## Language

Use `presentation.language` from `offer-config.yaml`; fall back to top-level `language` only when absent.

## Customer naming rule — visible copy

Never use generic nouns such as:

```text
cliente
el cliente
nuestro cliente
the client
the customer
```

in any **visible presentation copy** proposed by this phase, including:

- section/subsection titles;
- slide titles;
- visual headlines;
- bullets/body copy;
- callouts;
- diagram labels written by us.

When the organization must be named, use the actual configured/approved organization name (for example `Redeia` or `REINTEL`) according to the source/offer terminology. Otherwise omit the reference entirely.

Examples:

```text
FORBIDDEN:
Qué queda fuera de alcance, por decisión ya tomada por el cliente

BETTER:
Qué queda fuera de alcance

or, only when useful:
Qué queda fuera de alcance según Redeia
```

```text
FORBIDDEN:
Aspectos pendientes de confirmar con el cliente

BETTER:
Aspectos pendientes de confirmar
```

Internal traceability text may refer to a `customer source` concept, but final visible slide copy must not use generic `cliente/customer` wording.

## Context/source policy

Use approved offer artifacts as normal context. Do not reread the complete customer corpus by default.

Reopen original evidence only to:

- verify a material fact;
- recover a requested source visual;
- confirm an exact statement/number;
- resolve a specific contradiction.

## Optional human guidance

Optional:

```text
<opportunity>/presentation-guidance.yaml
```

Human guidance may define sections, descriptions, `max_slides`, subsections and concrete requested slides.

When absent, the Business Analyst designs the hierarchy.

When present:

- preserve human sections/subsections unless conflicting with approved upstream decisions;
- listed concrete slides are required by default unless `required: false`;
- complete missing narrative where needed;
- identify and justify AI-added sections/subsections/slides;
- never fabricate unsupported content to satisfy guidance.

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

A section/subsection is not merely a Markdown heading. Its title is an **approved structural presentation title** that phase 5 must be able to materialize verbatim when structural slides are enabled.

### Section contract

For every section include:

```text
Section ID
Exact section title
Section purpose
Section cover: yes/no
Content slide count
max_slides (when configured)
```

### Subsection contract

For every subsection include:

```text
Subsection ID
Exact subsection title
Subsection purpose
Subsection cover: yes/no
Content slide count
max_slides (when configured)
```

Section/subsection cover slides are structural slides and **do not count toward `max_slides`**, which applies to content slides.

When human guidance defines a section/subsection, default:

```text
section cover: yes
subsection cover: yes
```

unless the guidance/configuration explicitly suppresses the relevant structural cover.

## Slide-title contract — critical

Content-slide titles must be concise enough for corporate presentation layouts.

Rules:

```text
target: <= 10 words
hard maximum: 12 words
```

Count normal whitespace-delimited words; punctuation does not create an extra word.

Do not use a long sentence as a title merely because it captures the whole message. Move nuance to `Objetivo / mensaje principal` or body copy.

Examples:

```text
TOO LONG:
Resumen ejecutivo: de la dependencia de un proveedor a una plataforma abierta y alineada con Redeia

BETTER:
Una plataforma abierta y alineada con Redeia
```

```text
TOO LONG:
Qué queda fuera de alcance, por decisión ya tomada por Redeia

BETTER:
Qué queda fuera de alcance
```

Before completing phase 4, explicitly validate every title and rewrite any title exceeding 12 words.

## Visual headline

A separate display headline is optional.

If useful, define:

```text
Headline visual opcional: ...
```

Otherwise explicitly use:

```text
Headline visual opcional: No definido
```

Phase 5 may not invent one later.

A visual headline should normally be even shorter than the title and must follow the same no-`cliente/customer` rule.

## `max_slides` semantics

`max_slides` is a soft limit for **content slides only**.

Prefer fewer slides when concise. More are allowed when genuinely necessary, but disclose:

```text
configured max
proposed content slides
excess
reason
```

No extra pre-generation human approval is required for the exceedance; the normal phase-4 review is sufficient.

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

For every content slide define whether visual support helps:

```text
architecture diagram
conceptual diagram
process/flow
workstream model
timeline/sequence without invented dates
table/matrix
customer-provided visual
generated illustration/iconography
chart based on approved data
none
```

Describe visual intent/content, not final layout coordinates/colors/fonts.

## Canonical output

Exactly:

```text
generated/presentation/slides-plan.md
```

Do not generate `slides-plan.json`, PPTX or Google Slides.

## Required `slides-plan.md` shape

Use this hierarchy, translated to `presentation.language`:

```markdown
# Plan de presentación

## Resumen del plan
- Idioma de slides: es
- Guidance humana: sí/no
- Número de secciones: N
- Número de subsecciones: N
- Número de slides de contenido: N
- Portadas estructurales previstas: N
- Secciones añadidas por IA: ...
- Límites max_slides excedidos: ...

## Storyline global
...

# SECTION-01 — Resumen ejecutivo

**Título exacto de sección:** Resumen ejecutivo
**Objetivo de la sección:** ...
**Portada de sección:** Sí
**Máximo indicado de slides de contenido:** 3
**Slides de contenido propuestas:** 3
**Exceso:** 0
**Origen:** Humano

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
**Origen:** ...

### Notas explicativas
...

### Trazabilidad / base
...

# SECTION-04 — ¿Qué proponemos?

**Título exacto de sección:** ¿Qué proponemos?
**Portada de sección:** Sí
...

## SUBSECTION-04.01 — Solución / Arquitectura conceptual y lógica

**Título exacto de subsección:** Solución / Arquitectura conceptual y lógica
**Objetivo de la subsección:** ...
**Portada de subsección:** Sí
**Máximo indicado de slides de contenido:** 5
**Slides de contenido propuestas:** 4

## SLIDE-012
...
```

Content slide IDs remain globally sequential across sections/subsections.

## Final validation before output

Validate mechanically/consciously:

1. every content slide belongs to exactly one section or subsection;
2. every human section/subsection has an exact structural title;
3. section/subsection hierarchy is unambiguous;
4. every content-slide title is <= 12 words, preferably <= 10;
5. no visible proposed copy contains generic `cliente/customer` terminology;
6. every slide has exact title, optional visual headline, primary message, content, visual support and notes when useful;
7. `max_slides` counts content slides only;
8. structural covers are counted separately;
9. no unsupported estimates/commitments appear.

At the end include:

```markdown
## Control final de narrativa
- validación títulos <= 12 palabras: OK / issues
- uso de "cliente/customer" en copy visible: 0 occurrences
- duplicidades detectadas/evitadas
- mensajes materiales no incluidos y motivo
- deviations from human guidance
- soft limits exceeded and reasons
- upstream blockers/uncertainties
```

Set `slide_plan.status: waiting_for_human` and STOP.
