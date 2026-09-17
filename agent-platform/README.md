# Proposal Agent Platform

Independent Python service that hosts the reusable agent runtime for Proposal Copilot and future applications.

This service is intentionally isolated from the existing Spring Boot workflow. The current application remains unchanged until the platform reaches parity with the existing agents and skills.

## Current capabilities

- Python 3.11+ locally; Python 3.13 container runtime
- FastAPI + Pydantic v2
- PostgreSQL persistence with SQLAlchemy async and Alembic
- Dynamic Agent and Skill registries
- Provider-neutral model contract and Anthropic adapter
- Native Python Agent Runtime with persisted execution lifecycle
- Git-tracked bootstrap catalog containing the current Proposal Copilot agents and skills
- Provider-neutral Tool contracts and Tool Registry
- MCP server registry and stdio MCP adapter
- Google Workspace MCP bundled behind the Agent Platform
- `/health`, `/v1/agents`, `/v1/skills`, `/v1/executions`, `/v1/tools` and `/v1/mcp/servers` APIs

## Run locally

```bash
cd agent-platform
export ANTHROPIC_API_KEY="..."
docker compose up --build
```

The Compose build context is the repository root because the Agent Platform image now bundles `mcp/google-workspace`. Google OAuth files are mounted from repository `.secrets/` and the MCP workspace is mounted from repository `workspace/`.

Then verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/v1/mcp/servers
curl 'http://localhost:8000/v1/tools?refresh=true'
```

Swagger is available at `http://localhost:8000/docs`.

A tool can be invoked through the platform instead of calling MCP directly:

```bash
curl -X POST http://localhost:8000/v1/tools/drive_list_folder/invoke \
  -H 'Content-Type: application/json' \
  -d '{"arguments":{"folderId":"YOUR_FOLDER_ID"}}'
```

## Bootstrap Proposal Copilot definitions

After PostgreSQL is running, import missing definitions with:

```bash
python -m agent_platform.bootstrap
```

The default import is safe for definitions edited later through the runtime/API: existing DB definitions are left unchanged. To deliberately synchronize with the Git bootstrap snapshot:

```bash
python -m agent_platform.bootstrap --sync
```

When running with Docker Compose:

```bash
docker compose exec agent-platform python -m agent_platform.bootstrap
```

## Tests

```bash
python -m pip install -e '.[dev]'
pytest
```

The real Google Workspace MCP smoke test is opt-in because it requires a built MCP server and Google OAuth configuration:

```bash
export RUN_GOOGLE_WORKSPACE_MCP_INTEGRATION=1
export GOOGLE_WORKSPACE_MCP_COMMAND=node
export GOOGLE_WORKSPACE_MCP_SCRIPT=../mcp/google-workspace/dist/server.js
export GOOGLE_WORKSPACE_MCP_CWD=../mcp/google-workspace
pytest -m integration tests/integration/test_google_workspace_mcp.py -v
```

## Design rule

The platform owns cognitive/agentic execution and tools. Applications do not call MCP servers directly; they call the Agent Platform. Deterministic business workflows remain outside this service and integrate through stable platform contracts.
