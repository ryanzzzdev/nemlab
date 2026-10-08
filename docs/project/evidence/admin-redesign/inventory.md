# Admin workspace redesign — behaviour inventory (NEM-108)

Date: 2026-10-08. Maps every delivered Admin route, field, state and security
behaviour to its new workspace location under decision 025. Sources: current
`apps/admin` pages, `api/contracts/openapi.json`, `api/src/nemlab_api/*`.

## Route migration map

| Old route | New canonical route | Preservation notes |
|---|---|---|
| `/admin/` (index, Coverage) | `/admin?view=coverage` | same region+range draft → applied scope flow |
| `/admin/load` | drawer on Data Ops (`?drawer=load`) | sessionStorage `admin.loadDraft` prefills scope |
| `/admin/jobs` | `/admin?view=jobs` | op/job/detail states move into selection inspector |
| `/admin/publications` | `/admin?view=publications` | `?publication=<id>` selects inspector record |
| `/admin/access` | `/admin/access?tab=requests` | owner-only; tabs requests\|visitors\|audit |
| `/admin/how-it-works` | `/admin/help` + contextual help | content preserved verbatim |
| `/admin/welcome` `/request-access` `/request-status` `/sign-in` `/verify` | unchanged paths, restyled | token lifecycle untouched |

Browser Back/Forward restores `view`, applied scope (`region`, `from`, `to`),
tab and `sel` selection. IDs in URLs stay opaque; no names/emails/tokens.

## API field coverage (what the tables can honestly show)

Coverage day (`GridCoverageDay`): `day`, `availability`
(COMPLETE/PARTIAL/NOT_IMPORTED), `series[]` → `{metric, series, availability,
revision, retrievedAt, valid, missing, sourceNull}`. Metrics are `demand`,
`flow_imports`, `flow_exports` (required) plus optional `power` fueltech
series. **Consequence:** matrix columns are Demand / Flow imports / Flow
exports / Power series — there is no per-day *price* or *fuel-summary* column;
a per-day price figure does not exist in this API. Baseline is a separate
`/baseline` read (per-candidate `ready`, `completeDays`, `classDays`) — joined
client-side only when the applied scope is within its 1–31-day bound.

Jobs (`Job`/`GridImport`): `id`, `region`, `day` or `startDay`/`endExclusive`
+ `nextDay` progress, `status`, `attempts`, `availableAt`, `diagnostic`.
**No `updatedAt`/`createdAt`** — tables label `availableAt` honestly
("next attempt"); no fabricated updated time.

Load ops (`LoadOperation[Detail]`): `id`, `region`, range + `nextDay`,
`status`, `phase`, `actor`, `createdAt`, `updatedAt`, `children[]` →
`{phase, requestKey, startDay, endExclusive, submittedAt, jobs[]}`.

Publications (`AdminGridPublication`/`Detail`/`Attempt`): all needed fields —
`coverage`, `eventCounts`, `highlights`, `runId`, `actor`, `attemptKey`,
`diagnostic`. **No `current` flag** — derive client-side: latest `createdAt`
per region is the catalogue pointer (publication replaces it atomically).

Access: `AccessRequestView` (+`deliveries` on detail), `ViewerGrantView`.
**Gap: no audit-read endpoint** — `admin_access_audit` exists server-side but
has no route. Tracked as bounded gap task NEM-116; Access workspace shows a
deliveries+grant-history audit view without it, labelled honestly.

## State / cache / polling ownership

- Applied scope (`region`, `from`, `to`): URL canonical; coverage + baseline
  queries keyed on it. Editing draft inputs does not fetch until Apply.
- Selection: one `sel` param; cleared on scope or view change.
- SessionStorage drafts: `admin.loadDraft` (load review), `admin.publishAttempt`
  (lost-publish reconcile) — unchanged keys, unchanged semantics.
- Polling: one React Query per bounded list (20 s); the activity pane filters
  the *same* query caches — never a second dispatcher or duplicate fetch.
- Protected queries cleared on logout/role change (existing session hook).
- Security unchanged: cookie+CSRF+Origin mutations, bearer conflict 401,
  capability 403, viewer-safe projections — the workspace surfaces them as
  inspector/drawer denials, not new endpoints.

## Security state mapping

401 → session-expired panel (existing `getSession` null path); 403 → inspector
"no permission" copy; 409 ACCESS_CONFLICT → refresh-in-place prompt;
RECENT_AUTH_REQUIRED → drawer banner preserving intent; 429 → quiet retry-later
copy. Applicant sessions still land on request-status only.

## Uncommitted-work preservation

`api.ts` (`PUBLIC_BASE`), `Shell.tsx` (back link), `PublicationsPage.tsx`
(replay link), public `Layout.tsx` (dev `/admin/` link) — keep during rewrite;
the same dev-origin constants carry into the new shell.
