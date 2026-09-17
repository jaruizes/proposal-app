from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


app = FastAPI(
    title="Proposal Agent Platform",
    version="0.1.0",
    description="Independent runtime and API for configurable agents, skills and cognitive services.",
)


@app.get("/health", response_model=HealthResponse, tags=["platform"])
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="proposal-agent-platform",
        version=app.version,
    )
