# Albion Market Helper

Backend-first Albion Online market analysis project targeting Asia/East by default, with East, West, and Europe server isolation.

## Current pipeline

AODP → AlbionApiService → Collector → SQLite → AnalysisService → ArbitrageService → FastAPI → React

The project currently supports current prices, append-only historical snapshots, price statistics/trend/spread analysis, arbitrage opportunities, configurable gross/net profit calculations, data freshness, and a liquidity-aware execution model.

## Phase 5: Liquidity and execution model

- **Liquidity:** represented through a provider/adapter boundary. The current AODP price snapshot does not provide order quantity or full order-book depth, so the default provider reports liquidity as unavailable.
- **Executable Quantity:** when a real liquidity source supplies both buy-side and sell-side quantities, execution is limited to the requested quantity and both available quantities.
- **Slippage:** when real order-book depth is supplied, weighted execution prices and buy/sell slippage can be calculated. No depth is synthesized from price snapshots.
- **Realistic Profit:** calculated only when executable quantity is actually available; depth-aware execution prices are used when available. Otherwise the result is explicitly unavailable.
- **Confidence:** combines freshness, historical sufficiency, and liquidity availability without treating unknown data as zero.
- **Data Availability:** responses distinguish unavailable liquidity from zero liquidity and insufficient historical data.

### Data integrity policy

**AODP current price snapshots are never used to infer actual trading volume, order quantity, or order-book depth.** Missing liquidity is represented as unavailable rather than fabricated or converted to zero.

## Configuration

Configuration is centralized in `config.py`. Environment variables can select the server, AODP timeout/retry behavior, collection interval, watchlist, cities, qualities, database path, and freshness threshold.

## API

Core market endpoints remain under `/api/market/*`. Arbitrage endpoints remain:

- `GET /api/arbitrage`
- `GET /api/arbitrage/opportunities`
- `GET /api/arbitrage/calculate`
- `GET /api/arbitrage/liquidity`

Arbitrage responses include gross opportunity fields plus liquidity, executable quantity, slippage, realistic-profit availability, confidence, freshness, and data-availability status.

## Development validation

Python tests use fixtures/mocks and do not insert synthetic market data into the production database. Live AODP connectivity is tested separately from parser and engine tests.

## Phase 6: External liquidity source

The selected external liquidity source is the Albion Online Data Project (AODP) public NATS market-order stream, `marketorders.deduped`. AODP documents public NATS endpoints for Americas/West, Asia/East, and Europe. Its market-order messages contain individual orders including item, location, quality, unit price, amount, auction type, order ID, and expiry.

The project normalizes those messages through `MarketDataAdapter` / `AODPNatsAdapter` and persists them as provenance-aware `market_liquidity_orders` records. `DatabaseLiquidityProvider` converts real sell offers and buy requests into execution depth for the existing arbitrage engine. No quantity, volume, or order depth is inferred from AODP price snapshots.

AODP market-order data is observational rather than a guaranteed complete order book: the AODP client uploads orders that users actually load in-game, and subscribers can miss earlier messages. Therefore liquidity is only treated as available when recent normalized order data exists; otherwise it remains unavailable.

NATS ingestion is opt-in through `AODP_NATS_ENABLED`. The adapter and tests are network-independent; live NATS access is validated separately.
