# 019 — Rebuild the backend in Python

Date: 2026-10-01  
Status: Accepted; implementation pending.

## Context and acceptance source

The user chose Python to align the project with their energy-industry software career direction, requested a complete rebuild to current Java functionality, retained API/worker separation and Git history, and delegated Python stack selection to the agent. This decision records that direction; it does not assert an independently researched industry employment statistic.

## Decision

Use the existing `nemlab` repository. Preserve Java under `reference/java/`, keep canonical documentation and `api/contracts/` in place, and build Python core, infrastructure, API and worker packages in the existing module directories. Select CPython 3.13, uv, FastAPI/Uvicorn/Pydantic, PostgreSQL with SQLAlchemy 2 Core/Psycopg 3 and explicit SQL, Alembic and SciPy/HiGHS. Keep the PostgreSQL durable queue and separate supervised worker rather than introducing Redis/Celery. Exact patch pins, solver equivalence, migration compatibility and process limits require implementation evidence.

The [rebuild plan](../python-backend-rebuild.md) defines baseline, source mapping, schema adoption, numerical/version compatibility, tasks and cutover gates. Stack selection is accepted under the user's delegated authority; validation is not yet complete.

## Alternatives considered

- Retain Java or add only a Python solver: does not fulfil the complete-backend rebuild request.
- Django/ORM-centric rewrite: possible, but introduces unnecessary persistence and HTTP changes for the existing explicit SQL/contracts.
- SQLAlchemy ORM plus Celery/Redis: a wholesale ORM/queue redesign is unnecessary. After job-market research, use SQLAlchemy Core for active connections/transactions while retaining explicit SQL and the current durable queue.
- Delete Java, start a new repository, or relocate docs: loses convenient reference or breaks the requested continuity.
- Keep Flyway as the active migration runner: preserves migration machinery but retains Java in the active setup. Adopt the existing schema through verified Alembic baselining instead.

## 2026-10-01 evidence-based refinement

The user requested Australian and international energy-role research before finalising the stack. [NEM-081 findings](../evidence/python-rebuild/energy-python-stack-research.md) distinguish Django/Celery utility platforms from FastAPI optimisation/data-platform roles. Retain FastAPI and add SQLAlchemy 2 Core with a single Engine/pool per process over Psycopg 3. This refines the earlier direct-Psycopg/migration-only-SQLAlchemy choice under delegated authority. Add independently runnable Docker API/worker packaging to NEM-078. The research does not establish industry-wide rankings or choose exact package versions. Retain SciPy/HiGHS for bounded LP parity; Pyomo is a future modelling option.

## Consequences and supersession

Decision 004 is superseded for the future active runtime; its Java pins remain reference-build history. Decision 007's ojAlgo selection is superseded for new Python execution, while its ordered-window formulation and correctness obligations remain. Decision 002's repository/API-worker boundaries remain accepted; only its language choice is replaced. Java-specific tooling in decisions 005/008/009/016 is replaced by this decision for Python; their product, persistence, queue, isolation and immutable-result semantics remain requirements. Current Java code remains the implemented system until rebuild gates pass.

Keep old results and solver provenance; new Python runs use truthful solver/execution versions. Keep M5 beyond parity, preserve historical Done records, add NEM-065–080, and retain hosted CI/public launch gates. No implementation, file moves, commits or deployment are implied by this planning deliverable.
