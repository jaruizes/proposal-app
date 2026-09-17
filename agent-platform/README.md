# Proposal Agent Platform

Independent Python service that hosts the reusable agent runtime for Proposal Copilot and future applications.

This service is intentionally isolated from the existing Spring Boot workflow. The current application remains unchanged until the platform reaches parity with the existing agents and skills.

## Current capabilities

- Python 3.11+ locally; container runtime uses Python 3.13
- FastAPI + Pydantic v2
- PostgreSQL persistence with SQLAlchemy async and Alembic
- Dynamic Agent and Skill registries
- Provider-neutral model contract
- Anthropic adapter
- Native Python Agent Runtime with persisted execution lifecycle
- Git-tracked bootstrap catalog containing the current Proposal Copilot agents and skills
- Runtime parity tests for current agent/skill assignments
- Opt-in real Anthropic API integration smoke test
- `/health`, `/v1/agents`, `/v1/skills` and `/v1/executions` APIs

## Run locally

```bash
cd agent-platform
export ANTHROPIC_API_KEY="..."
docker compose up --build
```

Then verify:

```bash
curl http://localhost:8000/health
```

Swagger is available at `http://localhost:8000/docs`.

## Bootstrap Proposal Copilot definitions

The platform keeps the current Proposal Copilot Agent/Skill contracts under `agent_platform/bootstrap_data` so the independent platform can be tested before the Spring application is changed.

After PostgreSQL is running, import missing definitions with:

```bash
python -m agent_platform.bootstrap
```

The default import is safe for definitions edited later through the runtime/API: existing DB definitions are left unchanged.

To deliberately synchronize existing DB definitions with the Git bootstrap snapshot:

```bash
python -m agent_platform.bootstrap --sync
```

`--sync` updates only definitions whose Git representation differs and uses the normal registries, so updated definitions receive a new version.

When running with Docker Compose:

```bash
docker compose exec agent-platform python -m agent_platform.bootstrap
```

After bootstrap, verify:

```bash
curl http://localhost:8000/v1/agents
curl http://localhost:8000/v1/skills
```

## Tests

Local development supports Python 3.11 or newer:

```bash
python -m pip install -e '.[dev]'
pytest
```

The normal suite never performs a paid external LLM request. The Anthropic parity smoke test is explicit opt-in:

```bash
export ANTHROPIC_API_KEY="..."
export RUN_ANTHROPIC_INTEGRATION=1
pytest -m integration tests/integration/test_anthropic_execution.py -v
```

Optionally route the integration test to another Anthropic model without changing the bootstrap catalog:

```bash
export ANTHROPIC_INTEGRATION_MODEL="claude-sonnet-4-6"
```

The integration test calls `POST /v1/executions` with the bootstrapped `business-analyst` + `analyze-opportunity` definitions and verifies a completed artifact, token usage, model, provider request ID and persisted lifecycle events.

## Design rule

The platform owns cognitive/agentic execution. Deterministic business workflows remain outside this service and will integrate only through the stable API contract after platform parity is validated.
