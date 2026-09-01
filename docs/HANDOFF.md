# Albion Market Helper — Development Handoff

## PROJECT

Albion Market Helper — Albion Online market data collection, persistence, analysis, liquidity, strategy aggregation, FastAPI API, and React dashboard.

## CURRENT PHASE

Phase 23-T.2 — GitHub Actions Automated Verification Pipeline

**STATUS: VERIFIED / PASS**

## CURRENT HEAD SHA

Verification target/application commit:

`d15f10bd4b91053b79993cd8842f37bd9950b085`

This documentation update advances `main`. Before any future development, re-check the actual `main` HEAD and use the exact verified CI SHA separately from later documentation commits.

## WORKING TREE STATUS

No local working-tree state can be established through the GitHub API. Repository changes in this handoff are documentation-only.

Application code remains unchanged by this documentation task.

## WHAT WAS CONFIRMED

- GitHub `main` was rechecked before this documentation update.
- Deterministic workflow: `.github/workflows/phase23-t1-verification.yml`.
- Run `33519639248` completed successfully against execution SHA `d15f10bd4b91053b79993cd8842f37bd9950b085`.
- Workflow checkout explicitly used that SHA, and job logs reported the same execution SHA.
- SQLite concurrency regression passed: 3 tests passed.
- Python compileall passed.
- Full pytest passed: 99 passed, 1 warning, 3.35s.
- Frontend dependency installation passed.
- Frontend production build passed.
- Non-fatal warnings were emitted by GitHub Actions, pytest, and Vite.

## WHAT WAS NOT CONFIRMED

- No fresh Termux live runtime was performed during this task.
- Exact historical runtime thread interleaving for `idx_market_price_history_lookup already exists` remains unproven.
- The later documentation-only commits are not covered by Run `33519639248`.
- Local working-tree cleanliness cannot be established from GitHub API inspection alone.

## CHANGES MADE

Documentation only:

- Updated `docs/PROJECT_STATE.md` with deterministic CI evidence.
- Updated `docs/ROADMAP.md` to mark Phase 23-T.2 verified.
- Updated `docs/HANDOFF.md` with this recovery checkpoint.

No `db/`, `services/`, `api/`, `frontend/src/`, or test source was changed.
No Termux server or runtime database was modified.

## TEST RESULTS

Verified through GitHub Actions Run `33519639248`:

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

All three jobs completed successfully.

## RUNTIME RESULTS

Historical Phase 23-T Termux evidence:

- approximately 56 minutes of FastAPI HTTP responsiveness,
- East NATS connection maintained,
- subscription active,
- real AODP NATS messages received and parsed,
- SQLite persistence observed,
- event-loop hang not reproduced,
- more than 5,900 messages/orders observed,
- SQLite `PRAGMA integrity_check` returned `ok`.

Historical runtime error retained as evidence:

```text
OperationalError:
index idx_market_price_history_lookup already exists
```

The server and consumer reportedly continued operating. The exact thread interleaving was not captured.

No Termux runtime was modified during Phase 23-T.2 CI verification.

## KNOWN ISSUES

- Non-fatal GitHub Actions Node.js 20 deprecation warnings for checkout/setup actions.
- One non-fatal Starlette/httpx TestClient deprecation warning in pytest.
- One non-fatal Vite CSS minification warning during frontend production build.
- Historical SQLite index race remains relevant runtime evidence, although the current deterministic concurrency regression passed.

## CURRENT RISK

The deterministic regression/build path is verified for SHA `d15f10bd...`. Remaining risk is evidence separation: CI verification does not replace live Termux/NATS runtime verification, and the historical runtime exception's exact interleaving remains unproven.

## NEXT EXACT STEPS

1. Reconfirm the actual GitHub `main` HEAD after this documentation commit.
2. Treat Run `33519639248` / SHA `d15f10bd4b91053b79993cd8842f37bd9950b085` as the completed Phase 23-T.2 deterministic verification evidence.
3. Continue with the next roadmap phase from the actual current `main` HEAD, or perform a separately authorized bounded Termux runtime validation if live evidence is required.
4. Before any application change, re-check current source, tests, and current HEAD rather than relying on this handoff alone.

## DO NOT DO

- Do not treat historical Run `33500437389` as current.
- Do not treat Run `33519639248` as coverage of the later documentation-only commits.
- Do not weaken or delete assertions.
- Do not remove concurrency regression tests.
- Do not perform unrelated refactors.
- Do not change NATS architecture as part of this verification work.
- Do not stop/restart a live Termux server without explicit approval.
- Do not delete/reset the runtime database without explicit approval.
- Do not infer a specific runtime thread interleaving without captured evidence.
