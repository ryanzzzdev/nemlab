# NEMLab

NEMLab explores Australia's National Electricity Market through historical analysis and experiments. BatteryLab compares simulated battery trading strategies; GridReplay helps visitors investigate notable market periods.

This is the backend project and the home of shared project documentation. The planned Java/Spring Boot backend has separate API and worker applications. The frontend will live in a separate repository.

## Project documentation

- [Roadmap and milestone progress](docs/project/roadmap.md)
- [Backlog and next work](docs/project/backlog.md)
- [Architecture](docs/project/architecture.md)
- [Blockers and open questions](docs/project/blockers.md)
- [Data foundation](docs/project/features/data-foundation.md)
- [BatteryLab](docs/project/features/batterylab.md)
- [GridReplay](docs/project/features/gridreplay.md)
- [Admin](docs/project/features/admin.md)
- [Decision records](docs/project/decisions/)
- [Documentation workflow](docs/project/documentation-guide.md)
- [Work journal](docs/project/journal/)
- [Original project ideas](docs/summaries/nemlab-project-ideas.md)

## Development setup

This folder currently contains documentation only. The backend Git repository is initialised. Build files, application modules, database setup, and run commands will be added during implementation. No OE credentials are needed to read the plan. Future credentials belong in local configuration or a secret store, never in committed documents or samples.

Read [AGENTS.md](AGENTS.md) before working on this project.
