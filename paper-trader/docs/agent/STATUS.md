# V0 delivery status

Documentation consolidation: 6 September 2026. **V0 is unfinished; no launch or deployed-journey pass is recorded here.** This page summarizes existing evidence and pending work, not a new runtime audit.

## Ownership

Product continuation belongs to the task named in [the September 6 handoff](HANDOFF-2026-09-06-TRADER-UI.md). Earlier writers were frozen on transfer. Consult that handoff before touching shared product files; runtime handles and open defects can become stale.

The current documentation refactor is separate from product implementation. Work stays in the authorized `codex/execution-foundation` checkout and preserves inherited changes.

## Recorded progress

| Area | Evidence level and remaining work |
| --- | --- |
| Canonical research and optimization | [Bounded local signal/research journey verified](tasks/independent-signal-research-workflow-2026-09-06.md): 7,936 real-data flags match independent arithmetic; synthetic parameter discovery, neighborhood comparison, accepted version, updated builder and rerun work. Failed gates remain failed. Exact data restoration across remounts, broader provider/watchlist research, Monte Carlo and the final complete journey remain open. |
| Builder, Home, account and research UI | The reused local account verified workspace/strategy capital inheritance, account-limit persistence, separate V3/V4 version-1 saves, canvas panning and representative staging/inspector/Command-Z interactions across all five component families. This does not prove node calculations or backtest consumption. Evidence: `.agent/runs/v0-launch-reset-2026-09-05/dummy-account-journey/JOURNEY.md`. Final integrated checks remain open. |
| Imported data | Owner-scoped import/session metadata has backend and UI evidence. The latest direction prioritizes provider API acquisition; imports do not prove provider capture or fresh monitoring. |
| Monitoring and alerts | Inbox read/attention APIs and UI have focused evidence. End-to-end activation, fresh-data producer, resolver/evaluator and worker integration remain open. |
| Watchlists | The instrument-results view is being integrated following the September 7 functional correction: add/remove instruments, saved strategy/timeframe, independent pins, filters and monitoring controls. History and revision tools are secondary. The revised UI passed 103 focused tests; persisted row settings and exact retries have focused API and owner-isolation evidence. SQLite and native PostgreSQL 0056 migration checks passed in disposable databases. Assignment-backed reads distinguish unevaluated, HOLD, signal and stale results; these are fixture tests, not a fresh-market journey. Browser settings/restart verification is underway. The fresh-data producer, activation and worker remain open. Evidence: `.agent/runs/v0-launch-reset-2026-09-05/watchlist-monitoring/` and `.agent/runs/watchlist/persistence/`. |
| Provider history | The local API now has evidence for chunked historical acquisition, retained source attribution, canonical publication/reopen and reuse after DATA access is revoked. A fresh Python process restores a publication after the research-plane commit fails without fetching again. Pass-local attribution reuse reduced the 200-bar measured profile from about 31 to 14 seconds. The unprofiled 2,000-bar check passed: publication 52.53 seconds, commit 0.08 seconds, reopen 15.72 seconds and lookup 0.23 seconds, excluding setup and provider network latency. All ten targeted reuse mutations were killed. A real browser/auth/API/storage journey saved 60 synthetic bars, then reused the exact publication after a fresh API process and sign-in with further provider calls forbidden. Native PostgreSQL publication recovery after research-plane rollback and canonical reopen also passed. All 25 publication integration mutations were killed. The final date-label build and fresh-process browser reuse passed; dates use India time and daily coverage ends on the last recorded bar. The complete search/Add/Save watchlist variant passed with 60 synthetic bars, one retained empty request and four provider-transport calls; reload, sign-in and API restart made no additional provider calls and reported no browser errors or external origins. Local 0054-to-0055 migration preserved all original rows and the other database planes. SQLite backup copies require the research schema counter to be preserved; a serialized three-plane copy passed integrity checks and actual API startup. This does not establish real provider connectivity or deployment. Saving a provider selection grants no historical-data or execution authority. Evidence: `.agent/runs/v0-launch-reset-2026-09-05/provider-history/`. |
| Release | Frontend type checking and production build pass; the main bundle still exceeds Vite's 500 kB warning threshold. The combined changed backend subsystem passes, including its separate disposable PostgreSQL typed-authority reopen check. The safe API restarted and the same dummy account's V3/V4 records were read again. An unexpected browser account-context change was recovered by signing back in; its cause remains unproven. Full customer journey and remaining operational evidence are incomplete. Deployment requires a concrete approved candidate and later deployed verification. |

The [September 5 audit](V0-INDEPENDENT-AUDIT-2026-09-05.md) supplies stable finding IDs and the earlier reproduction baseline. Its open/closed wording must be read with later handoff evidence; it is not a fresh statement that every original defect remains.

## Next integration checks

- Complete provider instrument/history selection, coverage explanations and canonical dataset reuse through the actual UI/API/storage path.
- Finish monitoring activation and produce an attributable alert from supported current data, with restart and owner-isolation evidence.
- Reconcile remaining shared-select, route, styling and dependency-notice checks in the handoff; rerun only changed or unresolved checks.
- Complete preset/edit/save/data/backtest/challenge/compare/evidence/monitoring journeys and useful failure cases on a stable local candidate.
- Complete release operations and request deployment approval only for a concrete candidate. Repeat the journey on the deployed build before making a launch claim.

## Evidence locations

Detailed prior results and pending checks: [current handoff](HANDOFF-2026-09-06-TRADER-UI.md). The evidence root is `.agent/runs/v0-launch-reset-2026-09-05/`; load only the named result or reproduction. Runtime credentials and private conversation content do not belong in documentation.

[CURRENT.md](CURRENT.md), [PROGRAMME.json](programme/PROGRAMME.json) and task capsules preserve earlier machine routing and phase history. They are not the human startup path and do not supersede a current assignment. Phase completion is not product completion.
