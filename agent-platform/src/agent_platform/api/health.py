from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from agent_platform.api.dependencies import get_cache_service
from agent_platform.persistence.database import SessionFactory

router = APIRouter(tags=["platform"])


@router.get("/health")
@router.get("/health/live")
async def live() -> dict:
    return {"status": "ok", "service": "proposal-agent-platform"}


@router.get("/health/ready")
async def ready():
    checks = {"database": "unknown", "cache": "unknown"}
    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    try:
        cache = get_cache_service()
        provider = cache._provider
        ping = getattr(provider, "ping", None)
        checks["cache"] = "ok" if ping is None or await ping() else "error"
    except Exception:
        checks["cache"] = "error"

    ok = all(value == "ok" for value in checks.values())
    payload = {"status": "ready" if ok else "not_ready", "checks": checks}
    return payload if ok else JSONResponse(status_code=503, content=payload)
