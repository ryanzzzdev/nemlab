"""Access-request lifecycle endpoints (NEM-098).

Public ``/api/access/v1/*``: generic submission (never reveals request or
account state), scanner-safe POST verification that opens an applicant
session, applicant-only status and resend. Owner ``/api/admin/v1/*``:
verified-only queue, request detail with delivery state, atomic
approve/reject with optimistic version, grant list/extend/revoke. Every
decision route requires recent authentication (15 minutes) — the UI
re-authenticates and replays the preserved action rather than reusing a
stale session.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from nemlab_api.auth import (
    COOKIE,
    TokenExchange,
    check_mutation,
    require_session,
)
from nemlab_api.errors import ApiError, instant
from nemlab_api.settings import ApiSettings
from nemlab_infrastructure.admin.access import (
    AccessConflict,
    AccessNotFound,
    AccessRequest,
    AccessRequests,
    ViewerGrant,
    validate_fields,
)
from nemlab_infrastructure.admin.auth import (
    AdminAuth,
    InvalidToken,
    csrf_for,
)
from nemlab_infrastructure.admin.rate_limit import RateLimiter

PUBLIC = "/api/access/v1"
ADMIN = "/api/admin/v1"
EXCHANGE_WINDOW_SECONDS = 900
RECENT_AUTH = timedelta(minutes=15)


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    displayName: str
    email: str
    message: str | None = None


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    days: Literal[7, 30, 90] | None = None
    version: int


class Extension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days: Literal[7, 30, 90]


class Revocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = None


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _applicant(request: Request, auth: AdminAuth) -> tuple[str, UUID]:
    """Require an applicant session — owner/viewer sessions do not
    substitute, and an applicant can only ever see their own request."""
    raw, principal = require_session(request, auth)
    if principal.request_id is None:
        raise ApiError(403, "FORBIDDEN", "Applicant session required")
    return raw, principal.request_id


def _recent(request: Request) -> None:
    authenticated = getattr(request.state, "authenticated_at", None)
    if authenticated is None or datetime.now(UTC) - authenticated > RECENT_AUTH:
        raise ApiError(
            403,
            "RECENT_AUTH_REQUIRED",
            "Recent sign-in required — request a fresh sign-in link",
        )


def _request_view(request: AccessRequest) -> dict[str, Any]:
    return {
        "id": str(request.id),
        "name": request.name,
        "email": request.email,
        "message": request.message,
        "status": request.status,
        "submittedAt": instant(request.submitted_at),
        "verifiedAt": instant(request.verified_at) if request.verified_at else None,
        "decidedAt": instant(request.decided_at) if request.decided_at else None,
        "version": request.version,
    }


def _grant_view(grant: ViewerGrant) -> dict[str, Any]:
    now = datetime.now(UTC)
    state = (
        "revoked"
        if grant.revoked_at is not None
        else "active"
        if grant.expires_at > now
        else "expired"
    )
    return {
        "id": str(grant.id),
        "requestId": str(grant.request_id),
        "userId": str(grant.user_id),
        "email": grant.email,
        "state": state,
        "grantedAt": instant(grant.granted_at),
        "expiresAt": instant(grant.expires_at),
        "revokedAt": instant(grant.revoked_at) if grant.revoked_at else None,
    }


def access_router(
    access: AccessRequests,
    auth: AdminAuth,
    limits: RateLimiter,
    settings: ApiSettings,
) -> APIRouter:
    """Anonymous submission/verification plus the applicant-only status
    surface; every response is generic so existence cannot be probed."""
    router = APIRouter()

    @router.post(f"{PUBLIC}/requests", status_code=202)
    def submit(request: Request, body: Submission) -> dict[str, str]:
        validate_fields(body.displayName, body.email, body.message)
        if not limits.hit(
            "access_ip", _ip(request), settings.admin_mail_per_ip_hour, 3600
        ):
            raise ApiError(429, "RATE_LIMITED", "Too many requests — try later")
        email = body.email.lower()
        eligible = (
            limits.hit("access_email", email, settings.admin_mail_per_email_hour, 3600)
            and limits.hit(
                "access_resend", email, 1, settings.admin_resend_cooldown_seconds
            )
            and limits.hit(
                "mail_budget", "global", settings.admin_mail_budget_per_day, 86400
            )
        )
        if eligible:
            access.submit(body.displayName, body.email, body.message)
        return {"status": "accepted"}

    @router.post(f"{PUBLIC}/verifications")
    def verify(request: Request, body: TokenExchange) -> Response:
        try:
            raw, principal = access.verify(body.token)
        except InvalidToken:
            allowed = limits.hit(
                "exchange_fail",
                _ip(request),
                settings.admin_exchange_fail_per_ip,
                EXCHANGE_WINDOW_SECONDS,
            )
            status = 401 if allowed else 429
            code = "INVALID_TOKEN" if allowed else "RATE_LIMITED"
            raise ApiError(
                status, code, "Invalid or expired verification link"
            ) from None
        response = JSONResponse(
            {
                "role": principal.role,
                "name": principal.name,
                "expiresAt": instant(principal.expires_at),
                "csrfToken": csrf_for(raw),
            }
        )
        response.set_cookie(
            COOKIE,
            raw,
            max_age=8 * 3600,
            httponly=True,
            samesite="lax",
            secure=settings.secure_cookies,
            path="/",
        )
        return response

    @router.get(f"{PUBLIC}/requests/status")
    def status(request: Request) -> dict[str, Any]:
        _raw, request_id = _applicant(request, auth)
        found = access.status(request_id)
        if found is None:
            raise ApiError(404, "REQUEST_NOT_FOUND", "Access request not found")
        return {
            "status": found["status"],
            "submittedAt": instant(found["submittedAt"]),
            "verifiedAt": instant(found["verifiedAt"]) if found["verifiedAt"] else None,
            "decidedAt": instant(found["decidedAt"]) if found["decidedAt"] else None,
            "grantExpiresAt": instant(found["grantExpiresAt"])
            if found["grantExpiresAt"]
            else None,
        }

    @router.post(f"{PUBLIC}/requests/resend", status_code=202)
    def resend(request: Request) -> dict[str, str]:
        raw, request_id = _applicant(request, auth)
        check_mutation(request, raw)
        access.resend_own(request_id)
        return {"status": "accepted"}

    return router


def access_admin_router(access: AccessRequests) -> APIRouter:
    """Owner-only access management; the ``access.manage`` capability is
    enforced upstream by ``AdminAccess`` — cookie sessions only, and the
    decision routes additionally require a recent sign-in."""
    router = APIRouter()
    base = f"{ADMIN}/access-requests"
    grants_base = f"{ADMIN}/viewer-grants"

    @router.get(base)
    def queue(state: str = "pending", limit: int = 100) -> list[dict[str, Any]]:
        if state != "pending":
            raise ApiError(400, "INVALID_REQUEST", "Only the pending queue is listed")
        return [_request_view(request) for request in access.queue(limit)]

    @router.get(base + "/{id}")
    def detail(id: UUID) -> dict[str, Any]:
        request = access.find(id)
        if request is None:
            raise ApiError(404, "REQUEST_NOT_FOUND", "Access request not found")
        deliveries = [
            {
                "kind": row["kind"],
                "status": row["status"],
                "attempts": row["attempts"],
                "sentAt": instant(row["sentAt"]) if row["sentAt"] else None,
                "diagnostic": row["diagnostic"],
                "createdAt": instant(row["createdAt"]),
            }
            for row in access.deliveries(id)
        ]
        return {**_request_view(request), "deliveries": deliveries}

    @router.post(base + "/{id}/decisions")
    def decide(request: Request, id: UUID, body: Decision) -> dict[str, Any]:
        _recent(request)
        try:
            decided = access.decide(
                id,
                body.decision,
                body.days,
                body.version,
                request.state.user_id,
            )
        except AccessNotFound:
            raise ApiError(
                404, "REQUEST_NOT_FOUND", "Access request not found"
            ) from None
        except AccessConflict:
            raise ApiError(
                409,
                "ACCESS_CONFLICT",
                "Request already decided or stale version — refresh",
            ) from None
        return _request_view(decided)

    @router.post(base + "/{id}/resend", status_code=202)
    def resend_delivery(request: Request, id: UUID) -> dict[str, str]:
        try:
            access.resend(id, request.state.user_id)
        except AccessNotFound:
            raise ApiError(
                404, "REQUEST_NOT_FOUND", "Access request not found"
            ) from None
        except AccessConflict:
            raise ApiError(
                409, "ACCESS_CONFLICT", "Nothing to resend for this request"
            ) from None
        return {"status": "queued"}

    @router.get(grants_base)
    def grants(
        state: Literal["active", "expired", "revoked"] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return [_grant_view(grant) for grant in access.grants(state, limit)]

    @router.post(grants_base + "/{id}/extend")
    def extend(request: Request, id: UUID, body: Extension) -> dict[str, Any]:
        _recent(request)
        try:
            grant = access.extend(id, body.days, request.state.user_id)
        except AccessNotFound:
            raise ApiError(404, "GRANT_NOT_FOUND", "Viewer grant not found") from None
        except AccessConflict:
            raise ApiError(
                409, "ACCESS_CONFLICT", "Grant already revoked — refresh"
            ) from None
        return _grant_view(grant)

    @router.get(f"{ADMIN}/access-audit")
    def audit(limit: int = 100) -> list[dict[str, Any]]:
        return [
            {**row, "occurredAt": instant(row["occurredAt"])}
            for row in access.audit(limit)
        ]

    @router.post(grants_base + "/{id}/revoke")
    def revoke(request: Request, id: UUID, body: Revocation) -> dict[str, Any]:
        _recent(request)
        try:
            grant = access.revoke(id, request.state.user_id, body.reason)
        except AccessNotFound:
            raise ApiError(404, "GRANT_NOT_FOUND", "Viewer grant not found") from None
        except AccessConflict:
            raise ApiError(
                409, "ACCESS_CONFLICT", "Grant already revoked — refresh"
            ) from None
        return _grant_view(grant)

    return router
