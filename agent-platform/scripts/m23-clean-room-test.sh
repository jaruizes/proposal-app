#!/usr/bin/env sh
set -eu

REAL_MODEL=0
KEEP_SMOKE_DATA=0

for arg in "$@"; do
  case "$arg" in
    --real-model) REAL_MODEL=1 ;;
    --keep-smoke-data) KEEP_SMOKE_DATA=1 ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: $0 [--real-model] [--keep-smoke-data]" >&2
      exit 2
      ;;
  esac
done

echo "[M23] WARNING: this removes the agent-platform PostgreSQL named volume."
echo "[M23] Resetting platform to a clean database..."
docker compose down -v --remove-orphans

echo "[M23] Building and starting platform..."
docker compose up -d --build

echo "[M23] Waiting for readiness..."
attempt=0
until docker compose exec -T agent-platform python -m agent_platform.full_test --phase empty >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo "[M23] Platform did not become ready/empty in time." >&2
    docker compose logs agent-platform
    exit 1
  fi
  sleep 2
done

docker compose exec -T agent-platform python -m agent_platform.full_test --phase empty

echo "[M23] Loading the Git-tracked Proposal Copilot skills and agents..."
docker compose exec -T agent-platform python -m agent_platform.bootstrap --sync

echo "[M23] Verifying catalog and exercising platform..."
if [ "$REAL_MODEL" -eq 1 ]; then
  if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "[M23] --real-model requires ANTHROPIC_API_KEY in the shell environment." >&2
    exit 1
  fi
  docker compose exec -T agent-platform python -m agent_platform.full_test --phase full --real-model
else
  docker compose exec -T agent-platform python -m agent_platform.full_test --phase full
fi

if [ "$KEEP_SMOKE_DATA" -eq 1 ]; then
  echo "[M23] PASSED. Keeping smoke-test database as requested."
  exit 0
fi

echo "[M23] Smoke checks passed. Recreating a clean final platform..."
docker compose down -v --remove-orphans
docker compose up -d

attempt=0
until docker compose exec -T agent-platform python -m agent_platform.full_test --phase empty >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo "[M23] Final platform did not become ready/empty in time." >&2
    docker compose logs agent-platform
    exit 1
  fi
  sleep 2
done

docker compose exec -T agent-platform python -m agent_platform.bootstrap --sync
docker compose exec -T agent-platform python -m agent_platform.full_test --phase catalog

echo
echo "[M23] PASSED"
echo "[M23] Final state: clean DB + canonical 7 skills + 6 agents + 6 empty default knowledge bases."
echo "[M23] Admin UI: http://localhost:8000/admin/"
echo "[M23] API docs: http://localhost:8000/docs"
echo "[M23] Jaeger:   http://localhost:16686"
