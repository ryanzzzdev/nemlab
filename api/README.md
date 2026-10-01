# API: stored-price reads, simulations and protected operator controls

`nemlab_api` is the FastAPI application. Public startup health lives at
`/actuator/health` (always on). Every feature router mounts only when its flag
is enabled — disabled routes return a plain 404, and enabled features fail
startup fast without database credentials or a migrated schema. The API never
fetches OE data itself and does not need an OE key.

## Run it

```sh
set -a; . ./.env; set +a
uv run nemlab-api        # or: uv run python -m nemlab_api.main
```

`SERVER_ADDRESS`/`PORT` select the listener (default `127.0.0.1:8080`).
Container: `docker build --target api -t nemlab-api .` then
`docker run -p 127.0.0.1:8080:8080 -e SERVER_ADDRESS=0.0.0.0 nemlab-api`.

## Feature flags

| Flag | Surface | Also requires |
| --- | --- | --- |
| `NEMLAB_DATA_ENABLED` | `GET /api/v1/prices/{region}/coverage`, `GET /api/v1/prices/{region}/{day}` | `NEMLAB_DB_*`, migrated schema |
| `NEMLAB_ADMIN_ENABLED` | `POST/GET /api/admin/v1/price-refreshes*` bearer-protected operator routes | `NEMLAB_DB_*`, `NEMLAB_ADMIN_OPERATOR`, `NEMLAB_ADMIN_TOKEN` (43–128 chars) |
| `NEMLAB_SIMULATION_API_ENABLED` | `POST /api/v1/simulations`, `GET …/{id}`, `GET …/{id}/result` | `NEMLAB_DB_*` |

The flag names, envelopes, headers and status codes are frozen by
`api/contracts/openapi.json`; `node api/contracts/verify.mjs` validates live
captures written by `api/tests/test_contract_captures.py`.

## Behaviour notes

- Prices are decimal strings; incomplete days report `MISSING`/`SOURCE_NULL`
  gaps and are never filled. Simulation eligibility requires complete coverage.
- Submitting a simulation for an eligible but unfetched day enqueues a bounded,
  deduplicated visitor refresh (`visitor-price-v1:`) and returns 409
  `PRICE_REFRESH_PENDING`; repeated polls deduplicate, and visitor submissions
  are capped independently of the operator queue.
- Simulation results are immutable: reopening a job returns the stored
  projection and never recomputes. Public views never expose claim tokens,
  lease fields or internal diagnostics beyond a whitelisted failure code.
- Errors carry a stable `code`; storage failures map to 503
  `STORAGE_UNAVAILABLE` with no internals.

See [running locally](../docs/project/running-locally.md) for the full setup
walkthrough and [infrastructure/README.md](../infrastructure/README.md) for
migrations.
