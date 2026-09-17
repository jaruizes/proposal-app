# Proposal Agent Platform

Extensible agent platform whose first application is **Proposal Copilot**. The validated contracts from `proposal-copilot/feat/optimize-tokens` are preserved as versioned `SKILL.md` and agent resources.

## What is implemented

- Angular frontend connected to backend with REST + SSE.
- Spring Boot / Java 21 backend using Hexagonal Architecture: `infrastructure → business → domain`.
- PostgreSQL + Flyway for workflow state, versioned artifacts and agent executions.
- Anthropic Claude Messages API, including PDF multimodal attachments.
- The same `mcp/google-workspace` server used by Proposal Copilot, executed by the backend over MCP stdio.
- Real Google Drive source ingestion before analysis.
- Native Docs/Slides/Sheets representations plus binary download/text extraction with Apache Tika.
- PDF visual representations attached to Claude where available.
- Skill Registry + Agent Registry; every role execution receives its validated agent definition and complete SKILL contract.
- Human-gated workflow: `analysis → strategy → solution → slide_plan → presentation`.
- Phase 3: Architect source triage → up to 2 bounded specialist consultations in parallel → Solution Architect → Delivery Manager → Business Analyst coherence review.
- Real Google Slides materialization through MCP using an immutable copied corporate template.
- OpenTelemetry traces → Collector → Tempo, Prometheus metrics and provisioned Grafana dashboard.
- Extension ports for MCP/tools, RAG/knowledge, memory, ontology and cognitive services.

## Google Workspace authentication

The MCP server is intentionally the same local OAuth implementation used in `proposal-copilot`.

1. Put your Google OAuth desktop/web client file at:

```text
.secrets/google-oauth-credentials.json
```

2. Authenticate once on the host (the OAuth flow opens your browser):

```bash
npm --prefix mcp/google-workspace install
npm --prefix mcp/google-workspace run auth
npm --prefix mcp/google-workspace run doctor
```

This creates `.secrets/google-token.json`. Both files are gitignored and mounted read-only into the backend container.

## Configuration

```bash
cp .env.example .env
```

Set at least:

```text
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_SLIDES_TEMPLATE_ID=<corporate Google Slides template id>
```

In the UI, **Google Drive input/output folder** accepts either a Drive folder ID or a normal `https://drive.google.com/drive/folders/<id>` URL.

## Run everything

```bash
docker compose up --build
```

- Frontend: http://localhost:4200
- Backend: http://localhost:8080
- Grafana: http://localhost:3000 (`admin` / `admin`)
- Prometheus: http://localhost:9090
- Tempo: http://localhost:3200

## Runtime architecture

```text
Angular → REST/SSE → Spring Agent Platform
                        ├─ Workflow / Human Gates
                        ├─ Agent Registry + Skill Registry
                        ├─ Agent Runtime → Claude API
                        ├─ Tool Gateway → Google Workspace MCP
                        ├─ Source Ingestion → Drive/Docs/Slides/Sheets + Tika
                        ├─ Presentation Builder → Google Slides MCP
                        ├─ Knowledge/RAG port
                        ├─ Memory port
                        ├─ Ontology port
                        ├─ Cognitive port
                        └─ PostgreSQL artifacts/state
```

## Skills and deterministic enforcement

The semantic behavior remains under `backend/src/main/resources/skills/**/SKILL.md`. Agent role definitions live under `backend/src/main/resources/agents`.

The runtime assembles each isolated model context as:

```text
agent definition (WHO)
+ full SKILL contract (HOW)
+ deterministic runtime context (WHAT evidence)
+ current task/refinement
```

Rules such as human gates, phase dependencies, downstream staleness, specialist fan-out limits and slide-title validation are enforced in Java as well as described to the model.

## First end-to-end test

1. Authenticate Google Workspace and configure `.env`.
2. Start Docker Compose.
3. Create an offer in the Angular UI using a Drive source folder ID/URL and output folder ID/URL.
4. The backend ingests the Drive folder and starts Phase 1 automatically.
5. Review each generated artifact in the UI, refine if needed, then approve to start the next phase.
6. Phase 5 copies the configured corporate template and materializes the approved slide plan into the generated Google Slides deck.
