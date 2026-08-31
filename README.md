# Albion Market Helper

Backend-first Albion Online market analysis project targeting Asia/East by default, with East, West, and Europe server isolation.

## Current pipeline

AODP → AlbionApiService / AODPNatsAdapter → normalized market data → SQLite → AnalysisService / Liquidity → StrategyEngine → FastAPI → React

The project supports current prices, append-only historical snapshots, price statistics/trend/spread analysis, arbitrage opportunities, configurable gross/net profit calculations, data freshness, and a liquidity-aware execution model.

## Data integrity policy

**AODP current price snapshots are never used to infer actual trading volume, order quantity, or order-book depth.** Missing liquidity is represented as unavailable rather than fabricated or converted to zero. NATS liquidity is observational: only orders actually received and persisted are used.

## Phase 5–7: Liquidity and order lifecycle

- Liquidity is behind a provider/adapter boundary. `DatabaseLiquidityProvider` reads recent normalized AODP market orders.
- Executable quantity is limited by requested quantity and both sides' real available quantities.
- Weighted execution prices and slippage use actual order-depth levels only.
- Orders track provenance, first/last seen, expiry and observational lifecycle state (`ACTIVE`, `EXPIRED`, `STALE`, `UNKNOWN`). `STALE` and `EXPIRED` do not mean SOLD.
- Historical order observations are retained separately from current order state.
- NATS ingestion is opt-in and server-isolated for canonical `east`, `west`, and `europe`.

## Phase 8: External source and business architecture preparation

AODP public NATS `marketorders.deduped` is the selected external liquidity source. The adapter layer keeps source-specific protocol handling separate from analysis and strategy logic.

## Phase 10: Business Strategy Integration

The strategy layer is now executable rather than metadata-only:

- `StrategyDefinition` describes a strategy and its data/input requirements.
- `BusinessStrategy` defines the common `evaluate(**inputs)` contract.
- `StrategyRegistry` discovers independent strategy implementations.
- `ArbitrageStrategy` adapts the existing `ArbitrageService`; arbitrage calculations are not duplicated.
- `BusinessOpportunity` is strategy-neutral and carries required/available capital, capital utilization, expected revenue/cost/profit, ROI, risk, liquidity, confidence and freshness.
- `StrategyEngine` applies capital/risk filters and ranking without knowing strategy-specific calculation details.
- `/api/strategies`, `/api/strategies/{strategy_id}`, and `/api/opportunities` expose discovery and normalized opportunities.

### Dashboard policy

The React home screen is a dashboard shell around normalized strategy opportunities. It accepts user-provided capital, risk and ranking preferences and does not fabricate results for unimplemented strategies. Current implemented strategy output is arbitrage only. Crafting, refining, transport, gathering, and other strategies must be added as independent strategy modules with real calculation inputs before they can produce opportunities.

The canonical server IDs remain `east`, `west`, and `europe`; `east` may be displayed as `Asia / East`. Servers, item IDs, cities and profitability results are data/configuration inputs rather than strategy constants.

## API

Existing market and arbitrage endpoints remain compatible. Strategy endpoints:

- `GET /api/strategies`
- `GET /api/strategies/{strategy_id}`
- `GET /api/opportunities?server=east&capital=...&strategy=arbitrage&sort=profit`

Business calculations remain in backend services. The frontend displays backend results and does not reproduce profit calculations.

## Validation policy

Python tests use fixtures/mocks and do not insert synthetic market data into the production database. Live AODP connectivity is tested separately. A fixture PASS is never a LIVE PASS, and code inspection is not runtime verification.
