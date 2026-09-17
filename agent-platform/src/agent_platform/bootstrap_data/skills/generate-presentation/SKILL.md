---
name: generate-presentation
description: Execute phase 5. Materialize the approved hierarchical slides-plan.md into a corporate Google Slides deck without changing approved section/subsection structure or slide copy.
---

# Fase 5 — Materialización de presentación corporativa

Input:

```text
workspace/<proposal>
```

Phase 5 is a rendering/materialization phase, not a copywriting or narrative-design phase.

## Preconditions

Require:

```text
analysis.status: approved
strategy.status: approved
solution.status: approved
slide_plan.status: approved
```

Require:

```text
generated/presentation/slides-plan.md
```

Require complete `presentation.template` and `presentation.output` configuration.

## Owner

```text
Presentation Builder
```

A bounded `corporate-slide-designer` may advise only on visual pattern/layout selection.

It MUST NOT rewrite titles, structural headings, slogans, primary messages or proposal content.

## Frozen presentation contract

After human approval, `slides-plan.md` is authoritative for:

```text
section hierarchy
subsection hierarchy
section/subsection exact titles
section/subsection cover yes/no
content-slide membership
content-slide order/ID
exact slide title
optional explicit visual headline
primary message
content intent
visual-support intent
notes
```

Phase 5 MUST materialize that hierarchy faithfully.

### Section/subsection structural slides

Structural covers are no longer inferred independently by phase 5.

For each section/subsection read from `slides-plan.md`:

```text
Portada de sección: Sí/No
Portada de subsección: Sí/No
```

When `Sí`, materialize a structural cover using the **exact approved section/subsection title**.

Do not generate a structural cover for an item marked `No`.

Do not invent additional sections/subsections.

Corporate `cover`, `agenda` and `closing` slides may still be controlled by `offer-config.yaml`, but section/subsection covers are governed by the approved slide plan.

### Exact content-slide title rule

For each content slide:

```text
presentation title == approved slides-plan title
```

verbatim.

The title must already satisfy the phase-4 <=12-word contract. If a generated plan violates that contract, stop and return to phase 4 rather than silently shortening it.

Phase 5 may change only:

- natural line breaks between words;
- font size within safe limits;
- textbox geometry;
- chosen corporate layout.

Never change wording to fit.

### Visual headline rule

Use an additional display headline only when `slides-plan.md` explicitly defines one and it is not `No definido`.

Never invent slogans/taglines/display headlines.

## Generic customer-language prohibition

Do not introduce generic visible terms such as:

```text
cliente
el cliente
nuestro cliente
the client
the customer
```

If this wording somehow remains in an approved slide plan, treat it as a phase-4 contract violation and stop for correction rather than propagating or independently rewriting it.

Template example text such as `Cliente / Título presentación proyecto` must always be replaced/removed.

## Template safety

Corporate template is immutable:

```text
resolve template
→ inspect/catalog if necessary
→ copy template
→ verify generated ID != template ID
→ edit only generated copy
```

Persist:

```text
generated/presentation/presentation.json
```

## Source hierarchy

1. approved `slides-plan.md` → narrative + hierarchy + copy authority;
2. corporate template/catalog → UX/style/layout authority;
3. upstream artifacts → clarification only;
4. customer sources → only a specifically requested referenced visual/exact fact.

## Materialization order

Materialize the physical deck according to the approved hierarchy:

```text
optional corporate cover
optional corporate agenda
SECTION cover if approved
  section content slides
  SUBSECTION cover if approved
    subsection content slides
next SECTION...
optional corporate closing
```

The agenda should be derived from the approved top-level sections. Do not promote subsections into top-level agenda entries unless the approved plan/config explicitly requests that behavior.

## Template mapping

Priority:

```text
reuse corporate pattern
→ duplicate/adapt
→ minimal structural adjustment
→ alternate corporate pattern
→ create from scratch only as last resort
```

Template adapts to approved content, not vice versa.

## Automatic visual QA/fitting

For each materialized content or structural slide:

```text
render thumbnail
→ inspect
→ bounded visual correction
→ render again
→ repeat up to configured limit
```

Detect:

- clipping/overflow;
- overlap;
- word/syllable fragmentation;
- poor line balance;
- excessively small text;
- layout imbalance;
- residual template/example text;
- accidental generic `cliente/customer` copy;
- incorrect language.

### Safe correction order

1. natural manual line breaks between words;
2. resize/reposition textbox within layout;
3. reduce font in small increments;
4. select another valid corporate pattern;
5. flag for human review / return to phase 4 if still impossible.

Never solve fit by rewriting approved copy.

Defaults:

```yaml
presentation:
  visual_qa:
    max_fix_iterations: 3
    headline_max_font_reduction_pt: 4
    body_max_font_reduction_pt: 2
```

Do not exceed safe reductions merely to force a bad layout.

## Visual support

Materialize approved visual intent using template-compatible diagrams, shapes, tables, imagery or customer visuals.

Architecture diagrams should remain readable slide views rather than technical-specification dumps.

## Language

Visible content uses `presentation.language`, falling back to top-level `language` only when absent.

Remove/replace all irrelevant template boilerplate and prior-offer/customer text.

## Pre-completion reconciliation

Perform an explicit plan-to-deck reconciliation.

### Hierarchy reconciliation

For every approved section/subsection verify:

```text
correct parent?               YES
exact structural title?       YES
cover presence matches plan?  YES
content slides nested/order?  YES
```

### Content-slide reconciliation

For every approved content slide verify:

```text
Slide ID mapped?               YES
Order preserved?               YES
Exact title preserved?         YES
Title <=12 words?              YES
Visual headline only if approved? YES
Primary message preserved?     YES
No unsupported claim?          YES
No generic cliente/customer wording? YES
```

A failure in title/hierarchy/unauthorized headline is a build failure to correct, not a reportable creative deviation.

## Outputs

Required:

```text
generated/presentation/presentation.json
```

Expected for validation:

```text
generated/presentation/presentation-build-report.md
```

Report:

- deck URL/title;
- template;
- top-level sections materialized;
- subsections materialized;
- content slides planned/materialized;
- structural section/subsection covers materialized;
- other corporate slides (cover/agenda/closing);
- total physical slide count;
- exact-title fidelity result;
- hierarchy fidelity result;
- automatic visual adjustments by slide;
- unresolved visual issues;
- customer visuals reused;
- confirmation of zero unapproved `cliente/customer` visible wording;
- confirmation no estimates/commitments were invented.

## Completion criteria

Complete only when:

1. approved section/subsection hierarchy is faithfully materialized;
2. structural cover presence matches plan;
3. all content slides map 1:1;
4. exact approved titles are preserved;
5. no title violates the <=12-word phase-4 contract;
6. no unapproved display headlines exist;
7. no generic `cliente/customer` visible copy exists;
8. visual QA completed within safe bounds;
9. corporate style is preserved;
10. template remains unchanged;
11. `presentation.json` exists;
12. `presentation.status: waiting_for_human` is persisted.

STOP for human review.
