---
name: qualify-opportunity
description: Understand and qualify the opportunity in one Business Analyst execution, including response strategy and GO/NO-GO decision support.
---

# Understand & Qualify

Owner: **Business Analyst / Offer Owner**

This skill performs the complete first business phase in one reasoning pass over the customer evidence.

## Purpose

Establish a reliable canonical understanding of the opportunity before solution design starts.

Answer, when evidence allows:

- What does the customer want?
- Why do they want it?
- What outcomes/objectives are expected?
- What is in scope?
- What is explicitly or implicitly out of scope?
- What dates concern the bid process and what dates concern project execution?
- What constraints, dependencies and acceptance conditions are already known?
- What technologies/products/architectures are mandated, preferred or merely mentioned?
- What material questions remain open?
- What initial execution risks exist?
- Which assumptions are reasonable while questions remain open?
- What response strategy/positioning best addresses the opportunity?
- What potential value-add elements complement the requested scope without changing customer facts?

## Human GO/NO-GO gate

The skill provides evidence and decision support for a human business owner. It MUST NOT decide GO/NO-GO itself.

Include factors such as:

- opportunity fit;
- material blockers/gaps;
- response feasibility;
- important dependencies;
- differentiators/value-add opportunities;
- risks that should influence the human decision.

## Evidence rules

- Original customer sources are factual authority.
- Preserve evidence locators for material claims.
- Distinguish FACT, ASSUMPTION, GAP and RESPONSE STRATEGY.
- Do not design the technical solution in this phase.
- Do not invent dates, prices, staffing, effort or commitments.

## Outputs

One execution produces three logical outputs:

1. `opportunity-brief.md` — required and canonical.
2. `questions.md` — optional; use `NONE` if no material questions exist.
3. `technology.md` — optional; use `NONE` if no relevant technology/architecture constraints are stated.

`opportunity-brief.md` also contains the former standalone response-strategy content: scope, exclusions, objectives, assumptions, initial risks, response positioning and value-add opportunities.
