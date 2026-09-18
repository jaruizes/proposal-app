#!/usr/bin/env sh
set -eu

echo "[M23] WARNING: this removes the agent-platform PostgreSQL named volume."
docker compose down -v --remove-orphans
docker compose up -d --build

attempt=0
until docker compose exec -T agent-platform python -m agent_platform.full_test --phase empty >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    docker compose logs agent-platform
    exit 1
  fi
  sleep 2
done

docker compose exec -T agent-platform python -m agent_platform.bootstrap --sync
docker compose exec -T agent-platform python -m agent_platform.full_test --phase catalog

echo "[M23] Ready: clean platform with canonical agents/skills loaded."
echo "[M23] Open http://localhost:8000/admin/"
