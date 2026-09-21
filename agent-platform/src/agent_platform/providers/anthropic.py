from __future__ import annotations
import asyncio
from typing import Any
from anthropic import AsyncAnthropic
from agent_platform.application.models import ModelProviderError,ModelRequest,ModelResult,ModelUsage
from agent_platform.config import Settings,get_settings

class AnthropicModelProvider:
    RETRYABLE={"APITimeoutError","APIConnectionError","RateLimitError","InternalServerError","OverloadedError"}
    def __init__(self,settings:Settings|None=None,client:Any|None=None)->None:
        self._settings=settings or get_settings()
        if client is not None:self._client=client;return
        if not self._settings.anthropic_api_key:raise ModelProviderError("ANTHROPIC_NOT_CONFIGURED","ANTHROPIC_API_KEY is required to use the Anthropic provider")
        kwargs={"api_key":self._settings.anthropic_api_key,"timeout":self._settings.anthropic_timeout_seconds,"max_retries":0}
        if self._settings.anthropic_base_url and self._settings.anthropic_base_url.strip():kwargs["base_url"]=self._settings.anthropic_base_url.strip()
        self._client=AsyncAnthropic(**kwargs)
    async def generate(self,request:ModelRequest)->ModelResult:
        model=request.model or self._settings.anthropic_default_model;max_tokens=request.max_output_tokens or self._settings.anthropic_default_max_output_tokens
        messages=[]
        for index,m in enumerate(request.messages):
            if index==0 and request.cacheable_context:
                messages.append({"role":m.role.value,"content":[
                    {"type":"text","text":request.cacheable_context,"cache_control":{"type":"ephemeral"}},
                    {"type":"text","text":m.content},
                ]})
            else:
                messages.append({"role":m.role.value,"content":m.content})
        payload={"model":model,"max_tokens":max_tokens,"messages":messages}
        if request.system_prompt:
            payload["system"]=[{"type":"text","text":request.system_prompt,"cache_control":{"type":"ephemeral"}}] if request.cache_system_prompt else request.system_prompt
        if request.temperature is not None:payload["temperature"]=request.temperature
        attempts=max(1,self._settings.anthropic_max_retries+1);last_exc=None
        for attempt in range(attempts):
            try:
                async with self._client.messages.stream(**payload) as stream:
                    text=await stream.get_final_text();response=await stream.get_final_message()
                break
            except Exception as exc:
                last_exc=exc;name=type(exc).__name__;retryable=name in self.RETRYABLE
                if not retryable or attempt==attempts-1:raise ModelProviderError(f"ANTHROPIC_{name.upper()}",str(exc) or "Anthropic request failed",retryable=retryable) from exc
                await asyncio.sleep(self._settings.anthropic_retry_base_seconds*(2**attempt))
        else:raise ModelProviderError("ANTHROPIC_REQUEST_FAILED",str(last_exc) if last_exc else "Anthropic request failed",retryable=True)
        usage=getattr(response,"usage",None)
        model_usage=ModelUsage(input_tokens=getattr(usage,"input_tokens",0) or 0,output_tokens=getattr(usage,"output_tokens",0) or 0,cache_read_tokens=getattr(usage,"cache_read_input_tokens",0) or 0,cache_write_tokens=getattr(usage,"cache_creation_input_tokens",0) or 0)
        if getattr(response,"stop_reason",None)=="max_tokens":
            raise ModelProviderError(
                "ANTHROPIC_OUTPUT_TRUNCATED",
                "Model output reached max_tokens; the document may be incomplete",
                partial_content=text,
                usage=model_usage,
                model=getattr(response,"model",model),
                provider_request_id=getattr(response,"id",None),
            )
        return ModelResult(content=text,model=getattr(response,"model",model),usage=model_usage,provider_request_id=getattr(response,"id",None),finish_reason=getattr(response,"stop_reason",None),metadata={"provider":"anthropic","transport":"stream"})
