from __future__ import annotations

import time
from contextlib import contextmanager
from uuid import uuid4

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, Histogram


EXECUTIONS = Counter("agent_platform_executions_total","Agent executions",["agent","skill","status"])
EXECUTION_LATENCY = Histogram("agent_platform_execution_duration_seconds","Agent execution duration",["agent","skill"])
TOKENS = Counter("agent_platform_tokens_total","LLM tokens",["agent","skill","type"])
RETRIEVALS = Counter("agent_platform_retrieval_total","Knowledge retrievals",["mode","cache"])
RETRIEVAL_LATENCY = Histogram("agent_platform_retrieval_duration_seconds","Knowledge retrieval duration",["mode"])
RETRIEVAL_CANDIDATES = Histogram("agent_platform_retrieval_candidates","Retrieval candidate counts",["source"])
MEMORY_RECALLS = Counter("agent_platform_memory_recall_total","Memory recalls",["status"])
MEMORY_ITEMS = Histogram("agent_platform_memory_items","Memory items recalled")
TOOL_CALLS = Counter("agent_platform_tool_calls_total","Tool invocations",["tool","provider","status"])
TOOL_LATENCY = Histogram("agent_platform_tool_duration_seconds","Tool invocation duration",["tool","provider"])
CACHE_OPS = Counter("agent_platform_cache_operations_total","Cache operations",["namespace","operation","result"])


_configured=False


def configure_observability(*,service_name:str,enabled:bool,otlp_endpoint:str|None=None)->None:
    global _configured
    if _configured:return
    provider=TracerProvider(resource=Resource.create({"service.name":service_name}))
    trace.set_tracer_provider(provider)
    if enabled and otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint,insecure=True)))
    _configured=True


def tracer(name:str):
    return trace.get_tracer(name)


def trace_id_or_new()->str:
    span=trace.get_current_span()
    context=span.get_span_context()
    if context and context.is_valid:return f"{context.trace_id:032x}"
    return uuid4().hex


@contextmanager
def timed_span(name:str,**attributes):
    started=time.perf_counter()
    with tracer("agent-platform").start_as_current_span(name,attributes={k:v for k,v in attributes.items() if v is not None}) as span:
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.Status(trace.StatusCode.ERROR,str(exc)))
            raise
        finally:
            span.set_attribute("duration_ms",(time.perf_counter()-started)*1000.0)
