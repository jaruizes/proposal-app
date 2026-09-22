from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    model_config=SettingsConfigDict(env_file=".env",extra="ignore")
    database_url:str="postgresql+asyncpg://agent_platform:agent_platform@localhost:5433/agent_platform"
    agent_runtime:str="langgraph"
    langgraph_checkpoint_database_url:str="postgresql://agent_platform:agent_platform@localhost:5433/agent_platform"
    nats_enabled:bool=True
    nats_url:str="nats://localhost:4222"
    nats_commands_stream:str="AGENT_PLATFORM_COMMANDS"
    nats_events_stream:str="AGENT_PLATFORM_EVENTS"
    nats_command_subject:str="agent-platform.commands.execution.requested"
    nats_events_subject:str="agent-platform.events.execution.*"
    nats_command_durable:str="agent-platform-execution-worker"
    anthropic_api_key:str|None=None;anthropic_base_url:str|None=None;anthropic_default_model:str="claude-sonnet-4-6"
    anthropic_timeout_seconds:float=300.0;anthropic_default_max_output_tokens:int=4096;anthropic_max_retries:int=0;anthropic_retry_base_seconds:float=0.5
    embedding_provider:str="hash";embedding_model:str="hash-embedding-v1";embedding_dimensions:int=384
    cache_backend:str="memory";cache_url:str="redis://localhost:6379/0";cache_prefix:str="agent-platform";embedding_cache_ttl_seconds:int=86400;retrieval_cache_ttl_seconds:int=900;cognitive_cache_ttl_seconds:int=900;proposal_checkpoint_ttl_seconds:int=604800
    proposal_input_token_budget:int=250000;proposal_output_token_budget:int=30000;proposal_cost_budget_usd:float=2.0;proposal_hard_cost_limit_usd:float=5.0
    anthropic_input_cost_per_million_usd:float=3.0;anthropic_output_cost_per_million_usd:float=15.0;anthropic_cache_read_cost_per_million_usd:float=0.30;anthropic_cache_write_cost_per_million_usd:float=3.75
    observability_enabled:bool=False;otel_service_name:str="proposal-agent-platform";otel_exporter_otlp_endpoint:str="http://localhost:4317"
    api_key_enabled:bool=False;api_key:str|None=None;protect_metrics:bool=False
    max_request_body_bytes:int=Field(default=30*1024*1024,ge=1024);rate_limit_enabled:bool=True;rate_limit_requests_per_minute:int=Field(default=240,ge=1)
    database_pool_size:int=Field(default=10,ge=1,le=100);database_max_overflow:int=Field(default=20,ge=0,le=200);database_pool_recycle_seconds:int=Field(default=1800,ge=60)
    google_workspace_mcp_enabled:bool=True;google_workspace_mcp_command:str="node";google_workspace_mcp_script:str="/opt/mcp/google-workspace/dist/server.js";google_workspace_mcp_cwd:str="/opt/mcp/google-workspace";google_workspace_mcp_timeout_seconds:float=30.0;google_workspace_mcp_max_message_bytes:int=Field(default=16*1024*1024,ge=64*1024);google_oauth_credentials:str|None=None;google_oauth_token:str|None=None

@lru_cache
def get_settings()->Settings:return Settings()
