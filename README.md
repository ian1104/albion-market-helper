# Albion Market Helper

A personal Albion Online market analysis project.

Current phase:
Phase 4 — Arbitrage Engine + Profit Calculator + Opportunity Ranking

Core pipeline:
AODP → normalization → collector → SQLite current/history → FastAPI → React


Analysis endpoints:
- `/api/market/stats`
- `/api/market/quality`
- `/api/market/analysis`
- `/api/market/trend`
- `/api/market/spread`


Arbitrage endpoints:
- `/api/arbitrage`
- `/api/arbitrage/opportunities`
- `/api/arbitrage/calculate`
