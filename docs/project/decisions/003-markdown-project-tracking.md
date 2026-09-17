# 003 — Markdown project tracking

Date: 2026-09-13  
Status: Accepted

## Context

Project context must survive coding sessions without duplicate status across tools or sibling repositories.

## Decision

Keep canonical project-wide Markdown under backend docs/project, with a repository README linking to it. Task records initially live in backlog.md. Use the project-management skill and project AGENTS.md for affected-document updates and journaling after meaningful work. Every journal entry identifies the LLM model and coding agent.

## Alternatives

Linear, Notion and GitHub Projects were considered. A dedicated external tracker can be adopted later by migrating task ownership, not running two trackers.

## Consequences and follow-up

Keep specifications, decisions, task status and history in their designated files. Project instructions stay scoped to NEMLab; frontend instructions must link back to canonical docs.

## Acceptance source

User requested the documentation guide, creation of the skill, moving docs into nemlab, per-entry model/agent metadata, and initial planning documents. Recorded 2026-09-13.

## References

[Documentation guide](../documentation-guide.md), [NEM-001](../backlog.md#nem-001).
