from fastapi import APIRouter

from agent_platform.api.dependencies import CacheServiceDep


router = APIRouter(prefix="/v1/cache", tags=["cache"])


@router.get("/stats")
async def stats(cache: CacheServiceDep) -> dict:
    return {"namespaces": cache.stats()}


@router.delete("/{namespace}")
async def invalidate(namespace: str, cache: CacheServiceDep) -> dict:
    deleted = await cache.invalidate_namespace(namespace)
    return {"namespace": namespace, "deleted": deleted}
