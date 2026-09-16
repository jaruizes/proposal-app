# Proposal Agent Platform

Extensible agent platform whose first application is **Proposal Copilot**.

## Current vertical slice

- Angular frontend connected to backend with REST + SSE.
- Spring Boot / Java 21 backend.
- PostgreSQL + Flyway.
- Hexagonal packages: `domain`, `business`, `infrastructure`; dependency direction `infrastructure → business → domain`.
- Generic Agent Registry, Agent Runtime and AgentTask model.
- Parallel agent primitive using Java virtual threads.
- Anthropic Claude Messages API adapter.
- Proposal workflow with mandatory human gates: `analysis → strategy → solution → slide_plan → presentation`.
- Phase 3 preserves `Solution Architect → Delivery Manager → Business Analyst coherence`.
- Versioned artifacts and downstream stale handling on refinement.
- Ports for MCP/tools, knowledge/RAG, memory, ontology and cognitive services.
- OpenTelemetry traces → Collector → Tempo.
- Prometheus metrics + provisioned Grafana dashboard.

## First-version boundary

Google Drive ingestion and Google Slides materialization are explicit adapter boundaries and are not yet production integrations. Phase 5 currently uses a `PresentationPort` stub so the end-to-end state machine can be exercised without Google credentials. The next implementation can use Google Workspace APIs or MCP without changing business/domain packages.

## Run

```bash
cp .env.example .env
# set ANTHROPIC_API_KEY in .env for real Claude calls
docker compose up --build
```

- Frontend: http://localhost:4200
- Backend: http://localhost:8080
- Grafana: http://localhost:3000 (`admin` / `admin`)
- Prometheus: http://localhost:9090
- Tempo: http://localhost:3200

Without `ANTHROPIC_API_KEY`, fallback mode keeps the workflow runnable for UI validation.

## Architecture

```text
Angular → REST/SSE → Spring Agent Platform
                        ├─ Agent Registry / Runtime
                        ├─ Proposal Workflow + Human Gates
                        ├─ Model Gateway → Anthropic
                        ├─ Tool/MCP Gateway port
                        ├─ Knowledge/RAG port
                        ├─ Memory port
                        ├─ Ontology port
                        ├─ Cognitive port
                        └─ PostgreSQL artifacts/state
```

Proposal Copilot is the first application; platform ports are designed so future agent applications and cognitive/ontology layers can be added without coupling them to Anthropic or Google.
