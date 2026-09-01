# Albion Market Helper — Development Handoff

## PROJECT

Albion Market Helper — Albion Online market data collection, persistence, analysis, liquidity, strategy aggregation, FastAPI API, and React dashboard.

## CURRENT PHASE

Phase 23-T.1 — SQLite initialization/concurrency regression correction and verification.

This handoff records a documentation-only checkpoint. No application code was changed in this task.

## CURRENT HEAD SHA

After this documentation-only commit sequence, `main` advanced from the previously verified application HEAD `3e0160a0c8220f98f26a62af92448d7955713ed2` to the documentation commits. The final commit of this documentation task is recorded in the task report. Before any further development, re-read `main` and use its actual current HEAD as the source of truth.

Application-code baseline immediately before documentation:

`3e0160a0c8220f98f26a62af92448d7955713ed2`

## WORKING TREE STATUS

GitHub API inspection can establish committed repository state but cannot establish the cleanliness of a separate local working tree. No claim of local working-tree cleanliness is made.

The documentation task added only:

- `docs/PROJECT_STATE.md`
- `docs/ROADMAP.md`
- `docs/HANDOFF.md`

No application source file was modified.

## WHAT WAS CONFIRMED

- GitHub `main` was rechecked before documentation work.
- The application baseline HEAD was `3e0160a0c8220f98f26a62af92448d7955713ed2`.
- The repository did not contain `docs/PROJECT_STATE.md`, `docs/ROADMAP.md`, or `docs/HANDOFF.md` before this task.
- Current `db/database.py` contains shared `threading.RLock()` initialization synchronization, `_initialized`, `_initialized_path`, path-aware initialization caching, and migration-aware index rebuild behavior.
- Current regression coverage contains concurrent initialization, repeated initialization, and concurrent liquidity persistence tests.
- Current Phase 23 workflow runs the dedicated SQLite concurrency regression and later disables NATS for the full Python regression step.
- Historical CI Run `33500437389` ran at `5bbc7e69af39dd940fcc6360b9dda51ef95dfee5`, not the current application HEAD.

## WHAT WAS NOT CONFIRMED

- A fresh local pytest execution against the current application HEAD was not possible in the available execution environment.
- The exact current-HEAD result of the SQLite concurrency test is therefore unknown.
- The exact current-HEAD result of `tests/test_liquidity.py` and `tests/test_phase21_application_lifecycle.py` is unknown.
- The exact current-HEAD full pytest result is unknown.
- `compileall` was not executed against the current application HEAD in this environment.
- Frontend install/build was not executed against the current application HEAD in this environment.
- No verified GitHub Actions run was available for application HEAD `3e0160a0c8220f98f26a62af92448d7955713ed2` during inspection.
- The historical Termux index exception was not captured with thread stacks, so the exact runtime interleaving remains unproven.

## CHANGES MADE

Documentation only:

1. Added `docs/PROJECT_STATE.md` as the persistent current-state record.
2. Added `docs/ROADMAP.md` to separate future plans from implementation state.
3. Added `docs/HANDOFF.md` for future chat/session recovery.

No Python, FastAPI, SQLite schema, NATS, or frontend application code was changed.

## TEST RESULTS

No tests were executed in this documentation task.

The last execution state remains:

```text
Current HEAD execution: NOT VERIFIED
```

Do not infer PASS/FAIL from the existence of the documentation commits.

## CI RESULTS + RUN SHA

Current application baseline:

```text
HEAD: 3e0160a0c8220f98f26a62af92448d7955713ed2
Verified CI run: none available
```

Historical CI only:

```text
Run: 33500437389
SHA: 5bbc7e69af39dd940fcc6360b9dda51ef95dfee5
Result: 97 passed / 2 failed
```

Historical failures were:

- `test_liquidity_status_and_summary_endpoints`: expected `enabled=False`, received `True`.
- `test_liquidity_status_exposes_live_consumer_state`: `sqlite3.OperationalError: no such table: market_liquidity_orders`.

Those failures must not be treated as current HEAD failures.

## RUNTIME RESULTS

Historical Phase 23-T Termux result supplied by the project handoff:

- approximately 56 minutes of FastAPI HTTP responsiveness,
- East NATS connected,
- subscription active,
- real AODP NATS messages received,
- real message parsing,
- SQLite persistence,
- event-loop hang not reproduced,
- more than 5,900 messages received,
- more than 5,900 orders persisted,
- SQLite `PRAGMA integrity_check` returned `ok`.

Observed historical runtime error:

```text
OperationalError:
index idx_market_price_history_lookup already exists
```

The server and NATS consumer continued operating afterward. The code-level race capability was identified and subsequent synchronization/migration changes were committed, but the precise runtime thread interleaving was not captured.

## KNOWN ISSUES

- Current HEAD execution evidence is still missing.
- Current HEAD CI evidence is still missing.
- The historical SQLite index exception remains important runtime evidence even though later code changed the initialization path.

## CURRENT RISK

The primary risk is verification debt, not an identified current application failure: source-level fixes exist, but the current HEAD has not yet been executed through the required regression/build sequence in the available environment.

## NEXT EXACT STEPS

1. Reconfirm the actual GitHub `main` HEAD because documentation commits have advanced the branch after application baseline `3e0160a0c8220f98f26a62af92448d7955713ed2`.
2. Run `pytest -q tests/test_database_initialization_concurrency.py`.
3. Run `pytest -q tests/test_liquidity.py tests/test_phase21_application_lifecycle.py`.
4. Run `pytest -q`.
5. Run `python -m compileall .`.
6. Inspect frontend package configuration, then run `npm install` and `npm run build` if dependencies/network permit.
7. If anything fails, capture the exact traceback and diagnose before changing code.
8. Only if a current-HEAD failure is reproduced, make the smallest in-scope correction and rerun regression.
9. Confirm GitHub Actions for the exact resulting commit SHA.
10. Update `PROJECT_STATE.md` and `HANDOFF.md` again with the new verified results.

## DO NOT DO

- Do not treat historical Run `33500437389` as current.
- Do not claim tests passed when they were not executed.
- Do not weaken/delete assertions.
- Do not remove concurrency regression tests.
- Do not refactor unrelated code.
- Do not change NATS architecture during SQLite regression work.
- Do not stop/restart a live Termux server without explicit approval.
- Do not delete/reset the runtime database without explicit approval.
- Do not infer a specific runtime thread interleaving without captured evidence.
