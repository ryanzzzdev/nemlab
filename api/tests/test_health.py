from fastapi.testclient import TestClient

from nemlab_api.app import create_app
from nemlab_api.settings import ApiSettings


def test_health_matches_actuator_shape() -> None:
    client = TestClient(create_app(ApiSettings()))
    response = client.get("/actuator/health")
    assert response.status_code == 200
    assert response.json() == {"status": "UP"}


def test_disabled_features_return_404() -> None:
    client = TestClient(create_app(ApiSettings()))
    for path in (
        "/api/v1/prices/NSW1/2026-09-11",
        "/api/v1/prices/NSW1/coverage",
        "/api/v1/simulations",
        "/api/admin/v1/price-refreshes",
    ):
        assert client.get(path).status_code == 404, path
        assert client.post(path).status_code == 404, path
