---
name: build-strategy
description: Execute phase 2, Estrategia de respuesta, with the Business Analyst / Offer Owner and produce a single strategy.md for human validation.
---

# Fase 2 — Estrategia de respuesta

Input:

```text
workspace/<proposal>
```

## Owner and execution model

This phase is owned by:

```text
Analista de Negocio / Owner de Oferta
```

The Business Analyst is the same end-to-end offer owner that qualified the opportunity in phase 1. It gives coherence to the complete response, coordinates later base roles and owns the strategic story.

Run phase 2 in the current context with no subagents/forks. Do not invoke Solution Architect, Delivery Manager, optional specialists, reviewers or storytellers here.

## Preconditions and context

Require approved phase 1 and read:

```text
generated/analysis/opportunity-brief.md
generated/analysis/questions.md     # if present
generated/analysis/technology.md    # if present
```

Human-entered customer answers and decisions in `questions.md` supersede earlier unresolved assumptions while preserving provenance.

Use validated phase-1 artifacts as the normal strategy context. Original customer sources remain authoritative and may be reopened for targeted verification when needed, but do not repeat a full qualification pass.

Use `language` and preferred model `ai.task_models.response_strategy` from `offer-config.yaml`; default model hint is `sonnet`. Do not fork merely to route models.

## Purpose

Transform customer understanding into a coherent response direction before detailed solution design, delivery planning, estimation or slides.

The Business Analyst must define:

### 1. Tesis de la oferta / mensaje central

The central internal thesis that should keep the response coherent. It is our proposal framing, not a customer fact.

### 2. Storytelling estratégico

Cover:

- context and need;
- objectives and expected outcome;
- in-scope, out-of-scope and protected/unclear scope;
- how we can help at high level;
- proposed execution methodology at high level;
- concrete value-add/differentiators when credible.

This is strategic storytelling, not slide-by-slide planning.

### 3. High-level solution directions

Describe one or more credible directions. If several exist, compare customer fit, pros, cons/trade-offs, risks, dependencies and validations needed.

Do not force a final choice when technical validation is still required. Preserve explicit human decisions and never resurrect a rejected alternative without new material evidence.

### 4. Execution risks and preliminary mitigations

Start from phase-1 execution risks and add preliminary mitigations, preventive actions/conditions and dependencies. These are proposal ideas, not commitments.

### 5. Assumptions

Consolidate assumptions needed to continue, their origin, impact if wrong, related question and status.

### 6. Pending strategic decisions

Keep internal decisions separate from customer questions.

### 7. Additional expertise potentially required

Do **not** list the base offer roles as specialists. The normal downstream team is already:

```text
Business Analyst / Offer Owner
Solution Architect
Delivery Manager
```

This section identifies only **additional deep expertise** that may be needed later, for example security, AWS/Azure/GCP, OpenShift/Red Hat, SAP, network, data/AI, mainframe or a very specific domain SME.

For each optional specialist record:

```text
| Especialidad adicional | ¿Necesaria? | Motivo | Preguntas concretas | Evidencia/fuentes que debería revisar |
```

Do not request a specialist just because a technology appears. There must be a bounded question that the Solution Architect or Delivery Manager should not reasonably be expected to resolve alone.

### 8. Conditions for success and limits

Explain what must hold for the strategy to remain viable and what must not yet be overpromised.

## Epistemic discipline

Keep distinct:

- `FACT`
- `INFERENCE`
- `ASSUMPTION`
- `QUESTION`
- `DECISION`
- `PROPOSAL`

Do not present our choice as a customer requirement.

## Scope boundary

Phase 2 must not:

- create detailed architecture;
- create detailed workstreams/tasks/sprint plans;
- estimate effort, staffing, duration, price or margin;
- create slide inventory/storyboard;
- invoke base roles or specialists;
- generate separate supporting strategy files.

## Output

Write exactly:

```text
generated/strategy/strategy.md
```

Recommended structure:

```text
# Estrategia de respuesta
## Resumen de la estrategia
## 1. Tesis de la oferta / mensaje central
## 2. Storytelling estratégico
### 2.1 Contexto y necesidad
### 2.2 Objetivos y resultado esperado
### 2.3 Alcance que proponemos abordar
### 2.4 Cómo podemos ayudar
### 2.5 Metodología / enfoque de ejecución
### 2.6 Valor añadido / diferenciadores
## 3. Riesgos de ejecución y estrategia de mitigación
## 4. Asunciones para construir la propuesta
## 5. Decisiones estratégicas pendientes
## 6. Necesidades de capacidades/especialistas adicionales
## 7. Condiciones de éxito y límites de la estrategia
```

Stop with `strategy.status: waiting_for_human`. Do not begin solution definition until explicit human approval.
