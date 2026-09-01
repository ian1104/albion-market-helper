# Albion Market Helper — Roadmap

This document describes planned or ongoing work. It is not a statement that every listed phase is currently implemented or verified.

## Status vocabulary

- **PLANNED** — intended future work; implementation not established by the current repository state.
- **IN PROGRESS** — active work in the current development cycle.
- **IMPLEMENTED** — implementation exists; fresh verification may still be pending.
- **VERIFIED** — implementation has current, relevant execution evidence.
- **BLOCKED** — work cannot currently be completed because a required environment, dependency, or external condition is unavailable.

## Current phase

### Phase 23-T.2 — GitHub Actions Automated Verification
**Status: COMPLETED / VERIFIED**

The deterministic verification workflow was executed successfully against exact commit SHA `d15f10bd4b91053b79993cd8842f37bd9950b085`.

Run `33519639248` verified:

- SQLite concurrency regression: PASS (3 passed).
- Python compileall: PASS.
- Full Python regression: PASS (99 passed, 1 warning, 3.35s).
- Frontend dependency install: PASS.
- Frontend production build: PASS.
- Execution SHA matched the verification target SHA.

### Phase 23-T.1 — SQLite initialization/concurrency regression
**Status: VERIFIED through Phase 23-T.2 deterministic CI**

The repository contains synchronized, path-aware initialization and migration/index lifecycle handling, with regression coverage for concurrent initialization, repeated initialization, and concurrent liquidity persistence. The current implementation was exercised by the dedicated SQLite concurrency regression in Run `33519639248`.

## Completed implementation areas

### Market data foundation
**Status: IMPLEMENTED**

- Current-price persistence/querying.
- Append-only historical snapshots.
- Server isolation for `east`, `west`, and `europe`.
- AODP REST collection.

### Market analysis
**Status: IMPLEMENTED**

- Price statistics.
- Trend and spread analysis.
- Historical market analysis surfaces.

### Arbitrage
**Status: IMPLEMENTED**

- Arbitrage opportunity calculation.
- Configurable gross/net profit model.
- Data freshness handling.
- Backend calculation ownership.

### Liquidity and order lifecycle
**Status: IMPLEMENTED**

- Provider/adapter boundary for liquidity.
- Executable quantity constrained by real available quantities.
- Depth-weighted execution price and slippage.
- Observational order lifecycle: `ACTIVE`, `EXPIRED`, `STALE`, `UNKNOWN`.
- Separate order observations.
- AODP NATS ingestion with server isolation.

### Strategy/business aggregation
**Status: IMPLEMENTED**

- Strategy registry and common strategy contract.
- Arbitrage strategy adapter.
- Crafting strategy using normalized recipe/production-rule data when inputs exist.
- Strategy engine with capital/risk filtering and ranking.
- Strategy-neutral `BusinessOpportunity`.
- Business Dashboard consuming normalized backend opportunities.

### Phase 20 live collector work
**Status: IMPLEMENTED; LIVE VERIFICATION IS EVIDENCE-SPECIFIC**

- Canonical marketplace mappings in the adapter.
- Persistent NATS consumer behavior including reconnect/backoff, malformed-message isolation, order persistence, observation history, and graceful shutdown.
- Regression coverage for restart recovery/server isolation.
- Bounded live observation workflow.

## Phase 23-T workstream

### Deterministic CI verification
**Status: VERIFIED**

Workflow: `Phase 23-T.1 Automated Verification`

Run: `33519639248`

Execution SHA: `d15f10bd4b91053b79993cd8842f37bd9950b085`

The workflow uses exact-SHA checkout and separates deterministic regression from live NATS observation by setting `AODP_NATS_ENABLED=false` for Python jobs.

## Warnings retained

The successful run emitted non-fatal warnings:

- GitHub Actions Node.js 20 deprecation warnings for `actions/checkout@v4`, `actions/setup-python@v5`, and `actions/setup-node@v4`.
- One pytest `StarletteDeprecationWarning` concerning `httpx` with `starlette.testclient`.
- One Vite CSS minification warning: `Expected ":" [css-syntax-error]`.

These did not change the successful conclusion of Run `33519639248`.

## Historical evidence

Historical CI Run `33500437389` at SHA `5bbc7e69af39dd940fcc6360b9dda51ef95dfee5` reported `97 passed / 2 failed`. It is retained as historical evidence and is not the current deterministic verification result.

Historical Termux runtime validation reported sustained FastAPI responsiveness, East NATS connectivity/subscription, real message receipt/parsing/persistence, more than 5,900 messages/orders, and SQLite integrity check `ok`. It also observed `idx_market_price_history_lookup already exists`; the exact thread interleaving was not captured.

## Future work

### Improved live market-data validation
**Status: PLANNED**

- Repeatable bounded live REST/NATS validation.
- Explicit separation of connectivity, message receipt, parsing, persistence, and application responsiveness evidence.

### Production hardening
**Status: PLANNED**

- Continue tightening lifecycle, persistence, error isolation, and observability based on reproduced failures rather than speculative refactoring.

### Frontend/product refinement
**Status: PLANNED**

- Continue improving Business Dashboard usability, filtering, ranking presentation, and market-analysis workflows without moving business calculations into the frontend.

### Additional strategy modules
**Status: PLANNED**

- Add independently registerable business strategies only when their data requirements and calculation rules are defined and implemented.

## Scope rules

- Roadmap entries do not imply implementation unless marked accordingly.
- A feature is not VERIFIED merely because source code exists.
- Fixture PASS is not LIVE PASS.
- Historical runtime evidence is not current runtime evidence.
- Historical CI is not current CI.
- No Phase should be expanded into unrelated refactoring without an explicit project decision.
