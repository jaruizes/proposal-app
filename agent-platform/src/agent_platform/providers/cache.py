from __future__ import annotations

from redis.asyncio import Redis


class ValkeyCacheProvider:
    """Redis-protocol adapter; Valkey is the production/local container implementation."""

    def __init__(self, url: str) -> None:
        self._client = Redis.from_url(url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        return await self._client.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        if ttl_seconds and ttl_seconds > 0:
            await self._client.set(key, value, ex=ttl_seconds)
        else:
            await self._client.set(key, value)

    async def delete_prefix(self, prefix: str) -> int:
        deleted = 0
        batch: list[str] = []
        async for key in self._client.scan_iter(match=f"{prefix}*", count=200):
            batch.append(key)
            if len(batch) >= 200:
                deleted += int(await self._client.delete(*batch))
                batch.clear()
        if batch:
            deleted += int(await self._client.delete(*batch))
        return deleted

    async def ping(self) -> bool:
        return bool(await self._client.ping())


__all__ = ["ValkeyCacheProvider"]
