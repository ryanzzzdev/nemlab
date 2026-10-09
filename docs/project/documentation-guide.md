# NEMLab documentation guide

Created: 2026-09-13  
Scope: Project planning, task tracking, decisions, and work records across the backend and frontend repositories.

## Purpose and location

Use Markdown documents to keep NEMLab understandable between working sessions: what we intend to build, what is agreed, what to do next, what is blocked, and what has been verified as complete.

The canonical project-wide documents live in the NEMLab backend project at `nemlab/docs/project/`, relative to the shared workspace. Within the backend project, this guide is `docs/project/documentation-guide.md`. Idea and discussion records live in `nemlab/docs/initial-ideas/`. When the separate NEMLab frontend is created, link to the backend's canonical documents from its README and keep frontend-specific implementation and setup documentation in the frontend repository.

The `nemlab/` backend Git repository was initialised on 2026-09-17. Project documentation and validation evidence are included in the initial version history. Keep one authoritative copy in this project rather than duplicating them at the workspace root or in sibling projects.

There is no separate project README initially. The repository README provides links; the roadmap and backlog hold milestone progress and next work.

## File layout

```text
README.md                          Repository entry point and documentation links
docs/project/
  documentation-guide.md           This guide
  roadmap.md                       Milestones, scope, dependencies, exit criteria
  architecture.md                  Current technical design and proposal status
  backlog.md                       Canonical task records and task status
  blockers.md                      Active hurdles and unresolved questions
  features/
    data-foundation.md             Ingestion, coverage, and data-quality specification
    batterylab.md                  Simulation behaviour and product specification
    gridreplay.md                  Event discovery and replay specification
    admin.md                       Administrative workflows, when scoped
  decisions/
    001-short-decision-title.md     Significant decisions and their reasoning
  journal/
    YYYY-MM.md                     Dated records of completed work and verification
```

Create documents when they have useful content. This guide does not require empty files for every future feature.

## What belongs in each file

| File | Contents | When to update |
| --- | --- | --- |
| Repository `README.md` | Project introduction, setup instructions, and links to the roadmap, backlog, architecture, and this guide. | When setup or documentation locations change. Do not copy current task status here. |
| `documentation-guide.md` | Documentation responsibilities, templates, and working practices. | When we agree to change the process, layout, or tracking tool. |
| `roadmap.md` | Ordered milestones, intended outcomes, scope exclusions, dependencies, exit criteria, and milestone status. | When scope or sequencing changes, or a milestone starts or meets its exit criteria. |
| `architecture.md` | Current system structure, repository/module boundaries, data flows, API contracts, persistence, deployment, and important technical constraints. Clearly distinguish proposals from accepted choices. | When a design is agreed or implemented behaviour changes the documented design. Link to decision records for reasoning. |
| `backlog.md` | Task IDs, outcomes, repository ownership, priorities, status, dependencies, acceptance criteria, and completion evidence. | When work is identified, prioritised, started, blocked, reviewed, completed, or dropped. |
| `blockers.md` | Unresolved questions and obstacles, their impact, affected tasks, evidence, and the next action needed to resolve them. | When an obstacle is found, new evidence arrives, or it is resolved. |
| `features/*.md` | User-visible behaviour, inputs, outputs, business rules, edge cases, scope exclusions, and feature acceptance criteria. | Before implementation and whenever agreed behaviour changes. Link to tasks rather than duplicating their status. |
| `decisions/*.md` | A significant choice, context, alternatives, consequences, and its acceptance status. | When proposing or accepting an important decision, or replacing a previous decision. |
| `journal/YYYY-MM.md` | Short entries titled with UTC date and time, identifying the LLM model and coding agent used, completed work, verification, unresolved issues, and links to tasks and commits/PRs. | At the end of a meaningful work session. It is a historical record, not the next-work list. |

The existing documents in `docs/initial-ideas/` remain idea and discussion records. Link to them as background when drafting feature specifications. A discussion summary is not automatically an approved specification. If a later accepted specification replaces a proposal, make that relationship clear; avoid maintaining two current specifications for the same behaviour.

## Roadmap conventions

Use these agreed implementation milestones as the starting sequence:

1. Validate OE data and interval semantics.
2. Prove the battery engine.
3. Build the shared backend and frontend foundation.
4. Deliver BatteryLab end to end.
5. Deliver GridReplay.
6. Agree and deliver the Admin operator experience.
7. Complete launch readiness and release.

BatteryLab and GridReplay are intended for the initial public launch. Admin's UI is agreed M6 scope under decision 024; deployment and operational release verification remain M7.

For each milestone, record its outcome, scope, dependencies, exit criteria, and status: `Planned`, `In progress`, or `Complete`. Do not mark a milestone complete merely because coding has stopped; check its exit criteria and linked tasks.

Detail the upcoming milestone and immediate dependencies. Keep later milestones broad until earlier work resolves the relevant uncertainties.

## Task records in backlog.md

Initially, keep each task as a section in `backlog.md`. Use a compact index at the top listing every task link in ascending ID order, each prefixed with the icon for its current status; since IDs are sequential, append each new task's index link at the end of the list. The index links to task records and shows ordering; task sections own the status word — the icon only mirrors it for scannability, so update the index icon whenever a task's status changes. Delivery-order or current-work context belongs in a short `Delivery notes` section beside the index, not in list position.

Assign IDs sequentially, starting at `NEM-001`. Never reuse an ID. IDs identify tasks; they do not indicate priority. The previously discussed `NEM-014` was an illustration, not an existing task.

Use this template:

```markdown
## NEM-XXX — Short outcome-oriented title

- Repository: backend | frontend | both
- Milestone: milestone name
- Priority: High | Normal | Low
- Status: Backlog 📋 | Ready 🟢 | In progress 🚧 | Blocked ⛔ | Done ✅ | Dropped 🗑️
- Depends on: task IDs, or None
- References: relevant feature specification and decision links

### Outcome

Describe the concrete behaviour or deliverable.

### Done when

- Observable acceptance criterion.
- Relevant verification requirement.

### Completion evidence

Add actual verification results and commit/PR links when available.
If changes are uncommitted, say so and reference the changed files.

### Notes

Record material context, a blocker link, or a reason for dropping/reopening work.
```

Prefer tasks that can be completed and reviewed in a focused working session. Split large tasks by meaningful outcome, not arbitrary file count. When backend and frontend changes have separate dependencies or acceptance criteria, give them separate linked tasks.

Task states mean:

| State | Icon | Meaning |
| --- | --- | --- |
| Backlog | 📋 | Identified work that still needs refinement or prioritisation. |
| Ready | 🟢 | Scope and acceptance criteria are clear, and required dependencies are satisfied. |
| In progress | 🚧 | Work is actively underway. Keep the active set small. |
| Blocked | ⛔ | A specific obstacle prevents further meaningful progress. Link to its blocker record. |
| Done | ✅ | Acceptance criteria are met and completion evidence is recorded. |
| Dropped | 🗑️ | Deliberately removed from scope, with a reason. |

Write the icon after the status word in the task section (for example `Status: Done ✅`, keeping `Status: <word>` greppable) and as the leading marker on the task's index line. The word remains the authoritative value.

If implementation is finished but required verification is pending, the task is not Done. If a completed task needs more work, reopen it with a reason or create a follow-up task for newly discovered scope.

Retain completed records. If the file becomes difficult to navigate, move task sections into `tasks/NEM-XXX-short-title.md` and keep the backlog as an index. Preserve IDs and update links; do not maintain duplicate task bodies.

## Blockers and open questions

Use a stable ID such as `BLK-001`. Each record should include:

- The question or obstacle and when it was identified.
- Whether it blocks work or can be investigated alongside it.
- Affected task IDs or milestones and the practical impact.
- Evidence, attempted approaches, and relevant links.
- The next action and who or what can resolve it.
- Status: `Open` or `Resolved`; resolution and date when resolved.

For example, uncertainty about OE interval labels can block price-ingestion acceptance while frontend layout work continues. Do not mark the whole project blocked because one task is blocked.

Keep the evidence and resolution in the blocker record. Task records link to it. If the resolution establishes a lasting design choice, also create or update a decision record.

## Decision records

Create a numbered decision record for choices that materially affect architecture, correctness, product scope, or future maintenance. Routine implementation details do not need one.

Include:

- Title, date, and status: `Proposed`, `Accepted`, `Rejected`, or `Superseded`.
- Context and constraints.
- The proposed or accepted decision.
- Alternatives considered and why the choice fits.
- Consequences and follow-up work.
- Acceptance source, such as an explicit discussion agreement, when accepted.
- Links to related specifications, tasks, or replacement decisions.

Do not promote a recommendation to an accepted decision without supporting agreement. For example, a suggested runtime upgrade remains proposed until accepted or selected under delegated authority. Record that acceptance source explicitly.

When a decision changes, preserve the old reasoning, mark it Superseded, and link to the replacement. Update `architecture.md` or the relevant feature specification to show the current accepted position. Distinguish accepted design from implementation still in progress.

## Session workflow

### Before starting work

1. Read the roadmap and backlog to identify the current milestone and next ready task.
2. Read the relevant feature specification, architecture sections, decisions, and blockers.
3. Check the actual repository state; documentation can lag behind code.
4. Confirm the task's acceptance criteria and dependencies, then mark it In progress.

### During work

1. Keep changes within the task's scope; record newly discovered work as separate tasks when appropriate.
2. Update specifications if agreed behaviour changes.
3. Record significant decisions and blockers when they arise.
4. Record verification results accurately, including checks that failed or were not run.

### Before ending a session

1. Update the task status and completion evidence. Leave unfinished work clearly unfinished.
2. Update affected feature or architecture documentation so it agrees with the work.
3. Update blockers and put the next concrete action in the active task or backlog ordering.
4. Add a short journal entry with the LLM model and coding agent used, task IDs, what changed, verification, and any remaining issue.
5. Check changed document links and remove contradictions or duplicated status.

When making an authorised code commit, include related documentation updates where practical. Cross-repository work may require separate commits; reference both from the task. A journal entry does not replace a task update, and this process does not itself authorise commits or external publication.

### At a milestone boundary

Review the exit criteria, outstanding tasks, and blockers. Mark completion only when the evidence supports it. Then refine the next milestone, review priorities and dependencies, and reconsider optional scope such as Admin.

## Journal example

```markdown
## YYYY-MM-DD HH:MM UTC — Regional price ingestion

- LLM model: Model name/version reported by the session, or Unknown.
- Coding agent: Agent/application used, with version if available.
- Tasks: NEM-XXX.
- Completed: Describe the implemented outcome.
- Verification: Name the checks performed and their actual results.
- Remaining: Link to unfinished tasks or blockers, if any.
- Changes: Commit/PR links, or changed files if uncommitted.
```

Entry titles carry the UTC date and time (`YYYY-MM-DD HH:MM UTC`). Take the timestamp from the system clock (for example `date -u`) rather than estimating it or converting local time manually. Entries recorded under earlier title conventions keep their original titles.

Every entry must include separate `LLM model` and `Coding agent` fields. Record the model identity available from reliable session metadata or explicit session instructions; do not infer it from the agent's name, available-model lists, or default settings. If only the model family is known, record that family and note that the exact variant is unavailable. Use `Unknown (not recorded)` for historical entries without reliable evidence. The coding agent is the tool/application running the work, such as Codex desktop; include its version only when known. If several agents or models contributed, list their roles and identities where known.

Keep entries concise. Do not copy tool transcripts, whole conversations, or the full acceptance checklist into the journal. Correct factual mistakes when found, but preserve the history of what was known and done at the time.

## Maintenance rules

### Agent-assisted updates

The reusable `project-management` skill applies this workflow. NEMLab's project-root `AGENTS.md` instructs the agent to use it and update affected records before finishing meaningful work, without requiring a separate documentation request. These instructions are scoped to NEMLab, not its sibling workspace projects. The skill follows this guide rather than maintaining a copy of NEMLab's conventions.

This is an instruction-based end-of-work routine, not a background file watcher or a guarantee that interrupted sessions will finish their documentation. At the next session, reconcile unfinished records with actual changes. Pure explanations and unchanged status checks need no entry; repeated closeout of the same work should not duplicate journal entries.

The backend activation instruction now lives in `nemlab/AGENTS.md`. When the frontend is created, add an activation instruction in its own `AGENTS.md` and link it to this canonical guide; backend instructions do not automatically apply to a separately opened frontend repository. Use the journal defined here for this workflow, even if a generic journaling skill has a different default location.

### Record ownership

- Keep task status in the backlog, milestone status in the roadmap, and historical outcomes in the journal.
- Prefer links over copied explanations. Keep business rules in feature specifications and decision reasoning in decision records.
- Record dates explicitly and distinguish proposed, accepted, implemented, and verified work.
- Never include API keys, credentials, or unsanitised sensitive responses in project documents or evidence.
- Update only documents affected by the work. A small task should not require editing every file.
- Treat documents as durable project memory; reconcile them with code and new evidence rather than assuming they are always current.
- Known gap (2026-09-20): NEM-009, NEM-011 and NEM-012 completion evidence in `backlog.md` still says "Changes are uncommitted" although that work is committed in earlier history, and `evidence/jobs/findings.md`/`worker-findings.md` carry similar stale notes. Attributing each to its commit needs history archaeology; reconcile them when the records are next touched or when the mapping is checked against `git log`.

If we adopt GitHub Issues/Projects or Linear later, migrate task status and task records there and stop using the Markdown backlog as a second tracker. Retain specifications, architecture, decisions, and operational documentation in Git, linking to the external tasks. Update this guide to make the new ownership explicit.
