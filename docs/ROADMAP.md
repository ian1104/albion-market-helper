# Albion Market Helper — Roadmap

This document describes planned or ongoing work. It is **not** a statement that every listed phase is currently implemented or verified.

## Status vocabulary

- **PLANNED** — intended future work; implementation not established by the current repository state.
- **IN PROGRESS** — active work in the current development cycle.
- **IMPLEMENTED** — implementation exists in the repository; fresh verification may still be pending.
- **VERIFIED** — implementation has current, relevant execution evidence.
- **BLOCKED** — work cannot currently be completed because a required environment, dependency, or external condition is unavailable.

## Current phase

### Phase 23-T.1 — SQLite initialization/concurrency regression
**Status: IN PROGRESS**

Goals:

- Prevent concurrent SQLite initialization/migration races.
- Make initialization synchronization explicit and shared across `Database` instances in the same process.
- Make initialization caching aware of the database path.
- Avoid unnecessary migration/index rebuild work during normal repeated persistence.
- Preserve meaningful concurrency regression coverage.
- Verify the current HEAD with real pytest/compile/frontend execution and GitHub Actions.

Current repository evidence shows the synchronization and path-aware initialization implementation plus regression tests are already committed. Fresh execution of the current HEAD remains outstanding.

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

The repository's README describes these capabilities; fresh execution evidence must still be distinguished from historical runtime evidence.

## Phase 23-T.1 workstream

### Initialization synchronization
**Status: IMPLEMENTED; VERIFICATION PENDING**

- Shared `threading.RLock()`.
- `_initialized` state.
- `_initialized_path` state.
- Same-path initialization cache.
- Reinitialization after database path changes.

### Migration/index lifecycle
**Status: IMPLEMENTED; VERIFICATION PENDING**

- Migration detects schema/index-affecting changes.
- Historical price index rebuild is conditional on the relevant migration.
- Liquidity index rebuild is conditional on liquidity schema changes.
- Normal initialization still applies the declared schema safely.

### Regression coverage
**Status: IMPLEMENTED; VERIFICATION PENDING**

Current test coverage includes:

- concurrent initialization across multiple `Database` instances,
- repeated initialization idempotence,
- concurrent liquidity persistence without schema races,
- integrity/index checks after those operations.

## Planned verification sequence

### Current HEAD execution
**Status: BLOCKED until a usable repository execution environment is available**

1. `pytest -q tests/test_database_initialization_concurrency.py`
2. `pytest -q tests/test_liquidity.py tests/test_phase21_application_lifecycle.py`
3. `pytest -q`
4. `python -m compileall .`
5. Inspect frontend package configuration.
6. Run `npm install` and `npm run build` when dependencies/network are available.
7. If failures occur, diagnose from the exact traceback before changing code.
8. If code changes are necessary, rerun the complete regression sequence.
9. Confirm GitHub Actions results against the exact resulting commit SHA.

## Future work

The following are roadmap-level directions and should not be interpreted as current implementation status unless separately confirmed in the repository:

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

- Roadmap entries do not imply implementation.
- A feature is not `VERIFIED` merely because source code exists.
- Fixture PASS is not LIVE PASS.
- Historical runtime evidence is not current runtime evidence.
- Historical CI is not current CI.
- No Phase should be expanded into unrelated refactoring without an explicit project decision.
