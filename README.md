# Albion Market Helper

Backend-first Albion Online market analysis project targeting Asia/East by default, with East, West, and Europe server isolation.

## Current pipeline

AODP → AlbionApiService / AODPNatsAdapter → normalized market data → SQLite → AnalysisService / Liquidity → StrategyEngine → FastAPI → React Business Dashboard

The project supports current prices, append-only historical snapshots, price statistics/trend/spread analysis, arbitrage opportunities, configurable gross/net profit calculations, data freshness, and a liquidity-aware execution model.

## Data integrity policy

**AODP current price snapshots are never used to infer actual trading volume, order quantity, or order-book depth.** Missing liquidity is represented as unavailable rather than fabricated or converted to zero. NATS liquidity is observational: only orders actually received and persisted are used.

## Strategy architecture

The application treats economic activities as independent strategies behind a common contract:

StrategyRegistry → StrategyEngine → BusinessOpportunity → Business Dashboard

- `StrategyDefinition` describes a strategy and its data/input requirements.
- `BusinessStrategy` defines the common `evaluate(**inputs)` contract.
- `StrategyRegistry` discovers independently addable strategy implementations.
- `ArbitrageStrategy` adapts the existing `ArbitrageService`; arbitrage calculations are not duplicated.
- `CraftingStrategy` uses the normalized recipe/production-rule layer when recipe and market inputs are available.
- `BusinessOpportunity` is strategy-neutral and carries capital, revenue/cost/profit, ROI, risk, liquidity, confidence, freshness and time information.
- `StrategyEngine` applies capital/risk filters and ranking without knowing strategy-specific calculation details.

## Business Dashboard

The React home screen is a unified dashboard over `/api/strategies` and `/api/opportunities`. Users can select the canonical server, provide available capital, filter by risk or strategy, and choose a backend ranking criterion.

Strategy cards are generated from registry metadata rather than a hardcoded strategy list. Opportunity cards are generated from normalized `BusinessOpportunity` results. Unknown profit remains unavailable; it is never converted to zero. When there is no sufficient market/recipe data, the dashboard reports that no executable opportunities are available instead of fabricating a result.

The canonical server IDs remain `east`, `west`, and `europe`; `east` may be displayed as `Asia / East`. Server IDs, item IDs, cities and profitability results are data/configuration inputs rather than strategy constants.

The existing market-analysis and arbitrage views remain available below the dashboard and continue to use their existing backend services.

## Phase 5–7: Liquidity and order lifecycle

- Liquidity is behind a provider/adapter boundary. `DatabaseLiquidityProvider` reads recent normalized AODP market orders.
- Executable quantity is limited by requested quantity and both sides' real available quantities.
- Weighted execution prices and slippage use actual order-depth levels only.
- Orders track provenance, first/last seen, expiry and observational lifecycle state (`ACTIVE`, `EXPIRED`, `STALE`, `UNKNOWN`). `STALE` and `EXPIRED` do not mean SOLD.
- Historical order observations are retained separately from current order state.
- NATS ingestion is opt-in and server-isolated for canonical `east`, `west`, and `europe`.

## Recipe data

The recipe layer is source-adaptable and stores normalized recipes/material relationships in SQLite. Phase 13 does not add or invent recipe records. If recipe or market inputs are missing, Crafting produces no fabricated opportunity.

## API

Existing market and arbitrage endpoints remain compatible. Strategy endpoints:

- `GET /api/strategies`
- `GET /api/strategies/{strategy_id}`
- `GET /api/opportunities?server=east&capital=...&strategy=arbitrage&sort=profit`

`/api/opportunities` is the current backend aggregation surface used by the Business Dashboard; it delegates calculation to `StrategyEngine` and returns normalized `BusinessOpportunity` values.

Business calculations remain in backend services. The frontend displays backend results and does not reproduce profit calculations.

## Validation policy

Python tests use fixtures/mocks and do not insert synthetic market data into the production database. Live AODP connectivity is tested separately. A fixture PASS is never a LIVE PASS, and code inspection is not runtime verification.

## Phase 20: Live location and collector validation

AODP NATS `LocationId` values are treated as marketplace identifiers, not world-zone IDs. The known canonical marketplace mappings currently used by the adapter are `7 → Thetford`, `1002 → Lymhurst`, `2004 → Bridgewatch`, `3003 → Black Market`, `3005 → Caerleon`, `3010 → Martlock`, and `4002 → Fort Sterling`. Unknown numeric IDs remain numeric rather than being guessed.

The persistent NATS consumer retains reconnect/backoff, malformed-message isolation, order upsert, observation history, and graceful shutdown behavior. Phase 20 adds regression coverage for restart recovery and server isolation and a clean GitHub Actions workflow with bounded live observation. Live multi-city arbitrage remains observational: absence of a profitable candidate is reported as `NOT_OBSERVED`, never replaced by synthetic data.
