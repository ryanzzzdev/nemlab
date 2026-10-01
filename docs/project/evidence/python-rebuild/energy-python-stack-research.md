# Energy-sector Python stack research

Researched: 2026-10-01. Task: [NEM-081](../../backlog.md#nem-081). Outcome: retain FastAPI/PostgreSQL; adopt SQLAlchemy 2 Core over Psycopg 3; retain separate durable worker and current solver plan.

## Method and limits

Targeted public job-posting searches across Australia, USA, EU and UK for Python backend, energy trading, batteries, optimisation and energy-data platforms. Searches included both framework-neutral role/company queries and FastAPI/Django queries. Prefer employer sites and employer-controlled ATS pages; collapse repeat roles/mirrors from the same company rather than treating them as independent market votes. Exclude generic AI companies merely using the word energy, candidate CVs, search-result totals, and hardware-only roles from web-framework selection.

This is a qualitative convenience sample, biased by search visibility, English-language postings and technology terms. It establishes that stacks are used/requested by relevant employers, not relative market share, hiring volume, or that most energy software is Python. A missing technology in an advert does not establish absence from the employer's stack. Job pages can be stale; crawled dates are not posting dates. Availability and application eligibility were not independently verified.

Evidence grades: **direct** = readable employer/ATS page; **indexed primary** = employer ATS content available in search indexing, but opening returned a JavaScript shell; **historical indexed** = indexed employer ATS text, now unavailable when opened. No secondary-only listing determines the final stack.

## Employer/role sample

| Geography | Employer and role | Explicit technology / work signal | Evidence quality |
| --- | --- | --- | --- |
| Australia, Melbourne | [Kraken — Software Engineer II (Python/Django)](https://jobs.ashbyhq.com/krakentech/6d286b5a-874e-4484-b401-70ed53b0dfb9) | Python, Django, GraphQL, Celery, PostgreSQL; utility domain modelling | Indexed primary; page opened as JS shell |
| Australia, Melbourne | [Kraken — Senior Software Engineer, Client Engineering](https://jobs.ashbyhq.com/krakentech/f47c15ef-c002-4efd-8022-dc0538cbced9) | Same backend family; AWS EKS, Terraform, CI/CD and observability | Indexed primary; corroborates the same employer, not an extra independent vote |
| Australia, Melbourne | [Powerline — Senior Software Engineer, Australia](https://jobs.ashbyhq.com/powerline/4c721307-bb99-4cff-87ce-9d7d5ad25cfb) | Python, APIs, SQL/NoSQL, distributed systems, market-data pipelines and battery optimisation; no named web framework | Indexed primary; use as domain/engineering evidence, not FastAPI evidence |
| USA, New York | [Scale Microgrid Solutions — Sr Software Engineer](https://jobs.lever.co/ScaleMicrogridSolutions/68b3a663-c80e-4cc8-b4a6-e0cde42ba48d) | FastAPI, PostgreSQL, React, Python; LP/MILP with Pyomo and HiGHS/Gurobi; time-series and messaging | Direct; particularly close to NEMLab's optimisation/data/API shape |
| USA, Atlanta | [Joulea — Senior Software Engineer, Backend & MLOps](https://www.joulea.com/careers/senior-software-engineer) | FastAPI, PostgreSQL, React, AWS, Docker, Terraform, Kubernetes; energy-model/data workflows | Direct; building-energy rather than electricity-market domain |
| USA employer; role location not verified | [Form Energy — Staff Software Engineer, Data Platform](https://jobs.ashbyhq.com/formenergy/d9278f03-01ce-41aa-a749-e4264d6b56cd?embed=js) | Python/SQL, FastAPI or Flask, dbt, Dagster, PySpark; lab/factory/field data | Indexed primary; adjacent data-platform role, not a pure backend-framework preference |
| EU, Berlin, Germany | [trawa — Backend Engineer, Trading & Asset Optimization](https://jobs.ashbyhq.com/trawa/ddf52300-2d5f-47cc-b49f-7fcd3626ab5b) | Explicit production stack: Python, FastAPI, Pydantic, SQLAlchemy, AWS, Terraform | Indexed primary; especially relevant trading/asset-optimisation role |
| EU, Brno, Czechia | [Wattstor — Python developer, Energy Optimization Platform](https://wattstor.jobs.personio.com/job/2635039) | FastAPI, PostgreSQL/InfluxDB, Docker, AWS (including ECS/SQS); testing and observability | Direct; batteries/renewables optimisation platform |
| UK, Oxford | [Habitat Energy — Software Engineer](https://jobs.workable.com/view/ptvg2mkNrUA8Q2Mi9oTaAK/hybrid-software-engineer-in-oxford-at-habitat-energy) | Python, API frameworks such as FastAPI/Django, ideally SQLAlchemy; battery trading/operations | Historical indexed: open returned HTTP 410. Supporting historical signal only, not an asserted live vacancy |

Australia additionally surfaced a recruiter listing for an unnamed energy platform with FastAPI (or Django), SQLAlchemy and AWS. It was available through mirrors rather than a verified named employer, so it is excluded from the decision's primary evidence. Reposit's Python/Linux controller role illustrates the separate hardware/control career track and does not choose our web framework. Repeated Kraken regional listings should not inflate Django prevalence.

## Interpretation

1. **Two relevant families are visible.** Kraken provides strong evidence for Django/Celery/PostgreSQL in utility platforms. Independent NEMLab-like optimisation/data employers (Scale, trawa, Wattstor, Joulea) explicitly mention FastAPI. This is evidence of fit, not a claim that FastAPI wins an industry-wide popularity contest.
2. **Python and SQL plus operational reliability transfer broadly.** Domain modelling, tests, time-series correctness, model integration, retries and observability are recurring requirements. Powerline is a useful Australian example where those skills matter without naming a framework.
3. **SQLAlchemy deserves a place in our rebuild.** trawa explicitly uses it; Habitat's historical listing prefers it. This is a relevant ecosystem skill and gives a standard connection/transaction layer while retaining our SQL. It does not establish that employers specifically prefer SQLAlchemy Core over its ORM; Core is our design choice.
4. **Cloud/container literacy matters.** AWS and containers appear across several sources. Keep Docker packaging/local checks as a deliverable; AWS is a sensible learning/deployment candidate, not an authorised hosting purchase or a settled production provider. Terraform belongs to the later hosting decision.
5. **Optimisation is a separate skill from HTTP.** Scale explicitly asks for Pyomo and HiGHS/Gurobi. That supports HiGHS and learning mathematical modelling, but does not prove SciPy or Pyomo is the most common across the industry. Preserve NEMLab's small existing LP and independent certificate via SciPy/HiGHS for parity; consider Pyomo when the model grows to broader dispatch/MILP. Do not add a second production solver merely for a résumé keyword.

## Final stack selection

| Area | Rebuild choice | Evidence versus engineering judgment |
| --- | --- | --- |
| API | FastAPI + Pydantic v2 + Uvicorn | FastAPI/Pydantic have directly relevant employer evidence; server/version choice is implementation judgment |
| Persistence | PostgreSQL + SQLAlchemy 2 Core + Psycopg 3 driver | PostgreSQL/SQLAlchemy have employer evidence; Core/driver and explicit SQL preserve the existing design |
| Migrations | Alembic | Compatible tooling choice, not established by this hiring sample |
| Execution | Separate Python worker; PostgreSQL durable queue; isolated fetch/solver children | Existing correctness/operability needs; do not claim this custom queue is the industry's preferred queue |
| Numerical work | NumPy/SciPy + HiGHS | HiGHS appears in relevant roles; SciPy interface is selected for the current bounded LP and verification |
| Delivery | Docker/Compose, CI, logs/health checks | Job evidence supports containers/reliability; exact CI/tooling remains project-specific |
| Quality/tooling | pytest, Hypothesis, Ruff, mypy, uv; CPython 3.13 baseline | Project engineering selections; this sample does not rank their popularity or determine exact versions |

Django/Celery would be a good career-focused choice if Kraken/utility customer platforms were the primary target. NEMLab's current focus is battery simulation, market data and replay, so choose FastAPI. Celery, Redis, Kafka, Kubernetes, Airflow and Pyomo are useful in relevant roles, but only add them to this project when a feature or operating constraint calls for them. Maintain the user's four modules and two application processes.

## Concrete change from the first plan

Replace standalone Psycopg pool ownership with one SQLAlchemy Engine/pool per application process using the Psycopg 3 driver. Infrastructure owns Core statements and parameterised SQL, short explicit transaction contexts, and repository result mapping; ORM entities do not enter the domain or HTTP DTOs. Do not maintain parallel SQLAlchemy and psycopg_pool pools. Preserve locks, claims, trigger semantics and transaction fencing unchanged. SQLAlchemy Core supports explicit connections/transactions and textual SQL: [official engine/connection documentation](https://docs.sqlalchemy.org/en/20/core/connections.html).

NEM-067 provisions the stack; NEM-070/071/072/075 verify persistence parity through it; NEM-078 adds independently runnable API/worker container targets with measured native dependency packaging. The remaining parity scope and ordering are unchanged. Exact dependency versions and runtime support still need bootstrap validation.
