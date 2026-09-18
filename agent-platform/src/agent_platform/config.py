from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings,SettingsConfigDict


class Settings(BaseSettings):
    model_config=SettingsConfigDict(env_file=".env",extra="ignore")
    database_url:str="postgresql+asyncpg://agent_platform:agent_platform@localhost:5433/agent_platform"
    anthropic_api_key:str|None=None
    anthropic_base_url:str|None=None
    anthropic_default_model:str="claude-sonnet-4-6"
    anthropic_timeout_seconds:float=120.0
    anthropic_default_max_output_tokens:int=4096
    anthropic_max_retries:int=2
    anthropic_retry_base_seconds:float=0.5
    embedding_provider:str="hash";embedding_model:str="hash-embedding-v1";embedding_dimensions:int=384
    cache_backend:str="memory";cache_url:str="redis://localhost:6379/0";cache_prefix:str="agent-platform";embedding_cache_ttl_seconds:int=86400;retrieval_cache_ttl_seconds:int=900;cognitive_cache_ttl_seconds:int=900
    observability_enabled:bool=False;otel_service_name:str="proposal-agent-platform";otel_exporter_otlp_endpoint:str="http://localhost:4317"
    api_key_enabled:bool=False
    api_key:str|None=None
    protect_metrics:bool=False
    max_request_body_bytes:int=Field(default=30*1024*1024,ge=1024)
    rate_limit_enabled:bool=True
    rate_limit_requests_per_minute:int=Field(default=240,ge=1)
    database_pool_size:int=Field(default=10,ge=1,le=100)
    database_max_overflow:int=Field(default=20,ge=0,le=200)
    database_pool_recycle_seconds:int=Field(default=1800,ge=60)
    google_workspace_mcp_enabled:bool=True;google_workspace_mcp_command:str="node";google_workspace_mcp_script:str="/opt/mcp/google-workspace/dist/server.js";google_workspace_mcp_cwd:str="/opt/mcp/google-workspace";google_workspace_mcp_timeout_seconds:float=30.0;google_oauth_credentials:str|None=None;google_oauth_token:str|None=None


@lru_cache
def get_settings()->Settings:return Settings()
