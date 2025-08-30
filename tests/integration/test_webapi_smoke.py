import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from flock.core.api.main import FlockAPI
from flock.core.flock import Flock


pytestmark = pytest.mark.integration


def test_webapi_custom_endpoint_smoke():
    app = FastAPI()
    flock = Flock(name="api-smoke", show_flock_banner=False)

    def hello(flock: Flock):
        return {"name": flock.name}

    api = FlockAPI(flock_instance=flock, custom_endpoints=[])
    # Manually add single endpoint via convenience wrapper
    api.processed_custom_endpoints = []
    from flock.core.api.custom_endpoint import FlockEndpoint

    api.processed_custom_endpoints.append(FlockEndpoint(path="/hello", methods=["GET"], callback=hello))
    api.add_custom_routes_to_app(app)

    client = TestClient(app)
    r = client.get("/hello")
    assert r.status_code == 200
    assert r.json() == {"name": "api-smoke"}

