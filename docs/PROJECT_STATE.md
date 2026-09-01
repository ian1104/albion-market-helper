# Albion Market Helper — Project State

## CURRENT PHASE

**Phase 23-T.1 — SQLite initialization/concurrency regression correction and verification**

Current work is verification/documentation. No application-code change is being made in this documentation step.

## CURRENT HEAD SHA

`3e0160a0c8220f98f26a62af92448d7955713ed2`

Verified against GitHub `main` on 2026-09-01.

## CURRENT ARCHITECTURE

Backend-first Albion Online market analysis application targeting Asia/East by default, with canonical server isolation for `east`, `west`, and `europe`.

Current pipeline:

`AODP → AlbionApiService / AODPNatsAdapter → normalized market data → SQLite → AnalysisService / Liquidity → StrategyEngine → FastAPI → React Business Dashboard`

Major layers:

- Python backend with FastAPI.
- SQLite persistence for current prices, historical snapshots, collection runs, liquidity orders, and order observations.
- AODP REST price collection.
- Optional persistent AODP NATS consumers for observational order-book/liquidity data.
- Market analysis and arbitrage services.
- Liquidity provider/adapter boundary using persisted normalized orders.
- StrategyRegistry / StrategyEngine / BusinessOpportunity abstraction for business-strategy aggregation.
- React/Vite frontend Business Dashboard plus existing market-analysis and arbitrage views.

## IMPLEMENTED FEATURES

The current repository README and source indicate the following implemented capabilities:

- Current market-price storage and querying.
- Append-only historical market snapshots.
- Price statistics, trend, and spread analysis.
- Arbitrage opportunity calculation.
- Configurable gross/net profit calculations.
- Data freshness handling.
- Liquidity-aware executable quantity, weighted execution price, and slippage calculation.
- Normalized liquidity order persistence with provenance, first/last seen, expiry, and lifecycle state (`ACTIVE`, `EXPIRED`, `STALE`, `UNKNOWN`).
- Separate historical liquidity-order observations.
- Persistent AODP NATS consumer behavior including reconnect/backoff, malformed-message isolation, order upsert, observation history, and graceful shutdown.
- Server-isolated NATS ingestion for canonical `east`, `west`, and `europe`.
- Strategy abstraction with `StrategyDefinition`, `BusinessStrategy`, `StrategyRegistry`, `ArbitrageStrategy`, `CraftingStrategy`, `BusinessOpportunity`, and `StrategyEngine`.
- FastAPI strategy/opportunity endpoints including `/api/strategies`, `/api/strategies/{strategy_id}`, and `/api/opportunities`.
- React Business Dashboard driven by backend strategy/opportunity results.
- Recipe/production-rule persistence layer; missing recipe or market inputs do not fabricate crafting opportunities.
- Phase 23 SQLite initialization synchronization and path-aware initialization logic:
  - shared `threading.RLock()` initialization lock,
  - `_initialized` state,
  - `_initialized_path` state,
  - same-path initialization caching,
  - reinitialization when the configured database path changes,
  - migration-aware index rebuilding rather than unconditional rebuild on every initialization.
- Phase 23-T.1 regression tests covering concurrent initialization, repeated initialization, and concurrent liquidity persistence.

## VERIFIED FEATURES

Only evidence actually available is listed here. Fixture/test verification and live runtime verification are kept separate.

- GitHub `main` currently points to `3e0160a0c8220f98f26a62af92448d7955713ed2`.
- The Phase 23-T.1 SQLite synchronization implementation and its regression tests are present in the current HEAD.
- Current Phase 23 workflow separates live collector execution from the Python regression step by disabling NATS for the latter.
- Historical Termux runtime validation reported successful FastAPI responsiveness, East NATS connectivity/subscription, real AODP NATS message receipt and parsing, SQLite persistence, continued event-loop responsiveness, more than 5,900 received messages/orders persisted, and SQLite `PRAGMA integrity_check = ok`. These are **historical runtime results supplied by the project handoff, not a runtime execution performed in this documentation step**.

## UNVERIFIED FEATURES

- A fresh local execution of the current HEAD's full pytest suite has not been performed in the current execution environment.
- A fresh execution of `tests/test_database_initialization_concurrency.py` against current HEAD has not been performed here.
- A fresh execution of `tests/test_liquidity.py` and `tests/test_phase21_application_lifecycle.py` against current HEAD has not been performed here.
- `python -m compileall .` has not been performed against current HEAD in the current execution environment.
- A fresh frontend `npm install` / `npm run build` has not been performed against current HEAD in the current execution environment.
- No current HEAD GitHub Actions run is presently available to establish a PASS/FAIL result for `3e0160a`.
- The exact runtime thread interleaving that produced the historical `idx_market_price_history_lookup already exists` exception was not captured with thread stacks.

## KNOWN ISSUES

### Historical CI failure — not current HEAD

GitHub Actions Run `33500437389` executed at commit `5bbc7e69af39dd940fcc6360b9dda51ef95dfee5`, not the current HEAD. It reported `97 passed / 2 failed`:

1. `test_liquidity_status_and_summary_endpoints`: `enabled=True` while the test expected `False`.
2. `test_liquidity_status_exposes_live_consumer_state`: `sqlite3.OperationalError: no such table: market_liquidity_orders`.

This run is historical information only and is **not** the current CI result for `3e0160a`.

### Historical Termux runtime error

During prior live validation, the following was observed:

```text
OperationalError:
index idx_market_price_history_lookup already exists
```

The server and NATS consumer reportedly continued operating afterward. The code-level race was subsequently addressed through synchronized initialization and migration/index lifecycle changes. However, the exact runtime interleaving was not captured, so the runtime causal chain is not considered conclusively proven at thread-stack level.

## CURRENT RISKS

- The current SQLite initialization implementation is code-reviewed against the repository, but its regression status on the current HEAD remains unverified until tests are actually executed.
- The current HEAD has no verified CI run available in the present inspection.
- The historical runtime index error demonstrates why initialization/migration concurrency must remain covered by regression tests.
- Live NATS behavior and fixture-based Python tests must continue to be treated as separate evidence classes.
- Local working-tree cleanliness cannot be established through the GitHub repository API alone; no claim of a clean local working tree is made here.

## LAST TEST RESULTS

**Current HEAD:** no fresh local test execution available in this environment.

Historical results must not be substituted for a current result.

The required next verification sequence is:

```text
pytest -q tests/test_database_initialization_concurrency.py
pytest -q tests/test_liquidity.py tests/test_phase21_application_lifecycle.py
pytest -q
python -m compileall .
frontend: npm install && npm run build
```

## LAST CI RESULT

**No verified CI run currently available for HEAD `3e0160a0c8220f98f26a62af92448d7955713ed2`.**

Historical Run `33500437389` / SHA `5bbc7e69af39dd940fcc6360b9dda51ef95dfee5` is recorded above only as historical context.

## LAST RUNTIME RESULT

Historical Phase 23-T Termux validation, as recorded by the project handoff:

- FastAPI HTTP responsiveness maintained for approximately 56 minutes.
- East NATS connection maintained.
- NATS subscription remained active.
- Real AODP NATS messages were received.
- Messages were parsed and persisted to SQLite.
- Event-loop hang was not reproduced.
- More than 5,900 messages were received and more than 5,900 orders were persisted.
- SQLite `PRAGMA integrity_check` returned `ok`.
- `idx_market_price_history_lookup already exists` occurred during live measurement; server/consumer continued running afterward.

These results are preserved as historical runtime evidence and are not claimed as a fresh run of the current HEAD.

## NEXT EXACT STEPS

1. Obtain an execution environment containing a checkout of current GitHub `main` at the latest HEAD.
2. Run the SQLite concurrency regression test.
3. Run the two related liquidity/lifecycle regression files.
4. Run the full `pytest -q` suite.
5. Run `python -m compileall .`.
6. Inspect frontend package configuration, then run `npm install` and `npm run build` if network/dependencies permit.
7. If a test fails, record the exact traceback and compare it with current code before making any change.
8. Only if a current-HEAD failure is reproduced, apply the smallest in-scope correction and rerun regression.
9. Confirm the resulting commit SHA and obtain a GitHub Actions run for that exact SHA.

## DO NOT DO

- Do not treat Run `33500437389` as a current HEAD failure.
- Do not report PASS or FAIL for tests that were not executed.
- Do not weaken or delete assertions to obtain green tests.
- Do not remove the Phase 23-T.1 concurrency regression tests.
- Do not perform unrelated refactors.
- Do not change NATS architecture as part of SQLite regression work.
- Do not stop/restart a live Termux server without explicit approval.
- Do not delete or reset the existing runtime database without explicit approval.
- Do not infer runtime thread interleaving that was not captured.
