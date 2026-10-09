# 026 — BatteryLab stored simulations in Admin

Date: 2026-10-09. Status: Accepted direction, implementation pending.

The user identified missing BatteryLab visibility, accepted inspection/provenance within Data Operations, then requested detailed planning. Add Simulations to the desktop workspace and make shared price coverage explicit. Inspect stored scenarios, comparison results, lifecycle evidence and pinned/current price revisions. Reuse public BatteryLab for full charts; do not create a second scenario builder or new cancellation/rerun controls.

The [specification](../features/admin-batterylab.md) selects bounded admin read endpoints, owner/approved-viewer safe projections and future transactional lifecycle recording. Existing stored simulations have no reliable submitter ownership; do not fabricate it. Sanitized archive discovery is explicitly an approved-viewer capability; it is not anonymous catalogue access. New personal scenario fields would require a renewed visibility decision.

Historical execution gaps remain labelled rather than backfilled. Corrected prices do not invalidate or rewrite immutable results. This extends decisions 024/025 without changing identity or desktop direction. Tasks [NEM-117–123](../backlog.md#nem-117) are new M6 scope; prior M6 delivery stays recorded, and M7 launch gates remain open.
