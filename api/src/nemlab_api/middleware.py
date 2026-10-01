"""HTTP middleware ported from the Spring filter chain.

``SecurityHeaders`` mirrors the headers Spring Security writes on every
response (its cache-defeating trio only when the endpoint did not set
``Cache-Control`` itself, matching the observed captures). ``RequestLogging``
is the one-line ``method target -> status (Nms)`` filter — never headers or
bodies. ``OperatorBearer`` is the opaque-token check for ``/api/admin/**``:
SHA-256 digests compared in constant time, actor derived server-side.
"""

import hashlib
import hmac
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from nemlab_api.errors import unauthorised_response

LOG = logging.getLogger("nemlab_api.requests")

CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, max-age=0, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "0",
}


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if "cache-control" not in response.headers:
            for name, value in CACHE_HEADERS.items():
                response.headers.setdefault(name, value)
        return response


class RequestLogging(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        started = time.monotonic_ns()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            target = request.url.path
            if request.url.query:
                target += "?" + request.url.query
            LOG.info(
                "%s %s -> %s (%d ms)",
                request.method,
                target,
                response.status_code if response is not None else 500,
                (time.monotonic_ns() - started) // 1_000_000,
            )


class OperatorBearer(BaseHTTPMiddleware):
    """``/api/admin/**`` requires the configured operator bearer token."""

    def __init__(self, app: ASGIApp, operator: str, token: str) -> None:
        super().__init__(app)
        self._expected = hashlib.sha256(token.encode()).digest()
        self._actor = f"operator:{operator}"

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        if path == "/api/admin" or path.startswith("/api/admin/"):
            supplied = _bearer_token(request)
            if (
                supplied is None
                or len(supplied) > 128
                or not hmac.compare_digest(
                    self._expected, hashlib.sha256(supplied.encode()).digest()
                )
            ):
                return unauthorised_response()
            request.state.actor = self._actor
        return await call_next(request)


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if header is None:
        return None
    scheme, _, credentials = header.partition(" ")
    if scheme.lower() != "bearer" or not credentials:
        return None
    return credentials
