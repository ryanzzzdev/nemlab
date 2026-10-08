# Admin desktop workspace redesign

Date: 2026-10-08. Status: Accepted direction; detailed defaults selected under delegated design authority. Planning only. Supersedes the presentation/navigation requirements in [Admin](admin.md) through [decision 025](../decisions/025-admin-desktop-workspace.md). Tasks: [NEM-108–115](../backlog.md#nem-108).

## Outcome and boundaries

Completely replace the public-site-style Admin presentation with a full-viewport enterprise operations workspace. Optimise for a desktop owner scanning data and performing work, while retaining an understandable approved-viewer experience. High information density means aligned comparable information, visible context and short paths between related records; it does not mean tiny typography or every detail visible simultaneously.

Functional M6 delivery is retained: identity, roles, viewer redaction, access approvals, load operations, jobs, coverage, v2 publication, uncertain-outcome recovery and immutable replay links. No authentication rewrite, public-product redesign, new detector, batch permission model or generic CRM framework. Reuse domain clients/query logic after inventory; replace page composition and styling rather than merely removing max-width. Existing uncommitted changes in api.ts, Shell.tsx, PublicationsPage.tsx and public Layout.tsx must be inspected and preserved.

## Information architecture

Only two primary authenticated destinations:

- **Data Operations**: Coverage, Loads & Jobs and Publications are linked views within one workspace, sharing scope and inspection context.
- **Access** (owner only): Requests, Visitors and Access audit are views within one workspace.

Help is a contextual side panel plus a searchable-on-page glossary, not a mandatory navigation destination. Search here means filtering loaded explanatory text, not a new search backend. Welcome, request access, request status, sign-in and verification remain distinct security journeys but adopt the new Admin visual language. Authentication forms may use a focused centred panel; the full-viewport density requirement applies to authenticated operational work.

## Application shell and geometry

Independent Admin stylesheet/token scope; stop importing public layout CSS. Share genuinely unstyled behaviour such as theme preference, formatting and API types. Do not let public `.site`, `.card`, `.intro` or page-width rules determine Admin layout. Retain React/plain CSS and established libraries unless a measured table requirement justifies a narrowly scoped dependency.

Default light enterprise palette: neutral canvas, white work surfaces, subtle separators, dark text and a restrained blue interaction accent. Dark and Auto remain fully supported. Prefer flat sections, compact tab bars and dividers over repeated rounded cards, large headlines, hero text or generous whitespace. Use status colour only for meaning; render text/icon labels for every state.

Desktop defaults (tunable during visual review):

- 48px application header: product/workspace, environment label when known, help, theme and account/role. Session/grant expiry stays discoverable without dominating the toolbar.
- 176px collapsible left rail, 48px collapsed; two labelled destinations, Access request count for owner, public-site link at bottom. Collapsed icons retain accessible names/tooltips.
- Remaining viewport is the workspace; no centred max-width or marketing footer. Workspace heading and scope toolbar use approximately 88px together.
- Main work area: primary table/matrix and optional 360px right inspector (adjustable 300–520px). Optional lower activity pane defaults to 220px (range 160–400px). Provide collapse and reset-layout controls; persist dimensions only, not sensitive records.
- Body text 13–14px, section headings 14–16px, numbers tabular and right-aligned; standard rows 32px, compact 28px, comfortable 40px. Density setting is remembered locally. Controls have readable labels and adequate click/focus targets; compact spacing is not permission to hide focus or depend on hover.
- Sticky table headers, stable column alignment and bounded panel scrolling. Do not create a collection of competing nested scroll areas; main table, inspector and optional lower pane each have explicit boundaries.

Primary acceptance viewports: 1440×900 and 1920×1080; minimum desktop 1280×720. At minimum desktop, rail collapses, inspector becomes overlay and lower pane can be hidden so the table remains useful. Smaller screens get a truthful desktop-recommended message and a usable stacked/scrolling fallback; do not spend redesign effort on mobile card layouts. Sign-in/request/logout and session-expired recovery remain accessible on small screens. At 200% zoom, controls/content remain reachable through pane collapse/reflow; desktop-first does not waive keyboard or visual accessibility.

## Data Operations composition

```text
┌ NEMLab Admin                         Help  Theme  Owner ┐
│ Data Ops │ Region  From—To  Apply  Freshness  Refresh     │
│ Access   │ Prices … Demand … Baseline … Published …     │
│          │ Coverage | Loads & Jobs | Publications       │
│          │                                              │
│          │ Main table / coverage matrix │ Inspector     │
│          │                             │ facts/actions │
│          │─────────────────────────────┴───────────────│
│ Public ↗ │ Activity: related jobs / load progress        │
└──────────┴──────────────────────────────────────────────┘
```

Keep region/date scope visible. User edits draft filters then applies them; avoid requests for each keystroke. Toolbar shows actual data-as-of/refresh status where available, not invented freshness. Compact summary strip shows coverage counts, baseline readiness and latest publication scope; figures are actionable filters or inspector links, not ornamental KPI cards.

### Coverage view

Main matrix: one row per market day; columns for day, price coverage, demand, flows, fuel data, baseline eligibility where supported and revision/freshness detail. Use compact text/bars with counts, plus a legend; unknown/partial never implies complete. Default date-descending with explicit sort state. Select a row to inspect exact counts, gaps, revisions and related jobs. Inspecting a row must not silently change the global date range.

Primary owner actions **Load data** and **Review publication** in the context toolbar. Viewer instead sees an unobtrusive explanation that actions require owner access. Current stored coverage and published replay coverage remain separate. Keep v2 unusual-ramp baseline context accessible in the inspector, including insufficient baseline versus evaluated-with-no-match.

### Loads & Jobs view and activity pane

Use compact rows rather than stacked job cards. Columns: status, type, region, window/day, progress, attempts, updated time where supplied and shortened ID with copy/full detail. A load operation expands or opens its child jobs in the inspector. Tabs/filters distinguish load operations and individual grid/price jobs; do not fabricate one globally sorted dataset from incomplete independent endpoint pages.

The lower pane shows context-related activity by default, with an explicit “All recent” option when supported. Selected scope/record determines the filter, displayed in its title. Owner actions reside in the inspector: stop further dispatch, resume dispatch, cancel supported child work, submit remaining data. Preserve distinctions and actual backend status vocabulary. No bulk cancellation or speculative queue controls.

### Publications view

Rows show current indicator, region, window, suite/version, event count, creation time and coverage warnings. Inspector shows type counts, source/provenance, highlight explanations where supported, publication attempt state and public replay/catalogue links. Read-only inspection never starts detection or requests external data. “Current” is relative to the region, not the currently filtered list.

## In-place owner workflows

Load data opens a task drawer/expanded inspector with scope review, bounded chunks, warnings and Start load. It uses existing persisted operation IDs/idempotency behaviour. After submit, the activity pane shows progress without leaving Coverage. Reload/deep link can restore the selected operation. Do not run a second dispatcher because the same job appears in two panes.

Review publication opens a wider contextual drawer (approximately 480–640px) showing scope, v2 selection, coverage check and exact catalogue-replacement effect. Preserve <=31-day limits, partial-coverage acknowledgement and deliberate final Detect & publish. Importing a long range does not append catalogues. Preserve unknown-outcome reconciliation and never automatically retry publication.

Drawers have clear Close/Cancel semantics, draft preservation and focus return. Closing a drawer does not cancel a queued server operation. Keep an active task accessible in the lower pane. Dirty drafts warn before discard; successful actions update affected query caches and announce a concise result without losing table selection or scroll. Session expiry clears protected data and cannot auto-resubmit the action after sign-in.

## Access workspace

Compact summary of pending requests/active/expiring grants when supported; Requests, Visitors and Audit tabs. Main table + selected-record inspector. Request columns: name, email, verification/request date, state. Inspector shows optional message safely as plain text, delivery state and Approve duration/Reject controls. Visitors show grant expiry and Extend/Revoke actions. Audit retains actor/action/time/result visibility for owner only.

Preserve recent-auth requirements, optimistic conflict detection, idempotent decisions, immediate revocation and delivery-failure recovery. Select-next after a decision is deliberate and visible; no bulk approval, speculative role editing or browser-side authority. Counts must match server scope; if only a bounded recent page is available, label it honestly rather than implying global totals. Hide Access navigation for viewers and retain backend forbidden responses on direct navigation.

## Tables, inspectors and interaction rules

All tables: sticky header, visible row selection/focus, type-appropriate sorting, bounded pagination, count/scope label, empty/error/loading states, reset filters and exact values accessible without tooltip-only dependence. Support resize and visibility controls for useful optional columns; retain essential identification/status columns. Persist layout preferences per workspace locally, never applicant emails/messages/tokens. A large table is not an excuse to render unbounded data; start with existing page limits, measure before adding virtualisation.

Sort/filter must operate over the claimed dataset. If the API only offers a recent bounded list, label client sort as “within loaded results”; do not present page-local search as full archive search. Backend additions require a separately scoped gap task after inventory; this redesign does not silently enlarge API capabilities.

Use semantic tables first, explicit row inspection buttons/links, labelled sort controls and predictable Tab order. Arrow-key spreadsheet navigation is optional only if fully implemented/tested; do not set role=grid without its keyboard contract. Pane resize supports keyboard and reset; Escape closes transient drawers and returns focus. No action icons without accessible names. Menus must not hide the primary task.

Global scope applies to Coverage and explicitly scoped job/publication views. All-regions/history modes label their override. Changing scope clears incompatible selection with an explanation, preserves harmless layout preferences and never modifies an open task's captured scope silently. Define draft-applied-scope separately. Browser Back/Forward restores applied filters, active view and selected record; hover/polling do not add history entries.

## Routing and state migration

Canonical `/admin?view=coverage|jobs|publications&region=…&from=…&to=…` with optional `job`, `load` or `publication` selection (one active inspector kind). `/admin/access?tab=requests|visitors|audit&selected=…` is owner-only. Do not encode names, emails, tokens or draft messages in URLs. Auth routes remain compatible.

Old `/admin/jobs`, `/admin/publications` and `/admin/load` redirect/translate into the corresponding workspace view/action, preserving valid IDs and scope; `/admin/how-it-works` opens help. Invalid/missing/inaccessible IDs render a recoverable inspector error, not a blank workspace or automatic write. Namespace query/cache keys by scope and privilege; clear protected cache on logout/role change. Avoid duplicate polling across mounted panes; stop polling hidden/inactive detail queries and back off transient failures.

## Help and visitor experience

Default work surface is data, not prose. Compact workflow strip opens help for Load data → Check coverage → Detect & publish → Explore. Context help follows the selected entity with a pin option. Show concise domain explanations and expandable technical provenance. Preserve access to all existing educational content through help links/legacy route. The same safe real-data workspace serves viewers; no fake operator controls or simulated production activity.

## Implementation strategy and acceptance

NEM-108 inventories current fields/routes/states, captures owner/viewer baseline and creates a capability-preservation matrix. NEM-109 builds a realistic static desktop prototype with dense/empty/failure data and both themes, visually reviewed before broad page migration. This is a quality checkpoint, not a requirement to ask the user again; revise against this specification and expose a reviewable artifact. NEM-110 delivers shell/primitives, NEM-111 operations views, NEM-112 owner drawers, NEM-113 Access/auth/help, NEM-114 compatibility/regression, NEM-115 final visual/functional acceptance.

Acceptance evidence must demonstrate, at 1440×900: scope, coverage rows, latest publication summary and related activity visible together; inspect a job without leaving the workspace; start/recover a load and review publication without a full-page journey; approve/revoke from the request/visitor table while retaining context. At 1280×720, primary controls and useful table rows remain visible with panels collapsed. At 1920×1080, use extra width for useful columns/detail rather than stretching a centred card. Record visible row count and screenshots per density; target at least 10 coverage rows at standard density on 1440×900 with lower pane open.

Validate light/dark/auto, owner/viewer/applicant, keyboard, 200% zoom, long values, empty data, stale scopes, queue full, failed imports, uncertain publication response, recent-auth/conflicts, session expiry, mail failures and forbidden actions. Add dedicated Admin browser coverage: existing public 126 tests do not establish Admin behaviour. Run frontend format/check, targeted Admin tests and integrated live workflow on current backend; run relevant backend/contract tests only if backend contracts change. Public UI visual/build regression check is mandatory because shared-style extraction can affect it.

Record before/after screenshots and interaction counts for inspect failure, publish loaded data and approve access. No claim of faster users or enterprise certification without evidence. Original NEM-095–107 stay Done as historical delivery; M6 is reopened for this accepted UI scope. M7 deployment/email/CI gates remain unchanged. No implementation is performed by this planning document.
