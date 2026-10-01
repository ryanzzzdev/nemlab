# 007 — Ordered-window hindsight solver

Date: 2026-09-17  
Status: Superseded for the Python replacement by [decision 019](019-python-backend-rebuild.md); retained for the implemented Java reference

## Context

NEM-010 requires an open-source Java solver supported by correctness and runtime evidence. V1 specifies one charge window followed by one discharge window, with the same physical/cost constraints for fixed schedule and hindsight.

## Decision

Use **ojAlgo 57.3.0** for the exact ordered-window linear programme in `OrderedHindsight`. Keep it an implementation dependency; public types expose no ojAlgo classes. Pin and lock the dependency. Independently reconstruct/validate dispatch, recompute accounting and evaluate a dual upper bound. Report optimality only within the documented one-cent gap and time budget.

The [project](https://github.com/optimatika/ojAlgo) provides pure Java LP/QP/MIP solvers. The [published 57.3.0 POM](https://repo.maven.apache.org/maven2/org/ojalgo/ojalgo/57.3.0/ojalgo-57.3.0.pom) declares MIT licensing. The artifact ran successfully under our OpenJDK 25.0.4+7 build; no native library or separate service was required. Preserve MIT notices when dependencies are redistributed.

## Alternatives

A custom sorted-marginal algorithm could exploit these ordered windows, but a standard LP library plus explicit certificate keeps the model inspectable and gives room for later constraints. Native-backed solvers could support wider models; they were not benchmarked because this candidate met the bounded v1 gate without native packaging. Do not infer comparative performance superiority.

## Evidence and consequences

[Engine findings](../evidence/engine/findings.md) record the model proof, 47 passing tests, 15 full-day measurements, numerical conventions and actual abort probes. Ordered disjoint windows enforce exclusivity by construction; this LP must not be reused for unrestricted windows without a new formulation. No whole-day MIP is implemented.

Use five-second cooperative solve budgets and independent status checks. Worker-level hard termination, admission/concurrency limits and deployment resource validation remain NEM-013/NEM-020. Future numerical or scope changes require versioned contracts and fresh evidence.

## Acceptance source

Agent selection under the user's explicit instruction to proceed with NEM-010. It fulfils the agreed primary equal-window comparison; optional unrestricted hindsight remains deferred.

## References

[NEM-010](../backlog.md#nem-010), [contract](../features/battery-model-contract.md), [model decision](006-battery-model-contract.md).
