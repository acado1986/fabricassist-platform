from __future__ import annotations

from fastapi.testclient import TestClient

from fabricassist.api.main import create_app
from fabricassist.settings import Settings


class AvailableDatabase:
    closed = False

    async def is_available(self) -> bool:
        return True

    async def close(self) -> None:
        self.closed = True


class UnavailableDatabase(AvailableDatabase):
    async def is_available(self) -> bool:
        return False


def test_liveness_is_independent_of_database() -> None:
    with TestClient(create_app(Settings(environment="test"), UnavailableDatabase())) as client:
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_succeeds_when_database_is_available() -> None:
    with TestClient(create_app(Settings(environment="test"), AvailableDatabase())) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_uses_stable_error_envelope_when_database_is_unavailable() -> None:
    with TestClient(create_app(Settings(environment="test"), UnavailableDatabase())) as client:
        response = client.get("/api/v1/health/ready")

    body = response.json()
    assert response.status_code == 503
    assert body["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
    assert body["error"]["correlation_id"] == response.headers["X-Correlation-ID"]


def test_not_found_uses_stable_error_envelope() -> None:
    with TestClient(create_app(Settings(environment="test"), AvailableDatabase())) as client:
        response = client.get("/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_correlation_id_is_propagated() -> None:
    correlation_id = "6b5f4e09-57ef-4592-ae08-b1a1c889209f"
    with TestClient(create_app(Settings(environment="test"), AvailableDatabase())) as client:
        response = client.get("/api/v1/health/live", headers={"X-Correlation-ID": correlation_id})

    assert response.headers["X-Correlation-ID"] == correlation_id
