from functools import lru_cache
from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    model_config=SettingsConfigDict(env_file=".env",extra="ignore")
    database_url:str="postgresql+asyncpg://agent_platform:agent_platform@localhost:5433/agent_platform"
    anthropic_api_key:str|None=None;anthropic_base_url:str|None=None;anthropic_default_model:str="claude-sonnet-4-6";anthropic_timeout_seconds:float=120.0;anthropic_default_max_output_tokens:int=4096
    embedding_provider:str="hash";embedding_model:str="hash-embedding-v1";embedding_dimensions:int=384
    cache_backend:str="memory";cache_url:str="redis://localhost:6379/0";cache_prefix:str="agent-platform";embedding_cache_ttl_seconds:int=86400;retrieval_cache_ttl_seconds:int=900;cognitive_cache_ttl_seconds:int=900
    observability_enabled:bool=False;otel_service_name:str="proposal-agent-platform";otel_exporter_otlp_endpoint:str="http://localhost:4317"
    google_workspace_mcp_enabled:bool=True;google_workspace_mcp_command:str="node";google_workspace_mcp_script:str="/opt/mcp/google-workspace/dist/server.js";google_workspace_mcp_cwd:str="/opt/mcp/google-workspace";google_workspace_mcp_timeout_seconds:float=30.0;google_oauth_credentials:str|None=None;google_oauth_token:str|None=None

@lru_cache
def get_settings()->Settings:return Settings()
