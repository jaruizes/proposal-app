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

## Milestone 23 — independent clean-room test

Milestone 23 provides a destructive, repeatable clean-room validation of the independent platform.

The canonical bootstrap catalog is Git-tracked and contains:

- 7 skills: `create-offer`, `ingest-sources`, `analyze-opportunity`, `build-strategy`, `define-solution`, `design-proposal`, `generate-presentation`.
- 6 agents: `business-analyst`, `solution-architect`, `delivery-manager`, `presentation-builder`, `security-specialist`, `corporate-slide-designer`.

### Start clean with the existing agents and skills

From `agent-platform/`:

```bash
./scripts/m23-bootstrap-clean.sh
```

This command removes the platform PostgreSQL named volume, starts the stack, verifies the database is empty, imports the Git bootstrap catalog and creates/verifies the six default empty knowledge bases.

Final state:

```text
7 canonical skills
6 canonical agents
6 empty default knowledge bases
0 customer documents
0 ontology concepts
0 business memory
```

You can then test manually through http://localhost:8000/admin/.

### Complete automated clean-room test

```bash
./scripts/m23-clean-room-test.sh
```

The runner:

1. destroys the platform database volume;
2. builds and starts the complete isolated stack;
3. proves Agents, Skills, Knowledge and Ontology are initially empty;
4. imports the canonical skills and agents;
5. bootstraps the six default knowledge bases;
6. verifies registry references;
7. exercises ontology CRUD, document ingestion, metadata enrichment, ontology tagging and graph-aware retrieval;
8. exercises Memory, Cache, MCP registry, Admin API, readiness and security headers;
9. resets the database a second time;
10. finishes with a clean usable platform containing only the canonical agents, skills and empty default knowledge bases.

The smoke data is therefore not left in your final database.

To retain smoke data for inspection:

```bash
./scripts/m23-clean-room-test.sh --keep-smoke-data
```

### Optional real Anthropic call

The standard M23 test does not spend LLM tokens. To include one real execution using the existing `business-analyst` + `analyze-opportunity` definitions:

```bash
export ANTHROPIC_API_KEY='...'
./scripts/m23-clean-room-test.sh --real-model
```

This validates execution persistence, the real Anthropic adapter, token accounting and execution diagnostics in addition to the deterministic platform checks.

> Both M23 shell scripts are destructive for the `agent-platform-postgres-data` Docker volume.

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

## Architecture

The platform owns cognitive execution: agents, skills, model runtime, tools/MCP, memory, cache, RAG, ontology and observability. Business workflow orchestration remains outside this service.
