from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Protocol

from agent_platform.application.embeddings import EmbeddingProvider, EmbeddingRequest, EmbeddingResult
from agent_platform.application.observability import CACHE_OPS, timed_span


def stable_cache_key(value:Any)->str:
    payload=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class CacheProvider(Protocol):
    async def get(self,key:str)->str|None:...
    async def set(self,key:str,value:str,ttl_seconds:int|None=None)->None:...
    async def delete_prefix(self,prefix:str)->int:...


class InMemoryCacheProvider:
    def __init__(self)->None:self._values={};self._lock=asyncio.Lock()
    async def get(self,key):
        async with self._lock:
            current=self._values.get(key)
            if current is None:return None
            value,expires_at=current
            if expires_at is not None and expires_at<=time.monotonic():self._values.pop(key,None);return None
            return value
    async def set(self,key,value,ttl_seconds=None):
        expires_at=time.monotonic()+ttl_seconds if ttl_seconds and ttl_seconds>0 else None
        async with self._lock:self._values[key]=(value,expires_at)
    async def delete_prefix(self,prefix):
        async with self._lock:
            keys=[key for key in self._values if key.startswith(prefix)]
            for key in keys:self._values.pop(key,None)
            return len(keys)


@dataclass
class CacheNamespaceStats:
    hits:int=0;misses:int=0;writes:int=0;invalidations:int=0


class CacheService:
    def __init__(self,provider:CacheProvider,*,prefix:str="agent-platform")->None:self._provider=provider;self._prefix=prefix.rstrip(":");self._stats={}
    def _key(self,namespace,key):return f"{self._prefix}:{namespace}:{key}"
    def _namespace_prefix(self,namespace):return f"{self._prefix}:{namespace}:"
    def _ns(self,namespace):return self._stats.setdefault(namespace,CacheNamespaceStats())
    async def get_json(self,namespace,key):
        with timed_span("cache.get",cache_namespace=namespace):
            raw=await self._provider.get(self._key(namespace,key));stats=self._ns(namespace)
            if raw is None:stats.misses+=1;CACHE_OPS.labels(namespace,"get","miss").inc();return None
            stats.hits+=1;CACHE_OPS.labels(namespace,"get","hit").inc();return json.loads(raw)
    async def set_json(self,namespace,key,value,*,ttl_seconds=None):
        with timed_span("cache.set",cache_namespace=namespace):
            raw=json.dumps(value,ensure_ascii=False,separators=(",",":"),default=str);await self._provider.set(self._key(namespace,key),raw,ttl_seconds);self._ns(namespace).writes+=1;CACHE_OPS.labels(namespace,"set","ok").inc()
    async def invalidate_namespace(self,namespace):
        with timed_span("cache.invalidate",cache_namespace=namespace):
            deleted=await self._provider.delete_prefix(self._namespace_prefix(namespace));self._ns(namespace).invalidations+=1;CACHE_OPS.labels(namespace,"invalidate","ok").inc();return deleted
    def stats(self):
        return{namespace:{"hits":stats.hits,"misses":stats.misses,"writes":stats.writes,"invalidations":stats.invalidations} for namespace,stats in sorted(self._stats.items())}


class CachedEmbeddingProvider:
    def __init__(self,delegate:EmbeddingProvider,cache:CacheService,*,ttl_seconds:int=86400)->None:self._delegate=delegate;self._cache=cache;self._ttl_seconds=ttl_seconds
    @property
    def provider_key(self):return self._delegate.provider_key
    @property
    def model(self):return self._delegate.model
    @property
    def dimensions(self):return self._delegate.dimensions
    async def embed(self,request):
        with timed_span("embedding.generate",provider=self.provider_key,model=self.model,batch_size=len(request.texts)):
            vectors=[None]*len(request.texts);misses=[]
            for index,text in enumerate(request.texts):
                key=stable_cache_key({"provider":self.provider_key,"model":self.model,"dimensions":self.dimensions,"text":text});cached=await self._cache.get_json("embedding",key)
                if cached is None:misses.append((index,text,key))
                else:vectors[index]=[float(value) for value in cached["vector"]]
            if misses:
                generated=await self._delegate.embed(EmbeddingRequest(texts=[text for _,text,_ in misses]))
                if len(generated.vectors)!=len(misses):raise RuntimeError("Embedding provider returned an unexpected vector count")
                for(index,_,key),vector in zip(misses,generated.vectors,strict=True):
                    vectors[index]=vector;await self._cache.set_json("embedding",key,{"vector":vector,"model":generated.model,"dimensions":generated.dimensions},ttl_seconds=self._ttl_seconds)
            return EmbeddingResult(vectors=[v for v in vectors if v is not None],model=self.model,dimensions=self.dimensions)


__all__=["CacheProvider","CacheService","CachedEmbeddingProvider","InMemoryCacheProvider","stable_cache_key"]
