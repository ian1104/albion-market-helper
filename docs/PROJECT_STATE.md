# Albion Market Helper — Project State

## CURRENT PHASE

**Phase 23-T.3 — Backend ↔ Frontend Integration Verification**

**STATUS: IN PROGRESS / NOT FULLY VERIFIED**

## CURRENT HEAD SHA

Current GitHub `main` HEAD at the start of Phase 23-T.3 verification:

`2b5004a1f49768871e610ad8865a8c7d6318b30e`

This is a documentation-only continuation after application commit `d15f10bd4b91053b79993cd8842f37bd9950b085`.

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

## PHASE 23-T.3 SOURCE INSPECTION

The current `main` source was inspected before any modification.

Confirmed frontend market path:

`Market.jsx → api.market() → /api/market/prices + /api/market/analysis + /api/market/history + /api/market/spread`

The frontend also uses:

`/api/items/{item_id}`
`/api/items/{item_id}/market`
`/api/items/{item_id}/history`
`/api/items/{item_id}/opportunities`

Confirmed backend routes exist for all of the above paths.

Confirmed response-shape compatibility at source level:

- `/api/market/prices` returns an array; frontend uses the first row as `current`.
- `/api/market/analysis` returns an analysis object.
- `/api/market/history` returns an array; frontend consumes it as history.
- `/api/market/spread` is optional in the frontend and does not cause market loading failure when unavailable.
- `/api/items/{item_id}/market` returns `cities`; frontend consumes `marketResponse.cities`.
- `/api/items/{item_id}/history` returns `history`; frontend consumes `historyResponse.history`.
- `/api/items/{item_id}/opportunities` returns `opportunities`.

Confirmed CORS source configuration:

```text
allow_origins=["*"]
allow_credentials=False
allow_methods=["*"]
allow_headers=["*"]
```

### Important integration finding

`frontend/src/services/api.js` uses:

```text
import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
```

No Vite proxy configuration was found in the current repository source inspection.

Therefore, source-level evidence strongly suggests a Codespaces/browser deployment risk: when the browser is not running on the same host as FastAPI, `127.0.0.1:8000` refers to the browser client's localhost rather than the Codespace backend. This is a **strongly suspected cause** of the historical `시장의 데이터를 불러오지 못했습니다.` symptom, not a runtime-confirmed root cause.

## VERIFIED FEATURES

Existing deterministic CI evidence for application commit `d15f10bd4b91053b79993cd8842f37bd9950b085` remains valid:

- SQLite concurrency regression: PASS — 3 passed.
- Python compileall: PASS.
- Full pytest: PASS — 99 passed, 1 warning, 3.35s.
- Frontend dependency installation: PASS.
- Frontend production build: PASS.
- Exact execution SHA match: PASS.

These results verify build/regression behavior, not browser-level Backend ↔ Frontend integration.

## PHASE 23-T.3 VERIFICATION MATRIX

| Component | Current result |
|---|---|
| Frontend API URL | SOURCE VERIFIED; Codespaces risk identified |
| Frontend endpoint | SOURCE VERIFIED |
| FastAPI endpoint | SOURCE VERIFIED |
| FastAPI → service | SOURCE VERIFIED for market analysis path |
| Service → SQLite | SOURCE VERIFIED; runtime not re-executed in this phase |
| CORS / proxy | CORS SOURCE PASS; proxy NOT FOUND / NOT VERIFIED |
| Backend HTTP response | NOT TESTED in this phase |
| Frontend receives JSON | NOT TESTED |
| Frontend renders market data | NOT TESTED |
| Test-data E2E | NOT TESTED |
| Real AODP → UI path | NOT TESTED |

## UNVERIFIED FEATURES

- No fresh browser/network capture was available during this verification.
- No fresh local FastAPI runtime was executed during this phase.
- No fresh React/Vite dev-server execution was executed during this phase.
- No actual browser rendering of market data was observed.
- No test-data SQLite → FastAPI → React E2E run was observed.
- The historical Codespaces failure has not been reproduced with request URL, HTTP status, backend log, and browser rendering evidence.

## KNOWN ISSUES

### Historical CI failure — not current verification

Run `33500437389` executed at `5bbc7e69af39dd940fcc6360b9dda51ef95dfee5`, not the deterministic verification target. It reported `97 passed / 2 failed`.

### Historical Termux runtime error

```text
OperationalError:
index idx_market_price_history_lookup already exists
```

This remains historical evidence. The current deterministic SQLite concurrency regression passed.

### Current integration risk

The frontend API fallback is hard-coded to `http://127.0.0.1:8000`, while no Vite proxy configuration was found. This is compatible with a same-machine local browser/backend setup but is a significant Codespaces/browser-hosting risk.

### Current warnings

- GitHub Actions Node.js 20 deprecation warnings for checkout/setup actions.
- One Starlette/httpx TestClient deprecation warning in pytest.
- One Vite CSS minification warning during production build.

## CURRENT RISKS

- Backend ↔ Frontend runtime integration is not yet execution-verified.
- The Codespaces localhost API-base issue is strongly suspected but not proven as the historical failure's root cause.
- CI build success must not be treated as browser integration success.

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

## LAST RUNTIME RESULT

Historical Phase 23-T Termux validation remains the latest recorded live runtime evidence:

- FastAPI responsiveness maintained for approximately 56 minutes.
- East NATS connection/subscription maintained.
- Real AODP NATS messages received, parsed, and persisted to SQLite.
- More than 5,900 messages/orders observed.
- SQLite `PRAGMA integrity_check` returned `ok`.

No live runtime was modified during this Phase 23-T.3 source inspection.

## NEXT EXACT STEPS

1. Obtain an actual executable environment containing the current `main` source and run the backend plus frontend.
2. Capture the browser Network request made by `api.market()` and its HTTP status/response.
3. Verify the browser can reach the FastAPI host rather than its own `127.0.0.1:8000`.
4. Seed or use representative market data and verify SQLite → FastAPI → React rendering.
5. If failure occurs, capture request URL, status, backend log, JSON response, and frontend parsing error before changing code.
6. Only after runtime evidence identifies a real defect should a minimal application change be considered.

## DO NOT DO

- Do not mark Backend ↔ Frontend integration PASS from source inspection alone.
- Do not mark frontend PASS merely because `npm run build` succeeds.
- Do not mark E2E PASS merely because pytest succeeds.
- Do not change `api.js`, Vite configuration, or backend routes solely from the Codespaces hypothesis without runtime confirmation.
- Do not stop/restart a live Termux server without explicit approval.
- Do not delete/reset the runtime database without explicit approval.
- Do not weaken regression assertions.
- Do not perform unrelated refactors.
