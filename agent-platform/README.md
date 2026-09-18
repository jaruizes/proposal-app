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
- Liveness: http://localhost:8000/health/live
- Readiness: http://localhost:8000/health/ready
- Prometheus metrics: http://localhost:8000/metrics
- Jaeger: http://localhost:16686

## Administration UI

The same-origin administration console under `/admin/` covers Agents, Skills, Knowledge, Ontology, scoped Memory, MCP/tools, Cache and Observability.

## Hardening

Milestone 22 adds a production-oriented HTTP and runtime boundary:

- Optional API-key protection for the `/v1` surface using `X-API-Key`.
- Constant-time API-key comparison.
- Configurable request-size ceiling (30 MB by default).
- Per-client in-memory rate limiting (240 requests/minute by default).
- Security response headers and request IDs.
- Sanitized unexpected 500 responses.
- Separate liveness and readiness probes.
- Readiness checks PostgreSQL and Valkey.
- Explicit database pool sizing, pre-ping, recycle and rollback-on-error.
- Bounded exponential retries for retryable Anthropic failures.
- Google OAuth secrets mounted read-only in Docker.

Hardening defaults keep local development compatible: API-key protection is disabled unless `API_KEY_ENABLED=true`.

Example:

```bash
export API_KEY_ENABLED=true
export API_KEY='change-me'
docker compose up --build
curl -H 'X-API-Key: change-me' http://localhost:8000/v1/agents
```

When API-key protection is enabled, enter the same key in the Admin UI header; it is stored only in browser local storage.

## Architecture

The platform owns cognitive execution: agents, skills, model runtime, tools/MCP, memory, cache, RAG, ontology and observability. Business workflow orchestration remains outside this service.
