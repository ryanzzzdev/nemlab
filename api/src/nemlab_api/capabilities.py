"""Deny-by-default capability table for ``/api/admin/**`` (NEM-097).

Every operator route is registered here exactly once; a path/method pair
missing from the table denies like an unmapped route, so new endpoints can
never silently inherit viewer access. Grants are per resolved identity:

- ``owner`` — browser session with the owner role; every capability.
- ``viewer`` — browser session with an active grant; safe reads only.
- ``automation`` — legacy ``operator:<name>`` bearer; operational reads and
  writes but never browser-access management.
- ``applicant`` — session for an access-request subject; no grants here
  (applicant reads live under ``/api/access/**``, not this table).
"""

import re

READ = "ops.read"
WRITE = "ops.write"
ACCESS_MANAGE = "access.manage"

# (method, path-template) -> capability. Templates use the same ``{name}``
# shape as the routers so the table reads next to the route declarations.
ROUTES: dict[tuple[str, str], str] = {
    ("POST", "/api/admin/v1/price-refreshes"): WRITE,
    ("GET", "/api/admin/v1/price-refreshes"): READ,
    ("GET", "/api/admin/v1/price-refreshes/{id}"): READ,
    ("GET", "/api/admin/v1/price-refreshes/{id}/events"): READ,
    ("POST", "/api/admin/v1/price-refreshes/{id}/cancel"): WRITE,
    ("POST", "/api/admin/v1/grid-imports"): WRITE,
    ("GET", "/api/admin/v1/grid-imports"): READ,
    ("GET", "/api/admin/v1/grid-imports/{id}"): READ,
    ("GET", "/api/admin/v1/grid-imports/{id}/events"): READ,
    ("POST", "/api/admin/v1/grid-imports/{id}/cancel"): WRITE,
    ("POST", "/api/admin/v1/grid-publications"): WRITE,
    ("GET", "/api/admin/v1/grid-publications"): READ,
    # Literal ``attempts`` must precede the ``{id}`` template so the
    # detection-run history is not claimed as a publication id.
    ("GET", "/api/admin/v1/grid-publications/attempts"): READ,
    ("GET", "/api/admin/v1/grid-publications/{id}"): READ,
    ("GET", "/api/admin/v1/grid-coverage/{region}"): READ,
    ("GET", "/api/admin/v1/grid-coverage/{region}/baseline"): READ,
    ("POST", "/api/admin/v1/load-operations"): WRITE,
    ("GET", "/api/admin/v1/load-operations"): READ,
    ("GET", "/api/admin/v1/load-operations/{id}"): READ,
    ("POST", "/api/admin/v1/load-operations/{id}/dispatch"): WRITE,
    ("POST", "/api/admin/v1/load-operations/{id}/pause"): WRITE,
    ("POST", "/api/admin/v1/load-operations/{id}/resume"): WRITE,
    ("GET", "/api/admin/v1/access-requests"): ACCESS_MANAGE,
    ("GET", "/api/admin/v1/access-requests/{id}"): ACCESS_MANAGE,
    ("POST", "/api/admin/v1/access-requests/{id}/decisions"): ACCESS_MANAGE,
    ("POST", "/api/admin/v1/access-requests/{id}/resend"): ACCESS_MANAGE,
    ("GET", "/api/admin/v1/access-audit"): ACCESS_MANAGE,
    ("GET", "/api/admin/v1/viewer-grants"): ACCESS_MANAGE,
    ("POST", "/api/admin/v1/viewer-grants/{id}/extend"): ACCESS_MANAGE,
    ("POST", "/api/admin/v1/viewer-grants/{id}/revoke"): ACCESS_MANAGE,
}

GRANTS: dict[str, frozenset[str]] = {
    "owner": frozenset({READ, WRITE, ACCESS_MANAGE}),
    "viewer": frozenset({READ}),
    "automation": frozenset({READ, WRITE}),
    "applicant": frozenset(),
}

_TABLE = [
    (
        method,
        re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", template) + "$"),
        capability,
    )
    for (method, template), capability in ROUTES.items()
]


def capability_for(method: str, path: str) -> str | None:
    """The capability a route requires, or ``None`` when the pair is not
    registered — callers treat ``None`` as deny."""
    for registered, pattern, capability in _TABLE:
        if method == registered and pattern.match(path):
            return capability
    return None


def granted(role: str, capability: str) -> bool:
    return capability in GRANTS.get(role, frozenset())


def actor_label(actor: str) -> str:
    """Viewer-safe audit actor: ``operator:alice`` -> ``Operator``,
    ``owner:<uuid>`` -> ``Owner`` — the role, never the identity."""
    role, separator, _rest = actor.partition(":")
    if not separator and role == "worker":
        return "Worker"
    return role.capitalize() if role else "System"
