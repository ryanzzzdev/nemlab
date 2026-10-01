"""FastAPI application factory.

Health matches the Java actuator surface exactly: ``GET /actuator/health``
returns ``{"status": "UP"}`` with no details. Feature routers are mounted only
when their flag is enabled, so disabled routes return a plain 404 just like
the Java filters.
"""

from fastapi import FastAPI

from nemlab_api.settings import ApiSettings


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    if settings is None:
        settings = ApiSettings()
    app = FastAPI(title="nemlab-api", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/actuator/health")
    def health() -> dict[str, str]:
        return {"status": "UP"}

    # Feature routers land in NEM-074/NEM-077; while their flags are off or
    # routes are unimplemented, requests hit FastAPI's default 404 — matching
    # the Java behaviour for disabled endpoints.
    return app
