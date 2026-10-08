"""Error envelopes matching the Java ``*Errors`` controller advice.

Body shape is ``{"code": "...", "message": "..."}``; framework-level
unmatched/denied requests keep an empty 404 like the denyAll filter chain.
"""

import re
from datetime import UTC, datetime

import sqlalchemy as sa
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException

from nemlab_infrastructure.jobs import QueueFull, RequestKeyConflict

INVALID_PRICE_REQUEST = (
    "Use a valid region and 1\u201331 completed market days since 2021-10-01"
)
INVALID_ADMIN_REQUEST = "Check the request fields, completed market day and identifiers"
STORAGE_PRICE = "Price storage is unavailable"
STORAGE_ADMIN = "Refresh storage is temporarily unavailable"

_ADMIN_PATH = re.compile(r"^/api/(?:admin|auth|access)(?:/|$)")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message


class Unauthorised(Exception):
    pass


def unauthorised_response() -> Response:
    return Response(
        content=b'{"code":"UNAUTHORISED"}',
        status_code=401,
        headers={
            "Content-Type": "application/json;charset=ISO-8859-1",
            "WWW-Authenticate": "Bearer",
        },
    )


def instant(value: datetime) -> str:
    """``Instant`` serialization: UTC, ``Z`` suffix, microseconds only when
    nonzero — matching Jackson's output byte-for-byte."""
    text = value.astimezone(UTC).isoformat()
    return text[:-6] + "Z" if text.endswith("+00:00") else text


def envelope(code: str, message: str, status: int, **headers: str) -> Response:
    return JSONResponse(
        {"code": code, "message": message}, status_code=status, headers=headers
    )


def _is_admin(request: Request) -> bool:
    return _ADMIN_PATH.match(request.url.path) is not None


_SIMULATION_PATH = re.compile(r"^/api/v1/simulations(?:/|$)")


def is_simulation_path(request: Request) -> bool:
    return _SIMULATION_PATH.match(request.url.path) is not None


def simulation_error(
    status: int,
    code: str,
    message: str,
    field: str,
    reason: str,
    **headers: str,
) -> Response:
    """The four-field ``SimulationError`` envelope — distinct from the
    price/admin two-field shape."""
    return JSONResponse(
        {"code": code, "message": message, "field": field, "reason": reason},
        status_code=status,
        headers={"Cache-Control": "no-store", **headers},
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(Unauthorised)
    async def _unauthorised(_request: Request, _error: Unauthorised) -> Response:
        return unauthorised_response()

    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, error: ApiError) -> Response:
        headers = {"Retry-After": "30"} if error.code == "QUEUE_FULL" else None
        return envelope(error.code, error.message, error.status, **(headers or {}))

    @app.exception_handler(RequestKeyConflict)
    async def _conflict(_request: Request, _error: RequestKeyConflict) -> Response:
        return envelope(
            "IDEMPOTENCY_CONFLICT",
            "Request key belongs to a different price day",
            409,
        )

    @app.exception_handler(QueueFull)
    async def _full(request: Request, _error: QueueFull) -> Response:
        if is_simulation_path(request):
            return simulation_error(
                429,
                "QUEUE_FULL",
                "Wait for pending simulations to finish",
                "request",
                "QUEUE_FULL",
                **{"Retry-After": "5"},
            )
        return envelope(
            "QUEUE_FULL",
            "Wait for existing refresh jobs to finish",
            429,
            **{"Retry-After": "30"},
        )

    @app.exception_handler(RequestValidationError)
    async def _invalid_request(
        request: Request, error: RequestValidationError
    ) -> Response:
        if not _is_admin(request):
            return envelope("INVALID_REQUEST", INVALID_PRICE_REQUEST, 400)
        message = INVALID_ADMIN_REQUEST
        missing = [e for e in error.errors() if e.get("type") == "missing"]
        if missing:
            where, name, *_ = missing[0].get("loc", ())
            message += f" Missing {where} {name!r}."
        return envelope("INVALID_REQUEST", message, 400)

    @app.exception_handler(ValueError)
    async def _invalid_value(request: Request, _error: ValueError) -> Response:
        message = INVALID_ADMIN_REQUEST if _is_admin(request) else INVALID_PRICE_REQUEST
        return envelope("INVALID_REQUEST", message, 400)

    @app.exception_handler(sa.exc.SQLAlchemyError)
    async def _storage(request: Request, _error: sa.exc.SQLAlchemyError) -> Response:
        if is_simulation_path(request):
            return simulation_error(
                503,
                "STORAGE_UNAVAILABLE",
                "Simulation storage is unavailable",
                "request",
                "STORAGE_UNAVAILABLE",
            )
        return envelope(
            "STORAGE_UNAVAILABLE",
            STORAGE_ADMIN if _is_admin(request) else STORAGE_PRICE,
            503,
        )

    @app.exception_handler(HTTPException)
    async def _http(_request: Request, error: HTTPException) -> Response:
        # denyAll/disabled endpoints surface as a bare 404 — including
        # wrong-method requests that FastAPI would otherwise report as 405.
        if error.status_code in (404, 405):
            return Response(status_code=404)
        return Response(status_code=error.status_code, headers=error.headers)
