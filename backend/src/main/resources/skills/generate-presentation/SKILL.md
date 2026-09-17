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

Require analysis, strategy, solution and slide_plan approved. Require `generated/presentation/slides-plan.md` and complete presentation template/output configuration.

## Owner

```text
Presentation Builder
```

A bounded `corporate-slide-designer` may advise only on visual pattern/layout selection. It MUST NOT rewrite titles, structural headings, slogans, primary messages or proposal content.

## Frozen presentation contract

After human approval, `slides-plan.md` is authoritative for section hierarchy, subsection hierarchy, exact section/subsection titles, cover yes/no, content-slide membership/order/ID, exact slide title, optional explicit visual headline, primary message, content intent, visual-support intent and notes.

Phase 5 MUST materialize that hierarchy faithfully.

### Section/subsection structural slides

For each section/subsection read `Portada de sección: Sí/No` / `Portada de subsección: Sí/No`. When yes, materialize a structural cover using the exact approved title. Do not generate a cover when no. Do not invent additional sections/subsections.

Corporate cover, agenda and closing may be controlled globally; section/subsection covers are governed by the approved plan. The agenda derives from top-level approved sections and must not promote subsections unless explicitly requested.

### Exact content-slide title rule

For each content slide:

```text
presentation title == approved slides-plan title
```

verbatim. The title must already satisfy the phase-4 <=12-word contract. If not, stop and return to phase 4 rather than shortening it.

Phase 5 may change only natural line breaks between words, font size within safe limits, textbox geometry and chosen corporate layout. Never change wording to fit.

### Visual headline rule

Use an additional display headline only when explicitly defined in `slides-plan.md` and not `No definido`. Never invent slogans/taglines/display headlines.

## Generic customer-language prohibition

Do not introduce generic visible terms such as `cliente`, `el cliente`, `nuestro cliente`, `the client`, `the customer`. If this wording remains in an approved slide plan, treat it as a phase-4 contract violation. Template example text must always be replaced/removed.

## Template safety

Corporate template is immutable:

```text
resolve template
→ inspect/catalog if necessary
→ copy template
→ verify generated ID != template ID
→ edit only generated copy
```

Persist presentation metadata.

## Source hierarchy

1. approved `slides-plan.md` → narrative + hierarchy + copy authority;
2. corporate template/catalog → UX/style/layout authority;
3. upstream artifacts → clarification only;
4. customer sources → only a specifically requested referenced visual/exact fact.

## Materialization order

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

For each materialized slide:

```text
render thumbnail
→ inspect
→ bounded visual correction
→ render again
→ repeat up to configured limit
```

Detect clipping/overflow, overlap, word/syllable fragmentation, poor line balance, excessively small text, layout imbalance, residual template/example text, accidental generic cliente/customer copy and incorrect language.

Safe correction order:
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

## Visual support

Materialize approved visual intent using template-compatible diagrams, shapes, tables, imagery or customer visuals. Architecture diagrams should remain readable slide views rather than technical-specification dumps.

## Language

Visible content uses `presentation.language`, falling back to top-level `language` only when absent. Remove/replace irrelevant template boilerplate and prior-offer/customer text.

## Pre-completion reconciliation

For every approved section/subsection verify correct parent, exact structural title, cover presence and nested content order. For every approved content slide verify ID mapped, order preserved, exact title preserved, title <=12 words, visual headline only if approved, primary message preserved, no unsupported claim and no generic cliente/customer wording.

A failure in title/hierarchy/unauthorized headline is a build failure to correct, not a creative deviation.

## Outputs

Required presentation metadata plus actual Google Slides document. Expected build report records deck URL/title, template, sections/subsections, content slides planned/materialized, structural covers, other corporate slides, total count, exact-title fidelity, hierarchy fidelity, visual adjustments, unresolved issues, customer visuals reused, zero unapproved cliente/customer wording and no invented estimates/commitments.

## Completion criteria

Complete only when approved hierarchy is faithfully materialized; cover presence matches plan; all content slides map 1:1; exact titles are preserved; no title violates <=12 words; no unapproved display headlines exist; no generic cliente/customer visible copy exists; visual QA completed within safe bounds; corporate style preserved; original template unchanged; metadata exists; and presentation status is waiting for human.

STOP for human review.
