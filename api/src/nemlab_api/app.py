"""FastAPI application factory.

Health matches the Java actuator surface exactly: ``GET /actuator/health``
returns ``{"status": "UP"}`` with no details. Feature routers are mounted only
when their flag is enabled, so disabled routes return a plain 404 just like
the Java filters. The bounded engine is created — and its smoke check run —
only when a database-backed feature is enabled.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import sqlalchemy as sa
from fastapi import FastAPI
from sqlalchemy.engine import Engine

from nemlab_api.access import access_admin_router, access_router
from nemlab_api.admin import admin_router
from nemlab_api.auth import auth_router
from nemlab_api.errors import register_error_handlers
from nemlab_api.events import events_router
from nemlab_api.grid_coverage import grid_coverage_router
from nemlab_api.grid_imports import grid_imports_router, register_grid_errors
from nemlab_api.grid_publications import grid_publications_router
from nemlab_api.load_operations import load_operations_router
from nemlab_api.middleware import (
    AdminAccess,
    RequestLogging,
    SecurityHeaders,
)
from nemlab_api.prices import prices_router
from nemlab_api.settings import ApiSettings
from nemlab_api.simulations import register_simulation_errors, simulations_router
from nemlab_infrastructure.admin.access import AccessRequests
from nemlab_infrastructure.admin.auth import AdminAuth
from nemlab_infrastructure.admin.rate_limit import RateLimiter
from nemlab_infrastructure.database import create_bounded_engine
from nemlab_infrastructure.grid.events import GridCatalogue
from nemlab_infrastructure.grid.imports import GridImportJobs
from nemlab_infrastructure.grid.store import GridStore
from nemlab_infrastructure.jobs import RefreshJobService
from nemlab_infrastructure.load_operations import LoadOperations
from nemlab_infrastructure.prices.store import PriceStore
from nemlab_infrastructure.simulations import SimulationJobs


def _smoke(engine: Engine, simulation: bool) -> None:
    """Same probe as ``ApiDatabaseConfiguration``: fail startup fast when the
    database is unreachable or the migrations have not run."""
    try:
        with engine.connect() as connection:
            connection.execute(sa.text("SELECT count(*) FROM refresh_job WHERE false"))
            connection.execute(
                sa.text("SELECT count(*) FROM price_current WHERE false")
            )
            if simulation:
                connection.execute(
                    sa.text("SELECT count(*) FROM simulation_job WHERE false")
                )
    except sa.exc.SQLAlchemyError as failure:
        raise RuntimeError(
            "API database unavailable or migrations missing (details omitted)"
        ) from failure


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    if settings is None:
        settings = ApiSettings()
    engine: Engine | None = None

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        if engine is not None:
            engine.dispose()

    app = FastAPI(
        title="nemlab-api",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    register_error_handlers(app)

    @app.get("/actuator/health")
    def health() -> dict[str, str]:
        return {"status": "UP"}

    if (
        settings.data_enabled
        or settings.admin_enabled
        or settings.simulation_api_enabled
    ):
        engine = create_bounded_engine(settings)
        _smoke(engine, settings.simulation_api_enabled)
        prices = PriceStore(engine)
        if settings.data_enabled:
            app.include_router(prices_router(prices))
            app.include_router(events_router(GridCatalogue(engine)))
        if settings.simulation_api_enabled:
            register_simulation_errors(app)
            app.include_router(
                simulations_router(
                    SimulationJobs(engine), RefreshJobService(engine, prices)
                )
            )
        if settings.admin_enabled:
            admin_auth = AdminAuth(engine, base_url=settings.admin_base_url)
            rate_limits = RateLimiter(engine)
            app.add_middleware(
                AdminAccess,
                operator=settings.admin_operator,
                token=settings.admin_token,
                auth=admin_auth,
            )
            app.include_router(
                auth_router(admin_auth, rate_limits, settings)
            )
            access = AccessRequests(engine, admin_auth)
            app.include_router(
                access_router(access, admin_auth, rate_limits, settings)
            )
            app.include_router(access_admin_router(access))
            app.include_router(admin_router(RefreshJobService(engine, prices)))
            register_grid_errors(app)
            grid = GridStore(engine)
            app.include_router(grid_imports_router(GridImportJobs(engine, grid)))
            catalogue = GridCatalogue(engine)
            app.include_router(grid_coverage_router(grid, catalogue))
            app.include_router(grid_publications_router(catalogue))
            app.include_router(
                load_operations_router(
                    LoadOperations(
                        engine,
                        GridImportJobs(engine, grid),
                        RefreshJobService(engine, prices),
                    )
                )
            )

    app.add_middleware(RequestLogging)
    app.add_middleware(SecurityHeaders)
    return app
