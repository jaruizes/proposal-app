# Proposal Agent Platform

Independent Python/FastAPI agent platform used by Proposal Copilot and future applications.

## Local run

```bash
docker compose up --build
```

Main endpoints:

- API: http://localhost:8000
- OpenAPI: http://localhost:8000/docs
- Admin UI: http://localhost:8000/admin/
- Prometheus metrics: http://localhost:8000/metrics
- Jaeger: http://localhost:16686

## Administration UI

The platform ships a lightweight, same-origin administration console under `/admin/`. It is deliberately independent from the Proposal Copilot Angular UI and operates directly against the Agent Platform API.

The console covers:

- Dashboard/runtime overview.
- Agent and Skill JSON editing through the versioned registries.
- Knowledge Base browsing and file upload/ingestion.
- Ontology concept and relationship administration.
- Scoped Memory recall.
- MCP server and tool discovery.
- Cache statistics and invalidation.
- Observability links and execution diagnostics.

It does not expose secrets and it does not provide unrestricted global memory enumeration.

## Architecture

The platform owns cognitive execution: agents, skills, model runtime, tools/MCP, memory, cache, RAG, ontology and observability. Business workflow orchestration remains outside this service.
