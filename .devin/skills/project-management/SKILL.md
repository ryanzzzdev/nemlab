---
name: project-management
description: Maintain a project's Markdown roadmap, tasks, decisions, blockers, and work journal. Use when requested or when project instructions require documentation updates after meaningful implementation, investigation, or planning work. Follow the project's existing documentation guide; do not impose this system on unrelated projects.
---

# Project management and documentation

Keep durable project records aligned with actual work. This is an in-session workflow, not a background watcher or scheduled task.

## Establish the source of truth

- Read applicable AGENTS.md instructions and the project's documentation guide, normally `docs/project/documentation-guide.md`. Follow its locations, task format, statuses, timezone, and update rules instead of copying a generic structure into the project.
- Follow explicit links to shared documentation across repositories. Do not create a second backlog in the frontend when the backend owns project-wide tracking.
- Read only the roadmap, active tasks, and specifications/decisions relevant to the work. Reconcile records with code, verification output, and the current conversation.
- If no documentation convention exists, discover existing records first. For an explicit setup request, propose or create a small appropriate structure; otherwise report the missing location without inventing project history or scattering new trackers.

## Update after meaningful work

Before the final response following implementation, a substantive investigation, an accepted planning decision, or a documentation deliverable:

1. Update the affected task with actual status, completion evidence, remaining work, and the next concrete action. Reuse its ID. Add a task for newly identified work only when useful under the project convention; do not invent historical IDs or manufacture a ticket for every minor edit.
2. Update feature specifications for changed behaviour and architecture for changed technical design. Keep proposed, accepted, implemented, and verified states distinct; recommendations are not acceptance.
3. Record material obstacles and unresolved questions with affected tasks, impact, evidence, and an unblock action. Resolve existing records when evidence supports it.
4. Update milestone status only when its exit criteria warrant it. Preserve agreed scope and sequencing.
5. Add one concise journal entry for the completed work unit or meaningful partial outcome, following the project's format. Include verification performed, limitations, and task/commit/PR links when available. Mark uncommitted work honestly. Use the environment's date/time and project timezone conventions.
6. Check consistency and references among affected files. Briefly mention material documentation updates in the final response.

Update only affected records. If an answer is purely explanatory, a status check reveals no change, or the same outcome has already been recorded, make no documentation edit. If repeating this workflow for the same work unit, amend the existing entry rather than append a duplicate. Documentation updates do not themselves trigger another round of journaling.

## Campaign checkpoints

A campaign — one continuous push across several accepted backlog tasks — applies the update rhythm above **per task**, not once at the end. Each task is a checkpoint:

1. Implement the task's scope; do not absorb neighbouring tasks.
2. Verify with the relevant tests and project checks.
3. Update the affected records — task status plus completion evidence, affected specifications/decisions, and a journal entry naming model and coding agent.
4. Commit the coherent unit. A checkpoint is incomplete while the tree is dirty.
5. Update the in-progress ledger, then start the next checkpoint.

Independent, cleanly-bounded tasks may be delegated to sub-agents — on their own git branches when parallel work risks conflicts — but the main agent keeps ownership of sequencing, integration, review of delegated output, and the project records. Stop mid-campaign only for genuine human decisions (unplanned product choices, destructive operations, plan assumptions disproven by evidence); record partial outcomes honestly rather than inflating completion.

## Evidence and scope

- A task is Done only when acceptance criteria and required verification are satisfied. Report failed, skipped, or unavailable checks; do not claim that a commit, deployment, or test occurred without evidence.
- Keep status in the task tracker, milestone progress in the roadmap, reasoning in decisions, and historical outcomes in the journal. Prefer links to duplicate explanations.
- Preserve completed records and decision history. Supersede outdated decisions rather than silently rewriting their original reasoning.
- Do not overwrite unrelated work, bootstrap every missing document during routine closeout, or rewrite the backlog based on guesses. If a required record cannot be updated, state the specific limitation and next action.
- Project-specific journal conventions govern this workflow. If another journaling tool or skill already recorded the same outcome, do not create a second journal or entry. Explicit user instructions take precedence.
- This workflow does not authorise commits, pushes, messages, external tracker mutations, or scheduled automations. Preserve the user's existing authorisation scope.
