from __future__ import annotations

from types import SimpleNamespace

import pytest

from flock.storage.dapr._client import create_dapr_client


class _FakeDaprClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def test_create_dapr_client_passes_expected_arguments(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _factory(**kwargs):
        captured.update(kwargs)
        return _FakeDaprClient(**kwargs)

    monkeypatch.setattr("flock.storage.dapr._client.DaprClient", _factory)
    header_callback = lambda: {"x": "1"}
    config = SimpleNamespace(
        dapr_grpc_endpoint="localhost:50001",
        header_callback=header_callback,
        interceptors=["i1"],
        http_timeout_seconds=10,
        max_grpc_message_length=1024,
        retry_policy="retry",
    )

    client = create_dapr_client(config)

    assert isinstance(client, _FakeDaprClient)
    assert captured == {
        "address": "localhost:50001",
        "headers_callback": header_callback,
        "interceptors": ["i1"],
        "http_timeout_seconds": 10,
        "max_grpc_message_length": 1024,
        "retry_policy": "retry",
    }


def test_create_dapr_client_requires_header_callback_attribute(monkeypatch) -> None:
    monkeypatch.setattr("flock.storage.dapr._client.DaprClient", _FakeDaprClient)
    config = SimpleNamespace(
        dapr_grpc_endpoint="localhost:50001",
        headers_callback=lambda: {"x": "1"},
        interceptors=None,
        http_timeout_seconds=None,
        max_grpc_message_length=None,
        retry_policy=None,
    )

    with pytest.raises(AttributeError):
        create_dapr_client(config)
