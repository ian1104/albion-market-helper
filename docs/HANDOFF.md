# Albion Market Helper — Development Handoff

## PROJECT

Albion Market Helper — Albion Online market data collection, persistence, analysis, liquidity, strategy aggregation, FastAPI API, and React dashboard.

## CURRENT PHASE

Phase 23-T.3 — Backend ↔ Frontend Integration Verification

**STATUS: IN PROGRESS / NOT FULLY VERIFIED**

## CURRENT HEAD SHA

At the start of Phase 23-T.3 verification, GitHub `main` was:

`2b5004a1f49768871e610ad8865a8c7d6318b30e`

A documentation-only status update was subsequently committed. Before future development, re-check the actual `main` HEAD again.

## WORKING TREE STATUS

No local working-tree state can be established through the GitHub API.

Application source was not modified during this Phase 23-T.3 investigation. Documentation only was changed.

## WHAT WAS CONFIRMED

### Source-level integration

- `frontend/src/services/api.js` defines the API base as `import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'`.
- `api.market()` requests `/api/market/prices`, `/api/market/analysis`, `/api/market/history`, and `/api/market/spread`.
- `Market.jsx` consumes those responses and renders current prices, statistics, history, spread, and city rows.
- FastAPI contains the corresponding market routes.
- `/api/items/{item_id}/market`, `/history`, and `/opportunities` routes also match the frontend callers.
- FastAPI CORS is permissive (`*`) with credentials disabled.
- No Vite proxy configuration was found in the repository source inspection.
- The current source therefore has a strong Codespaces integration risk: browser-side `127.0.0.1:8000` can point to the browser host rather than the Codespace backend.

### Existing deterministic evidence

Run `33519639248` verified application SHA `d15f10bd4b91053b79993cd8842f37bd9950b085`:

```text
SQLite concurrency regression: PASS — 3 passed
Python compileall: PASS
Full pytest: PASS — 99 passed, 1 warning, 3.35s
Frontend dependency install: PASS
Frontend production build: PASS
SHA MATCH: YES
```

These results are not browser-level integration evidence.

## WHAT WAS NOT CONFIRMED

- No fresh browser execution was available.
- No browser Network request/response was captured.
- No fresh FastAPI runtime was executed during this Phase.
- No React/Vite dev-server execution was observed during this Phase.
- No SQLite test-data → FastAPI → React rendering path was observed.
- No current AODP → UI path was observed.
- The historical `시장의 데이터를 불러오지 못했습니다.` failure was not reproduced with request/response evidence.
- The `127.0.0.1:8000` Codespaces hypothesis is strongly suspected, not proven as root cause.

## CHANGES MADE

Documentation only:

- Updated `docs/PROJECT_STATE.md` with Phase 23-T.3 source inspection and verification matrix.
- Updated `docs/HANDOFF.md` with the current integration findings.
- `docs/ROADMAP.md` was intentionally not changed because Phase 23-T.3 is not complete/verified.

No `db/`, `services/`, `api/`, `frontend/src/`, tests, or architecture was changed.
No Termux server or runtime database was modified.

## TEST RESULTS

No new local or browser test result was produced in Phase 23-T.3.

Existing deterministic CI remains:

```text
SQLite concurrency regression: PASS — 3 passed
Python compileall: PASS
Full pytest: PASS — 99 passed, 1 warning, 3.35s
Frontend dependency install: PASS
Frontend production build: PASS
```

## CI RESULTS + RUN SHA

```text
Workflow: Phase 23-T.1 Automated Verification
Run ID: 33519639248
Execution SHA: d15f10bd4b91053b79993cd8842f37bd9950b085
Verification target SHA: d15f10bd4b91053b79993cd8842f37bd9950b085
SHA MATCH: YES
Overall: PASS
```

Run `33519639248` does not cover the later documentation-only commits.

## RUNTIME RESULTS

Latest live runtime evidence remains historical Phase 23-T Termux validation:

- approximately 56 minutes of FastAPI HTTP responsiveness,
- East NATS connection/subscription active,
- real AODP NATS messages received and persisted,
- more than 5,900 messages/orders observed,
- SQLite `PRAGMA integrity_check` returned `ok`.

Historical runtime error retained:

```text
OperationalError:
index idx_market_price_history_lookup already exists
```

The exact thread interleaving was not captured.

No Termux runtime was modified during Phase 23-T.3.

## VERIFICATION MATRIX

```text
Frontend API URL        SOURCE VERIFIED; Codespaces risk identified
Frontend endpoint       SOURCE VERIFIED
FastAPI endpoint        SOURCE VERIFIED
FastAPI → service       SOURCE VERIFIED
Service → SQLite        SOURCE VERIFIED; runtime not executed here
CORS                    SOURCE PASS
Vite proxy              NOT FOUND / NOT VERIFIED
Backend HTTP response   NOT TESTED
Frontend receives JSON  NOT TESTED
Frontend renders data   NOT TESTED
Test-data E2E           NOT TESTED
Real AODP → UI          NOT TESTED
```

## KNOWN ISSUES

- Frontend API fallback uses `http://127.0.0.1:8000`.
- No Vite proxy configuration was found.
- This is likely compatible with same-machine local development but is risky in Codespaces/browser-hosted execution.
- Vite build has a non-fatal CSS warning.
- GitHub Actions currently emits Node.js 20 deprecation warnings.
- pytest emits one non-fatal Starlette/httpx TestClient warning.

## CURRENT RISK

The main unresolved question is runtime reachability from the browser to FastAPI. Source inspection shows endpoint/response alignment, but the actual HTTP and React rendering path remains unverified.

## NEXT EXACT STEPS

1. Run the current `main` in an executable environment with FastAPI and Vite available.
2. Open the frontend in a real browser.
3. Use Network inspection to capture the exact market request URL, HTTP status, and response JSON.
4. Confirm whether the browser is attempting `127.0.0.1:8000` or the actual backend host/forwarded port.
5. Verify a representative market row reaches the React UI.
6. If the request fails, classify it as host/port, CORS, backend HTTP, response-shape, parsing, or rendering failure before modifying code.
7. Only after a runtime-confirmed defect should application code be changed.

## DO NOT DO

- Do not call Backend ↔ Frontend PASS yet.
- Do not call Frontend PASS merely because production build succeeds.
- Do not change the localhost API fallback solely from source-level suspicion.
- Do not add Playwright or another E2E framework until the actual verification environment and required coverage are established.
- Do not stop/restart a live Termux server without explicit approval.
- Do not delete/reset the runtime database without explicit approval.
- Do not weaken regression tests.
- Do not perform unrelated refactors.
