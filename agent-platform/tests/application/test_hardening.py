from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_platform.application.hardening import HardeningMiddleware
from agent_platform.config import Settings


def app_for(**kwargs):
    app=FastAPI()
    settings=Settings(rate_limit_enabled=False,**kwargs)
    app.add_middleware(HardeningMiddleware,settings=settings)
    @app.get("/v1/private")
    async def private():return{"ok":True}
    @app.get("/health")
    async def health():return{"status":"ok"}
    return TestClient(app)


def test_api_key_is_optional_by_default():
    client=app_for()
    assert client.get("/v1/private").status_code==200


def test_api_key_can_protect_v1_surface():
    client=app_for(api_key_enabled=True,api_key="secret")
    assert client.get("/v1/private").status_code==401
    assert client.get("/v1/private",headers={"X-API-Key":"secret"}).status_code==200
    assert client.get("/health").status_code==200


def test_security_headers_are_added():
    client=app_for()
    response=client.get("/v1/private")
    assert response.headers["x-content-type-options"]=="nosniff"
    assert response.headers["x-frame-options"]=="DENY"
    assert response.headers["x-request-id"]
