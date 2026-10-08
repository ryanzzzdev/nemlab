"""HTTP middleware ported from the Spring filter chain.

``SecurityHeaders`` mirrors the headers Spring Security writes on every
response (its cache-defeating trio only when the endpoint did not set
``Cache-Control`` itself, matching the observed captures). ``RequestLogging``
is the one-line ``method target -> status (Nms)`` filter — never headers or
bodies. ``AdminAccess`` is the identity + capability check for
``/api/admin/**``: a browser session cookie or the operator bearer (SHA-256
digests compared in constant time, actor derived server-side) mapped onto
the deny-by-default capability table.
"""

import hashlib
import hmac
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from nemlab_api import capabilities
from nemlab_api.auth import COOKIE, mutation_denied
from nemlab_api.errors import envelope, unauthorised_response
from nemlab_infrastructure.admin.auth import AdminAuth

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
            # Authentication material must never reach the request log —
            # auth-family query strings are dropped outright (NEM-096).
            if request.url.query and not target.startswith("/api/auth/"):
                target += "?" + request.url.query
            LOG.info(
                "%s %s -> %s (%d ms)",
                request.method,
                target,
                response.status_code if response is not None else 500,
                (time.monotonic_ns() - started) // 1_000_000,
            )


class AdminAccess(BaseHTTPMiddleware):
    """Identity + capability check for ``/api/admin/**`` (NEM-097).

    Resolves exactly one credential — browser session cookie or operator
    bearer, never both — then enforces the deny-by-default capability
    table: unregistered routes answer a bare 404 like the denyAll chain,
    registered routes without a grant answer ``403 FORBIDDEN``. Cookie
    sessions on mutating methods additionally pass the same CSRF + Origin
    guard as the auth router. The resolved ``request.state`` carries
    ``actor`` (label-safe ``role:id`` for sessions, ``operator:<name>``
    for automation) and ``viewer`` so routes can pick safe projections.
    """

    _SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    def __init__(
        self,
        app: ASGIApp,
        *,
        operator: str,
        token: str,
        auth: AdminAuth,
    ) -> None:
        super().__init__(app)
        self._expected = hashlib.sha256(token.encode()).digest()
        self._actor = f"operator:{operator}"
        self._auth = auth

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        if not (path == "/api/admin" or path.startswith("/api/admin/")):
            return await call_next(request)

        cookie = request.cookies.get(COOKIE)
        bearer = _bearer_token(request)
        if cookie is not None and bearer is not None:
            return unauthorised_response()

        principal = None
        if cookie is not None:
            principal = self._auth.resolve(cookie)
            if principal is None:
                return unauthorised_response()
            actor = f"{principal.role}:{principal.user_id}"
            role = principal.role
        elif bearer is not None:
            if len(bearer) > 128 or not hmac.compare_digest(
                self._expected, hashlib.sha256(bearer.encode()).digest()
            ):
                return unauthorised_response()
            actor, role = self._actor, "automation"
        else:
            return unauthorised_response()

        required = capabilities.capability_for(request.method, path)
        if required is None:
            return Response(status_code=404)
        if not capabilities.granted(role, required):
            return envelope("FORBIDDEN", "Insufficient capability", 403)
        if cookie is not None and request.method not in self._SAFE_METHODS:
            denied = mutation_denied(request, cookie)
            if denied is not None:
                return envelope("FORBIDDEN", denied, 403)

        request.state.actor = actor
        request.state.viewer = role == "viewer"
        request.state.user_id = principal.user_id if principal else None
        request.state.authenticated_at = (
            principal.authenticated_at if principal else None
        )
        return await call_next(request)


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if header is None:
        return None
    scheme, _, credentials = header.partition(" ")
    if scheme.lower() != "bearer" or not credentials:
        return None
    return credentials
