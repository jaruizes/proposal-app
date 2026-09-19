# Proposal Agent Platform

Independent Python/FastAPI agent platform used by Proposal Copilot and future applications.

## LangGraph spike branch

Branch `feat/langraph` keeps the public Agent Platform contracts unchanged but replaces the background cognitive runtime with LangGraph by default.

The boundary is intentional:

```text
Proposal/Spring
      -> Agent Platform HTTP contract
      -> AgentRuntime abstraction
      -> LangGraphAgentRuntime
           -> CognitiveContextBuilder
           -> Memory / RAG / Ontology
           -> Anthropic provider
           -> PostgreSQL LangGraph checkpoints
```

LangGraph is therefore an internal runtime implementation, not the platform API.

Configuration:

```env
AGENT_RUNTIME=langgraph
LANGGRAPH_CHECKPOINT_DATABASE_URL=postgresql://agent_platform:agent_platform@postgres:5432/agent_platform
LANGGRAPH_STRICT_MSGPACK=true
```

Set `AGENT_RUNTIME=native` to compare against the native runtime without changing clients.

Ordinary skills use two nodes:

```text
START
  -> build_context
  -> invoke_model
  -> END
```

`compose-proposal` uses a dedicated graph after `build_context`:

```text
plan_proposal -> draft_sections -> review_sections -> assemble_proposal -> review_proposal
```

The planner validates enabled sections from the application's structured proposal
guidance. Drafting and section review run with bounded concurrency (three model
calls). A global review can request one targeted revision pass; unresolved
findings fail the execution. The result remains one canonical Markdown artifact,
with total token usage across all model calls and section-stage execution events.
The proposal graph does not retrieve reference proposals; that is a separate
milestone. The application continues to own the human approval gate.

The graph persists checkpoints in PostgreSQL using `AsyncPostgresSaver`. Existing platform execution state/events remain the external source of truth. This lets the spike compare LangGraph orchestration/checkpointing while keeping Agents, Skills, Memory, RAG, Ontology, Cache, Observability and provider adapters owned by the platform.

## Try it

```bash
git checkout feat/langraph
cd agent-platform
docker compose up -d --build
curl http://localhost:8000/v1/admin/config
```

The config response should show:

```json
{
  "runtime": {
    "engine": "langgraph",
    "checkpoint_backend": "postgres"
  }
}
```

Submit executions through the same API as before. The response remains asynchronous (`202 Accepted`). Inspect:

```text
GET /v1/executions/{id}
GET /v1/executions/{id}/events
GET /v1/executions/{id}/result
GET /v1/executions/{id}/diagnostics
```

Events include `langgraph.execution.started`, `langgraph.node.context.completed`, `langgraph.node.model.completed` and `langgraph.execution.completed`.

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

## Architecture

The platform owns stable contracts and cognitive capabilities. Runtime implementation is replaceable: `native` or `langgraph`.
