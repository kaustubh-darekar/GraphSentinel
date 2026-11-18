"""Smoke test: the package and API import and answer."""

from fastapi.testclient import TestClient

from graphsentinel.api.main import app


def test_health() -> None:
    assert TestClient(app).get("/api/health").json() == {"status": "ok"}
