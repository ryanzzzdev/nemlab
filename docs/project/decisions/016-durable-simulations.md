# 016 — Durable simulation execution

Date: 2026-09-20
Status: Accepted and verified under delegated NEM-040 implementation authority.

Persist immutable normalised request/version metadata and a complete price revision reference
atomically with a simulation job. A unique scenario key deduplicates submissions across all
states, including terminal states. A failed job remains diagnosable; this slice does not
reset terminal jobs or promise a user retry API. Worker retries handle transient failures.

Simulation jobs use their own advisory lock and one global running claim, independent of
price refreshes. Pending capacity is 100, lease duration 60 seconds, maximum attempts three,
and retry delay 5/10 seconds. Expired claims recover on subsequent polling. Every terminal
write checks the claim token and live lease again, so expired workers cannot publish results.

One child JVM executes the fixed and ordered-hindsight comparison with a 512 MiB heap,
two active processors and the existing 5-second/100,000-iteration cooperative solver limits.
The parent enforces a 15-second deadline and confirms termination within five seconds; a
child watchdog also halts orphaned execution. These are process/heap bounds, not a total RSS
or deployment resource guarantee. Children receive only input/output paths and a cleared
environment, without provider/database credentials. Parent and child bound JSON file sizes.

Parent independently validates dispatch, fixed-policy identity and all accounting fields
before committing one immutable result and the terminal job status atomically. Only a
validated OPTIMAL outcome succeeds; feasible-but-unproven and other solver statuses are
preserved as diagnostic results on FAILED jobs. Hard timeout/crash retries are bounded;
invalid child results and unsupported stored versions fail terminally. No diagnostic
exception text is exposed. Inputs/results survive source corrections.

Worker simulation polling is separately opt-in through NEMLAB_SIMULATION_ENABLED. It
needs the shared database but no OE credential. Public submission/result HTTP endpoints
remain NEM-041. Retention, launch quotas and hosted resource measurements remain NEM-020.


Verification: [execution findings](../evidence/engine/execution-findings.md) record the
141-test full build, packaged execution and bounded-process checks. Changes are uncommitted.
