from pydantic import BaseModel
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from flock.core.api.main import FlockAPI
from flock.core.api.custom_endpoint import FlockEndpoint
from flock.core.flock import Flock


pytestmark = pytest.mark.integration


class Q(BaseModel):
    x: int


class B(BaseModel):
    y: str


def test_webapi_post_with_models():
    app = FastAPI()
    flock = Flock(name="api-post", show_flock_banner=False)

    def handle(flock: Flock, query: Q, body: B):
        return {"name": flock.name, "sum": query.x + len(body.y)}

    ep = FlockEndpoint(path="/calc", methods=["POST"], callback=handle, request_model=B, query_model=Q)
    api = FlockAPI(flock_instance=flock, custom_endpoints=[ep])
    api.add_custom_routes_to_app(app)

    client = TestClient(app)
    resp = client.post("/calc?x=3", json={"y": "abcd"})
    assert resp.status_code == 200
    assert resp.json() == {"name": "api-post", "sum": 3 + 4}

