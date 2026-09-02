# Albion Market Helper — Project State

## CURRENT PHASE

**Phase 23-T.3 — Backend ↔ Frontend Integration Verification**

**STATUS: VERIFIED / PASS**

## CURRENT HEAD / VERIFICATION BASELINE

The Phase 23-T.3 application verification target was GitHub `main` SHA:

`289843227fa74f49e77f9174a22c27532a5eb8d0`

This SHA contains the complete application change for the Phase 23-T.3 frontend API integration fix. Documentation closeout commits may advance `main` beyond this application verification SHA; the SHA above is the exact application revision against which the reported verification was performed.

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
- StrategyRegistry / StrategyEngine / BusinessOpportunity aggregation.
- React/Vite frontend Business Dashboard plus market-analysis and arbitrage views.

## PHASE 23-T.3 IMPLEMENTED

The application change is limited to two frontend files:

- `frontend/src/services/api.js`
- `frontend/vite.config.js`

API base behavior:

```js
const API = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? '' : 'http://127.0.0.1:8000');
```

Development Vite proxy:

```text
/api/* → http://127.0.0.1:8000/api/*
```

This makes development browser requests same-origin while preserving the explicit local FastAPI fallback outside development. Backend API routes, CORS, dependencies, tests, and business logic were not changed.

## VERIFIED FEATURES

### Local verification at application SHA `289843227fa74f49e77f9174a22c27532a5eb8d0`

- Full pytest: **99 passed, 1 warning, 2.21s**.
- Python compileall: **PASS** — `python -m compileall -q .` exited successfully with no output.
- Frontend production build: **PASS** — Vite `5.4.21`, 42 modules transformed, build completed successfully in 1.33s.

### Codespaces Browser ↔ Backend integration

Actual Browser Network evidence:

```text
/api/sources?server=east → 200 OK
```

Request URL used the forwarded frontend origin:

```text
https://animated-bassoon-7xqw4xqq7jvhxxgg-5173.app.github.dev/api/sources?server=east
```

The browser did not directly call `127.0.0.1:8000`.

Backend logs confirmed corresponding successful requests:

```text
GET /api/sources?server=east HTTP/1.1 200 OK
GET /api/strategies HTTP/1.1 200 OK
GET /api/sources?server=europe HTTP/1.1 200 OK
GET /api/opportunities?server=east&sort=profit&limit=12 HTTP/1.1 200 OK
GET /api/sources?server=west HTTP/1.1 200 OK
```

Verified runtime path:

```text
Browser
  ↓
Frontend :5173
  ↓ /api/...
Vite proxy
  ↓
127.0.0.1:8000
  ↓
FastAPI
  ↓
200 OK
```

### GitHub Actions

Representative successful CI run at the exact application verification SHA:

```text
Run ID: 33615308345
Execution SHA: 289843227fa74f49e77f9174a22c27532a5eb8d0
Result: success
```

Confirmed successful stages include:

- Python syntax — PASS
- Full pytest — PASS
- Frontend dependencies — PASS
- Frontend production build — PASS
- NATS validation — PASS
- Live NATS ingestion — PASS
- FastAPI runtime smoke test — PASS

Separate runtime-validation Run `33615308321` also completed successfully.

## VERIFICATION MATRIX

| Component | Result |
|---|---|
| Frontend development API base | VERIFIED |
| Vite `/api` proxy | VERIFIED |
| Browser → Frontend | VERIFIED |
| Frontend → FastAPI through proxy | VERIFIED |
| `/api/sources` | 200 OK |
| `/api/strategies` | 200 OK |
| `/api/opportunities` | 200 OK |
| Backend corresponding GET logs | VERIFIED |
| Local pytest | 99 passed |
| Python compileall | PASS |
| Frontend production build | PASS |
| Exact-SHA GitHub Actions | PASS |

## UNVERIFIED / OUT OF SCOPE

- This Phase does not establish a new full real-AODP-to-React data-content validation beyond the existing runtime/CI evidence listed above.
- No new E2E framework was added.
- No backend, CORS, dependency, or business-logic changes were made.

## KNOWN WARNINGS

- Pytest: one `StarletteDeprecationWarning` because using httpx with `starlette.testclient` is deprecated. This is non-fatal and unrelated to the Phase 23-T.3 API proxy change.
- Frontend build: one non-fatal Vite CSS minification warning. This is unrelated to the Phase 23-T.3 API proxy change and was not modified.
- GitHub Actions may retain Node.js 20 deprecation warnings for existing actions.

Warnings are not recorded as failures.

## HISTORICAL EVIDENCE / ISSUES

Historical Termux runtime validation remains evidence of:

- approximately 56 minutes of FastAPI responsiveness,
- East NATS connection/subscription,
- real AODP NATS messages received, parsed, and persisted,
- more than 5,900 messages/orders observed,
- SQLite `PRAGMA integrity_check` returning `ok`.

Historical runtime error retained for context:

```text
OperationalError:
index idx_market_price_history_lookup already exists
```

The exact thread interleaving was not captured. The current deterministic SQLite concurrency regression passed.

## CURRENT RISKS

No Phase 23-T.3 blocker remains based on the completed verification evidence. The retained warnings above are non-fatal and unrelated to the Phase 23-T.3 integration fix.

## LAST TEST RESULTS

```text
Application verification SHA: 289843227fa74f49e77f9174a22c27532a5eb8d0
pytest -q: 99 passed, 1 warning in 2.21s
python -m compileall -q .: PASS
cd frontend && npm run build: PASS
```

## LAST CI RESULT

```text
Run ID: 33615308345
Execution SHA: 289843227fa74f49e77f9174a22c27532a5eb8d0
Result: success
```

Separate runtime-validation Run `33615308321`: success.

## LAST RUNTIME RESULT

Codespaces Browser ↔ FastAPI integration was directly verified through the frontend forwarded origin and backend HTTP logs. `/api/sources`, `/api/strategies`, and `/api/opportunities` requests returned 200 OK through the Vite development proxy path.

## NEXT EXACT STEPS

Phase 23-T.3 is closed. Do not perform additional work under this phase. Future work must follow `docs/ROADMAP.md` and begin by re-checking the actual GitHub `main` HEAD and project-state documents.

## DO NOT DO

- Do not expand Phase 23-T.3 into unrelated feature development or refactoring.
- Do not modify backend routes, CORS, dependencies, or tests solely to revisit this closed phase.
- Do not delete or commit the locally observed untracked lockfiles merely for cleanup.
- Do not stop/restart a live Termux server without explicit approval.
- Do not delete/reset the runtime database without explicit approval.
- Do not weaken regression assertions.
