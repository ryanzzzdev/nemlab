# M3 shared-foundation exit review — NEM-037

Date: 2026-09-20. Review baseline: backend `2411439`, frontend `e963747`.

## Verdict

The scoped local foundation is implemented and supported by recorded verification.
M3 remains **In progress** because the explicit CI execution criterion has no hosted
run evidence. NEM-037 is complete as a review; [NEM-038](../../backlog.md#nem-038)
and [BLK-007](../../blockers.md#blk-007) track the remaining gate. A configured workflow
and a local pass do not establish that the hosted workflow runs successfully.

## Exit criteria and evidence

| Criterion | Evidence inspected | Assessment |
| --- | --- | --- |
| Clean local setup | [Foundation findings](findings.md): fresh temporary source checkout, cached-dependency clean build, executable API/worker smoke checks; [frontend foundation](../frontend/foundation-findings.md): locked clean install/build and browser startup. Repository setup guides document Java, Node and PostgreSQL prerequisites. | Pass for a clean working directory with dependencies available; not an empty-cache or hosted-run claim. |
| Ingest a validated day and report coverage | [Ingestion findings](../data-foundation/findings.md): saved historical OE fixture normalises 289 points to 288 interval endings; real PostgreSQL migrations/storage tests. [Public reads](../data-foundation/read-api-findings.md): actual HTTP coverage/series checks. | Pass using validated saved input; no new live OE request required. |
| Submit work through API | [Operator findings](../jobs/admin-findings.md): actual authenticated HTTP requests persist jobs in PostgreSQL, with idempotency and audit identity. [Worker findings](../jobs/worker-findings.md): submitted queue work reaches persisted coverage. | Pass for price refresh jobs; simulation submissions are M4. |
| Recover interrupted work | [Queue findings](../jobs/findings.md) and [worker findings](../jobs/worker-findings.md): expired lease replacement, stale-token rejection, retry exhaustion, subprocess shutdown/deadline and checkpoint recovery. | Pass. |
| Display API data in frontend | [Price integration](../frontend/price-integration-findings.md) and [chart findings](../frontend/chart-findings.md): two real packaged-Java/PostgreSQL browser cases plus desktop/mobile fixture cases. | Pass; live browser suite seeds synthetic database days and does not exercise OE ingestion. |
| Repeated ingestion does not duplicate observations | [Ingestion findings](../data-foundation/findings.md): repeated/concurrent imports reuse revisions, corrections create new revisions, attempts remain separately recorded. | Pass. |
| Stored simulation inputs survive source refresh | [Ingestion findings](../data-foundation/findings.md) and [public reads](../data-foundation/read-api-findings.md): immutable price snapshots retain exact prior values after corrections. | Pass for M3 price-input storage; parameters, dispatch and complete saved simulation results are explicitly M4. |
| CI runs relevant checks | [Backend workflow](../../../../.github/workflows/backend.yml) runs clean Gradle build/contract checks and packaged smoke tests. Frontend workflow in sibling `nemlab-ui/.github/workflows/frontend.yml` runs locked installation, Chromium setup and `npm run check`. | Configuration reviewed; hosted execution pending. |

## Verification performed in this review

Read the implementation evidence, current workflow definitions, real-backend browser
harness, and test cases in `PriceIngestionTest`, `PriceReadHttpTest` and
`RefreshWorkerTest`. Checked both working trees were clean at review start and both
`git remote` inventories were empty. Previously recorded final checks are 103 backend
tests, 46 HTTP contract responses, 40 frontend browser cases and two real-backend
browser cases. These counts are historical evidence, not new executions today.

The existing integration slices cover the cross-component boundaries. There is no
single full browser-to-operator-to-worker-to-live-OE test, and no such claim is made.
No additional local test was identified as necessary for the scoped criterion mapping;
repeating the suites would not resolve the hosted CI gap. This review makes documentation
changes only and validates their links and diff whitespace.

## Follow-up and scope

Record successful hosted runs at identified commits for both repositories, fixing any
workflow failures, before changing M3 to Complete. Repository destinations/publication
must be authorised first. No remotes, pushes, new accounts or deployments were created.

NEM-016 is refined into NEM-039 request validation/input identity, NEM-040 durable
execution/immutable results, and NEM-041 HTTP lifecycle/generated contract. NEM-039
follows the M3 gate. The accepted engine remains fixed schedule versus ordered-window
hindsight. Unrestricted optimisation, full GridReplay ingestion, Admin UI, broad coverage,
launch quotas/retention and production operations remain outside this foundation review.

The architecture's stale frontend directory sketch was reconciled with the actual
`apps/public` layout; optional packages/Admin are not present. Review records are uncommitted.


Follow-up (2026-09-20): the user directed local implementation to continue. NEM-039
is now verified and NEM-040 is next; this sequencing change does not resolve hosted CI
or change the M3 review verdict. See [decision 015](../../decisions/015-simulation-request-boundary.md).
