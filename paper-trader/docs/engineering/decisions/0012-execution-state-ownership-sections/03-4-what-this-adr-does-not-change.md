Reference: [section index](../0012-execution-state-ownership.md). Read with its scope; this is not a new assignment.

## 4. What this ADR does not change

The order lifecycle, accounting, reconciliation, exits, kill controls, rollback and
deployment authority are untouched. The hand-written strategy remains the sole execution
authority. The wiring changed **which code answers "what runs here"**, not what the answer
is: the equivalence test covers the whole space of values `strategy_keys` can hold — unset,
the default, another registered strategy, and a stale key that no longer resolves — and in
every case the engine selects the same `Strategy` *object* it selected before.

### 4.1 Execution attribution — found here, closed in the next slice

**L1.2 canonicalised execution selection authority. The following slice canonicalises
execution attribution.**

The divergence this ADR originally recorded: selection went through the binding while the
intraday and futures entry paths still stamped `strategy_key=self.strategy_keys.get(key)` —
the raw assigned key — onto the position. For a stale assignment those disagree. The engine
trades the default (fail-safe, deliberate, unchanged) while the position and every trade row
descending from it claimed the key that *failed to resolve*. That is the misattribution shape
the registry docstring warns about, surviving in the one place nothing checked.

It is now closed. The binding that produced a signal is carried from the scan to the fill and
is what the money record is attributed to. The five identities stay separate — requested
assignment (`instrument_state.strategy_key`), executed strategy (`positions`/`trades`), graph
content identity, deployment identity, and authority — and no field was added or repurposed.

Three consequences worth stating:

- **`publish_signal` is the only door.** A signal state and the binding that produced it are
  written together, because `process_entries` opens from `self.state` and attributes from the
  binding. A state entry with no binding is a signal whose author is unknown; the entry paths
  refuse to open on one rather than guessing. Nineteen test call sites moved to this door —
  they had been constructing a state the engine cannot reach.
- **A refusal now withdraws the previous answer.** `self.state` survives a skipped scan, so
  refusing to evaluate an instrument without also dropping its last signal would let
  `process_entries` open on a signal produced while it was still authorised.
- **The identity is captured at the signal, not resolved at the fill.** Re-resolving would
  attribute the trade to whatever is configured by the time it fills, which is not what
  produced it.

### 4.1a A shared-state leak the slice uncovered

Ten attribution tests failed in the suite and passed in isolation, all reporting "no
intraday position opened". The cause was not attribution at all: five wiring test files pin
a session time with `r.provider.now = lambda: <fixed datetime>`, and `get_provider()` returns
a **process-wide singleton**. Sixteen call sites, none restoring — so the last writer froze
the clock at 09:20 for the rest of the run, and every later entry was refused by the 09:30
entry-window gate. The failure pointed at the innocent test.

Fixed in the rootdir `conftest.py` with an autouse fixture that restores the provider's
`now` after every test, rather than at the sixteen sites: the leak is the shape, not the
site. This is the same family as the cursor leak (`test_execution_attribution` pins and
restores `_cursor` for the same reason) and the third time this singleton has cost a
debugging session.

### 4.1b Historical rows: measured, not assumed

Existing rows *may* contain incorrect attribution — any row written while an instrument was
assigned a key the registry could not resolve. Measured on the production ledger
(2026-08-04, read-only):

```
sqlite3 'file:/opt/paper-trader/backend/paper_trader.db?mode=ro' \
  "SELECT COALESCE(strategy_key,'<NULL>'), COUNT(*), SUM(mode='live') FROM trades GROUP BY 1;"
<NULL>|22|22
expanding_z_v4|50|50
```

All 72 live trades carry either `NULL` — the documented "the engine default produced this"
encoding, coalesced to `trend_impulse_v3` by `analytics.py`, `models.py` and `sweep.py` — or a
registered key. **No production row carries an unregistered key, so the defect was latent and
never fired.** No migration and no repair tool: nothing is known to be wrong, and where a row
could be wrong the correct identity is *not* deterministically derivable (a key unregistered
today may have been registered when the row was written, and the reverse).

One benign discontinuity: from this slice forward an unassigned instrument records the
resolved key explicitly rather than `NULL`. Both read identically everywhere in the codebase,
so `NULL` now simply means "written before 2026-08-04". No schema change was required — the
model already keeps requested assignment and executed identity in different tables.

### 4.2 Remaining unconsumed mechanisms

- `strategy_lifecycle.deployed_watchlist_id` (#4) remains a record, not a resolver — by
  design; it is named in `BINDING_MECHANISMS` so it cannot quietly become one.
- `graph_artifacts.current_version` (#6) is consumed only by the shadow lane. It becomes a
  binding input at Stage 2, which is owner-gated.
- `deployments.strategy_key` (#1) now **has** a production caller for the first time, but
  only ever resolves to `None` today, because no production path writes it. A deployment
  that pins a strategy is exercised by tests, not by the running system.
