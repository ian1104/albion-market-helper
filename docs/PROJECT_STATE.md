# Albion Market Helper — Project State

## CURRENT PHASE

**Phase 24 — System Status Dashboard**

**STATUS: COMPLETED / VERIFIED**

## CURRENT HEAD SHA

`59499eadd5d37bbfbedd90ae2f21cb276f3d03ac`

Commit:

`feat: add system status dashboard`

Parent:

`88d5bfbadb3092df8875db9f8823428f2a34e0d7`

## CURRENT ARCHITECTURE

### Market Data Pipeline

AODP REST
    ↓
Market Data / Persistence
    ↓
SQLite
    ↓
FastAPI API
    ↓
React/Vite Frontend

### Liquidity Pipeline

AODP NATS
    ↓
Liquidity Collector / Adapter
    ↓
SQLite liquidity order + observation persistence
    ↓
FastAPI liquidity/status APIs
    ↓
Frontend System Status

## IMPLEMENTED FEATURES

- Market price persistence and querying
- Historical market-price snapshots
- Server isolation
- AODP REST market-data collection
- Historical market analysis
- Price trend and spread analysis
- Arbitrage analysis
- Liquidity and order-lifecycle persistence
- AODP NATS connectivity and market-order ingestion
- Strategy engine
- Crafting strategy analysis
- Business-opportunity aggregation
- Collector scheduler lifecycle integration
- System Status Dashboard

## VERIFIED FEATURES

Phase 23-T.4 and Phase 24 were verified against the current implementation.

Verified areas include:

- FastAPI application startup
- Collector scheduler startup through application lifecycle
- AODP NATS connection and subscription
- Live market-order message reception
- SQLite persistence
- SQLite integrity
- API responses
- Frontend production build
- System Status Dashboard browser behavior
- External browser access
- Runtime live accumulation
- SQLite restart-preservation behavior

## UNVERIFIED FEATURES / LIMITATIONS

- There is no dedicated frontend database-health endpoint. The Database status therefore remains UNKNOWN rather than being inferred from unrelated components.
- Collector status may remain UNKNOWN when recent successful collection evidence is unavailable.
- Future roadmap phases are not implemented unless explicitly listed above as implemented and verified.
- No claim is made that all future frontend strategy interactions are fully implemented.

## STATUS DASHBOARD SEMANTICS

### Backend API

- Successful status request → ONLINE
- Request failure → UNKNOWN

### Collector

- Running → RUNNING
- Not running with recent successful collection evidence → IDLE
- Clear recent collection failure → ERROR
- Endpoint failure → UNKNOWN

### AODP NATS / Liquidity

- Connected and subscription active → CONNECTED
- Connection unavailable → OFFLINE
- Lack of recent messages alone does not imply OFFLINE
- Request failure → UNKNOWN

### Database

No dedicated database-health endpoint exists in the frontend status flow.

Therefore:

- Database health cannot be safely inferred from collector or backend status.
- Frontend status → UNKNOWN

### Market Engine

The Market Engine is an aggregate availability indicator:

- Backend API online → AVAILABLE
- Backend unavailable → UNKNOWN

## KNOWN ISSUES / WARNINGS

- Pytest emits an existing Starlette deprecation warning related to the httpx/TestClient integration.
- Frontend production build emits an existing CSS warning related to a malformed transition declaration in the original stylesheet.
- GitHub Actions reports the existing Node.js 20 deprecation warning.
- These warnings were not treated as Phase 24 functional failures.

## LAST TEST RESULTS

### Backend regression

101 passed, 1 warning

### Python compile check

compileall PASS

### Frontend production build

PASS

## LAST CI RESULT

Workflow:

Phase 21 Runtime Validation

Run:

33843449468

Commit SHA:

59499eadd5d37bbfbedd90ae2f21cb276f3d03ac

Result:

SUCCESS

The run included live accumulation and SQLite restart-preservation verification.

## LAST RUNTIME RESULT

Phase 24 runtime verification confirmed:

- FastAPI API responses
- System Status Dashboard
- Desktop Sidebar status display
- Mobile Header status display
- Live backend integration
- AODP NATS live connectivity
- External browser access
- 300-second live data accumulation
- SQLite restart-preservation

Observed status behavior included:

- Backend API → ONLINE
- Collector → UNKNOWN when recent success evidence was unavailable
- AODP NATS → CONNECTED
- Database → UNKNOWN
- Market Engine → AVAILABLE

These results matched the approved Phase 24 semantics.

## NEXT EXACT STEPS

**Next phase: P1 — Market Data Freshness**

Before implementation:

1. Re-check current GitHub main.
2. Inspect the current market API/frontend data flow.
3. Identify the existing timestamp fields used for market data.
4. Define exact freshness semantics.
5. Determine whether existing backend data is sufficient.
6. Implement the minimum required change.
7. Run focused regression tests.
8. Run full pytest.
9. Run compileall.
10. Run frontend production build.
11. Perform runtime/browser verification where appropriate.
12. Verify GitHub Actions against the exact commit SHA.

## DO NOT DO

- Do not modify unrelated features during P1.
- Do not weaken or remove meaningful tests.
- Do not use git add ..
- Preserve the existing untracked frontend/package-lock.json and package-lock.json.
- Do not restart a running runtime environment without explicit approval.
- Do not reset or delete the SQLite database.
- Do not trigger manual collector execution against the live environment without explicit approval.
- Do not treat old reports or previous chat state as the current source of truth.
- Do not start P1 implementation as part of this documentation closeout.
