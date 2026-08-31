# Albion Market Helper

A personal Albion Online market analysis project.

Current phase:
Phase 3 — Historical Market Analysis + Data Quality Engine

Core pipeline:
AODP → normalization → collector → SQLite current/history → FastAPI → React


Analysis endpoints:
- `/api/market/stats`
- `/api/market/quality`
- `/api/market/analysis`
- `/api/market/trend`
- `/api/market/spread`
