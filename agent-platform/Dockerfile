FROM node:22-bookworm-slim AS google-workspace-mcp-builder

WORKDIR /build/mcp/google-workspace
COPY mcp/google-workspace/package.json mcp/google-workspace/tsconfig.json ./
COPY mcp/google-workspace/src ./src
RUN npm install && npm run build

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=google-workspace-mcp-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=google-workspace-mcp-builder /build/mcp/google-workspace /opt/mcp/google-workspace

WORKDIR /app

COPY agent-platform/pyproject.toml agent-platform/README.md agent-platform/alembic.ini ./
COPY agent-platform/alembic ./alembic
COPY agent-platform/src ./src

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn agent_platform.main:app --host 0.0.0.0 --port 8000"]
