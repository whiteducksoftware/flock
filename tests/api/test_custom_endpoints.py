import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from flock.core import Flock
from flock.core.api.custom_endpoint import FlockEndpoint
from flock.core.api.main import FlockAPI


class EchoRequest(BaseModel):
    text: str


async def echo_endpoint(body: EchoRequest):  # type: ignore[valid-type]
    """Simple echo used for tests."""
    return {"echo": body.text}


@pytest.fixture()
def api_client() -> TestClient:
    """Returns a TestClient with a single custom endpoint mounted."""
    flock = Flock(show_flock_banner=False)

    ep = FlockEndpoint(
        path="/api/echo",
        methods=["POST"],
        callback=echo_endpoint,
        request_model=EchoRequest,
        summary="Echo endpoint (test-only)",
    )

    api = FlockAPI(flock, custom_endpoints=[ep])
    return TestClient(api.app)


def test_custom_endpoint_in_openapi(api_client: TestClient):
    openapi = api_client.get("/openapi.json").json()
    assert "/api/echo" in openapi["paths"], "Custom endpoint missing from OpenAPI schema"


def test_custom_endpoint_success(api_client: TestClient):
    resp = api_client.post("/api/echo", json={"text": "hi"})
    assert resp.status_code == 200
    assert resp.json() == {"echo": "hi"}


def test_custom_endpoint_validation_error(api_client: TestClient):
    # Missing required field 'text'
    resp = api_client.post("/api/echo", json={})
    assert resp.status_code == 422 