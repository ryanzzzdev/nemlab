"""Browser authentication — ``/api/auth/v1/*`` (NEM-096).

Sign-in links are minted only for enabled, grant-active accounts but every
response is the same generic acceptance, so the endpoint cannot enumerate
accounts. The emailed raw token travels in a URL fragment and is exchanged
here by POST — scanners prefetching the link never consume it. Sessions
are opaque cookies; cookie-authenticated mutations additionally require
the derived CSRF header and a same-origin ``Origin``/``Referer``.
"""

import re
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from nemlab_api.errors import ApiError, instant
from nemlab_api.settings import ApiSettings
from nemlab_infrastructure.admin.auth import (
    AdminAuth,
    InvalidToken,
    Principal,
    csrf_for,
    csrf_matches,
)
from nemlab_infrastructure.admin.rate_limit import RateLimiter

BASE = "/api/auth/v1"
COOKIE = "nemlab_session"
CSRF_HEADER = "x-csrf-token"

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+")
EXCHANGE_WINDOW_SECONDS = 900


class SignInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str


class TokenExchange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str


def _check_email(value: str) -> None:
    if len(value) > 254 or _EMAIL.fullmatch(value) is None:
        raise ValueError("invalid email")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _bearer_present(request: Request) -> bool:
    header = request.headers.get("authorization")
    return header is not None and header.lower().startswith("bearer ")


def session_of(request: Request, auth: AdminAuth) -> tuple[str, Principal] | None:
    """Resolve the session cookie; a request carrying both the cookie and
    a bearer token is rejected deterministically (never silently mixed)."""
    raw = request.cookies.get(COOKIE)
    if raw is None:
        return None
    if _bearer_present(request):
        raise ApiError(401, "UNAUTHORISED", "Conflicting cookie and bearer credentials")
    principal = auth.resolve(raw)
    return (raw, principal) if principal is not None else None


def require_session(request: Request, auth: AdminAuth) -> tuple[str, Principal]:
    found = session_of(request, auth)
    if found is None:
        raise ApiError(401, "UNAUTHORISED", "Sign in required")
    return found


def mutation_denied(request: Request, raw_session: str) -> str | None:
    """CSRF + origin guard for cookie-authenticated state changes; returns
    the denial reason or ``None``. Shared with the admin-access middleware
    (NEM-097), which returns its own responses instead of raising."""
    presented = request.headers.get(CSRF_HEADER)
    if presented is None or not csrf_matches(raw_session, presented):
        return "CSRF token missing or invalid"
    source = request.headers.get("origin") or request.headers.get("referer")
    if source is None:
        return "Origin header required"
    if urlsplit(source).netloc != request.headers.get("host", ""):
        return "Origin does not match this server"
    return None


def check_mutation(request: Request, raw_session: str) -> None:
    denied = mutation_denied(request, raw_session)
    if denied is not None:
        raise ApiError(403, "FORBIDDEN", denied)


def _session_body(principal: Principal, raw_session: str) -> dict[str, Any]:
    return {
        "role": principal.role,
        "name": principal.name,
        "expiresAt": instant(principal.expires_at),
        "csrfToken": csrf_for(raw_session),
    }


def auth_router(
    auth: AdminAuth, limits: RateLimiter, settings: ApiSettings
) -> APIRouter:
    router = APIRouter()

    @router.post(f"{BASE}/sign-in-requests", status_code=202)
    def sign_in_request(request: Request, body: SignInRequest) -> dict[str, str]:
        _check_email(body.email)
        ip = _client_ip(request)
        if not limits.hit("sign_in_ip", ip, settings.admin_mail_per_ip_hour, 3600):
            raise ApiError(429, "RATE_LIMITED", "Too many requests — try later")
        email = body.email.lower()
        eligible = (
            limits.hit("sign_in_email", email, settings.admin_mail_per_email_hour, 3600)
            and limits.hit(
                "sign_in_resend",
                email,
                1,
                settings.admin_resend_cooldown_seconds,
            )
            and limits.hit(
                "mail_budget", "global", settings.admin_mail_budget_per_day, 86400
            )
        )
        if eligible:
            auth.request_sign_in(body.email)
        return {"status": "accepted"}

    @router.post(f"{BASE}/sessions")
    def exchange(request: Request, body: TokenExchange) -> Response:
        ip = _client_ip(request)
        try:
            raw, principal = auth.exchange(body.token)
        except InvalidToken:
            allowed = limits.hit(
                "exchange_fail",
                ip,
                settings.admin_exchange_fail_per_ip,
                EXCHANGE_WINDOW_SECONDS,
            )
            status = 401 if allowed else 429
            code = "INVALID_TOKEN" if allowed else "RATE_LIMITED"
            raise ApiError(status, code, "Invalid or expired sign-in link") from None
        response = JSONResponse(_session_body(principal, raw))
        response.set_cookie(
            COOKIE,
            raw,
            max_age=72 * 3600,
            httponly=True,
            samesite="lax",
            secure=settings.secure_cookies,
            path="/",
        )
        return response

    @router.get(f"{BASE}/session")
    def current(request: Request) -> dict[str, Any]:
        raw, principal = require_session(request, auth)
        return _session_body(principal, raw)

    @router.post(f"{BASE}/logout")
    def logout(request: Request) -> Response:
        raw, _principal = require_session(request, auth)
        check_mutation(request, raw)
        auth.logout(raw)
        response = Response(status_code=204)
        response.delete_cookie(COOKIE, path="/")
        return response

    return router
