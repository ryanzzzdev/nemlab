"""NEM-098 access-request lifecycle — submission, verification, atomic
decisions, grant mutations and retention cleanup over the V8 schema."""

import uuid
from uuid import UUID

import pytest
import sqlalchemy as sa
from db_fixture import apply_admin_schema

from nemlab_infrastructure.admin.access import (
    AccessConflict,
    AccessNotFound,
    AccessRequests,
    validate_fields,
)
from nemlab_infrastructure.admin.auth import AdminAuth, InvalidToken
from nemlab_infrastructure.admin.identity import AdminIdentity

BASE_URL = "http://localhost:8080/admin"
OWNER_EMAIL = "owner@example.test"
APPLICANT = "applicant@example.test"


@pytest.fixture
def access(scratch_db: sa.Engine) -> AccessRequests:
    apply_admin_schema(scratch_db)
    return AccessRequests(scratch_db, AdminAuth(scratch_db, base_url=BASE_URL))


@pytest.fixture(autouse=True)
def owner_id(scratch_db: sa.Engine, access: AccessRequests) -> UUID:
    return AdminIdentity(scratch_db).bootstrap_owner("Owner", OWNER_EMAIL)[0].id


def _scalar(engine: sa.Engine, sql: str, **params: object) -> object:
    with engine.connect() as conn:
        return conn.execute(sa.text(sql), params).scalar_one()


def _rows(engine: sa.Engine, sql: str, **params: object) -> list[tuple]:
    with engine.connect() as conn:
        return [tuple(row) for row in conn.execute(sa.text(sql), params)]


def _pending(
    access: AccessRequests, email: str = APPLICANT, *, submit: bool = True
) -> UUID:
    if submit:
        access.submit("Applicant", email, None)
    body = _scalar(
        access.engine,
        "SELECT body FROM admin_email_outbox ORDER BY created_at DESC LIMIT 1",
    )
    raw = str(body).split("#token=")[1].split("\n")[0]
    _raw_session, principal = access.verify(raw)
    assert principal.role == "applicant"
    assert principal.request_id is not None
    return principal.request_id


def test_field_validation() -> None:
    validate_fields("Name", "a@b.test", None)
    for args in (
        ("", "a@b.test", None),
        (" ", "a@b.test", None),
        ("x" * 101, "a@b.test", None),
        ("Name", "no-at", None),
        ("Name", "x" * 250 + "@b.test", None),
        ("Name", "a@b.test", "m" * 1001),
    ):
        with pytest.raises(ValueError):
            validate_fields(*args)


def test_submit_verify_and_duplicate_rules(access: AccessRequests) -> None:
    access.submit("Applicant", APPLICANT, "hello")
    # Duplicate while unverified resends the verification mail — no new row.
    access.submit("Applicant", APPLICANT, "hello")
    access.submit("Other", APPLICANT.upper(), "different")
    assert _scalar(access.engine, "SELECT count(*) FROM admin_access_request") == 1
    assert (
        _scalar(
            access.engine,
            "SELECT count(*) FROM admin_email_outbox"
            " WHERE kind = 'request_verification'",
        )
        == 3
    )
    request_id = _pending(access, submit=False)
    status = access.status(request_id)
    assert status is not None and status["status"] == "pending"
    # Duplicate while pending is a silent no-op — no mail, no new row.
    access.submit("Applicant", APPLICANT, "hello")
    assert _scalar(access.engine, "SELECT count(*) FROM admin_access_request") == 1
    assert (
        _scalar(
            access.engine,
            "SELECT count(*) FROM admin_email_outbox"
            " WHERE kind = 'request_verification'",
        )
        == 3
    )


def test_verify_rejects_bad_and_replayed_tokens(access: AccessRequests) -> None:
    access.submit("Applicant", APPLICANT, None)
    for raw in ("", "bogus"):
        with pytest.raises(InvalidToken):
            access.verify(raw)
    body = _scalar(access.engine, "SELECT body FROM admin_email_outbox LIMIT 1")
    raw = str(body).split("#token=")[1].split("\n")[0]
    access.verify(raw)
    with pytest.raises(InvalidToken):
        access.verify(raw)


def test_approve_creates_user_grant_and_invite(
    access: AccessRequests, owner_id: UUID
) -> None:
    request_id = _pending(access)
    decided = access.decide(request_id, "approve", 30, 1, owner_id)
    assert decided.status == "approved" and decided.version == 2
    user_id = _scalar(
        access.engine,
        "SELECT id FROM admin_user WHERE lower(email) = lower(:e)",
        e=APPLICANT,
    )
    assert user_id is not None
    assert (
        _scalar(
            access.engine,
            "SELECT count(*) FROM admin_viewer_grant WHERE user_id = :u"
            " AND request_id = :r AND revoked_at IS NULL",
            u=user_id,
            r=request_id,
        )
        == 1
    )
    assert (
        _scalar(
            access.engine, "SELECT count(*) FROM admin_token WHERE purpose = 'sign_in'"
        )
        == 1
    )
    # Invite mail carries the request-linked dedupe key for delivery views.
    deliveries = access.deliveries(request_id)
    kinds = {row["kind"] for row in deliveries}
    assert kinds == {"request_verification", "sign_in"}
    actions = {
        row[0] for row in _rows(access.engine, "SELECT action FROM admin_access_audit")
    }
    assert {"REQUEST_VERIFIED", "REQUEST_APPROVED", "GRANT_CREATED"} <= actions


def test_conflicting_and_stale_decisions(
    access: AccessRequests, owner_id: UUID
) -> None:
    request_id = _pending(access)
    with pytest.raises(AccessConflict):  # stale version
        access.decide(request_id, "approve", 30, 0, owner_id)
    access.decide(request_id, "reject", None, 1, owner_id)
    with pytest.raises(AccessConflict):  # already decided
        access.decide(request_id, "approve", 30, 2, owner_id)
    with pytest.raises(AccessNotFound):
        access.decide(uuid.uuid4(), "reject", None, 0, owner_id)
    with pytest.raises(ValueError):
        access.decide(request_id, "approve", 14, 2, owner_id)


def test_grant_extend_revoke_and_expiry(access: AccessRequests, owner_id: UUID) -> None:
    request_id = _pending(access)
    access.decide(request_id, "approve", 7, 1, owner_id)
    grant = next(g for g in access.grants("active") if g.request_id == request_id)
    extended = access.extend(grant.id, 30, owner_id)
    assert extended.expires_at > grant.expires_at
    revoked = access.revoke(grant.id, owner_id, "test")
    assert revoked.revoked_at is not None
    with pytest.raises(AccessConflict):
        access.extend(grant.id, 30, owner_id)
    with pytest.raises(AccessConflict):
        access.revoke(grant.id, owner_id, None)
    with pytest.raises(AccessNotFound):
        access.revoke(uuid.uuid4(), owner_id, None)
    assert access.grants("revoked")


def test_resend_paths(access: AccessRequests, owner_id: UUID) -> None:
    # Unverified: applicant self-resend and owner resend both re-queue.
    access.submit("Applicant", APPLICANT, None)
    request_id = UUID(
        str(
            _scalar(
                access.engine,
                "SELECT id FROM admin_access_request WHERE email = :e",
                e=APPLICANT,
            )
        )
    )
    access.resend_own(request_id)
    access.resend(request_id, owner_id)
    assert (
        _scalar(
            access.engine,
            "SELECT count(*) FROM admin_email_outbox"
            " WHERE kind = 'request_verification'",
        )
        == 3
    )
    _pending(access, APPLICANT)
    # Pending has nothing to resend.
    with pytest.raises(AccessConflict):
        access.resend(request_id, owner_id)
    access.decide(request_id, "approve", 30, 1, owner_id)
    access.resend(request_id, owner_id)
    invites = _scalar(
        access.engine,
        "SELECT count(*) FROM admin_email_outbox WHERE kind = 'sign_in'",
    )
    assert invites == 2


def test_prune_retention(access: AccessRequests, owner_id: UUID) -> None:
    # An ancient unverified request and an old rejected one are removed
    # with their tokens and sessions.
    access.submit("Applicant", APPLICANT, "old")
    stale_id = _pending(access, "rejected@example.test")
    access.decide(stale_id, "reject", None, 1, owner_id)
    with access.engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE admin_access_request"
                " SET submitted_at = now() - interval '8 days'"
                " WHERE email = :e"
            ),
            {"e": APPLICANT},
        )
        conn.execute(
            sa.text(
                "UPDATE admin_access_request"
                " SET decided_at = now() - interval '31 days'"
                " WHERE id = :id"
            ),
            {"id": stale_id},
        )
    counts = access.prune()
    assert counts["requests"] == 2
    assert _scalar(access.engine, "SELECT count(*) FROM admin_access_request") == 0
    assert (
        _scalar(
            access.engine,
            "SELECT count(*) FROM admin_token WHERE request_id IS NOT NULL",
        )
        == 0
    )

    # Lapsed viewers lose contact data; their grants keep pointing at rows.
    approved_id = _pending(access, "gone@example.test")
    access.decide(approved_id, "approve", 7, 1, owner_id)
    with access.engine.begin() as conn:
        conn.execute(
            sa.text(
                "UPDATE admin_viewer_grant"
                " SET granted_at = now() - interval '100 days',"
                " expires_at = now() - interval '95 days'"
            )
        )
    counts = access.prune()
    assert counts["contacts"] == 2
    email = _scalar(access.engine, "SELECT email FROM admin_user WHERE role = 'viewer'")
    assert str(email).startswith("removed-")
    request_email = _scalar(
        access.engine,
        "SELECT email FROM admin_access_request WHERE id = :id",
        id=approved_id,
    )
    assert str(request_email).startswith("removed-")
