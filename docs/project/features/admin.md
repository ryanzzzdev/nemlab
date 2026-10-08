# Admin — M6 delivery specification

Updated: 2026-10-08. Status: Accepted product direction; implementation defaults selected under the user's delegated design authority. Planned, not implemented. Tasks: [NEM-093 and NEM-095–107](../backlog.md#nem-093). Decision: [024](../decisions/024-admin-experience-and-access.md).

## Purpose and scope

Answer “What data do I have, what is missing, and how do I make it available?” Provide the owner with real operating controls and approved visitors with a guided, read-only view of the same system. Demonstrate traceability and understandable operations without claiming production certification.

Deliver a separate `apps/admin` build in the existing frontend repository, using the existing Python API/worker/PostgreSQL. Serve it at `/admin` under the same origin; development uses the Vite proxy. Reuse theme tokens, components and generated clients through shared modules where useful; do not import Admin into the public bundle. No new backend service, general database editor, billing, organisations or configurable role designer.

## Navigation and visual direction

Public navigation/footer includes **Admin**, leading to a public welcome screen explaining the console, with Sign in, Request access and a static workflow illustration. It reveals no private operational data before approval.

Authenticated navigation: **Coverage** (default), **Jobs**, **Publications**, **How it works**, and owner-only **Access**. Account menu provides role, session expiry and sign out. Approved visitors see a persistent “Read-only access” badge with their grant expiry. Keep a route back to the public products.

Use a centred, wide content area consistent with BatteryLab/GridReplay, compact navigation, matching typography/panels and Light/Dark/Auto. Tables scroll within their panel on narrow screens; core actions and explanations remain usable at 320px. Use status text/icons as well as colour. Avoid decorative dashboard charts with no operational purpose. All screens need loading, empty, unavailable, partial-data and permission-expired states.

### Coverage

Region selector and inclusive NEM date range; summary of price, demand, flow and fuel-series coverage; per-day grid/table; separate current stored coverage from latest publication coverage. Show complete, partial, missing and unavailable distinctly, observation counts and revision/freshness where known. Unknown is never green. Offer a textual legend and selected-day detail.

Owner primary action: **Load data** for selected scope. Secondary action: **Review & publish**. Viewer sees explanatory action descriptions, not usable write forms. Show baseline readiness separately from candidate-window coverage; September coverage alone does not establish unusual-ramp eligibility. Do not imply an inspected range is already the public catalogue range.

### Jobs

Bounded, paginated/filterable price/grid job list with type, region, requested range/day, progress, attempts and status. Detail includes safe diagnostic summary, chronological audit, checkpoint and linked load operation. Distinguish queued, running, waiting for retry, failed, cancelled and succeeded; derive only states the API supports. Owner may cancel supported work and start a new submission for remaining/failed days. Label this “Resume remaining data” or “Submit again”, not an in-place retry. Viewers cannot initiate polling that starts work.

### Publications

Region-specific current publication and history; date scope, detector suite/version, creation time, coverage warnings, event counts by type and links to real public replays. Detail explains frozen source revisions and preserved old links. Where available, show highlight selection version, ranked reasons/populations and constituent suppression, clearly separate from detection. No manual highlight editing or new detector-threshold editor in M6.

### Access (owner only)

Pending verified requests with name, email, optional message, requested/verified timestamps. Approve (30 days default; selectable 7/30/90 days), reject, extend or revoke. Separate active/expired/revoked visitors; no visitor-to-owner promotion in the UI. Concurrent approvals are atomic and idempotent. Decisions and delivery failures are visible and audited. Never expose applicants or account lists to viewers.

## Embedded workflow guide

Persistent compact stepper: **Load data → Check coverage → Detect & publish → Explore**. Each step has one sentence, a “What does this mean?” disclosure and a link to the relevant live view. How it works expands this into a diagram and glossary, using examples explicitly labelled illustrative when not live.

Explain: grid observations versus prices; market days in fixed NEM UTC+10; jobs versus stored revisions; complete versus partial coverage; event detector versus Highlights selection; publication versus new data; immutable replay snapshots; safe recovery and republishing.

The actual [runbook](../runbook-grid-data.md) pipeline is grid import → price refresh → publication. Detection currently runs synchronously inside publication; no independent detection job or unpublished detector preview is invented. Grid and prices have separate stores. A successful grid import does not imply price availability. New data does not rewrite a published replay.

V2 education covers ordinary versus unusual ramps, negative runs, price spikes, negative-to-high reversals and compound negative episodes. Unusual ramps use preceding 90 days with minimum 60 complete days and 20 comparable weekday/weekend days; show insufficient baseline distinctly from zero qualifying events. Explain Highlights as a bounded selection from published candidates, with exact scoped reasons and overlap suppression, not an additional detector or a NEM-wide rarity claim. Frozen definitions remain owned by [decision 022](../decisions/022-detector-v2-definitions.md) and [discovery spec](gridreplay-discovery.md).

## Owner load and publication journey

1. Select one region and inclusive range (initial UI cap 366 completed market days). Convert to exclusive API end once, show the exact scope, missing coverage and estimated number of bounded submissions. Default loads selected scope; any skip-complete option must use explicit metric completeness, never guesses.
2. Persist a lightweight load-operation record with scope, phase, child request keys and job IDs. Submit <=31-day grid chunks sequentially with backpressure; then <=31-day price windows using NEM-092. Reuse existing durable queues; no second worker scheduler. Polling, tab closure or reload cannot lose child references or cause duplicate requests. Resume dispatch explicitly on return; already queued jobs continue independently.
3. Show phase and per-day progress, optional fuel failures and actionable diagnostics. Partial dispatch remains visible. Queue-full pauses new submissions; do not retry publication or fan out unbounded requests. “Stop submitting” differs from cancelling already queued work. Recovery uses new bounded submissions for remaining work, with audit links to the previous operation.
4. Recheck authoritative coverage. Show candidate-period and prior-baseline gaps. Prior demand history is an explicit optional import with its own range/count; never silently fetch 90 more days. UI admission limits do not bypass backend bounds or quotas.
5. Review publication scope (1–31 days), region, **v2 default** (explicit in request), data warnings and replacement effect. Loading more than 31 days does not trigger multiple automatic publications: the latest publication replaces the region catalogue pointer, it does not append monthly catalogues. Let the owner choose one intended public window. v1 remains available under advanced compatibility controls.
6. Owner explicitly confirms **Detect & publish**. Block accidental incomplete price/required-demand publication by default; allow an owner acknowledgement of specific gaps when partial publication is intentional. Optional flow/fuel gaps remain labelled. This is a coverage preview, not a promise of precomputed event counts. Publication remains atomic and synchronous, with no automatic retry; a lost response becomes “Outcome unknown—check history”, not “Failed, retrying”.
7. Show resulting publication, counts, coverage and links to GridReplay/Highlights. Refreshing source data requires explicit republication. Existing saved replay links remain immutable and readable.

Persist request identity, scope and actor on publication attempts/results so a response lost after commit can be reconciled safely. Preserve the existing rule that deliberate repeated publishes create new publications; correlation is for inspection, not silent publication deduplication. Authorisation is rechecked when actions execute.

## Identity and permissions

Two human roles: **Owner** (the user's superadmin, all application operations) and **Viewer** (approved operational reads only). Anonymous visitors can view the welcome/help introduction and submit/verify access requests. An unapproved verified applicant has no operational read access.

| Capability | Anonymous / applicant | Viewer | Owner |
| --- | --- | --- | --- |
| Welcome and request access | Yes | Yes | Yes |
| Safe coverage/jobs/publications/help | No | Yes | Yes |
| Imports, cancellation, recovery, publication | No | No | Yes |
| Applicant personal data, grants, security audit | No | No | Yes |
| Credentials, raw provider responses, arbitrary SQL | No | No | No UI |

Enforce permissions in every backend route/service boundary with deny-by-default capabilities, not HTTP-method-only rules. Viewer reads use explicit safe response schemas: no emails, applicant messages, tokens, raw exception text, sensitive source URLs, actor identities or operational secrets. Show a role label such as “Owner” instead of personal actor identity in viewer audit. All list/detail/child-audit endpoints follow the same policy; unknown routes do not inherit viewer access. Owner operational detail still excludes secrets.

Existing bearer authentication is retained for trusted operator automation, scoped to legacy operational capabilities, not browser access management. Browser cookies cannot bypass capability checks. Define deterministic rejection of conflicting authentication credentials; never embed the operator token in either frontend bundle.

### Owner bootstrap and sign-in

Use email sign-in links for owner and approved viewers; no shared/default password. Bootstrap exactly one owner via a server-side setup command with explicitly supplied owner name/email and confirmation. It is idempotent, has no public bootstrap route, and does not derive ownership from the first signup or reset on restart. Owner identity is required at setup, not guessed during planning. Provide a documented server-side recovery procedure that audits changes and revokes sessions. Protect the last owner from revocation/deletion through ordinary UI. Implemented as `python -m nemlab_infrastructure.admin bootstrap-owner|recover-owner` over the V8 `admin_*` tables (NEM-095); the command contract is documented in [infrastructure README](../../../infrastructure/README.md#admin-identity).

Email sign-in proves mailbox control; it is not phishing-resistant MFA. Passkeys/MFA are deferred, with this limitation explicit at M7 review. Access decisions and owner recovery require recent sign-in (within 15 minutes); re-authentication uses a fresh email sign-in link, and the UI preserves the pending action and resumes it after re-verification rather than replaying a stale request. Server-side opaque sessions: 30-minute idle and 8-hour absolute expiry; secure HttpOnly SameSite=Lax host-only cookies in production, rotation on login, CSRF token plus origin validation for cookie-authenticated mutations, logout revocation and grant checks on every request. No credentials in localStorage. Development-only cookie relaxation is explicit and cannot be enabled accidentally in production; a documented development-only command may seed a test session against local data and likewise cannot run in production.

Sign-in tokens: random, hashed at rest, single-use, 15-minute expiry, transactional consumption. Token URLs use a fragment exchanged by POST, removed immediately from browser history; no third-party scripts on auth pages. Link GET does not consume the token, protecting against email scanners; explicit Continue completes sign-in. Current request logging includes query strings: redact authentication material before shipping. Validate same-origin return paths; no open redirects. Implemented as `/api/auth/v1/sign-in-requests|sessions|session|logout` over `AdminAuth`, `LocalMailbox`+`OutboxMailer` (worker `NEMLAB_MAIL_*`) and persisted `RateLimiter` (NEM-096).

### Request and approval lifecycle

Visitor submits name (1–100 chars), email (validated, max 254) and optional plain-text message (max 1000). Explain purpose and retention at the form; no marketing consent or employer-specific questions. Generic acknowledgement avoids disclosing existing accounts. Verify email using a single-use 24-hour token before showing the request in the owner approval queue. Verification proves ownership but grants no Admin access.

States: unverified → pending → approved or rejected; approved grants can expire or be revoked. Duplicate submissions for the same normalised email do not create duplicate active requests or reset an existing decision. Do not strip provider-specific dots/plus aliases. Reapplication after rejection/revocation is explicit and throttled; never silently restore access. Verified users can view only their own request state through a limited applicant session; applicant sessions share the same expiry, rotation, revocation and cleanup rules as owner/viewer sessions and count toward the same rate limits.

Approval creates a viewer grant and queues an invitation/sign-in email. Email failure does not undo approval or create duplicate grants; owner sees delivery state and can resend within limits. Expiry/revocation invalidates active access immediately on the next request. Default access duration is 30 days, extendable by owner. Viewer can sign out; session/expiry errors clear cached private data and explain how to request renewed access.

Transactional email uses a provider-neutral transport and durable outbox with bounded retry, dedupe and visible delivery failure; the existing worker drains the outbox on its poll cycle, with no new scheduler or process. Local tests use a captured mailbox, never live recipients or production logs. Provider, sender domain and credentials are deployment inputs; no purchase/provider signup is implied. Initially notify the owner inside Admin with pending count; no unsolicited owner email digest.

Rate limits are persisted/shared across processes: initial configurable defaults of 5 mail requests/email/hour, 20/IP/hour, resend cooldown 60 seconds and 10 failed token exchanges/IP/15 minutes, plus a global mail budget. Use generic responses, bounded body sizes and no raw token logging. CAPTCHA is deferred unless observed abuse warrants it.

Retention defaults: unverified requests 7 days; rejected requests/messages 30 days; approved messages removed after decision +30 days; expired/revoked visitor contact data removed after 90 days unless reapproved; security/access audit 180 days with pseudonymous IDs where practical. Cleanup preserves immutable market evidence and operational referential integrity. Explain actual policy and deletion contact in the UI; M7 must verify it against deployed backup retention. These are product defaults, not a legal-compliance certification.

## Data and API additions

Migration-backed users/roles, viewer grants, access requests, hashed one-use tokens, sessions, email outbox, access audit, persisted rate limits and lightweight load-operation/child links. Reuse existing job tables, event/revision storage and audit semantics. Atomic approval/grant/outbox writes; optimistic version checks on conflicting access decisions; migration rollback/recovery documented without deleting existing market data.

Route families to finalise in OpenAPI before UI integration: public `/api/access/v1/requests` and verification; `/api/auth/v1/` email-link, token exchange, session and logout; owner-only `/api/admin/v1/access-requests` and grants; bounded coverage, load-operation and safe job/publication reads under `/api/admin/v1/`. Existing operational endpoints keep their contracts and add capability enforcement. Applicant status reads require applicant authentication and cannot enumerate requests. Do not reuse the old bearer-only middleware unchanged for viewers.

NEM-082 delivered `GET /api/admin/v1/grid-coverage/{region}`; NEM-092 date-range price refresh is already committed (`349f4ad`). Add only missing projections and orchestration metadata. Generate frontend contracts and test captures for every added/changed endpoint. Reconcile runbook v1 examples, v2/schema prerequisites and auth instructions rather than copying stale snippets into UI help.

## Delivery and verification

Deliver backend security first, then a real read-only console, then owner workflow and access-management UI; public link ships only when request/sign-in paths work. See task sequencing in the backlog. Early visual work may use clearly marked fixtures; the accepted product must use real data.

M6 exit requires: secure owner bootstrap; verified request→approval→viewer sign-in→revocation journey; permission tests for every endpoint including direct write attempts; coverage→bounded import→recovery→explicit v2 publication→real replay; refresh/tab-close/queue-full/lost-publication-response handling; correct baseline/Highlights explanations; safe viewer redaction; email outage/expiry/replay/CSRF/concurrent-decision tests; desktop and 768/390/320px Light/Dark/Auto review, keyboard/touch and accessible text alternatives. Run backend/contract/frontend checks and real API/worker/PostgreSQL/mail-capture journeys. Record measurements for largest supported coverage range and bounded lists; target no unbounded queries or polling after logout/unmount.

A plan does not complete M6. Hosted CI, production email/domain configuration, TLS/proxy deployment, backup/retention rehearsal and deployed smoke remain M7 release gates. No real owner or visitor account is created by this planning change.

## Historical context

M5 NEM-019/NEM-063 proved protected operator APIs/runbook and deferred Admin UI in [decision 021](../decisions/021-admin-ui-deferred.md). That UI deferral is superseded by this accepted M6 scope; historical rehearsal evidence remains valid. Existing API bearer identity is not the planned browser account system.
