# Albion Market Helper — Project State

## CURRENT PHASE

**Phase 23-T.2 — GitHub Actions Automated Verification Pipeline**

**STATUS: VERIFIED / PASS**

## CURRENT HEAD SHA

Verification target/application commit: `d15f10bd4b91053b79993cd8842f37bd9950b085`.

The documentation update advances `main`; Run `33519639248` verifies the exact application/CI commit above, not later documentation commits.

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

- Current market-price storage and querying.
- Append-only historical market snapshots.
- Price statistics, trend, and spread analysis.
- Arbitrage opportunity calculation.
- Configurable gross/net profit calculations.
- Data freshness handling.
- Liquidity-aware executable quantity, weighted execution price, and slippage calculation.
- Normalized liquidity order persistence and historical observations.
- Persistent AODP NATS consumer behavior including reconnect/backoff, malformed-message isolation, order upsert, observation history, and graceful shutdown.
- Server-isolated NATS ingestion for canonical `east`, `west`, and `europe`.
- Strategy abstraction and business-opportunity aggregation.
- FastAPI strategy/opportunity endpoints.
- React/Vite Business Dashboard and existing market-analysis/arbitrage views.
- Recipe/production-rule persistence and crafting opportunity safeguards.
- Phase 23-T.1 SQLite initialization synchronization and path-aware initialization logic.

## VERIFIED FEATURES

Current deterministic GitHub Actions evidence for `d15f10bd4b91053b79993cd8842f37bd9950b085`:

- SQLite initialization/concurrency regression: PASS — 3 passed.
- Python compileall: PASS.
- Full Python regression: PASS — 99 passed, 1 warning, 3.35s.
- Frontend dependency install: PASS.
- Frontend production build: PASS.
- Workflow checkout used the exact execution SHA `d15f10bd4b91053b79993cd8842f37bd9950b085`.
- The deterministic verification workflow completed successfully.
- The historical CI failures are not present in this current deterministic verification.

## UNVERIFIED FEATURES

- No fresh local execution outside GitHub Actions is recorded for this verification.
- Current live Termux runtime behavior was not re-executed during Phase 23-T.2.
- Exact runtime thread interleaving for the historical SQLite index exception remains unproven.
- Later documentation-only commits are not covered by Run `33519639248`.

## KNOWN ISSUES

### Historical CI failure — not current verification

Run `33500437389` executed at `5bbc7e69af39dd940fcc6360b9dda51ef95dfee5`, not the deterministic verification target. It reported `97 passed / 2 failed`:

1. `test_liquidity_status_and_summary_endpoints`: expected `enabled=False`, received `True`.
2. `test_liquidity_status_exposes_live_consumer_state`: `sqlite3.OperationalError: no such table: market_liquidity_orders`.

This remains historical information only.

### Historical Termux runtime error

During prior live validation:

```text
OperationalError:
index idx_market_price_history_lookup already exists
```

The server and NATS consumer reportedly continued operating afterward. Subsequent source changes addressed initialization/migration synchronization. The exact runtime interleaving was not captured with thread stacks.

### Current warnings

- GitHub Actions emits Node.js 20 deprecation warnings for `actions/checkout@v4`, `actions/setup-python@v5`, and `actions/setup-node@v4` on the current runner.
- Frontend Vite build emitted a CSS minification warning: `Expected ":" [css-syntax-error]` while still completing successfully.
- Python pytest emitted one `StarletteDeprecationWarning` concerning use of `httpx` with `starlette.testclient`.

These warnings did not fail the deterministic CI run.

## CURRENT RISKS

- The verified CI SHA is `d15f10bd...`; documentation commits now advance `main`, so future development must re-check the actual current HEAD.
- Live runtime behavior remains evidence-specific and is not replaced by deterministic CI.
- Action/runtime deprecation warnings should eventually be addressed, but they are not Phase 23-T.2 failures.

## LAST TEST RESULTS

Deterministic CI Run `33519639248` at SHA `d15f10bd4b91053b79993cd8842f37bd9950b085`:

```text
SQLite concurrency regression: 3 passed
Python compileall: PASS
Full pytest: 99 passed, 1 warning, 3.35s
Frontend dependency install: PASS
Frontend production build: PASS
```

## LAST CI RESULT

```text
Workflow: Phase 23-T.1 Automated Verification
Run ID: 33519639248
Execution SHA: d15f10bd4b91053b79993cd8842f37bd9950b085
Verification target SHA: d15f10bd4b91053b79993cd8842f37bd9950b085
SHA MATCH: YES
Overall: PASS
```

All three jobs completed successfully.

## LAST RUNTIME RESULT

Historical Phase 23-T Termux validation:

- FastAPI HTTP responsiveness maintained for approximately 56 minutes.
- East NATS connection maintained and subscription remained active.
- Real AODP NATS messages were received, parsed, and persisted to SQLite.
- Event-loop hang was not reproduced.
- More than 5,900 messages were received and more than 5,900 orders were persisted.
- SQLite `PRAGMA integrity_check` returned `ok`.
- Historical `idx_market_price_history_lookup already exists` occurred; server/consumer continued operating afterward.

No Termux server or runtime database was modified during Phase 23-T.2 CI verification.

## NEXT EXACT STEPS

1. Reconfirm the actual GitHub `main` HEAD after the documentation commit.
2. Treat Run `33519639248` / SHA `d15f10bd4b91053b79993cd8842f37bd9950b085` as the completed deterministic verification evidence.
3. Continue with the next roadmap phase from the actual current `main` HEAD, or perform a separately authorized bounded Termux runtime validation if live evidence is required.

## DO NOT DO

- Do not treat historical Run `33500437389` as current.
- Do not treat Run `33519639248` as coverage of later documentation-only commits.
- Do not weaken or delete regression assertions.
- Do not remove the Phase 23-T.1 concurrency regression tests.
- Do not perform unrelated refactors.
- Do not change NATS architecture during SQLite regression work.
- Do not stop/restart a live Termux server without explicit approval.
- Do not delete/reset the runtime database without explicit approval.
- Do not infer a specific runtime thread interleaving without captured evidence.
