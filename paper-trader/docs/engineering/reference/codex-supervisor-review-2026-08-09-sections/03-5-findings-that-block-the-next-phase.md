Reference: [section index](../codex-supervisor-review-2026-08-09.md). Read with its scope; this is not a new assignment.

## 5. Findings that block the next phase

### F-01: market data and execution selection are still one object

**Severity:** critical for adapter #2 and multiple brokers\
**Files:** `app/providers/factory.py:8-30`, `app/engine/broker_factory.py:72-106`

`get_provider()` returns one process-global `MarketDataProvider`. `make_broker(provider)` asks that same object for `LIVE_EXECUTION`, copies its access token into a Kite execution client, and takes tick-size lookup from it. If an Upstox data-only provider is selected, the broker factory returns `PaperBroker`. It cannot produce Upstox data with Zerodha execution.

**Required change:** create one runtime connection composition root with explicit role bindings:

- market-data connection;
- execution connection;
- account/portfolio connection;
- instrument mapping for each connection;
- deployment-to-account binding.

A connection owns credentials and capabilities. It does not replace the existing market-data, execution, account, or resolver protocols.

**Acceptance proof:** a test configures fake Upstox-like market data and a distinct Kite-like execution connection. The selected runner reads candles from the first, sends an order through the second, and records both provenance values. Reversing or removing either binding must fail closed.

### F-02: the token latch declares recovery on `None`

**Severity:** high operational correctness\
**Files:** `app/engine/runner.py:693-707`, `app/providers/kite.py:491-499`, `tests/test_token_storm_suppression.py:71-103`

`_token_sweep_suspended()` clears the token latch after any non-throwing `get_ltp()` call. `KiteProvider.get_ltp()` catches the expired-token exception and returns `None`. The real adapter therefore clears the latch while the token remains invalid. Existing tests use a fake whose `get_ltp()` raises, so they prove different behaviour from production.

A read-only reproduction against the current method contract produced:

```text
before_bad=True
suspended=False
after_bad=False
latch=None
```

**Required change:** only clear the latch after a positive health result. A `None` quote is not proof of recovery. Add a regression test through the concrete `KiteProvider.get_ltp()` failure semantics, not a fake that raises differently.

### F-03: candle transport health and usable-data freshness are conflated

**Severity:** high operator truthfulness\
**Files:** `app/engine/runner.py:724-727`, `app/providers/kite.py:390-427`

The typed candle failure channel is correct. A successful empty or too-short frame still updates `last_scan_ok` before the runner checks whether the frame is usable. The cockpit can therefore show fresh signal data when no signal frame was evaluated.

**Required change:** keep transport success separate from usable-frame freshness. A successful empty response may clear transport failure, but it must not advance the instrument’s last usable scan timestamp. Test failed transport, valid empty history, short history, and a valid completed frame as four distinct states.

### F-04: a real order may be sent without durable intent

**Severity:** critical for real money and multi-account execution\
**Files:** `app/engine/live_broker.py:83-114`, `app/engine/order_executor.py:61-74`

The system writes a WORKING journal row before placement, which is the right order. It catches journal failure, returns `None`, and places the real order anyway. It also ignores failure to persist the broker order ID after acknowledgement. A crash can leave an accepted order with no durable record. The tag sweep alerts but does not safely adopt the order.

**Required change:**

- Entry orders must fail closed if durable intent cannot commit.
- Exit handling needs a separate safety rule because an accounting outage must not block risk reduction. Persist an emergency-exit receipt to an independent append-only fallback before or immediately after submit, then reconcile loudly.
- Persist a client intent ID before submit and send it as the broker correlation tag where supported.
- Store connection, broker, account, deployment, canonical contract, side, product intent, order type, requested quantity/price, decision/reference price, and timestamps.
- Reduce immutable broker events into order state. Do not overwrite history into one aggregate row.

### F-05: order recovery is not scoped to a book or account

**Severity:** critical once more than one deployment/account exists\
**Files:** `app/engine/live_broker.py:160-180`, `app/engine/live_broker.py:204-255`

`recover_journal()` selects every WORKING row. `journal_mark_terminal()` finds by broker order ID and status only. `_inflight` and `_pending_entries` are keyed by tradingsymbol. The same symbol in two deployments, accounts, products, or brokers collides.

**Required change:** use `(tenant, connection, broker_account, deployment, client_intent_id, broker_order_id)` for lifecycle identity. Scope recovery and terminal updates by that identity. Use canonical contract plus account for position reconciliation, never symbol alone.

### F-06: live futures can inherit simulated venue methods

**Severity:** critical if the feature flag changes\
**Files:** `app/engine/broker_protocol.py:190-202`

The guard list explicitly tolerates `LiveBroker` inheriting `open_futures_position` and `close_futures_position` from `PaperBroker`. The feature defaults off, but the runtime has a setting and tests turn it on. If it becomes reachable in live mode before the methods exist, the live broker can book a simulated position without an order.

**Required change:** add a live startup/deployment capability gate that refuses futures whenever the selected execution venue lacks both live open and close implementations. Remove the tolerated inheritance before granting the feature.

### F-07: commercial tenancy has no storage boundary

**Severity:** critical commercial blocker\
**Files:** `app/api/principal.py:75-159`, `app/db/models.py:797-876`, `app/providers/factory.py:8-30`

Auth is one optional shared bearer token. When it is absent, every caller becomes `ANONYMOUS_OWNER` with wildcard scope. `Project` has no owner. Graph identifiers are global. Deployments have an unbound `account_id` string. Provider credentials and caches are process-global.

Adding route checks cannot fix this because the queried objects carry no owner.

**Required change before customer data:** add organization/user membership, owner-scoped resource keys, durable encrypted broker connections and accounts, connection grants, and owner dimensions on every query and cache key. Backfill all existing rows to the legacy owner in one migration sequence.

### F-08: DSR breadth correction is calculated but does not decide promotion

**Severity:** high research-integrity risk\
**Files:** `research/orchestrator/run.py:406-469`

The code computes `dsr_breadth_deflated` for each validated instrument, then selects `best` by the original per-instrument `dsr`. The persisted `validated_universe` drops the breadth-deflated value. A correction that cannot change selection is telemetry, not a gate.

There is a second statistical concern. The DSR paper defines the benchmark from the variance across the tested Sharpe ratios and the number of independent trials. Current parameter optimization pools Sharpe values across repeated walk-forward folds and candidates, counts folds times candidates, then multiplies by sibling compositions while keeping the original variance. It applies that in-sample trial distribution to a pooled OOS Sharpe. Those quantities do not clearly describe one independent trial population.

**Required change:** stop treating the current DSR as admission-grade until an independent statistical review defines:

- the trial family;
- effective independent trial count;
- the Sharpe distribution whose variance feeds the expected maximum;
- whether fold repetitions are trials or dependent estimates;
- whether breadth and parameter selection require nested or combined correction;
- the exact score used to select and persist the promoted candidate.

The original paper explicitly requires unselected trials, variance across trial Sharpe estimates, and the number of independent trials. See [Bailey and López de Prado, The Deflated Sharpe Ratio](https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf).

### F-09: backtest cache identity can return a stale answer

**Status 2026-08-09:** remediated on local branch `codex/execution-foundation`, not pushed or
deployed. Schema v8 now uses the full ordered dataset address plus a closed execution manifest;
the regression suite revises an older candle without changing the final timestamp and proves a
cold run. Warm-copy parity and transient premium-error rejection are also covered.

**Severity:** high research correctness\
**Files:** `app/backtest/cache.py:43-89`, `app/backtest/sweep.py:242-252`

The cache key uses strategy settings, window label, schema, instrument, interval, and last candle timestamp. It omits:

- the content hash of the full candle frame;
- provider/dataset identity and adjustment policy;
- first timestamp and bar count in the lookup;
- strategy implementation or graph content address;
- `backtest_slippage_pct`, even though the simulator reads it;
- charges/calendar/model version;
- tenant and connection.

A revised historical bar with the same final timestamp reuses stale metrics. A slippage setting change can also reuse stale metrics.

**Required change:** key results by an immutable dataset/frame address plus executable strategy/graph address and all economic model versions. Keep the current human window fields as metadata, not identity.

### F-10: SafePaperKite is strong but not proven at every construction site

**Severity:** medium-high safety assurance\
**Files:** `app/providers/kite.py:81-90`, `backend/scripts/reconcile_ledger.py:29-38`

`SafePaperKite` has a strong fail-closed allowlist and the live path uses a separate `LiveExecutionKite`. Tests prove the wrapper itself. They do not appear to prove that a normally constructed `KiteProvider` always holds that wrapper. Many tests bypass `__init__` and assign `.kite` directly. The ledger reconciliation script creates a raw `KiteConnect`; it currently calls only `margins`, but its type can place orders.

**Required change:** add a constructor invariant test, route read-only operational scripts through a read-only client/provider, and keep raw order-capable SDK objects out of scripts that do not place orders.
