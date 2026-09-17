# Proposal Agent Platform

Independent Python service that will host the reusable agent runtime for Proposal Copilot and future applications.

This service is intentionally isolated from the existing Spring Boot workflow. The current application remains unchanged until the platform reaches parity with the existing agents and skills.

## Current scope

Bootstrap only:

- Python 3.13
- FastAPI
- Pydantic v2
- Uvicorn
- pytest/httpx development dependencies
- Docker image
- standalone Docker Compose
- `/health` endpoint

No agent runtime, LLM provider, MCP, persistence, RAG, memory or ontology is implemented in this block.

## Run locally

```bash
cd agent-platform
docker compose up --build
```

Then verify:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "proposal-agent-platform",
  "version": "0.1.0"
}
```

## Run tests

Using a local Python 3.13 environment:

```bash
pip install -e '.[dev]'
pytest
```

## Design rule

The platform owns cognitive/agentic execution. Deterministic business workflows remain outside this service and will integrate only through a stable API contract in a later milestone.
