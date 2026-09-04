# Albion Market Helper — Roadmap

## CURRENT PHASE

**Phase 24 — System Status Dashboard**

**STATUS: COMPLETED / VERIFIED**

Phase 24 is implemented and verified.

The current application includes backend status, collector status, AODP NATS/liquidity status, database status semantics, and aggregate Market Engine availability in the frontend.

## COMPLETED IMPLEMENTATION AREAS

The following areas are implemented and verified in the current project:

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

## FUTURE ROADMAP

The following phases are planned work and must not be treated as implemented until separately verified.

### P1 — Market Data Freshness

**STATUS: PLANNED**

Goal:

Prevent stale market prices from appearing to users as if they were current.

Planned considerations:

- Display the age of market data.
- Distinguish recent, aging, and stale data.
- Consider user-facing states such as:
  - 2 minutes ago
  - 14 minutes ago
  - 1 hour ago
  - old/stale
- Reuse existing timestamp data where sufficient.
- Avoid backend changes if the existing API already provides sufficient information.

The exact freshness thresholds and implementation approach are not yet finalized.

### P2 — Interactive Market Chart

**STATUS: PLANNED**

Goal:

Improve historical market-data visualization and interaction.

Planned functionality:

- Touch interaction on mobile.
- Hover interaction on desktop.
- Price/time tooltip.
- Crosshair or equivalent point-selection interaction.
- Clear visualization of historical price movement.

Exact chart library and final interaction design are not yet finalized.

### P3 — Strategy Tab Functionality Verification

**STATUS: PLANNED**

Goal:

Review and verify the existing strategy-related frontend areas.

Planned scope:

- City Arbitrage functionality review.
- Crafting functionality review.
- Identify which existing UI controls are functional.
- Identify incomplete or placeholder interactions.
- Implement only the minimum required functionality after inspection.

No assumption should be made that every existing strategy UI element is already fully functional.

### P4 — Opportunity / Market Analysis Enhancement

**STATUS: PLANNED**

Goal:

Improve the usefulness of market analysis and opportunity discovery.

Potential areas:

- Better opportunity ranking.
- Improved spread and liquidity interpretation.
- More useful filtering.
- More actionable market-analysis presentation.

Exact scope must be defined from the current implementation before development begins.

### P5 — AI Advisor

**STATUS: PLANNED**

Goal:

Add an AI-assisted explanation and decision-support layer on top of deterministic market data.

Planned architecture principle:

- Raw market prices and economic calculations remain deterministic.
- The AI layer interprets structured market results.
- The AI should explain opportunities, risks, assumptions, and relevant market signals.
- AI output should not replace the underlying market-data calculations.

Exact model, API integration, prompt architecture, cost controls, and safety/failure behavior are not yet finalized.

## SCOPE RULES

- Planned phases are not evidence of implemented functionality.
- A phase becomes completed only after implementation and verification.
- Current GitHub main is the source of truth.
- Previous reports and conversations must not override the current repository state.
- Each phase should use the minimum necessary change.
- Regression tests must remain meaningful.
- Runtime validation must be separated from code-level verification.
- CI results must be interpreted against the exact commit SHA on which the workflow ran.

## VERIFICATION BASELINE

Latest verified application revision:

`59499eadd5d37bbfbedd90ae2f21cb276f3d03ac`

Commit:

`feat: add system status dashboard`

Latest verified CI run:

`33843449468`

Result:

**SUCCESS**

Next exact development target:

**P1 — Market Data Freshness**
