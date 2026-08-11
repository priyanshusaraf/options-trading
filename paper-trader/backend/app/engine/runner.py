"""
The autonomous engine loop. One `tick()` is the whole brain:

  1. Recompute the strategy on each enabled instrument's latest candles.
  2. EXIT pass — mark open positions to market; close any that hit the premium
     stop/target or the strategy's exit flag (run first so freed capital is
     usable this same tick).
  3. ENTRY pass — collect instruments showing a FRESH entry crossover that we
     are not already holding; price the best contract for each; hand the costed
     candidates to the allocator (priority order only bites under a shortfall);
     fill the funded ones at 1 lot each. Unfunded signals are dropped, never
     queued.
  4. Snapshot portfolio equity.

In mock mode the loop also advances the simulated clock each iteration so the
whole story plays out on its own. In live mode it polls on a fixed cadence and
acts on completed candles. The owner does nothing after starting it.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import time
from contextlib import contextmanager

import pandas as pd
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.async_tasks import to_thread_drained
from app.core.instruments import all_instruments, get_instrument
from app.core.logging import log
from app.db.models import (
    LEGACY_DEPLOYMENT_ID,
    LEGACY_BROKER_ACCOUNT_ID,
    LEGACY_OWNER_ID,
    CapitalState,
    InstrumentState,
    SignalEvent,
    Trade,
)
from app.db.session import SessionLocal
from app.core.config import DEFAULT_LIVE_INTERVAL, normalize_live_interval
from app.engine.allocator import Candidate, allocate
from app.providers import capabilities as caps
from app.engine.broker import PaperBroker
from app.engine.broker_factory import make_broker
from app.engine.capital import deployable_capital
from app.engine.charges import compute_charges
from app.engine.equity_entry import (
    IntradayCandidate, equity_exit, equity_qty, qty_for_margin,
    select_intraday_entries)
from app.engine.execution_policy import plan_order, plan_reference_entry
from app.engine.event_risk import active_blackout, normalize_key, pending_flatten
from app.engine.ledger_reconcile import plan_reanchor, should_reanchor
# The Kite spellings, imported under their honest names: this is a Kite `order_margin`
# payload, guarded three lines down by `prov.name != "kite"`. A neutral-looking alias
# here would hide that the block is venue-specific.
from app.engine.kite_venue import kite_exchange, kite_product_for_charge_segment
from app.backtest.ratchet import RatchetState, wilder_atr
from app.engine.exit_monitor import evaluate_exit, trailing_stop
from app.engine.health import HealthTracker, is_stale
from app.engine.ir_shadow_metrics import ShadowMetrics
from app.engine import readiness
from app.market_data.candles import candles_to_df, frame_from, validate_candles
from app.market_data.quality import FeedQuality
from app.core.market_hours import ist_epoch
from app.core.mis_blocklist import is_mis_blocked
from app.engine.risk_controls import (
    before_entry_window, daily_loss_halt, daily_profit_lock, expiry_too_close,
    gap_halt_active, in_reentry_cooldown, intraday_blocked_for_expiry_day,
    outside_trading_session, over_per_trade_cap, round_trip_cap_reached,
    signal_already_evaluated, signal_too_old, slots_available)
from app.notify.notifier import Notifier
from app.options.picker import pick_option
from app.providers.connection import configured_execution_connection
from app.providers.factory import get_provider
from app.core import execution_binding, execution_book
from app.strategy.registry import DEFAULT_STRATEGY_KEY
from app.strategy.signals import latest_state, to_payload


def _to_df(candles) -> pd.DataFrame:
    """Live signal frame. Thin alias for the shared, VALIDATED converter — this
    was a byte-identical twin of `backtest.engine._candles_to_df`, so a data fix
    could land in one plane and miss the other. Kept as a name because callers
    and tests refer to it."""
    return candles_to_df(candles)


def _equity_charge_segment(inst) -> str:
    """Charge segment for an intraday-equity position (MIS): BSE names on BSE,
    everything else on NSE."""
    seg = (getattr(inst, "segment", "") or "").upper()
    return "BSE_INTRADAY" if seg in ("BSE", "BSE_EQ") else "NSE_INTRADAY"


# live-interval string -> candle minutes (shared by the scan gate and the
# signal-age guard; an unknown interval falls back to 15m, the strategy default)
_INTERVAL_MINUTES = {"5minute": 5, "15minute": 15, "30minute": 30, "60minute": 60}


class EngineRunner:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.provider = get_provider()
        self.notifier = Notifier()             # Telegram alerts (no-op if unconfigured)
        # Which deployment this runner executes. One runner drives one book today,
        # and that book is the legacy deployment — so this is the value every row
        # already carries and nothing changes. It is an attribute rather than a
        # literal because the whole point of Phase B is that "which book" becomes a
        # parameter of execution instead of an assumption baked into every query.
        self.deployment_id = LEGACY_DEPLOYMENT_ID
        self.owner_id = LEGACY_OWNER_ID
        # Disarm every deployment on process start — the same invariant the global
        # `armed` flag has (it is False below), for the same reason: nobody was
        # watching when the process went down, so no arm state may be inherited
        # across a restart. Best-effort; a failure here must not stop the engine
        # booting, and the in-memory flag is disarmed regardless.
        try:
            from app.core.deployments import disarm_all
            with SessionLocal() as _s:
                if disarm_all(_s):
                    _s.commit()
        except Exception as e:
            log.warn(f"could not clear persisted deployment arm state at boot: {e}",
                     event="ARM_RESET_FAIL")
        # PaperBroker unless the live-execution flags are set (then LiveBroker).
        # The execution connection is resolved here, at the composition root, because
        # this is the only place that knows both roles: `self.provider` serves prices,
        # and PT_EXECUTION_PROVIDER may name a different connection to place the
        # orders. It returns None for the single-connection config production runs,
        # which is the pre-seam path unchanged.
        # A session is opened ONLY when a stored connection is actually configured. Opening one
        # unconditionally made every `Runner()` construction take a database connection — which
        # the backtest sweep's spawned workers each do, against the same SQLite file, so a
        # parallel sweep turned into `busy_timeout` contention. The default configuration reads
        # no connection row at all and must therefore touch no session.
        if (get_settings().execution_connection or "").strip():
            with SessionLocal() as _conn_s:
                _execution_connection = configured_execution_connection(
                    self.provider, session=_conn_s)
        else:
            _execution_connection = configured_execution_connection(self.provider)
        self.broker = make_broker(self.provider, self.notifier,
                                  deployment_id=self.deployment_id,
                                  execution_connection=_execution_connection)
        # Which execution book this runner's money state belongs to. Taken from the
        # broker that was actually built rather than from configuration, because that
        # object is the one doing the writing (`core/execution_book.py`).
        self.book = execution_book.book_of(self.broker)
        # Paper-authoritative IR deployments, by instrument. Loaded at the startup
        # boundary rather than here, for the same reason the shadow deployments are —
        # construction must not read the database. Empty until then, which is what an
        # engine that has not started operating should believe.
        self.paper_authority: dict = {}
        self.paper_authority_problems: list[str] = []
        self.state: dict[str, dict] = {}      # latest per-instrument engine snapshot
        self.last_pick: dict[str, dict] = {}  # latest picker output (Options-Calc view)
        self.enabled: set[str] = self._load_enabled()
        self.intervals: dict[str, str] = self._load_intervals()   # per-instrument live TF
        self.entry_blocks: set[str] = self._load_entry_blocks()   # entries disabled
        # dual-segment / multi-strategy per-instrument config
        self.products, self.strategy_keys, self.priority_flags, self.overtrade_flags = self._load_instr_config()
        # What this runner's deployment pins, if anything — the first mechanism the
        # engine has ever consulted. The legacy deployment pins nothing
        # (`strategy_key=NULL` by contract, and no production path writes it), so this is
        # None today and resolution is per-instrument exactly as before. Resolved once at
        # boot, not per tick: it changes only when a deployment does.
        #
        # Deliberately NOT wrapped in a try. `resolve_deployment_strategy` is fail-closed,
        # and a deployment that pins a strategy the registry cannot resolve is a broken
        # promise about what is trading. Swallowing it here would resolve the
        # contradiction in favour of the weaker claim — fall through to the instrument row
        # and trade something nobody chose — which is the exact failure the fail-closed
        # split was introduced for.
        self._deployment_pin = self._load_deployment_pin()
        # The binding that produced each instrument's current signal, carried from the
        # scan to the fill. This is what a position and its trade row are attributed to:
        # the identity of the strategy whose output actually produced the entry, not the
        # raw assignment, which for a stale row names logic the registry could not resolve
        # and which therefore never ran. Rebuilt every scan; never persisted.
        self.executed_binding: dict = {}
        # L1.3A — managed, non-authoritative shadow deployments, keyed by instrument.
        # Loaded once here and at explicit refresh boundaries, never per instrument per
        # tick: a database round-trip inside the ~2.5 s scan is the shape that took the box
        # down in July. Verification happens at load, so what the loop holds has already
        # been checked.
        self.shadow_deployments: dict = {}
        self.shadow_deployment_problems: list[str] = []
        self.health = HealthTracker()
        self.params: dict = self._effective_params()   # runtime-overridable knobs
        self.position_ticks: dict[str, dict] = {}   # latest marks for open positions (fast UI feed)
        self.last_scan_ok: dict[str, object] = {}   # key -> last successful candle scan time (per-instrument freshness)
        self._stopped_at: dict[str, object] = {}    # instrument -> last stop-out time (re-entry cooldown)
        self._next_scan: dict[str, float] = {}      # key -> earliest epoch to refetch candles
        self._unresolvable_keys: set[str] = set()   # E1: alerted-once poisoned position keys
        # bad-token latch: once Kite rejects our token, every instrument's fetch would
        # fail identically (~3,800 lines/morning in the 2026-07-15 autopsy). Latch it and
        # probe with ONE instrument per loop until the owner re-auths.
        self._token_bad_until: dt.datetime | None = None
        self.last_entry_bar: dict[str, int] = {}    # key -> candle epoch of the last ENTRY signal evaluated (fresh-signal guard #12)
        self.running = False
        # ARM-TO-TRADE gate: the engine always scans, marks open positions, fires
        # SL/TP and sends alerts — but it NEVER opens a new position until the owner
        # explicitly arms it. Defaults disarmed on every process start (you must arm
        # each session), and the kill switch disarms it again.
        self.armed = False
        self._halt_notified_date = None        # de-dupe the daily-loss-halt alert
        # E1 daily profit-lock (give-back guard) — symmetric twin of the loss halt,
        # but on the upside: intraday state only, reset each new session.
        self._pl_date = None                   # date the profit-lock state below belongs to
        self._pl_high_water = 0.0              # running peak of day_pnl (₹), trails up only
        self._pl_deployed_peak = 0.0           # peak concurrent Σ open entry_cost today (denominator)
        self._pl_halted_date = None            # date the give-back flatten fired (sticky entry halt)
        self._next_reconcile_epoch = 0.0       # throttle live orphan reconciliation
        self._next_cache_sweep_epoch = 0.0     # throttle the watchlist option-chain research cache
        self._account_funds: dict | None = None  # cached live Kite funds {available, net}
        self._next_funds_epoch = 0.0           # throttle margins() polling (live balance)
        self._reanchored = False               # a re-anchor fired at least once this process
        self._reanchor_reason = ""             # WHY the ledger is/isn't anchored to the broker
        self._earnings_cache: dict[str, dt.date] = {}   # symbol -> next results date
        self._earnings_cache_date: dt.date | None = None  # calendar day the cache was built
        self._pruned_date: dt.date | None = None       # last day telemetry retention ran
        self._next_ledger_epoch = 0.0          # throttle the cash-invariant self-check (H10)
        self._ledger_drift_alerted = False     # de-dupe the ledger-drift alert per episode
        self._beat: dict[str, float] = {}      # per-lane heartbeat epoch (P3 liveness)
        # A SECOND heartbeat, on a monotonic wall clock, for the /api/health
        # readiness probe. `_beat` above is stamped from `provider.now()`, which
        # under the mock provider is SIMULATED time that jumps a whole candle per
        # tick — a staleness budget measured against it reports a perfectly
        # healthy dev engine as stale. Monotonic also survives an NTP step, which
        # `time.time()` would not. The watchdog keeps using `_beat` (it reasons in
        # market time); readiness uses this one.
        self.feed_quality = FeedQuality()   # per-instrument candle anomalies (visible, non-fatal)
        self._beat_wall: dict[str, float] = {}
        self._boot_wall = time.monotonic()      # process start, same clock as above
        self._infra_alert_epoch: dict[str, float] = {}  # throttle infra alerts per key (M1)
        self._gap_cache: tuple | None = None   # (date, open, prev_close) — index gap, once/day (fix D)
        self._gap_logged_day = None            # de-dupe the daily gap-guard alert
        self.tick_count = 0
        # L1 Stage 1 — the Component IR shadow lane's counters (ADR 0011). Observer only:
        # nothing in the entry, exit, sizing or accounting path reads them, and the lane
        # is off unless `params["ir_shadow_enabled"]` says otherwise.
        self.shadow_metrics = ShadowMetrics()
        #: Per-instrument admission verdict, carrying the interval it was decided for, so a
        #: live interval change re-decides instead of leaving a stale rejection that would
        #: need a restart to clear.
        self._shadow_admission: dict[str, object] = {}
        #: Consecutive post-admission refusals per instrument, reset by any other outcome.
        self._shadow_refusals: dict[str, int] = {}
        self._shadow_seconds = 0.0   # shadow cost accumulated within one signal iteration
        self._idle_logged = False  # de-dupe the "markets closed" log line
        self._lock = asyncio.Lock()           # serialise risk vs signal lane DB mutations
        self.on_update = None                 # async callback(state) — signal-lane snapshot
        self.on_position_ticks = None         # async callback(ticks) — fast-lane marks

    # ── instrument enable/disable ─────────────────────────────────────────
    def _load_enabled(self) -> set[str]:
        with SessionLocal() as s:
            rows = list(s.scalars(select(InstrumentState).where(
                InstrumentState.owner_id == self.owner_id)))
            en = {r.instrument_key for r in rows if r.enabled}
        return en or {i.key for i in all_instruments()}

    def set_enabled(self, key: str, enabled: bool) -> None:
        with SessionLocal() as s:
            r = s.get(InstrumentState, (self.owner_id, key))
            if r:
                r.enabled = enabled
                s.commit()
        self.enabled.add(key) if enabled else self.enabled.discard(key)
        log.info(f"{'ENABLED' if enabled else 'DISABLED'} {key} for trading")

    def apply_universe_entry(self, key: str, res: dict) -> None:
        """H11: apply a newly-added instrument's config THEN enable it. Enabling LAST
        means the engine loops — which snapshot `enabled` with list() — never see the
        key before its interval/product/strategy are set, so a config-add from the API
        threadpool can't race the loops to a half-applied state. Individual set/dict
        writes are GIL-atomic; ordering gives a consistent view without a lock."""
        if res.get("interval"):
            self.intervals[key] = res["interval"]
        if res.get("product"):
            self.products[key] = res["product"]
        if res.get("strategy_key"):
            self.strategy_keys[key] = res["strategy_key"]
        self.enabled.add(key)   # LAST — the loop only ever sees a fully-configured key

    def remove_universe_entry(self, key: str) -> None:
        """H11: disable FIRST (the loop stops acting on it), then drop its config."""
        self.enabled.discard(key)
        self.intervals.pop(key, None)
        self.products.pop(key, None)
        self.strategy_keys.pop(key, None)

    # ── per-instrument live interval + entry blocks ───────────────────────
    def _load_intervals(self) -> dict[str, str]:
        with SessionLocal() as s:
            return {r.instrument_key: normalize_live_interval(r.live_interval or "")
                    for r in s.scalars(select(InstrumentState).where(
                        InstrumentState.owner_id == self.owner_id))}

    def _load_entry_blocks(self) -> set[str]:
        with SessionLocal() as s:
            return {r.instrument_key for r in s.scalars(select(InstrumentState).where(
                InstrumentState.owner_id == self.owner_id))
                    if r.entries_blocked}

    def _load_instr_config(self) -> tuple[dict, dict, dict, dict]:
        """Per-instrument product (options|equity_intraday), assigned strategy, the
        purple priority flag, and the red overtrading flag. Missing/legacy rows
        default to options/v3/not-priority/not-overtraded."""
        from app.core.watchlists import effective_strategy_map
        products, strategies, priority, overtrade = {}, {}, {}, {}
        with SessionLocal() as s:
            for r in s.scalars(select(InstrumentState).where(
                    InstrumentState.owner_id == self.owner_id)):
                products[r.instrument_key] = r.product or "options"
                if r.strategy_key:
                    strategies[r.instrument_key] = r.strategy_key
                if r.priority_flag:
                    priority[r.instrument_key] = True
                if getattr(r, "overtrade_flag", False):
                    overtrade[r.instrument_key] = True
            # An active watchlist's strategy overrides the per-instrument default for
            # its members. Empty when no watchlists exist -> resolution unchanged.
            strategies.update(effective_strategy_map(s))
        return products, strategies, priority, overtrade

    # ── strategy selection: one path, through the binding contract ────────
    def _load_deployment_pin(self):
        """The `Strategy` this runner's deployment pins, or None for the legacy
        deployment, which pins nothing and resolves per instrument by design."""
        from app.core.deployments import resolve_deployment_strategy
        with SessionLocal() as s:
            return resolve_deployment_strategy(s, self.deployment_id)

    def _binding_for(self, key: str):
        """What executes for `key`, and on whose say-so.

        Every strategy-selection decision in the engine goes through here. Before this
        the engine called `get_strategy(self.strategy_keys.get(key))` directly, which
        answered the question correctly but privately: no version, no record of which
        layer decided, no place to ask whether the strategy was even allowed to trade.

        Note what this does *not* do, per RFC 0001 C13: the engine never asks where a
        strategy came from. It asks the binding whether it may execute and consumes the
        verdict. The one place that inspects a source lives in `core/`, outside the
        executor perimeter, and is a single reviewed boundary by design. The contract in
        `core/execution_binding.py` described that resolution and was called by nothing —
        a mechanism wired to nothing, which is this codebase's recorded defining defect.

        This is the decision half of the contract (`bind`), not the read half
        (`resolve_binding`): the deployment pin and the assignment map are already in
        memory, so consulting the contract costs no database round-trip on a ~2.5 s loop.
        """
        return execution_binding.bind(
            deployment_id=self.deployment_id, instrument_key=key,
            deployment_pin=self._deployment_pin,
            assigned_key=self.strategy_keys.get(key),
            paper_authority=self.paper_authority.get(key))

    def _execution_for(self, key: str):
        """The binding and the `Strategy` it authorises, together.

        Both, because the entry paths need both and must not derive one from the other by
        a second lookup: what a money record claims about which strategy traded it has to
        be the identity of the strategy whose output produced *that* signal. Resolving
        again at the fill would name whatever the configuration says by then.
        """
        execution = self._binding_for(key)
        return execution, execution_binding.strategy_for_execution(execution)

    def _strategy_for(self, key: str):
        """The `Strategy` that may execute for `key`.

        Authority is re-checked here, at the point of use, rather than trusted from the
        binding's `authority` field — see `strategy_for_execution`. Raises
        `AuthorityNotGranted` for a source that may not trade (today: any graph-backed
        strategy) and `StrategyNotFound` for a graph-backed key that is not registered.
        Neither is caught here: the caller decides what a refusal means for its lane.
        """
        return self._execution_for(key)[1]

    def refresh_paper_authority(self) -> int:
        """Reload the paper-authoritative IR deployments, re-verifying and registering each.

        A controlled boundary — process start, and whenever an operator changes a binding —
        never a per-tick read. Two things happen here and both are deliberate:

        * every active binding's content address is re-derived from the stored artefact
          bytes, and a mismatch drops the binding and is reported rather than repaired;
        * each surviving graph's adapter is registered in the ONE strategy registry, so a
          graph-backed key resolves like any other strategy.

        Registration confers nothing. `execution_binding` still refuses a graph-backed key
        unless the binding came from one of these records *and* the adapter's address still
        matches — resolvability and authority are different questions, and answering them
        with the same lookup is the L1.2 hazard.

        A live process loads these too. It has to: `/api/health` should be able to say what
        is deployed, and the refusal must come from the authority boundary rather than from
        an absence. `bind` does not consult them when the mode is not paper, so live
        selection is byte-for-byte what it was.
        """
        from app.core import paper_authority

        problems: list[str] = []
        try:
            with SessionLocal() as s:
                bindings = paper_authority.register_active_adapters(
                    s, on_problem=problems.append)
        except Exception as e:
            log.error(f"could not load paper-authority deployments: {e}",
                      event="PAPER_AUTHORITY_LOAD_FAIL")
            return 0
        previous = self.paper_authority
        self.paper_authority = {b.instrument_key: b for b in bindings}
        self._withdraw_superseded_signals(previous, self.paper_authority)
        self.paper_authority_problems = problems
        for problem in problems:
            log.warn(f"paper-authority deployment dropped: {problem}",
                     event="PAPER_AUTHORITY_DROPPED")
        if bindings:
            log.info(f"{len(bindings)} paper-authoritative IR deployment(s) loaded: "
                     + ", ".join(f"{b.instrument_key}={b.graph_identifier}"
                                 f" v{b.graph_version}" for b in bindings),
                     event="PAPER_AUTHORITY_LOADED")
        return len(bindings)

    def _withdraw_superseded_signals(self, previous: dict, current: dict) -> None:
        """Withdraw the signals a no-longer-authoritative paper deployment already authored.

        **The hazard.** `refresh_paper_authority` runs from the lifecycle routes, i.e. in
        between a scan and an entry pass. `process_entries` opens from `self.state` and
        attributes from `self.executed_binding`, neither of which the refresh touched — so
        an operator retiring a deployment could still have the *previous* tick's signal
        opened afterwards, and the money record would name a graph that is no longer
        authorised. Measured, not theorised: before this, `test_a_withdrawn_deployment_
        opens_no_position` opened one.

        This is the same defect L1.2b closed in `scan_signals`, arriving through the other
        door. The rule is the same, and it is the one that makes a refusal mean something:
        **withdrawing authority withdraws the signal it produced.** Skipping the next
        evaluation is only a refusal if it also retracts the last answer.

        Scoped three ways, and each one matters:

        * to instruments this deployment *held* — dropping the whole state map would be a
          different defect wearing this fix's clothes;
        * to a genuine change — a refresh that re-verifies the same content address
          withdraws nothing;
        * to state **this binding actually authored**. A paper deployment can be retired in
          a window where the instrument's pending signal came from the previous authority
          instead, and discarding that is over-withdrawal: harmless (a dropped signal never
          opens a wrong position, and the next scan republishes it) but wrong, because it
          silences a binding that was never in question.

        The attribution test is the recorded binding's own identity — its origin and the
        exact content address it carried — recomputed here rather than assumed from the
        instrument key. State with **no** recorded binding is withdrawn: it cannot open
        anything (`process_entries` refuses a signal whose author is unknown) and an
        unattributable pending signal is not something to leave lying next to a withdrawal.
        """
        from app.core.execution_binding import ORIGIN_PAPER_AUTHORITY

        for key, binding in previous.items():
            still = current.get(key)
            if still is not None and still.content_address == binding.content_address:
                continue
            executed = self.executed_binding.get(key)
            if executed is not None and not (
                    executed.origin == ORIGIN_PAPER_AUTHORITY
                    and executed.strategy_key == binding.strategy_key
                    and executed.strategy_version == binding.content_address):
                continue      # authored by something else; not this withdrawal's business
            # Both, unconditionally. An `or` here short-circuits: popping the state
            # returns a truthy value and the binding is left behind, still available to
            # attribute a fill. That is the whole defect, surviving the fix for it.
            dropped_state = self.state.pop(key, None)
            dropped_binding = self.executed_binding.pop(key, None)
            if dropped_state is not None or dropped_binding is not None:
                log.info(
                    f"withdrew the pending signal for {key}: the paper deployment that "
                    f"authored it ({binding.graph_identifier} v{binding.graph_version}) is "
                    f"no longer authoritative",
                    instrument=key, event="PAPER_AUTHORITY_WITHDRAWN")

    def report_foreign_book_positions(self) -> list[str]:
        """Name the open positions belonging to the *other* execution book.

        The compensating control for L1.3B. `broker.open_positions()` is book-scoped now,
        so a live position left open while this process runs the paper book is marked by
        nobody, ratcheted by nobody and exited by nobody — and hard invariant 2 says not
        getting out is the worst failure there is.

        Widening the read back out is not the answer: this broker cannot close the other
        book's contract, it can only write a close that never happened. So the orphan is
        made impossible to miss instead, here at the startup boundary and on
        `/api/health`. Returns the instrument keys so the caller can surface them.
        """
        try:
            with SessionLocal() as s:
                keys = sorted({p.instrument_key
                               for p in execution_book.foreign_book_positions(s, self.book)})
        except Exception as e:
            log.error(f"could not check for foreign-book positions: {e}",
                      event="FOREIGN_BOOK_CHECK_FAIL")
            return []
        if keys:
            log.warn(f"{len(keys)} open position(s) belong to the other execution book "
                     f"and are managed by nobody in this process: {', '.join(keys)}. "
                     f"This process runs the {self.book!r} book.",
                     event="FOREIGN_BOOK_POSITIONS")
        return keys

    def refresh_shadow_deployments(self) -> int:
        """Reload the managed shadow deployments, re-verifying each one.

        A controlled boundary — process start, and whenever an operator changes a binding —
        rather than a per-tick read. A deployment whose graph no longer hashes to its
        recorded address is dropped and the reason retained in
        `shadow_deployment_problems`: silently rebinding to whatever bytes are there now is
        the silent-substitution failure this project keeps closing one plane at a time, and
        a shadow that quietly observes the wrong graph produces evidence nobody can trust.

        Never raises. The shadow lane may not be able to stop the engine booting.
        """
        problems: list[str] = []
        loaded: dict = {}
        try:
            from app.core import shadow_deployments

            with SessionLocal() as session:
                for found in shadow_deployments.active_bindings(
                        session, on_problem=problems.append):
                    loaded[found.instrument_key] = found
        except Exception as e:      # noqa: BLE001 — see the docstring
            problems.append(f"could not load managed shadow deployments: {e}")
        self.shadow_deployments = loaded
        self.shadow_deployment_problems = problems
        for problem in problems:
            log.warn(f"managed shadow deployment disabled: {problem}",
                     event="IR_SHADOW_DEPLOYMENT")
        return len(loaded)

    def publish_signal(self, key: str, execution, state: dict) -> None:
        """Publish a signal and the binding that produced it — together, through one door.

        These two must not be settable independently. `process_entries` opens positions
        from `self.state`, and the money record it writes is attributed to the binding; a
        state entry with no binding is a signal whose author is unknown, and the entry
        paths refuse to open on one. Keeping the pair behind a single method is what makes
        that invariant hold by construction rather than by everyone remembering.

        Callers that simulate a scan — the entry, futures, guard and circuit-breaker
        tests — use this rather than assigning `self.state[key]`, so they exercise a state
        the engine can actually reach.
        """
        self.state[key] = state
        self.executed_binding[key] = execution

    def _executed_binding(self, key: str):
        """The binding that produced `key`'s current signal, or None if the scan did not
        resolve one this tick.

        None is unreachable by construction — every entry candidate descends from a
        `self.state` entry, and that entry is written immediately after the binding is
        recorded — so a caller seeing None is looking at a defect, and the only safe
        response is to not open. A position that never opened is recoverable; a money
        record attributing logic that did not run is not.
        """
        return self.executed_binding.get(key)

    def _interval_for(self, key: str) -> str:
        return normalize_live_interval(self.intervals.get(key, DEFAULT_LIVE_INTERVAL))

    def set_interval(self, key: str, interval: str) -> str:
        iv = normalize_live_interval(interval)
        with SessionLocal() as s:
            r = s.get(InstrumentState, (self.owner_id, key))
            if r:
                r.live_interval = iv
                s.commit()
        self.intervals[key] = iv
        self._next_scan.pop(key, None)   # force a re-scan at the new interval
        log.info(f"live interval set to {iv}", instrument=key)
        return iv

    def _effective_params(self) -> dict:
        """The engine's parameter dict, resolved through the ONE scoped path
        (Phase C): platform defaults + runtime_config, then this deployment's own
        overrides, narrowest winning.

        For the legacy deployment — the only one that exists — `params_json` is
        `{}`, so this returns exactly what `effective()` returned before. That
        equivalence is asserted directly in tests/test_scoped_config.py rather than
        left as a claim.

        Instrument scope is deliberately NOT applied here. This dict is resolved
        once per loop iteration and shared across every instrument, so folding a
        per-instrument layer into it would apply one instrument's overrides to all
        of them. Instrument scope belongs at the per-instrument call sites, which
        is where `resolve(..., instrument_key=...)` is meant to be used.
        """
        from app.core.scoped_config import resolve
        with SessionLocal() as s:
            return resolve(s, self.settings, deployment_id=self.deployment_id,
                           owner_id=self.owner_id)

    def refresh_params(self) -> None:
        """Re-read runtime overrides so live Settings edits take effect."""
        self.params = self._effective_params()

    def set_entries_blocked(self, key: str, blocked: bool) -> None:
        with SessionLocal() as s:
            r = s.get(InstrumentState, (self.owner_id, key))
            if r:
                r.entries_blocked = blocked
                s.commit()
        self.entry_blocks.add(key) if blocked else self.entry_blocks.discard(key)
        log.info(f"{'BLOCKED' if blocked else 'UNBLOCKED'} new entries", instrument=key)

    @contextmanager
    def _upsert_state(self, key: str):
        """Yield the InstrumentState row for `key`, creating it if missing (a freshly
        added instrument may not have a row yet), and commit on a clean exit.

        A context manager rather than a `(session, row)` pair on purpose. The old
        shape handed an OPEN session back to four callers that each ended with
        `s.commit(); s.close()` — so any raise in between (a failed commit, a bug
        in the lines that follow) skipped the close and leaked the session's
        pooled connection. SQLAlchemy reclaims those on GC, which is why it never
        surfaced as a clean error: it surfaces as pool pressure under load, with
        /api/health answering 200 throughout. Closing is now structural, and the
        caller cannot forget it.

        The commit lives INSIDE the block, so a caller's in-memory bookkeeping
        after the `with` only runs if the write actually landed.
        """
        with SessionLocal() as s:
            r = s.get(InstrumentState, (self.owner_id, key))
            if r is None:
                r = InstrumentState(owner_id=self.owner_id, instrument_key=key)
                s.add(r)
            yield r
            s.commit()

    def set_product(self, key: str, product: str) -> str:
        """Assign an instrument to the options or equity_intraday segment (live-applied).
        Refuses intraday for a name the MIS-availability sheet marks ineligible (#5)."""
        product = "equity_intraday" if product == "equity_intraday" else "options"
        if product == "equity_intraday" and is_mis_blocked(key):
            raise ValueError(f"{key} is not MIS-eligible (no/low intraday leverage) — "
                             f"can't add it to the intraday portfolio")
        with self._upsert_state(key) as r:
            r.product = product
        self.products[key] = product
        log.info(f"PRODUCT set to {product}", instrument=key)
        return product

    def set_priority_flag(self, key: str, flag: bool) -> None:
        """Toggle the watchlist 'purple' priority flag (intraday selection always wins)."""
        with self._upsert_state(key) as r:
            r.priority_flag = bool(flag)
        if flag:
            self.priority_flags[key] = True
        else:
            self.priority_flags.pop(key, None)
        log.info(f"PRIORITY {'set' if flag else 'cleared'}", instrument=key)

    def set_overtrade_flag(self, key: str, flag: bool) -> None:
        """Toggle the watchlist 'red' overtrading flag. Advisory only — the engine
        does NOT change behavior based on it."""
        with self._upsert_state(key) as r:
            r.overtrade_flag = bool(flag)
        if flag:
            self.overtrade_flags[key] = True
        else:
            self.overtrade_flags.pop(key, None)
        log.info(f"OVERTRADE {'set' if flag else 'cleared'}", instrument=key)

    def set_strategy(self, key: str, strategy_key: str | None) -> str | None:
        """Assign which registered strategy trades this instrument (None = default v3).

        Raises `AuthorityNotGranted` if the key names a source that may not execute.
        Without that check this route is the entire path from "a graph-backed strategy
        exists" to "a graph-backed strategy trades real money": the registry resolves it,
        so the membership test below passes, and the engine would then trade it. The
        refusal is loud rather than a coercion to the default — silently assigning
        something other than what was asked for is the failure mode, not the fix.
        """
        from app.strategy.registry import strategy_keys as _keys
        execution_binding.assert_may_execute(strategy_key)
        sk = strategy_key if (strategy_key and strategy_key in _keys()) else None
        with self._upsert_state(key) as r:
            r.strategy_key = sk
        if sk:
            self.strategy_keys[key] = sk
        else:
            self.strategy_keys.pop(key, None)
        log.info(f"STRATEGY set to {sk or 'default'}", instrument=key)
        return sk

    # ── bad-token latch (autopsy rank 5: token-auth error storm) ──────────
    @staticmethod
    def _is_auth_error(exc: Exception) -> bool:
        """Kite's SDK surfaces a dead/expired token as a generic exception whose
        message quotes the literal 'Incorrect `api_key` or `access_token`.'"""
        msg = str(exc)
        return "Incorrect" in msg and ("api_key" in msg or "access_token" in msg)

    def _is_token_probably_bad(self, now: dt.datetime) -> bool:
        return self._token_bad_until is not None and now < self._token_bad_until

    def _mark_token_bad(self, now: dt.datetime, cooldown_seconds: float = 20.0) -> None:
        self._token_bad_until = now + dt.timedelta(seconds=cooldown_seconds)

    def _mark_token_ok(self) -> None:
        self._token_bad_until = None

    @staticmethod
    def _is_positive_quote(px: object) -> bool:
        """A probe result that actually proves the session can read the market.

        `KiteProvider.get_ltp` catches the expired-token exception and returns `None`, so
        "did not raise" is not evidence of anything — it is the adapter's normal answer to
        a dead token, an unresolvable symbol and an empty quote payload alike. Only a real
        finite price above zero clears the latch. `bool` is excluded because it is an `int`.
        """
        return (isinstance(px, (int, float)) and not isinstance(px, bool)
                and px == px and px not in (float("inf"), float("-inf")) and px > 0)

    def _token_sweep_suspended(self) -> bool:
        """True when the sweep should be skipped this loop. While latched we spend
        exactly ONE provider call on a probe instrument to detect re-auth, instead of
        letting every enabled instrument hammer historical_data with a dead token."""
        now = self.provider.now()
        if not self._is_token_probably_bad(now):
            return False
        probe_key = next(iter(sorted(self.enabled)), None)
        if probe_key is not None:
            try:
                px = self.provider.get_ltp(get_instrument(probe_key))
            except Exception:
                px = None  # still bad — stay latched, suppressed until next loop's probe
            if self._is_positive_quote(px):
                self._mark_token_ok()
                log.info("token recovered — resuming full market-data sweep",
                         event="TOKEN_RECOVERED")
                return False
            # A `None` quote is absence of evidence, not evidence of recovery. Staying
            # latched costs one probe call per loop and the latch's own cooldown still
            # expires it, so a genuinely-recovered session is never stranded.
        log.warn("token invalid — pausing market-data sweep until re-auth",
                 event="TOKEN_SUSPEND_SWEEP")
        return True

    # ── lane 1: strategy recompute (per-instrument interval) ──────────────
    def scan_signals(self) -> None:
        s, prov = self.settings, self.provider
        if self._token_sweep_suspended():
            return
        opens = {p.instrument_key: p for p in self.broker.open_positions()}
        for key in list(self.enabled):
            inst = get_instrument(key)
            if not prov.is_tradable_now(inst):
                continue  # market closed — no new candle can print; don't poll
            try:
                candles = prov.get_candles(inst, self._interval_for(key), s.history_days)
                # Transport health only. The read succeeded, so the connection is fine —
                # but "the provider answered" is not "a frame was evaluated". Freshness is
                # stamped below, once the frame is known to be usable.
                self.health.record_ok("candle", prov.now())
            except Exception as e:
                self.health.record_fail("candle", str(e), prov.now())
                if self._is_auth_error(e):
                    # every other instrument would fail identically this loop — latch
                    # now so the remaining fetches are skipped, not repeated.
                    self._mark_token_bad(prov.now())
                if self.health.should_log_failure("candle"):
                    log.error(f"candles failed: {e}", instrument=key)
                if self._is_token_probably_bad(prov.now()):
                    break
                continue
            # Validate ONCE here and build the frame from the result, so the
            # report is available to surface rather than being discarded inside
            # the converter. A repaired feed is corrected silently otherwise, and
            # "we handle bad data" is not the same claim as "the data is fine".
            candles, feed_report = validate_candles(candles)
            if self.feed_quality.record(key, feed_report, prov.now()):
                log.warn(f"candle feed anomaly: {feed_report.summary()}",
                         instrument=key, event="FEED_QUALITY")
            if len(candles) < s.ema_length + 5:
                continue
            # Per-instrument freshness: a usable frame exists for this key on this loop.
            # Deliberately AFTER the empty/short checks — an empty-but-successful read used
            # to stamp this, so the cockpit showed a fresh scan time beside a signal from
            # whenever the data last worked. Transport ok, data absent: two claims, two
            # surfaces. `stale` in /api/watchlist reads this one.
            self.last_scan_ok[key] = prov.now()
            # per-instrument strategy: the default (v3) keeps the exact chart payload;
            # any other strategy yields a strategy-agnostic latest (canonical flags).
            try:
                execution, strat = self._execution_for(key)
            except execution_binding.AuthorityNotGranted as e:
                # Fail closed on this instrument only. Two things this must NOT do:
                # substitute the default (the silent-substitution class the registry
                # split exists to prevent — the trade rows would name a strategy that
                # never ran), or abort the scan (one refused instrument has no claim
                # over the rest of the book, and invariant 2 forbids blocking exits).
                # Rate-limited: the scan revisits every enabled key every ~2.5 s, and
                # unthrottled per-tick errors buried the journal in the 2026-07-15
                # autopsy. `error_ratelimited` re-surfaces after the window.
                log.error_ratelimited(
                    f"{key} is assigned a strategy that may not execute: {e}",
                    key=key, event="authority_refused", window_seconds=300.0)
                # Drop the earlier tick's signal with it. `process_entries` reads
                # `self.state`, which survives a skipped scan — so leaving it would let a
                # refused instrument open on a signal produced while it was still
                # authorised, and stamp an identity nothing authorises now. Skipping the
                # evaluation is only a refusal if it also withdraws the last answer.
                self.state.pop(key, None)
                self.executed_binding.pop(key, None)
                continue
            signal_frame = frame_from(candles)
            if strat.key == DEFAULT_STRATEGY_KEY:
                sig = strat.signals(signal_frame, ema_length=s.ema_length,
                                    z_length=s.z_length, entry_z=s.entry_z,
                                    slope_lookback=s.slope_lookback)
                # latest_state, NOT to_payload: the payload walks every bar to
                # build chart arrays this path immediately discards. See
                # strategy/signals.py — it was 76% of the scan's runtime.
                latest = latest_state(sig, entry_z=s.entry_z)
            else:
                sig = strat.signals(signal_frame)
                latest = self._generic_latest(sig)
            # L1 Stage 1 — observe the IR mirror on the SAME frame the authoritative
            # strategy just consumed. Deliberately before the `if not latest` guard: a
            # frame the authoritative lane found nothing in is exactly the case a shadow
            # is meant to see. Nothing below reads its result.
            self._observe_shadow(key, strat, signal_frame, sig)
            if not latest:
                continue
            held = opens.get(key)
            self.publish_signal(key, execution, {
                "instrument": key, "name": inst.name, "segment": inst.segment,
                "interval": self._interval_for(key),
                "time": latest["time"], "close": latest["close"], "ema": latest["ema"],
                "z": latest["z"], "z_prev": latest["z_prev"], "slope": latest["slope"],
                "std": latest["std"], "trend": latest["trend"], "signal": latest["signal"],
                "long_exit": latest["long_exit"], "short_exit": latest["short_exit"],
                "position": held.to_dict() if held else None,
                "has_options": inst.has_options,
                "entries_blocked": key in self.entry_blocks,
                "product": self.products.get(key, "options"),
                "strategy": strat.key,
                "priority_flag": self.priority_flags.get(key, False),
            })
            # H2 — ratchet management for strategies that declare a risk_model: stash the
            # latest completed-bar ATR (for seeding a new entry) and, for a held
            # ratchet-managed position, advance its spot ratchet + flag a close-confirmed hit.
            rm = getattr(strat, "risk_model", None)
            if rm:
                try:
                    atr_ser = wilder_atr(_to_df(candles), int(rm["atr_length"]))
                    last_atr = float(atr_ser.iloc[-1]) if len(atr_ser) else float("nan")
                    self.state[key]["_ratchet_atr"] = last_atr if last_atr == last_atr else None
                    if held is not None and held.entry_atr is not None:
                        self.state[key]["ratchet_exit"] = self._apply_ratchet(held, candles, rm)
                except Exception as e:
                    log.error(f"ratchet update failed: {e}", instrument=key)

    def _shadow_admitted(self, key: str, pairing) -> bool:
        """Decide once, per (instrument, live interval), whether this graph may be shadowed
        at all — and make a refusal terminal and visible rather than repeated.

        Without this the lane learns the answer from a refusal instead of from the
        configuration, and an instrument whose interval can never satisfy the graph's
        warmup refuses on every scan for the whole session: no signal, a log line every
        2.5 s, and evaluation cost for a result that was knowable in advance.
        """
        from app.engine import ir_shadow

        interval = self._interval_for(key)
        cached = self._shadow_admission.get(key)
        if cached is not None and cached.interval == interval:
            return cached.ok

        adapter = pairing.adapter()
        verdict = ir_shadow.admit(
            instrument_key=key, segment=get_instrument(key).segment, interval=interval,
            history_days=int(self.settings.history_days),
            warmup=int(getattr(adapter, "declared_warmup", 0) or 0))
        self._shadow_admission[key] = verdict
        self._shadow_refusals.pop(key, None)
        if verdict.ok:
            self.shadow_metrics.admitted(key)
        else:
            self.shadow_metrics.rejected(key, verdict.reason)
            log.warn(f"IR shadow pairing REJECTED at admission — {verdict.reason}",
                     instrument=key, event="IR_SHADOW_ADMISSION")
        return verdict.ok

    def _shadow_track_refusals(self, key: str, observation) -> None:
        """Demote a pairing the feed keeps refusing, however confident admission was.

        Admission reasons from configuration and can be right about the arithmetic while the
        feed returns something else entirely. The contract is not "predict correctly", it is
        "never repeat an in-hours refusal", so observation gets the last word.
        """
        from app.engine import ir_shadow

        if observation.reason != ir_shadow.INSUFFICIENT_HISTORY:
            self._shadow_refusals.pop(key, None)
            return
        refusals = self._shadow_refusals.get(key, 0) + 1
        self._shadow_refusals[key] = refusals
        if refusals < ir_shadow.REFUSALS_BEFORE_DEMOTION:
            return
        admission = self._shadow_admission.get(key)
        if admission is None:
            return
        demoted = ir_shadow.demote(admission, observed_bars=observation.frame_bars,
                                   refusals=refusals)
        self._shadow_admission[key] = demoted
        self.shadow_metrics.rejected(key, demoted.reason)
        log.warn(f"IR shadow pairing DEMOTED — {demoted.reason}",
                 instrument=key, event="IR_SHADOW_ADMISSION")

    def _observe_shadow(self, key: str, strat, signal_frame, sig) -> None:
        """L1 Stage 1 — evaluate the IR mirror of `strat` and record any disagreement.

        **This method may not influence anything.** It returns None, writes nothing into
        `self.state`, `self.params`, `self.strategy_keys` or the broker, and swallows every
        failure: a shadow that can interrupt the authoritative lane would be a worse defect
        than the one it exists to detect. Its cost is measured, not hidden.

        The whole body is inside one `try` on purpose — including the flag read. Any way
        this can fail is a way the lane fails closed and the engine carries on.
        """
        try:
            if not self.params.get("ir_shadow_enabled", False):
                return
            from app.engine import ir_shadow, ir_shadow_store

            # One question, one boundary. A managed deployment outranks the Stage 1 runtime
            # pairing; `shadow_source_for` states that order in one place so the observer
            # never has to know there are two sources.
            source = execution_binding.shadow_source_for(
                instrument_key=key, authoritative_key=strat.key,
                managed=self.shadow_deployments.get(key),
                interval=self._interval_for(key))
            if source is None:
                self.shadow_metrics.skipped(key)
                return
            pairing = ir_shadow.pairing_for(source.pairing_key)
            if pairing is None:
                self.shadow_metrics.skipped(key)
                return
            if not self._shadow_admitted(key, pairing):
                return
            started = time.perf_counter()
            observation = ir_shadow.observe(
                instrument_key=key, authoritative_key=strat.key,
                authoritative_frame=sig, frame=signal_frame, now=self.provider.now())
            self._shadow_seconds += time.perf_counter() - started
            if observation is None:
                return
            # Every observation the live lane makes is taken on a tradable instrument —
            # `scan_signals` has already skipped the closed ones — so these are the
            # in-hours events Stage 1 criterion 8 is about.
            self.shadow_metrics.observe(observation, market_open=True)
            self._shadow_track_refusals(key, observation)
            if observation.reason != ir_shadow.AGREEMENT:
                if ir_shadow_store.record(observation, market_open=True):
                    log.warn(f"IR shadow disagreement: {observation.reason} — "
                             f"{observation.detail}", instrument=key,
                             event="IR_SHADOW_DIVERGENCE")
        except Exception as e:
            log.error(f"IR shadow lane error (authoritative lane unaffected): {e}",
                      instrument=key, event="IR_SHADOW")

    def _apply_ratchet(self, pos, candles, rm) -> bool:
        """H2 — drive the backtest-validated RatchetState on the underlying's COMPLETED
        candles for a ratchet-managed options position, persisting hw/spot_stop and
        advancing ratchet_last_bar_ts (so a bar is never consumed twice). Manages bars
        strictly after the fill bar (Pine canManage). Returns True if the spot stop is
        close-confirmed hit — the risk loop consumes it as a RATCHET_STOP exit."""
        if pos.entry_atr is None or not candles:
            return False
        atr = wilder_atr(_to_df(candles), int(rm["atr_length"]))
        rs = RatchetState.restore(
            pos.direction, pos.entry_spot, pos.entry_atr, rm,
            hw=pos.ratchet_hw if pos.ratchet_hw is not None else pos.entry_spot,
            stop=pos.spot_stop if pos.spot_stop is not None else pos.entry_spot)
        for i, c in enumerate(candles):
            if c.ts <= pos.entry_time:
                continue   # no management on/before the fill bar
            if pos.ratchet_last_bar_ts is not None and c.ts <= pos.ratchet_last_bar_ts:
                continue   # already consumed on a prior scan
            rs.update(c.high, c.low, c.close, float(atr.iloc[i]))
            pos.ratchet_last_bar_ts = c.ts
        pos.ratchet_hw = rs.hw
        pos.spot_stop = rs.stop
        self.broker.commit()
        return rs.stop_hit(candles[-1].close)

    def _seed_ratchet(self, pos, spot, rm, atr, strategy_key) -> None:
        """H2 — freeze the entry ATR + seed the initial spot stop at fill, so scan_signals
        can manage the position with the same ratchet the strategy was backtested with."""
        if not rm or atr is None or atr <= 0:
            return
        d = 1.0 if pos.direction == "LONG" else -1.0
        pos.strategy_key = strategy_key
        pos.entry_atr = float(atr)
        pos.ratchet_hw = float(spot)
        pos.spot_stop = float(spot) - d * float(rm["initial_risk_atr"]) * float(atr)
        pos.ratchet_last_bar_ts = pos.entry_time
        self.broker.commit()

    def _generic_latest(self, sig) -> dict | None:
        """Strategy-agnostic 'latest bar' for non-default strategies — reads the
        canonical flag columns (and whatever indicator columns exist) so any
        registered strategy can drive the engine without the v3-only chart payload."""
        from app.strategy.signals import _epoch
        sig = sig.dropna(subset=["longEntry", "shortEntry"]).reset_index(drop=True) \
            if "longEntry" in sig.columns else sig
        if sig.empty:
            return None
        last = sig.iloc[-1]

        def g(col):
            return float(last[col]) if col in sig.columns and pd.notna(last[col]) else None
        signal = ("LONG_ENTRY" if bool(last["longEntry"])
                  else "SHORT_ENTRY" if bool(last["shortEntry"]) else "NONE")
        drift, z = g("driftScore"), g("z")
        trend = (None if drift is None else
                 "bull" if drift > 0 else "bear" if drift < 0 else "flat")
        return {
            "time": _epoch(last["date"]), "close": round(float(last["close"]), 2),
            "ema": round(g("ema"), 2) if g("ema") is not None else None,
            "z": round(z, 4) if z is not None else None, "z_prev": None,
            "slope": None, "std": None, "trend": trend, "signal": signal,
            "long_exit": bool(last["longExit"]), "short_exit": bool(last["shortExit"]),
        }

    # ── E1: a position whose instrument left the universe must never take the book down ─
    def _resolve_or_skip(self, key: str):
        """Resolve an open position's instrument, or None if it has left the universe.

        `load_universe` pops deactivated instruments, so `get_instrument` raises for a
        position on an instrument the owner has since removed. Callers must skip THAT
        position only — an unguarded lookup used to abort marking, trailing stops, SL/TP
        and the MIS close-flatten for the entire book, silently, on every risk tick."""
        try:
            return get_instrument(key)
        except KeyError:
            if key not in self._unresolvable_keys:
                self._unresolvable_keys.add(key)     # alert once, not every ~1s tick
                log.error(
                    f"open position on unresolvable instrument '{key}' — skipping it; "
                    f"the rest of the book is still managed. Re-add the instrument or "
                    f"close the position manually.",
                    instrument=key, event="UNRESOLVABLE_INSTRUMENT")
            return None

    # ── lane 2 (fast): mark open positions, trail stop, staleness guard, exit ─
    def mark_and_exit_positions(self) -> None:
        prov = self.provider
        now = prov.now()
        # Scheduled-release flatten runs in the EXIT lane, before marking: a position
        # must be out before the window opens, and exits are never gated by arm state,
        # halts or blackouts.
        self._safe_flatten_before_events(now)
        opens = {p.instrument_key: p for p in self.broker.open_positions()}
        insts = []
        for k in list(opens):
            inst = self._resolve_or_skip(k)
            if inst is None:
                opens.pop(k, None)
            else:
                insts.append(inst)
        if not opens:
            self.position_ticks = {}
            self._safe_maybe_profit_lock(now)
            return
        try:
            snap = prov.live_snapshot(insts, list(opens.values()))
            self.health.record_ok("quote", now)
        except Exception as e:
            self.health.record_fail("quote", str(e), now)
            if self.health.should_log_failure("quote"):
                log.error(f"position snapshot failed: {e}")
            snap = {}
        ticks: dict[str, dict] = {}
        for key, pos in list(opens.items()):
            data = snap.get(key) or {}
            premium = data.get("option_premium")
            spot = data.get("spot")
            # intraday equity marks to SPOT (no option), exits on direction-aware
            # SL/TP + strategy flag, and never trails. Handled separately so the
            # options long-premium path below is untouched.
            if pos.segment == "equity_intraday":
                self._mark_exit_equity(pos, key, spot, now, ticks, opens)
                continue
            if pos.segment == "index_futures":
                self._mark_exit_futures(pos, key, now, ticks, opens)
                continue
            if premium is not None:
                self.broker.mark(pos, premium, spot, now=now)
                self._apply_trailing(pos)
            pos_stale = premium is None or is_stale(
                pos.last_mark_time, now, self.settings.max_stale_seconds)
            st = self.state.get(key, {})
            if not pos_stale:
                should, reason = evaluate_exit(
                    pos.direction, pos.stop_price, pos.target_price, premium,
                    st.get("long_exit", False), st.get("short_exit", False),
                    target_disabled=pos.no_take_profit,
                    ratchet_exit=st.get("ratchet_exit", False))   # H2
                if should:
                    trade = self.broker.close_position(pos, premium, reason, now, spot)
                    if trade is not None:
                        if reason == "STOP_LOSS":
                            self._stopped_at[key] = now   # start the re-entry cooldown
                        if self.params.get("notify_enabled", True):
                            self.notifier.closed(trade)
                        opens.pop(key, None)
                        if key in self.state:
                            self.state[key]["position"] = None
                        continue
                    # live close didn't go through (unfilled / ownership block) —
                    # keep managing the position; LiveBroker has already alerted.
                # not exiting — warn (once) if the premium is nearing the SL or TP
                if self.params.get("notify_enabled", True):
                    self.notifier.check_proximity(
                        key, pos.tradingsymbol, premium, pos.stop_price, pos.target_price,
                        self.params.get("alert_proximity_pct", 0.10))
            d = pos.to_dict()
            ticks[key] = {
                "instrument": key, "tradingsymbol": pos.tradingsymbol,
                "option_premium": round(premium, 2) if premium is not None else None,
                "spot": round(spot, 2) if spot else None,
                "unrealized_pnl": d["unrealized_pnl"],
                "stop_price": d["stop_price"], "target_price": d["target_price"],
                "high_water_premium": d["high_water_premium"],
                "stale": pos_stale,
                "stale_age": None if pos.last_mark_time is None
                             else round((now - pos.last_mark_time).total_seconds(), 1),
                "last_mark_time": pos.last_mark_time.isoformat() if pos.last_mark_time else None,
            }
        self.broker.commit()  # persist marks + ratcheted stops
        self.position_ticks = ticks
        self._safe_maybe_profit_lock(now)

    def _apply_trailing(self, pos) -> None:
        """Ratchet the premium stop upward as profit thresholds are crossed."""
        self.broker.ensure_stop_protection(pos, pos.last_premium)  # self-heal a missing backstop every tick
        p = self.params
        # H2 — a ratchet-managed position (declared risk_model, entry_atr seeded) is
        # governed by the backtest-validated spot ratchet in scan_signals, NOT this
        # legacy percent-of-premium trail. The GTT stays parked at the initial premium
        # stop as the disaster floor; the ratchet fires the primary exit.
        if pos.entry_atr is not None:
            return
        if not p.get("trail_enabled", True):
            return
        new_stop = trailing_stop(
            pos.entry_premium, pos.high_water_premium or pos.entry_premium, pos.stop_price,
            trigger_pct=p["trail_trigger_pct"],
            first_step_lock_pct=p["trail_first_step_lock_pct"],
            step_lock_pct=p["trail_step_lock_pct"])
        if new_stop > pos.stop_price:
            log.info(f"TRAIL SL {pos.tradingsymbol} {pos.stop_price:.2f} -> {new_stop:.2f} "
                     f"(high {pos.high_water_premium:.2f})", instrument=pos.instrument_key,
                     event="TRAIL")
            pos.stop_price = new_stop
            self.broker.update_stop_protection(pos, pos.last_premium)  # ratchet the GTT too (live)

    def _apply_lockstep(self, pos) -> None:
        """Lockstep band: once an equity position is in profit, ratchet its stop AND
        target together (break-even floored). A hand-pinned target is left in place;
        only the stop slides then. `pos.entry_sl_pct`/`entry_tp_pct` (purple tiering,
        2026-07-17), when set, override the global knobs so a purple position's band
        never reshapes if the global intraday_stop_loss_pct/intraday_target_pct or the
        purple flag itself changes after entry."""
        self.broker.ensure_stop_protection(pos, pos.last_premium)  # self-heal a missing backstop every tick
        from app.engine.equity_entry import lockstep_band
        p = self.params
        if not p.get("intraday_lockstep_enabled", True):
            return
        last = pos.last_premium or pos.entry_premium
        margin = pos.entry_cost - pos.entry_charges
        rt = (2.0 * pos.entry_charges / pos.qty) if pos.qty else 0.0   # round-trip cost/share
        be = pos.entry_premium + rt if pos.direction == "LONG" else pos.entry_premium - rt
        sl_pct = pos.entry_sl_pct if pos.entry_sl_pct is not None else p.get("intraday_stop_loss_pct", 0.01)
        tp_pct = pos.entry_tp_pct if pos.entry_tp_pct is not None else p.get("intraday_target_pct", 0.02)
        new_stop, new_target = lockstep_band(
            pos.direction, pos.entry_premium, pos.qty, margin,
            pos.stop_price, pos.target_price, last,
            trigger_pct=p.get("intraday_lockstep_trigger_pct", 0.02),
            sl_pct=sl_pct, tp_pct=tp_pct,
            breakeven_price=be, rt_per_share=rt,
            profit_lock_threshold=p.get("intraday_profit_lock_threshold", 200.0),
            profit_lock_frac=p.get("intraday_profit_lock_frac", 0.5))
        if pos.manual_target:
            new_target = pos.target_price   # owner-pinned target isn't auto-extended
        if new_stop != pos.stop_price or new_target != pos.target_price:
            log.info(f"LOCKSTEP {pos.tradingsymbol} SL {pos.stop_price:.2f}->{new_stop:.2f} "
                     f"TP {pos.target_price:.2f}->{new_target:.2f}",
                     instrument=pos.instrument_key, event="LOCKSTEP")
            stop_moved = new_stop != pos.stop_price
            pos.stop_price, pos.target_price = new_stop, new_target
            if stop_moved:
                # #18: ratchet the exchange-side SL-M backstop too (no-op on paper;
                # LiveBroker re-prices the resting SL-M). Options trail this at L402.
                self.broker.update_stop_protection(pos, pos.last_premium)

    def _mark_exit_equity(self, pos, key, spot, now, ticks, opens) -> None:
        """Mark + exit an intraday-equity position against SPOT (direction-aware
        SL/TP + strategy flag + lockstep band). No proximity alerts; mirrors the
        options lane's bookkeeping (ticks, cooldown, state) for the equity case."""
        if spot is not None:
            self.broker.mark(pos, spot, spot, now=now)
        pos_stale = spot is None or is_stale(pos.last_mark_time, now, self.settings.max_stale_seconds)
        st = self.state.get(key, {})
        if not pos_stale:
            self._apply_lockstep(pos)   # ratchet SL+TP together before the exit check
            should, reason = equity_exit(
                pos.direction, spot, pos.stop_price, pos.target_price,
                st.get("long_exit", False), st.get("short_exit", False),
                target_disabled=pos.no_take_profit)
            if should:
                trade = self.broker.close_equity_position(pos, spot, reason, now)
                if trade is not None:
                    if reason == "STOP_LOSS":
                        self._stopped_at[key] = now
                    if self.params.get("notify_enabled", True):
                        self.notifier.closed(trade)
                    opens.pop(key, None)
                    if key in self.state:
                        self.state[key]["position"] = None
                    return
        d = pos.to_dict()
        ticks[key] = {
            "instrument": key, "tradingsymbol": pos.tradingsymbol,
            "option_premium": None, "spot": round(spot, 2) if spot else None,
            "unrealized_pnl": d["unrealized_pnl"],
            "stop_price": d["stop_price"], "target_price": d["target_price"],
            "high_water_premium": d["high_water_premium"], "stale": pos_stale,
            "stale_age": None if pos.last_mark_time is None
                         else round((now - pos.last_mark_time).total_seconds(), 1),
            "last_mark_time": pos.last_mark_time.isoformat() if pos.last_mark_time else None,
        }

    def _mark_exit_futures(self, pos, key, now, ticks, opens) -> None:
        """Mark + exit an index-futures position against the FUTURES price.

        Marks on `get_futures_ltp`, NOT on spot. A future trades at a basis to its
        underlying — tens of points on an index — so marking to spot mis-prices
        the position on every tick and corrupts both unrealized P&L and the
        distance to the stop. If the provider cannot price the contract the mark
        is skipped and the position goes STALE, which suppresses the exit check
        rather than acting on a wrong price.

        The delivery guard runs FIRST and outranks everything else. A contract
        inside its delivery window must be closed regardless of P&L, stop, target
        or staleness — holding it is an obligation to deliver, not a trade. Index
        futures are cash-settled so this never fires today; it exists so a
        commodity extension inherits the protection instead of having to
        remember it.
        """
        inst = get_instrument(key)
        # 1) Delivery guard — higher priority than any normal exit.
        if self.params.get("index_futures_delivery_guard", True):
            from app.engine.delivery_calendar import (CashSettledCalendar,
                                                      no_delivery_window)
            try:
                safe = no_delivery_window(key, now.date(), pos.expiry,
                                          CashSettledCalendar())
            except Exception:
                safe = False        # unknown means unsafe
            if not safe:
                px = self.provider.get_futures_ltp(inst, pos.expiry) or pos.last_premium
                trade = self.broker.close_futures_position(
                    pos, px, "DELIVERY_WINDOW", now)
                if trade is not None:
                    self._alert_infra(
                        f"delivery_{key}",
                        f"{key} force-closed: inside its delivery window. A futures "
                        f"position held through delivery is an obligation, not a trade.")
                    opens.pop(key, None)
                    if key in self.state:
                        self.state[key]["position"] = None
                return

        fut = self.provider.get_futures_ltp(inst, pos.expiry)
        if fut is not None:
            self.broker.mark(pos, fut, fut, now=now)
        pos_stale = fut is None or is_stale(pos.last_mark_time, now,
                                            self.settings.max_stale_seconds)
        st = self.state.get(key, {})
        if not pos_stale:
            self._apply_lockstep(pos)
            should, reason = equity_exit(
                pos.direction, fut, pos.stop_price, pos.target_price,
                st.get("long_exit", False), st.get("short_exit", False),
                target_disabled=pos.no_take_profit)
            if should:
                trade = self.broker.close_futures_position(pos, fut, reason, now)
                if trade is not None:
                    if reason == "STOP_LOSS":
                        self._stopped_at[key] = now
                    if self.params.get("notify_enabled", True):
                        self.notifier.closed(trade)
                    opens.pop(key, None)
                    if key in self.state:
                        self.state[key]["position"] = None
                    return
        d = pos.to_dict()
        ticks[key] = {
            "instrument": key, "tradingsymbol": pos.tradingsymbol,
            "option_premium": None, "spot": round(fut, 2) if fut else None,
            "unrealized_pnl": d["unrealized_pnl"],
            "stop_price": d["stop_price"], "target_price": d["target_price"],
            "high_water_premium": d["high_water_premium"], "stale": pos_stale,
            "stale_age": None if pos.last_mark_time is None
                         else round((now - pos.last_mark_time).total_seconds(), 1),
            "last_mark_time": pos.last_mark_time.isoformat() if pos.last_mark_time else None,
        }

    def _intraday_margin_sizer(self):
        """Fix A: a sizer that sizes intraday MIS qty against the REAL Zerodha margin
        (`order_margins`) instead of an assumed 5x leverage — the 2026-07-13 rejection
        cascade was a 5x-assumed vs ~2.5x-real mismatch. Returns None on the mock /
        unauthenticated provider (→ select_intraday_entries uses the leverage model).

        Per (symbol, side) the real per-share margin is quoted once per session and
        cached (it's stable intraday), so a full entry cycle makes at most one quote
        per name. A per-name quote failure degrades to the leverage model for that name
        only — never a hard stop.

        2026-07-21 (owner): the artificial notional cap added in Task 2 (R2) is REMOVED
        — it was throttling deployed real margin to ~4.5k. qty is now sized purely to
        the real margin quote (deploy the full `target_margin` of real margin) and
        Zerodha's own MIS multiplier decides the resulting notional. `intraday_leverage`
        is used ONLY to size the initial probe and as the fallback estimate on a failed
        quote. Returned margin is always qty × per_share — the real margin actually
        blocked — never the (larger, un-quoted) target."""
        prov = self.provider
        if prov.name != "kite" or not getattr(prov, "is_authenticated", lambda: False)():
            return None
        lev = self.params.get("intraday_leverage", 2.5) or 2.5
        cache: dict[tuple, float] = {}

        def sizer(cand: IntradayCandidate, target_margin: float) -> tuple[int, float]:
            inst = get_instrument(cand.instrument_key)
            seg = _equity_charge_segment(inst)
            tsym = getattr(inst, "spot_symbol", None) or inst.key
            side = "BUY" if cand.direction == "LONG" else "SELL"
            ckey = (tsym, side)
            per_share = cache.get(ckey)
            if per_share is None:
                probe = max(1, equity_qty(target_margin, lev, cand.price))
                total = prov.order_margin([{
                    "exchange": kite_exchange(seg), "tradingsymbol": tsym,
                    "transaction_type": side, "variety": "regular",
                    "product": kite_product_for_charge_segment(seg), "order_type": "MARKET",
                    "quantity": probe, "price": 0}])
                if not total or total <= 0:
                    q = equity_qty(target_margin, lev, cand.price)   # graceful fallback
                    return q, q * cand.price / lev
                per_share = total / probe
                cache[ckey] = per_share
            # Size to the FULL real margin — no artificial notional cap (owner,
            # 2026-07-21). Zerodha's own MIS multiplier sets the notional; we only
            # deploy `target_margin` of the real margin it blocks.
            qty = qty_for_margin(per_share, target_margin)
            return qty, qty * per_share

        return sizer

    def _futures_margin_sizer(self):
        """Size an index-futures position to REAL SPAN+exposure margin.

        Two branches, and the difference between them is the whole point:

        - **Live (Kite, authenticated):** quote `order_margin` for a 1-lot probe
          and size from the answer. SPAN is portfolio-scanned and
          instrument-specific — it is not price × a leverage constant — so the
          broker is the only source of truth for it.
        - **Paper/mock:** fall back to `index_futures_margin_pct` of notional,
          which is a FLAGGED APPROXIMATION and labelled as one everywhere it
          appears. It exists so paper and backtests can size something plausible;
          it must never be what a live position is booked against.

        Returns whole LOTS, never a share count: a futures position that is not a
        multiple of the lot size is not a position the exchange will accept, and
        rounding it silently at order time would mean the sizing that was risk-
        checked is not the sizing that gets sent.

        Returns `None` when it cannot obtain a real quote in live mode. The
        caller must then refuse the entry — `open_futures_position` rejects a
        missing margin outright, so a fabricated SPAN figure cannot reach the
        ledger through this path.
        """
        prov = self.provider
        pct = float(self.params.get("index_futures_margin_pct",
                                    self.settings.index_futures_margin_pct))
        is_live = (caps.provider_supports(prov, caps.ORDER_MARGIN)
                   and getattr(prov, "is_authenticated", lambda: False)())
        cache: dict[tuple, float] = {}

        def sizer(inst, direction: str, price: float, lot_size: int,
                  target_margin: float) -> tuple[int, float] | None:
            lot_size = max(1, int(lot_size))
            if price <= 0 or target_margin <= 0:
                return None
            if not is_live:
                per_lot = price * lot_size * pct
                if per_lot <= 0:
                    return None
                lots = int(target_margin // per_lot)
                return (lots * lot_size, lots * per_lot) if lots > 0 else None

            tsym = getattr(inst, "option_name", None) or inst.key
            side = "BUY" if direction == "LONG" else "SELL"
            ckey = (tsym, side)
            per_lot = cache.get(ckey)
            if per_lot is None:
                total = prov.order_margin([{
                    "exchange": "NFO", "tradingsymbol": tsym,
                    "transaction_type": side, "variety": "regular",
                    "product": "NRML", "order_type": "MARKET",
                    "quantity": lot_size, "price": 0}])
                if not total or total <= 0:
                    # No real quote, no trade. Unlike equity there is NO leverage
                    # fallback here: guessing SPAN would put a fabricated number
                    # straight into the ledger.
                    return None
                per_lot = float(total)
                cache[ckey] = per_lot
            lots = int(target_margin // per_lot)
            return (lots * lot_size, lots * per_lot) if lots > 0 else None

        return sizer

    def _index_open_prevclose(self, now) -> tuple[float | None, float | None]:
        """Today's index open + prior-session close, from daily candles — cached once
        per calendar day (both are fixed after 09:15). None,None on any read failure
        (mock/off-hours/no history) so the gap guard fails open."""
        if self.provider.name == "mock":
            return None, None      # no real overnight gaps on the always-open sim clock
        today = now.date()
        if self._gap_cache and self._gap_cache[0] == today:
            return self._gap_cache[1], self._gap_cache[2]
        o = pc = None
        try:
            inst = get_instrument(self.params.get("gap_guard_index", "NIFTY"))
            candles = self.provider.get_candles(inst, "day", 3)
            if len(candles) >= 2 and candles[-1].ts.date() == today:
                o, pc = candles[-1].open, candles[-2].close
        except Exception as e:
            log.warn(f"gap guard: index read failed: {e}", event="GAP_GUARD")
        self._gap_cache = (today, o, pc)
        return o, pc

    def _gap_guard_active(self, now) -> bool:
        """Fix D: True if the Nifty opened past the gap threshold and it's before the
        resume time — block ALL new entries through the erratic post-gap window."""
        if not self.params.get("gap_guard_enabled", True):
            return False
        o, pc = self._index_open_prevclose(now)
        return gap_halt_active(now, o, pc,
                               gap_pct=self.params.get("gap_guard_pct", 0.6),
                               resume_hhmm=self.params.get("gap_guard_resume", "11:00"))

    # ── lane 3: entries + reinforcement (fresh crossovers) ────────────────
    def process_entries(self) -> None:
        s, prov = self.settings, self.provider
        now = prov.now()
        held = {p.instrument_key: p for p in self.broker.open_positions()}
        halted = self._entries_halted(now)   # daily-loss circuit breaker (new entries only)
        # fix D: Nifty opening-gap guard — a big overnight gap makes the first hour
        # erratic, so block ALL new entries until the resume time (default 11:00).
        # Computed once/tick (index open+prev-close cached per day); logged once/day.
        gap_active = self._gap_guard_active(now)
        if gap_active and self._gap_logged_day != now.date():
            self._gap_logged_day = now.date()
            log.warn(f"GAP GUARD active — {self.params.get('gap_guard_index', 'NIFTY')} "
                     f"gapped ≥ {self.params.get('gap_guard_pct', 0.6)}% at the open; no "
                     f"new entries until {self.params.get('gap_guard_resume', '11:00')} "
                     f"(open positions still managed)", event="GAP_GUARD")
            if self.params.get("notify_enabled", True):
                self.notifier._emit(f"⏸️ GAP GUARD: index gapped ≥ "
                                    f"{self.params.get('gap_guard_pct', 0.6)}% — pausing new "
                                    f"entries until {self.params.get('gap_guard_resume', '11:00')}.")
        # #14 order circuit breaker: N CONSECUTIVE live order failures means the
        # problem is systemic (expired token, IP not whitelisted, margin exhausted)
        # — every further attempt is another real-money order shot into the same
        # wall. DISARM once and alert; the owner re-arms after fixing the cause
        # (arm(True) resets the streak). Exits/protection keep running regardless.
        cb = self.params.get("order_failure_disarm_count", 3)
        streak = getattr(self.broker, "order_fail_streak", 0)
        if self.armed and cb and cb > 0 and streak >= cb:
            self.arm(False)
            log.error(f"ORDER CIRCUIT BREAKER — {streak} consecutive live order "
                      f"failures; DISARMED. Check Zerodha/token/IP, then re-arm.",
                      event="ORDER_CB_DISARM")
            if self.params.get("notify_enabled", True):
                self.notifier._emit(f"⛔ ORDER CIRCUIT BREAKER: {streak} consecutive "
                                    f"live order failures — bot DISARMED. Fix the "
                                    f"cause (token/IP/margin), then re-arm.")
        cands: list[Candidate] = []
        meta: dict[str, tuple] = {}
        eq_cands: list[IntradayCandidate] = []   # intraday-equity signals this tick
        eq_meta: dict[str, tuple] = {}
        intraday_on = self.params.get("intraday_enabled", False)
        for key in list(self.enabled):
            st = self.state.get(key)
            sig = st["signal"] if st else "NONE"
            # A fresh SAME-DIRECTION crossover on a held position is a reinforcement,
            # never added quantity (no pyramiding). Equity (MIS) is never reinforced.
            if key in held:
                if held[key].segment == "equity_intraday":
                    continue
                if sig in ("LONG_ENTRY", "SHORT_ENTRY"):
                    pos = held[key]
                    sig_dir = "LONG" if sig == "LONG_ENTRY" else "SHORT"
                    if sig_dir == pos.direction:
                        self._record_signal(now, key, st, note="reinforcement")
                        self.broker.reinforce_position(pos, self.params, now)
                continue
            if key in self.entry_blocks:
                continue  # entries manually disabled for this instrument
            if not st or sig not in ("LONG_ENTRY", "SHORT_ENTRY"):
                continue
            direction = "LONG" if sig == "LONG_ENTRY" else "SHORT"
            inst = get_instrument(key)
            self._record_signal(now, key, st)
            if self.params.get("notify_on_signal", False):
                self.notifier.signal(key, sig)
            # fresh-signal guard (#12): evaluate each candle's entry signal ONCE. A
            # signal that fires but can't enter (no capital / concurrency cap full) is
            # DROPPED, not re-attempted every tick and filled stale when a slot frees
            # up. Held positions (reinforcement) are handled above and exempt.
            bar = st.get("time")
            if signal_already_evaluated(bar, self.last_entry_bar.get(key)):
                continue
            if bar is not None:
                self.last_entry_bar[key] = bar
            # ── day-shape guards — BOTH branches (options AND intraday) ──
            # #15: act only on a LIVE crossover. After a (re)start the latest
            # completed candle can be hours old (pre-open it is the PREVIOUS
            # session's last bar) — that crossover is history and the move has
            # already left (LODHA 2026-07-03: fired at 09:00 on a prior-session
            # bar, ~5% past its origin by noon). Age runs from candle COMPLETION.
            iv_min = _INTERVAL_MINUTES.get(self._interval_for(key), 15)
            if signal_too_old(bar, ist_epoch(now), iv_min,
                              self.params.get("max_signal_age_minutes", 5.0)):
                age_min = (ist_epoch(now) - (bar + iv_min * 60)) / 60.0
                log.info(f"STALE SIGNAL — {key} crossover candle completed "
                         f"~{age_min:.0f}m ago; dropped (history, not a live signal)",
                         instrument=key, event="SIGNAL_STALE_SKIP")
                continue
            # #16: never OPEN outside continuous trading. A protected-market order
            # placed pre-open (before 09:15) just rests and can miss the uncross —
            # the LODHA 09:01:25 dangling-limit. Gates entries only; open positions
            # are still managed/exited elsewhere.
            seg = (_equity_charge_segment(inst)
                   if self.products.get(key, "options") == "equity_intraday"
                   else inst.segment)
            if outside_trading_session(seg, now):
                log.info(f"SESSION not open — not taking {key} "
                         f"(pre-open/closed; a resting order can miss the uncross)",
                         instrument=key, event="SESSION_SKIP")
                continue
            # #16b: the owner's start-of-day gate — in-session but before the entry
            # window opens (default 09:30; the first minutes after the 09:15 open
            # are erratic and the 09:00-09:15 window took the 2026-07-03 orders).
            if before_entry_window(now, self.params.get("entry_window_start", "09:30")):
                log.info(f"ENTRY WINDOW closed — not taking {key} before "
                         f"{self.params.get('entry_window_start', '09:30')}",
                         instrument=key, event="ENTRY_WINDOW_SKIP")
                continue
            if gap_active:      # fix D: index gapped at the open — sit out (logged once above)
                continue
            # #9 (extended): sit out the weekly-expiry weekday (default Tuesday) unless
            # the owner opted in for today (intraday_override_date == today). Scoped by
            # expiry_day_block_keys — default NIFTY only, '*' for the whole book.
            if intraday_blocked_for_expiry_day(
                    now.date(), self.params.get("intraday_override_date", ""),
                    self.params.get("intraday_block_weekday", 1), key,
                    self.params.get("expiry_day_block_keys", "NIFTY")):
                log.info(f"ENTRIES blocked today (expiry-day guard) — not taking {key}; "
                         f"set intraday_override_date to opt in",
                         instrument=key, event="EXPIRY_DAY_SKIP")
                continue
            # ── scheduled-event risk (owner, 2026-08-01) ──────────────────────────
            # Known event → no new position. Covers the EIA gas (Thu) / petroleum (Wed)
            # windows, index weekday sit-outs, and any stock on its results date. The
            # bullion-into-expiry rule needs the contract's expiry and so is applied
            # further down, once the chain is known. ENTRIES ONLY — nothing here can
            # ever gate an exit.
            product = self.products.get(key, "options")
            eb = active_blackout(
                key, product, now,
                earnings_date=self._earnings_date_for(key),
                enabled=bool(self.params.get("event_risk_enabled", True)))
            if eb is not None and not self._event_override_today(now):
                log.info(f"EVENT RISK — not taking {key}: {eb.label} ({eb.detail})",
                         instrument=key, event="EVENT_RISK_SKIP")
                continue
            # ── intraday-equity branch (MIS): collect a candidate; the cap-3 /
            # purple / qty-max selection runs after the loop. Guarded by the
            # opt-in flag so the default options behaviour is unchanged. ──
            if self.products.get(key, "options") == "equity_intraday":
                if not intraday_on:
                    continue
                if is_mis_blocked(key):   # #5: never intraday-trade a non-MIS-eligible name
                    log.info(f"INTRADAY skip — {key} not MIS-eligible (blocklist)",
                             instrument=key, event="MIS_BLOCK")
                    continue
                if in_reentry_cooldown(self._stopped_at.get(key), now,
                                       self.params.get("reentry_cooldown_minutes", 0.0)):
                    log.info(f"RE-ENTRY COOLDOWN — skipping {key}", instrument=key,
                             event="COOLDOWN_SKIP")
                    continue
                if not self.armed:
                    log.info(f"DISARMED — intraday signal ready, not taking {key} (arm to trade)",
                             instrument=key, event="DISARMED_SKIP")
                    continue
                if halted:
                    log.warn(f"DAILY LOSS HALT — not taking {key}", instrument=key, event="HALT_SKIP")
                    continue
                # price the entry at the LIVE spot, not the last completed-candle
                # close (st["close"]). Exits mark against the live spot, so opening at
                # a stale candle close on a fast move lands the position already past
                # its SL/TP — an instant exit + re-entry loop. Fall back to the candle
                # close only if there's no live tick.
                live_spot = self.provider.get_ltp(inst)
                entry_price = float(live_spot) if live_spot and live_spot > 0 else float(st["close"])
                eq_cands.append(IntradayCandidate(key, direction, entry_price,
                                                  self.priority_flags.get(key, False)))
                eq_meta[key] = (inst, direction)
                continue
            if not inst.has_options:
                continue  # tracking-only: show the signal, never options-trade it
            # re-entry cooldown after a recent stop-out on this instrument
            if in_reentry_cooldown(self._stopped_at.get(key), now,
                                   self.params.get("reentry_cooldown_minutes", 0.0)):
                log.info(f"RE-ENTRY COOLDOWN — skipping {key}", instrument=key,
                         event="COOLDOWN_SKIP")
                continue
            if not self.armed:
                log.info(f"DISARMED — signal ready, not taking {key} (arm to trade)",
                         instrument=key, event="DISARMED_SKIP")
                continue
            if halted:
                log.warn(f"DAILY LOSS HALT — not taking {key}", instrument=key, event="HALT_SKIP")
                continue
            chain = prov.get_option_chain(inst)
            if not chain:
                log.warn("signal fired but no option chain — skipped", instrument=key)
                continue
            # theta-cliff guard (#1): never OPEN an option within N days of expiry —
            # 0/1/2-DTE premium can evaporate on a small adverse move. Owner rule: >=3 DTE.
            min_dte = self.params.get("entry_min_days_to_expiry", 3)
            if expiry_too_close(chain.expiry, now.date(), min_dte):
                dte = (chain.expiry - now.date()).days
                log.warn(f"signal skipped — option expiry too close ({dte}d < {min_dte}d, "
                         f"theta cliff)", instrument=key, event="DTE_SKIP")
                continue
            # Per-contract event risk — the bullion (GOLDM/SILVERM) "no options within 2
            # days of expiry" rule, which can only be judged once the chain's expiry is
            # known. Same table, same reasons, same log event as the pre-branch gate.
            eb = active_blackout(key, "options", now, expiry=chain.expiry,
                                 enabled=bool(self.params.get("event_risk_enabled", True)))
            if eb is not None and not self._event_override_today(now):
                log.info(f"EVENT RISK — not taking {key}: {eb.label} ({eb.detail})",
                         instrument=key, event="EVENT_RISK_SKIP")
                continue
            pick = pick_option(chain, direction, s, now)
            if self.params.get("option_cache_enabled", True):
                try:
                    from app.options.cache import persist_chain
                    persist_chain(chain, inst, now, self.params["option_cache_snapshot_minutes"])
                except Exception as e:
                    log.error(f"option cache persist failed: {e}")
            self.last_pick[key] = {
                "time": now.isoformat(), "direction": direction, "reason": pick.reason,
                "spot": round(chain.spot, 2), "expiry": chain.expiry.isoformat(),
                "chosen": pick.chosen.to_dict() if pick.chosen else None,
                "candidates": pick.candidates,
            }
            if not pick.chosen:
                log.warn(f"signal fired but {pick.reason}", instrument=key)
                continue
            # Entry purpose is explicit: a SELL can also be a short entry in the equity
            # branch, so order side must never stand in for risk-reduction intent.
            plan = plan_order("ENTRY", "BUY", pick.chosen.bid, pick.chosen.ask,
                              pick.chosen.ltp, pick.chosen.ask_qty,
                              pick.chosen.lot_size, self.params)
            if plan.action == "SKIP":
                log.warn(f"signal fired but routing SKIP — {plan.reason}",
                         instrument=key, event="ROUTE_SKIP")
                if self.params.get("notify_enabled", True):
                    self.notifier.route_skip(key, plan.reason)
                continue
            self.last_pick[key]["route"] = {"action": plan.action,
                                            "limit_price": plan.limit_price,
                                            "reason": plan.reason}
            qty = pick.chosen.lot_size
            charges = compute_charges(inst.segment, "BUY", pick.chosen.ltp, qty)["total"]
            cost = pick.chosen.ltp * qty + charges
            if over_per_trade_cap(cost, self.params.get("max_capital_per_trade", 0.0)):
                log.warn(f"signal skipped — 1-lot cost ₹{cost:,.0f} exceeds per-trade cap "
                         f"₹{self.params['max_capital_per_trade']:,.0f}",
                         instrument=key, event="PER_TRADE_CAP_SKIP")
                continue
            cands.append(Candidate(key, direction, cost))
            meta[key] = (inst, direction, pick, chain, plan)

        if cands:
            # bound auto-entries by DEPLOYABLE capital — your own trades take priority
            alloc = allocate(cands, self.deployable_cash())
            if len(alloc.funded) < len(cands):
                log.info(f"capital shortfall — {len(alloc.funded)}/{len(cands)} "
                         f"signals funded by priority")
            # cap concurrent open positions (counts positions already held this call)
            slots = slots_available(len(held), self.params.get("max_open_positions", 0))
            opened = 0
            for c in alloc.funded:
                if not self.armed:   # #8 defense-in-depth: arm() flips WITHOUT the engine
                    log.warn("DISARMED mid-cycle — aborting remaining entries (gate re-check)",
                             event="ARM_RECHECK_ABORT")
                    break            # lock, so a disarm can land after the entry gate-check
                if slots is not None and opened >= slots:
                    log.info(f"MAX POSITIONS reached ({len(held)} open, cap "
                             f"{self.params['max_open_positions']}) — skipping {c.instrument_key}",
                             instrument=c.instrument_key, event="MAX_POS_SKIP")
                    continue
                inst, direction, pick, chain, plan = meta[c.instrument_key]
                # Before the order, not after: the options path stamps its identity via
                # `_seed_ratchet` once the position exists, so a check placed there would
                # come too late to prevent an unattributable fill. All three entry paths
                # refuse on the same condition, at the last moment they still can.
                executed = self._executed_binding(c.instrument_key)
                if executed is None:
                    log.error(f"no execution binding for {c.instrument_key} at fill — not "
                              f"opening rather than attributing a trade to logic that may "
                              f"not have produced it",
                              instrument=c.instrument_key, event="ATTRIBUTION_MISSING")
                    continue
                log.info(f"ROUTE {plan.action} {pick.chosen.tradingsymbol}"
                         + (f" @ {plan.limit_price:.2f}" if plan.limit_price else "")
                         + f" — {plan.reason}", instrument=c.instrument_key, event="ROUTE")
                pos = self.broker.open_position(
                    inst, direction, pick.chosen, pick.reason, now, chain.spot,
                    self.params, plan=plan,
                    strategy_key=executed.strategy_key,
                    strategy_version=executed.strategy_version)
                if pos is None:
                    continue  # live order not filled — nothing recorded (already alerted)
                # H2 — seed the ratchet for a risk_model strategy so this position is
                # managed by the backtest-validated ratchet, not the legacy premium trail.
                strat_e = execution_binding.strategy_for_execution(executed)
                rm_e = getattr(strat_e, "risk_model", None)
                if rm_e:
                    self._seed_ratchet(pos, chain.spot, rm_e,
                                       self.state.get(c.instrument_key, {}).get("_ratchet_atr"),
                                       executed.strategy_key)
                opened += 1
                if self.params.get("notify_enabled", True):
                    self.notifier.opened(pos)
                if c.instrument_key in self.state:
                    p = self.broker.position_for(c.instrument_key)
                    self.state[c.instrument_key]["position"] = p.to_dict() if p else None
            for c, reason in alloc.skipped:
                log.warn(f"signal dropped — {reason}", instrument=c.instrument_key)

        # ── intraday-equity selection: purple-first, qty-max, hard cap of 3 ──
        if eq_cands and intraday_on:
            open_equity = [p for p in self.broker.open_positions()
                           if p.segment == "equity_intraday"]
            slots = max(0, self.params.get("intraday_max_positions", 3) - len(open_equity))
            if slots <= 0:
                log.info(f"INTRADAY CAP reached ({len(open_equity)} open) — "
                         f"{len(eq_cands)} signals dropped")
            else:
                # same session-close clock the force-flat uses (square_off_intraday)
                # — a fresh entry must not land inside the force-flat window.
                from app.core import market_hours
                mtc_by_key = {key: market_hours.minutes_to_close(inst.spot_exchange, now)
                             for key, (inst, _direction) in eq_meta.items()}
                sel = select_intraday_entries(
                    eq_cands, max_positions=slots,
                    min_margin=self.params.get("intraday_min_margin", 5000.0),
                    max_margin=self.params.get("intraday_max_margin", 8000.0),
                    purple_margin=self.params.get("intraday_purple_margin", 8000.0),
                    leverage=self.params.get("intraday_leverage", 2.5),
                    available_cash=self.deployable_cash(),
                    sizer=self._intraday_margin_sizer(),
                    minutes_to_close=mtc_by_key,
                    entry_cutoff_minutes=self.params.get(
                        "intraday_entry_cutoff_minutes", 25.0))
                for pickk in sel.selected:
                    if not self.armed:   # #8 defense-in-depth: disarm may have landed mid-cycle
                        log.warn("DISARMED mid-cycle — aborting remaining intraday entries",
                                 event="ARM_RECHECK_ABORT")
                        break
                    inst, direction = eq_meta[pickk.instrument_key]
                    seg = _equity_charge_segment(inst)
                    # purple names get the wider band, frozen onto the row at entry
                    sl_pct = (self.params.get("intraday_purple_stop_loss_pct", 0.015)
                              if pickk.is_purple else None)
                    tp_pct = (self.params.get("intraday_purple_target_pct", 0.03)
                              if pickk.is_purple else None)
                    log.info(f"INTRADAY {pickk.direction} {pickk.instrument_key} "
                             f"{pickk.qty}@{pickk.price:.2f} (margin ₹{pickk.margin:,.0f}"
                             f"{', purple' if pickk.is_purple else ''})",
                             instrument=pickk.instrument_key, event="INTRADAY_ENTRY")
                    executed = self._executed_binding(pickk.instrument_key)
                    if executed is None:
                        log.error(f"no execution binding for {pickk.instrument_key} at "
                                  f"fill — not opening rather than attributing a trade to "
                                  f"logic that may not have produced it",
                                  instrument=pickk.instrument_key,
                                  event="ATTRIBUTION_MISSING")
                        continue
                    side = "BUY" if pickk.direction == "LONG" else "SELL"
                    plan = plan_reference_entry(side, pickk.price, self.params)
                    if plan.action == "SKIP":
                        log.warn(f"INTRADAY routing SKIP — {plan.reason}",
                                 instrument=pickk.instrument_key, event="ROUTE_SKIP")
                        continue
                    pos = self.broker.open_equity_position(
                        inst, pickk.direction, pickk.price, pickk.qty, seg,
                        f"INTRADAY {pickk.direction}", now, self.params,
                        strategy_key=executed.strategy_key,
                        strategy_version=executed.strategy_version,
                        margin=pickk.margin, sl_pct=sl_pct, tp_pct=tp_pct, plan=plan)
                    if pos is None:
                        continue
                    if self.params.get("notify_enabled", True):
                        self.notifier.opened(pos)
                    if pickk.instrument_key in self.state:
                        p = self.broker.position_for(pickk.instrument_key)
                        self.state[pickk.instrument_key]["position"] = p.to_dict() if p else None
                for c, reason in sel.skipped:
                    log.info(f"intraday signal dropped — {reason}", instrument=c.instrument_key)
        self._process_futures_entries(now)

    def _process_futures_entries(self, now) -> None:
        """Open index-futures entries. A separate method, called last, so the
        equity and options paths above are untouched by it.

        Returns immediately unless `index_futures_enabled` — which is False by
        default and gated on owner review. Every guard the equity path applies is
        applied here too, plus two that are specific to futures: the delivery
        window, and a margin sizer that REFUSES rather than estimates.
        """
        if not self.params.get("index_futures_enabled",
                               self.settings.index_futures_enabled):
            return
        # Fail closed if the connection cannot price a futures contract.
        #
        # Kite and the mock implement `get_futures_ltp`; replay overrides it precisely in order
        # to refuse (a recording carries no futures feed), and the base default returns None.
        # What the guard defends against is a connection for which `fut` is None at every mark
        # (`_mark_exit_futures`): the position would never mark on a real futures price, would
        # read permanently stale — and a stale futures position skips its exit check entirely,
        # so it would not exit at all. The declaration is necessary and, as the expiry
        # resolution below records, not yet sufficient.
        #
        # Opening a position that cannot be marked is worse than not opening it, so this
        # refuses to open rather than trading blind. Removing the guard requires implementing
        # the capability, which is the point.
        if not self.provider.supports(caps.FUTURES_QUOTES):
            self._alert_infra(
                "futures_no_price_feed",
                f"index_futures_enabled is ON but the {self.provider.name!r} connection does "
                f"not declare {caps.FUTURES_QUOTES!r} — it cannot price a futures contract, so "
                f"a position could not be marked or exited at market. No futures entries taken.")
            return
        from app.core import market_hours
        from app.engine.delivery_calendar import (CashSettledCalendar,
                                                  no_delivery_window)

        open_futs = [p for p in self.broker.open_positions()
                     if p.segment == "index_futures"]
        cap = int(self.params.get("index_futures_max_positions",
                                  self.settings.index_futures_max_positions))
        slots = cap - len(open_futs)
        if slots <= 0:
            return
        if self._entries_halted(now):
            return
        held = {p.instrument_key for p in open_futs}
        sizer = self._futures_margin_sizer()
        target = float(self.params.get("index_futures_max_margin",
                                       self.settings.index_futures_max_margin))
        floor = float(self.params.get("index_futures_min_margin",
                                      self.settings.index_futures_min_margin))
        buf = float(self.params.get("index_futures_square_off_buffer_minutes",
                                    self.settings.index_futures_square_off_buffer_minutes))

        for key, st in list(self.state.items()):
            if slots <= 0:
                break
            if key in held:
                continue
            direction = ("LONG" if st.get("long_entry") else
                         "SHORT" if st.get("short_entry") else None)
            if direction is None:
                continue
            inst = self._resolve_or_skip(key)
            if inst is None or not getattr(inst, "has_options", False):
                continue      # index futures exist only for derivative-eligible names
            if not self.armed:
                log.info(f"DISARMED — futures signal ready, not taking {key}",
                         instrument=key, event="DISARMED_SKIP")
                continue
            # Which CONTRACT would this be? `Instrument` carries no expiry — it is the
            # economic underlying, not a series — so `getattr` here has always returned None
            # and the `or now.date()` it used to carry invented *today* as the expiry.
            #
            # That invention was invisible while no provider declared FUTURES_QUOTES, and
            # false in both directions the moment one did: Kite matches an expiry exactly, so
            # today resolves to no contract on all but one day a month; the mock prices every
            # expiry, and at zero days to run its basis has converged, so it returns exactly
            # spot — the substitution this whole capability exists to forbid, arriving through
            # a working provider.
            #
            # The connection is the only thing that knows its own listed series, so it is asked
            # (`front_month_expiry`) and its refusal is honoured. Inventing a date to get past
            # this line is what produced the defect.
            expiry = self.provider.front_month_expiry(inst)
            if expiry is None:
                log.info(f"FUTURES skip — no resolved contract expiry for {key}",
                         instrument=key, event="FUTURES_NO_CONTRACT")
                continue
            # Delivery guard BEFORE anything else: never OPEN into a window we
            # would immediately have to force-close out of.
            if self.params.get("index_futures_delivery_guard", True):
                try:
                    safe = no_delivery_window(key, now.date(), expiry,
                                              CashSettledCalendar())
                except Exception:
                    safe = False
                if not safe:
                    log.warn(f"FUTURES skip — {key} is inside its delivery window",
                             instrument=key, event="DELIVERY_SKIP")
                    continue
            # Never open inside the force-flat window — the position would be
            # closed minutes later, paying both legs' charges for nothing.
            mtc = market_hours.minutes_to_close(inst.spot_exchange, now)
            if mtc is not None and mtc <= buf:
                continue
            price = self.provider.get_futures_ltp(inst, expiry)
            if not price or price <= 0:
                log.info(f"FUTURES skip — no futures price for {key}",
                         instrument=key, event="FUTURES_NO_PRICE")
                continue
            sized = sizer(inst, direction, float(price),
                          int(getattr(inst, "lot_size", 1) or 1), target)
            if sized is None:
                log.info(f"FUTURES skip — no real margin quote for {key}",
                         instrument=key, event="FUTURES_NO_MARGIN")
                continue
            qty, margin = sized
            if margin < floor or margin > self.deployable_cash():
                continue
            executed = self._executed_binding(key)
            if executed is None:
                log.error(f"no execution binding for {key} at fill — not opening rather "
                          f"than attributing a trade to logic that may not have produced "
                          f"it", instrument=key, event="ATTRIBUTION_MISSING")
                continue
            pos = self.broker.open_futures_position(
                inst, direction, float(price), qty, "NFO_FUT",
                f"FUTURES {direction}", now, expiry, margin=margin,
                params=self.params,
                strategy_key=executed.strategy_key,
                strategy_version=executed.strategy_version)
            if pos is None:
                continue
            slots -= 1
            if self.params.get("notify_enabled", True):
                self.notifier.opened(pos)
            if key in self.state:
                self.state[key]["position"] = pos.to_dict()

    # ── overnight holding (option buying) ─────────────────────────────────
    # ── scheduled-event risk ─────────────────────────────────────────────────
    def _event_override_today(self, now) -> bool:
        """The owner's per-day, self-expiring opt-in (`intraday_override_date`), reused
        for event blackouts: yesterday's opt-in never carries forward."""
        try:
            return dt.date.fromisoformat(
                str(self.params.get("intraday_override_date", "")).strip()) == now.date()
        except (ValueError, TypeError):
            return False

    def _earnings_date_for(self, key: str) -> dt.date | None:
        """Next results date for an equity symbol, from the `earnings_events` cache that
        `scripts/refresh_earnings.py` fills daily. Cached in-process per calendar day —
        this is consulted on every signal and must never become a per-tick query.

        Returns None when the calendar is unknown, which means NO block: an unrefreshed
        cache must not silently freeze the whole equity book. The staleness of the cache
        is surfaced by /api/event-risk instead, so a stale calendar is visible rather
        than either dangerous or paralysing."""
        today = self.provider.now().date()
        if self._earnings_cache_date != today:
            self._earnings_cache_date = today
            self._earnings_cache = {}
            try:
                from app.core.earnings import earnings_map
                # Query with the RAW instrument keys. `earnings_events.symbol` is the
                # full instrument key as the universe stores it — production rows read
                # 'NSE:HEG', not 'HEG' — so querying normalized names matched nothing and
                # the earnings blackout could never have fired on a real symbol. Index
                # the RESULT by the normalized name so lookups work in either form.
                with SessionLocal() as s:
                    for sym, rec in earnings_map(s, list(self.enabled), today).items():
                        self._earnings_cache[normalize_key(sym)] = dt.date.fromisoformat(
                            rec["date"])
            except Exception as e:
                log.warn(f"earnings calendar unavailable: {e}", event="EARNINGS_CACHE_FAIL")
        return self._earnings_cache.get(normalize_key(key))

    def flatten_before_events(self, now) -> list[str]:
        """Square off open positions in an instrument whose release window is about to
        open (EIA gas / crude). Blocking entries alone would leave a position opened an
        hour earlier fully exposed to the print — the exact risk the owner is avoiding.

        This is an EXIT, so it runs regardless of arm state and is never itself gated by
        a blackout (hard invariant #2)."""
        if not self.params.get("event_risk_flatten", True):
            return []
        closed: list[str] = []
        for pos in list(self.broker.open_positions()):
            key = pos.instrument_key
            b = pending_flatten(key, pos.segment or "options", now,
                                lead_minutes=float(self.params.get(
                                    "event_risk_flatten_lead_minutes", 2.0)),
                                enabled=bool(self.params.get("event_risk_enabled", True)))
            if b is None:
                continue
            prem = pos.last_premium or pos.entry_premium
            try:
                self.broker.close_position(pos, prem, "EVENT_RISK_FLATTEN", now, pos.last_spot)
            except Exception as e:
                log.error(f"event-risk flatten failed for {pos.tradingsymbol}: {e}",
                          instrument=key, event="EVENT_RISK_FLATTEN_FAIL")
                continue
            if key in self.state:
                self.state[key]["position"] = None
            closed.append(pos.tradingsymbol)
            log.warn(f"EVENT RISK FLATTEN {pos.tradingsymbol} — {b.label} window opens "
                     f"{b.window[0]:%H:%M}; not carrying a position into the release",
                     instrument=key, event="EVENT_RISK_FLATTEN")
        return closed

    def square_off_for_overnight(self, now) -> list[dict]:
        """At session close: keep eligible positions overnight (tag + snapshot the
        close mark), paper-close the rest. Returns the per-position decisions."""
        from app.engine.overnight import overnight_decision
        equity = self.capital_dict()["equity"]
        out = []
        for pos in list(self.broker.open_positions()):
            # E10: MIS cannot legally carry overnight, so the overnight HOLD decision
            # (an options/expiry notion) must never be applied to it — it was tagging
            # equity_intraday positions `held_overnight` and closing them for reasons
            # like "expiry too close". square_off_intraday is the sole MIS authority.
            if pos.segment == "equity_intraday":
                continue
            if pos.last_squareoff_date == now.date():
                continue  # already decided this session — don't re-snapshot/re-close
            dte = (pos.expiry - now.date()).days if pos.expiry else None
            holding_days = max(0, (now.date() - pos.entry_time.date()).days)
            into_weekend = now.weekday() == 4   # Friday close
            keep, reason = overnight_decision(
                pos.entry_cost, equity, pos.reinforcement_count,
                dte, holding_days, into_weekend, self.params)
            if keep:
                pos.held_overnight = True
                pos.session_close_premium = pos.last_premium or pos.entry_premium
                pos.last_squareoff_date = now.date()   # re-arm: re-evaluated next session
                self.broker.commit()
                log.info(f"OVERNIGHT HOLD {pos.tradingsymbol} — {reason}",
                         instrument=pos.instrument_key, event="OVERNIGHT_HOLD")
            else:
                prem = pos.last_premium or pos.entry_premium
                self.broker.close_position(pos, prem, "OVERNIGHT_SQUAREOFF", now, pos.last_spot)
                if pos.instrument_key in self.state:
                    self.state[pos.instrument_key]["position"] = None
                log.info(f"OVERNIGHT SQUAREOFF {pos.tradingsymbol} — {reason}",
                         instrument=pos.instrument_key, event="OVERNIGHT_SQUAREOFF")
            out.append({"key": pos.instrument_key, "keep": keep, "reason": reason})
        return out

    def book_overnight_gap(self, now) -> None:
        """At session open: attribute the close→open premium gap to overnight P&L.

        Gated on a LATER calendar day than the close that took the snapshot, so it
        fires once per session boundary and never zeroes the snapshot in the same
        pass it was taken (which would erase the gap before it could be booked)."""
        for pos in list(self.broker.open_positions()):
            if (pos.held_overnight and pos.session_close_premium > 0
                    and pos.last_squareoff_date is not None
                    and now.date() > pos.last_squareoff_date):
                prem = pos.last_premium or pos.entry_premium
                pos.overnight_pnl += (prem - pos.session_close_premium) * pos.qty
                pos.session_close_premium = 0.0
                self.broker.commit()

    def handle_overnight(self, now) -> None:
        """Live-mode orchestration: square off near each segment's close, book the
        gap just after open. No-op for the always-open mock clock."""
        if self.provider.name == "mock":
            return
        try:
            from app.core import market_hours
            buf = self.params["square_off_buffer_minutes"]
            for pos in list(self.broker.open_positions()):
                inst = self._resolve_or_skip(pos.instrument_key)
                if inst is None:
                    continue
                seg = inst.spot_exchange
                mtc = market_hours.minutes_to_close(seg, now)
                if mtc is not None and 0 <= mtc <= buf and pos.last_squareoff_date != now.date():
                    self.square_off_for_overnight(now)
                    break
            self.square_off_intraday(now)   # MIS equity must be flat by close
            self.book_overnight_gap(now)
        except Exception as e:
            log.error(f"overnight handler error: {e}")

    def square_off_intraday(self, now) -> None:
        """Force every MIS-equity AND index-futures position flat near its segment's
        close. Marks to the last price and books the close.

        Futures are included because the owner's directive is explicit: intraday
        only, **no rollovers, ever**. There is deliberately no "it is expiry day,
        let it settle" carve-out — settling is a decision the engine is not
        allowed to make, and the absence of rollover code anywhere in `engine/`
        is an invariant to preserve rather than a gap to fill. Futures get their
        own buffer knob because close-auction dynamics differ from cash equity.
        """
        from app.core import market_hours
        eq_buf = self.params.get("intraday_square_off_buffer_minutes", 15.0)
        fut_buf = self.params.get("index_futures_square_off_buffer_minutes",
                                  self.settings.index_futures_square_off_buffer_minutes)
        for pos in list(self.broker.open_positions()):
            if pos.segment not in ("equity_intraday", "index_futures"):
                continue
            is_fut = pos.segment == "index_futures"
            buf = fut_buf if is_fut else eq_buf
            # MIS cannot legally carry overnight, so an unresolvable key must NOT exempt
            # a position from the flatten — equity-intraday is always NSE cash, so fall
            # back to that clock rather than skipping (and leaving it to carry).
            inst = self._resolve_or_skip(pos.instrument_key)
            seg = inst.spot_exchange if inst is not None else "NSE"
            mtc = market_hours.minutes_to_close(seg, now)
            if mtc is not None and 0 <= mtc <= buf:
                price = pos.last_premium or pos.entry_premium
                if is_fut:
                    self.broker.close_futures_position(
                        pos, price, "INTRADAY_SQUAREOFF", now)
                else:
                    self.broker.close_equity_position(
                        pos, price, "INTRADAY_SQUAREOFF", now)
                if pos.instrument_key in self.state:
                    self.state[pos.instrument_key]["position"] = None
                log.info(f"INTRADAY SQUAREOFF {pos.tradingsymbol} @ {price:.2f}",
                         instrument=pos.instrument_key, event="INTRADAY_SQUAREOFF")

    # ── combined step — mock dry-run + tests (semantics unchanged) ────────
    def tick(self) -> None:
        self.scan_signals()
        self.mark_and_exit_positions()
        self.process_entries()
        self.broker.snapshot(self.provider.now())
        self.tick_count += 1

    # ── capital available to the bot (owner's trades take priority) ────────
    def deployable_cash(self) -> float:
        cap_state = self.broker.capital()
        bot_deployed = sum(p.entry_cost for p in self.broker.open_positions())
        is_live = caps.provider_supports(self.provider, caps.ACCOUNT_FUNDS)
        funds = self.provider.account_funds() if is_live else None
        return deployable_capital(
            ledger_base=cap_state.cash + bot_deployed,
            bot_deployed=bot_deployed,
            account_available=(funds["available"] if funds else None),
            reserve=self.params.get("capital_reserve", 0.0),
            cap=self.params.get("bot_capital_cap", 0.0),
            is_live=is_live)

    # ── daily-loss circuit breaker ────────────────────────────────────────
    def _today_net_realized(self, today) -> float:
        """This book's net realised P&L today — drives the daily-loss circuit breaker.

        Book-scoped (L1.3B): a paper loss must not halt the live book, and a paper win
        must not mask a live loss. A risk control counting the wrong book's money is not
        a conservative approximation — it is wrong in both directions."""
        from app.engine.analytics import realized_on
        with SessionLocal() as s:
            return realized_on(s, today, self.book)

    def _today_round_trips(self, today) -> int:
        """This book's completed round trips today — the hard daily round-trip cap (#10)."""
        from app.engine.analytics import round_trips_on
        with SessionLocal() as s:
            return round_trips_on(s, today, self.book)

    def _open_unrealized(self) -> float:
        """Mark-to-market P&L across all currently open positions (can be negative).
        Direction-aware for intraday-equity SHORTs (which profit as price falls)."""
        total = 0.0
        for p in self.broker.open_positions():
            last = p.last_premium or p.entry_premium
            if p.segment == "equity_intraday" and p.direction == "SHORT":
                total += (p.entry_premium - last) * p.qty
            else:
                total += (last - p.entry_premium) * p.qty
        return total

    def _safe_flatten_before_events(self, now) -> None:
        """Defensive wrapper — a failure inside the event flatten must never stop the
        risk loop from marking and exiting the rest of the book."""
        try:
            self.flatten_before_events(now)
        except Exception as e:
            log.error(f"event-risk flatten check failed: {e}", event="EVENT_RISK_ERROR")

    def _safe_maybe_profit_lock(self, now) -> None:
        """Defensive wrapper — an exception inside the give-back guard must never
        break the risk loop (matches the defensive style used elsewhere here)."""
        try:
            self._maybe_profit_lock(now)
        except Exception as e:
            log.error(f"daily profit-lock check failed: {e}", event="PROFIT_LOCK_ERROR")

    def _maybe_profit_lock(self, now) -> None:
        """E1 — daily profit-lock (give-back guard). Tracks the day's realized+
        unrealized P&L high-water; once it clears `daily_profit_lock_pct` of the
        day's deployed capital, ARMS a give-back floor at `daily_profit_giveback_frac`
        of the peak. If the day retraces down to that floor -> SQUARE OFF every open
        position and HALT new entries for the rest of the session (`_entries_halted`
        consults `_pl_halted_date`). Symmetric twin of `daily_loss_halt`, but this one
        protects a good day from round-tripping to flat/red. `daily_profit_lock_pct
        <= 0` disables the feature entirely (default; zero behavior change)."""
        lock_pct = self.params.get("daily_profit_lock_pct", 0.0)
        if not lock_pct or lock_pct <= 0:
            return  # feature off — do NOT reset _pl_halted_date; leave state untouched
        today = now.date()
        if self._pl_date != today:
            # new session — the give-back state is intraday only.
            self._pl_high_water = 0.0
            self._pl_deployed_peak = 0.0
            self._pl_date = today
        day_pnl = float(self._today_net_realized(today)) + float(self._open_unrealized())
        deployed_now = float(sum(p.entry_cost for p in self.broker.open_positions()))
        # trail up only — peak concurrent deployed capital today (not cumulative,
        # so re-entries cycling the same capital don't inflate the denominator).
        self._pl_high_water = float(max(self._pl_high_water, day_pnl))
        self._pl_deployed_peak = float(max(self._pl_deployed_peak, deployed_now))
        if self._pl_halted_date == today:
            return  # already fired today — entries stay blocked via _entries_halted
        giveback_frac = self.params.get("daily_profit_giveback_frac", 0.5)
        breached, floor = daily_profit_lock(day_pnl, self._pl_high_water,
                                            self._pl_deployed_peak, lock_pct, giveback_frac)
        if not breached:
            return
        self._pl_halted_date = today
        closed = self._square_off_all("PROFIT_LOCK", now)
        log.warn(f"DAILY PROFIT-LOCK — day P&L ₹{day_pnl:,.0f} gave back to floor "
                 f"₹{floor:,.0f} (peak ₹{self._pl_high_water:,.0f}, deployed "
                 f"₹{self._pl_deployed_peak:,.0f}); squared off {len(closed)}, no new "
                 f"entries today", event="PROFIT_LOCK")
        if self.params.get("notify_enabled", True):
            self.notifier._emit(f"🔒 DAILY PROFIT-LOCK: day P&L ₹{day_pnl:,.0f} gave back "
                                f"to the floor ₹{floor:,.0f} (peak ₹{self._pl_high_water:,.0f}) "
                                f"— squared off {len(closed)} position(s), no new entries "
                                f"for the rest of the session.")

    def _square_off_all(self, reason: str, now) -> list[str]:
        """Flatten every open position at its last mark, routing each segment
        through its correct close. The ONE square-off implementation — used by
        `kill()` and the daily profit-lock give-back guard. Does NOT disarm or
        cancel working entry orders (callers that need that do it themselves)."""
        closed: list[str] = []
        for pos in list(self.broker.open_positions()):
            prem = pos.last_premium or pos.entry_premium
            # route each segment through its correct close (equity covers a short
            # via BUY; the options close always SELLs) — same fix as reconcile.
            if pos.segment == "equity_intraday":
                tr = self.broker.close_equity_position(pos, prem, reason, now)
            else:
                tr = self.broker.close_position(pos, prem, reason, now, pos.last_spot)
            if tr is None:
                log.error(f"{reason} could not square off {pos.tradingsymbol} — left open",
                          instrument=pos.instrument_key, event=f"{reason}_FAIL")
                continue
            self.notifier.clear(pos.instrument_key)
            if pos.instrument_key in self.state:
                self.state[pos.instrument_key]["position"] = None
            closed.append(pos.instrument_key)
        return closed

    def _entries_halted(self, now) -> bool:
        """Halt NEW entries for the day once a circuit breaker trips (open positions
        are still managed throughout). Three breakers, any trips:
          • max_daily_loss          — today's REALIZED net loss.
          • max_open_drawdown       — today's REALIZED + UNREALIZED (open MTM) loss.
          • max_round_trips_per_day — count of completed round trips today (#10).
        Alerts at most once per day; the open-drawdown breaker un-trips on recovery."""
        max_loss = self.params.get("max_daily_loss", 0.0)
        max_dd = self.params.get("max_open_drawdown", 0.0)
        max_rt = self.params.get("max_round_trips_per_day", 0)
        today = now.date()
        if ((not max_loss or max_loss <= 0) and (not max_dd or max_dd <= 0)
                and (not max_rt or max_rt <= 0)):
            return self._pl_halted_date == today
        realized = self._today_net_realized(today)
        unreal = self._open_unrealized() if (max_dd and max_dd > 0) else 0.0
        halted, why = daily_loss_halt(realized, unreal, max_loss, max_dd)
        rts = self._today_round_trips(today) if (max_rt and max_rt > 0) else 0
        if not halted and round_trip_cap_reached(rts, max_rt):
            halted, why = True, "round_trips"
        if halted and self._halt_notified_date != today:
            self._halt_notified_date = today
            if why == "round_trips":
                log.warn(f"ROUND-TRIP CAP — {rts} completed round trips today >= cap "
                         f"{max_rt}; no new entries today")
            elif why == "open_drawdown":
                combined = realized + unreal
                log.warn(f"DAILY DRAWDOWN HALT — today realized ₹{realized:,.0f} + open "
                         f"₹{unreal:,.0f} = ₹{combined:,.0f} <= -₹{max_dd:,.0f}; no new entries today")
                if self.params.get("notify_enabled", True):
                    self.notifier.daily_halt(combined, max_dd)
            else:
                log.warn(f"DAILY LOSS HALT — today realized net ₹{realized:,.0f} <= "
                         f"-₹{max_loss:,.0f}; no new entries today")
                if self.params.get("notify_enabled", True):
                    self.notifier.daily_halt(realized, max_loss)
        # E1 profit-lock give-back — independent of the loss/drawdown breakers above
        # (never fires the daily-loss alert, and vice-versa); own state, own reason.
        if self._pl_halted_date == today:
            return True
        return halted

    def halt_status(self, now) -> dict:
        """Pure, side-effect-free read of the daily-loss / open-drawdown circuit
        breaker for the snapshot/UI. Mirrors _entries_halted's computation but does
        NOT log, notify, or mutate _halt_notified_date — safe to call on every WS
        push. _entries_halted stays the one place that fires the once-per-day alert.

        Returns: {halted, reason ('', 'realized', 'open_drawdown', 'round_trips',
        'profit_lock'), realized, open_unrealized, max_daily_loss, max_open_drawdown,
        round_trips, max_round_trips, profit_lock_halted}."""
        today = now.date()
        pl_halted = self._pl_halted_date == today
        max_loss = self.params.get("max_daily_loss", 0.0) or 0.0
        max_dd = self.params.get("max_open_drawdown", 0.0) or 0.0
        max_rt = self.params.get("max_round_trips_per_day", 0) or 0
        if max_loss <= 0 and max_dd <= 0 and max_rt <= 0:
            return {"halted": pl_halted, "reason": "profit_lock" if pl_halted else "",
                    "realized": 0.0, "open_unrealized": 0.0, "max_daily_loss": max_loss,
                    "max_open_drawdown": max_dd, "round_trips": 0,
                    "max_round_trips": max_rt, "profit_lock_halted": pl_halted}
        realized = self._today_net_realized(today)
        unreal = self._open_unrealized() if max_dd > 0 else 0.0
        halted, reason = daily_loss_halt(realized, unreal, max_loss, max_dd)
        rts = self._today_round_trips(today) if max_rt > 0 else 0
        if not halted and round_trip_cap_reached(rts, max_rt):
            halted, reason = True, "round_trips"
        if not halted and pl_halted:
            halted, reason = True, "profit_lock"
        return {
            "halted": halted, "reason": reason,
            "realized": round(realized, 2), "open_unrealized": round(unreal, 2),
            "max_daily_loss": max_loss, "max_open_drawdown": max_dd,
            "round_trips": rts, "max_round_trips": max_rt,
            "profit_lock_halted": pl_halted,
        }

    def _record_signal(self, now, key, st, note: str = "") -> None:
        with SessionLocal() as s:
            s.add(SignalEvent(deployment_id=self.deployment_id,
                              time=now, instrument_key=key, signal=st["signal"],
                              z=st["z"], slope=st["slope"], close=st["close"],
                              acted=True, note=note))
            s.commit()

    # ── next-candle gating ────────────────────────────────────────────────
    def _due_for_scan(self, key: str, now) -> bool:
        """Refetch candles only when a new completed candle could exist — gates
        Kite historical calls so the signal lane stays cheap."""
        import datetime as _dt
        epoch = now.timestamp() if isinstance(now, _dt.datetime) else float(now)
        nxt = self._next_scan.get(key)
        if nxt is None or epoch >= nxt:
            minutes = _INTERVAL_MINUTES.get(self._interval_for(key), 15)
            self._next_scan[key] = epoch + minutes * 60
            return True
        return False

    # ── per-lane single iterations (lock-serialised DB mutation) ──────────
    # ── liveness + infra alerting (M1/P3) ─────────────────────────────────
    def _alert_infra(self, key: str, msg: str, now: float | None = None) -> bool:
        """M1: surface an infrastructure/provider failure (loop death, token expiry,
        data staleness) as a Telegram alert + log — the loops previously swallowed
        these silently, so a dead engine looked healthy. Throttled per key so a
        recurring failure alerts once, not every tick. Returns True if it fired."""
        now = self.provider.now().timestamp() if now is None else now
        window = float(self.params.get("infra_alert_throttle_seconds", 300))
        if now < self._infra_alert_epoch.get(key, 0.0):
            return False
        self._infra_alert_epoch[key] = now + window
        log.error(f"INFRA ALERT [{key}]: {msg}", event="INFRA_ALERT")
        try:
            self.notifier._emit(f"🚨 {msg}")
        except Exception:
            pass
        return True

    def _beat_now(self, lane: str, now: float | None = None) -> None:
        """P3: record a heartbeat for a loop lane at the end of each iteration.

        Two clocks on purpose — see `_beat_wall` in __init__. `now` overrides only
        the market-time beat (that is what tests drive the watchdog with); the
        wall-clock beat is always real, because its whole job is to be.
        """
        self._beat[lane] = self.provider.now().timestamp() if now is None else now
        self._beat_wall[lane] = time.monotonic()

    def lane_ages(self) -> dict[str, float | None]:
        """Seconds since each lane last beat, on the wall clock, for the readiness
        probe. `None` = this lane has never beaten (never started, or died before
        its first iteration) — which is NOT the same as "beat a long time ago" and
        must not collapse to a large number."""
        now = time.monotonic()
        return {lane: (None if lane not in self._beat_wall
                       else now - self._beat_wall[lane])
                for lane in (readiness.LANE_RISK, readiness.LANE_SIGNAL)}

    def uptime_seconds(self) -> float:
        """Wall-clock seconds since this runner was constructed (≈ process boot)."""
        return time.monotonic() - self._boot_wall

    def markets_open(self) -> bool | None:
        """True if ANY enabled instrument is tradable right now; None if we could
        not tell. The probe needs this to know whether a silent signal lane is a
        stall or just a closed market — and a failed read must stay `None` rather
        than guess, or it invents a nightly false alarm."""
        try:
            return any(self.provider.is_tradable_now(get_instrument(k))
                       for k in self.enabled)
        except Exception:
            return None

    def _lane_stale(self, lane: str, max_age: float, now: float | None = None) -> bool:
        """P3: True if a lane hasn't beaten within max_age seconds (dead/stuck loop)."""
        last = self._beat.get(lane)
        if last is None:
            return False   # never started beating yet — not 'stale'
        now = self.provider.now().timestamp() if now is None else now
        return (now - last) > max_age

    def _maybe_watchdog(self) -> None:
        """P3: from the (free, post-offload) signal lane, alert if the risk lane has
        stopped beating — the fast lane marks positions + fires SL/TP, so a stall there
        is the dangerous one. Only meaningful once the risk lane has beaten at least once."""
        max_age = float(self.params.get("watchdog_stale_seconds", 30))
        if self._lane_stale("risk", max_age):
            self._alert_infra("risk_loop_stalled",
                              f"risk loop has not run for >{max_age:.0f}s — open positions "
                              f"may be UNMANAGED (no marking / SL / TP). Check the backend.")

    def startup_account_reconcile(self) -> list[str]:
        """H14: surface any REAL account position the bot's book does NOT track — a
        position it may have opened before a crash that never persisted, or a fill it
        lost. It does NOT adopt them: the account also holds the owner's discretionary
        trades and positions() carries no bot tag, so the bot can't prove ownership.
        Flags them for the operator to reconcile. Returns the untracked tradingsymbols.
        No-op on mock/paper (account_positions is []) or on a failed read (None)."""
        acct = self.provider.account_positions()
        if not acct:
            return []
        booked = {p.tradingsymbol for p in self.broker.open_positions()}
        untracked = [p["tradingsymbol"] for p in acct
                     if int(p.get("quantity", 0) or 0) != 0 and p.get("tradingsymbol") not in booked]
        if not untracked:
            return []

        # Classify rather than dump. `positions()` carries no bot tag, so ownership can't
        # be proven — but the ORDER JOURNAL can distinguish the two cases that matter, and
        # they have opposite urgency:
        #   • the symbol appears in the bot's own journal → a fill the bot LOST. That is a
        #     phantom-book risk (invariant #2) and deserves a real alert every time.
        #   • it does not → almost certainly the owner's discretionary trade. Informational.
        # Before this, both raised the same ERROR + Telegram on every single restart, so
        # NETWEB and DIXON — the owner's own positions — cried wolf indefinitely and would
        # have buried a genuine lost fill arriving in the same channel.
        bot_symbols = self._journaled_symbols_today()
        lost = [s for s in untracked if s in bot_symbols]
        yours = [s for s in untracked if s not in bot_symbols]

        if yours:
            log.info(f"STARTUP: {len(yours)} account position(s) not in the bot book and not "
                     f"in its order journal: {yours} — treated as YOUR discretionary "
                     f"positions; the bot will not touch them.", event="STARTUP_UNTRACKED_YOURS")
        if lost:
            log.error(f"STARTUP: {len(lost)} account position(s) NOT in the bot book but "
                      f"PRESENT in the bot's order journal: {lost} — a fill the bot lost. "
                      f"The book and the account disagree; reconcile before arming.",
                      event="STARTUP_UNTRACKED")
            self._alert_infra("startup_untracked",
                              f"{len(lost)} position(s) the bot ORDERED but is not tracking: "
                              f"{lost} — the book and your account disagree. Reconcile before "
                              f"arming; the bot won't touch them.")
        return untracked

    def _journaled_symbols_today(self) -> set[str]:
        """Symbols the bot itself placed orders for today, from the order journal.

        Fails CLOSED — on any error every untracked position is treated as a possible lost
        bot fill and alerted, because under-alerting here risks a phantom book."""
        try:
            from app.db.models import OrderJournal
            today = self.provider.now().date()
            with SessionLocal() as s:
                rows = s.query(OrderJournal.tradingsymbol, OrderJournal.placed_at).all()
            return {sym for sym, placed in rows
                    if placed is not None and placed.date() == today}
        except Exception as e:
            log.warn(f"order-journal read failed during startup reconcile: {e}",
                     event="STARTUP_UNTRACKED")
            return {p["tradingsymbol"] for p in (self.provider.account_positions() or [])}

    def _rollback_session(self) -> None:
        """H3: discard any half-applied dirty state after a mid-iteration exception, so
        the next lane never inherits a partially-mutated session (there was no rollback
        anywhere in the codebase)."""
        try:
            self.broker.s.rollback()
        except Exception as e:
            log.error(f"session rollback failed: {e}", event="ROLLBACK_FAIL")

    async def _risk_iteration(self) -> None:
        # L5 — mark_and_exit_positions can block for the live order-poll window
        # (place + poll to a terminal state). Run it OFF the event loop so a slow
        # poll never freezes WS heartbeats, the signal scheduler, or the cockpit.
        # The lock is still held across the offload, so the single shared DB session
        # is only ever touched by one lane at a time (risk vs signal stay serialised).
        async with self._lock:
            try:
                await to_thread_drained(self.mark_and_exit_positions)
            except Exception:
                self._rollback_session()   # H3 — clean the session before releasing the lock
                raise
        self._beat_now("risk")             # P3 heartbeat
        if self.on_position_ticks:
            try:
                await self.on_position_ticks(self.position_ticks)
            except Exception:
                pass

    def _maybe_refresh_funds(self) -> None:
        """Throttled (~20s) poll of the REAL Kite account funds in live mode, cached
        for the snapshot so the cockpit shows the actual account balance instead of
        the paper ledger. margins() is rate-limited, so never call it per-tick. No-op
        (and clears the cache) on the mock/paper provider."""
        if self.provider.name != "kite":
            self._account_funds = None
            return
        epoch = self.provider.now().timestamp()
        if epoch < self._next_funds_epoch:
            return
        self._next_funds_epoch = epoch + 20.0
        try:
            funds = self.provider.account_funds()
            if funds:
                self._account_funds = funds
                self._persist_daily_snapshot(funds)
                self._maybe_auto_reanchor(funds)
        except Exception as e:
            log.warn(f"account funds refresh failed: {e}")

    def _maybe_auto_reanchor(self, funds: dict) -> None:
        """Keep the reported equity equal to the REAL account equity.

        The internal ledger starts at the synthetic ₹50k `initial_capital` (config.py) and
        the equity curve is built from it (`cash + mtm`). The original E0.2 auto-reanchor
        only fired on a ledger that had NEVER traded — so on the production book (trading
        since 2026-07-13) it was unreachable, and the cockpit reported ₹49,833 (= 50,000 −
        realized) for three weeks against a far smaller real account. Every %-return,
        drawdown and curve figure inherited that lie.

        Now: re-anchor at most ONCE PER DAY, before the day's first entry, only when the
        book is flat and the ledger has actually drifted past `ledger_reanchor_tolerance`.
        That is the one window where moving the anchor cannot change the meaning of an
        in-flight session — today's realized P&L, the daily-loss halt and the profit-lock
        all read from `trades`/session state, never from `capital_state`, so a pre-session
        re-anchor leaves those semantics untouched.

        Every guard fails closed and the refusal reason is recorded on
        `self._reanchor_reason` so the cockpit can show WHY the ledger is adrift instead of
        quietly reporting a fiction."""
        net = float(funds.get("net", 0.0) or 0.0) if funds else 0.0
        try:
            now = self.provider.now()
            today = now.date()
            open_entry_cost = sum(p.entry_cost for p in self.broker.open_positions())
            cap = self.broker.capital()
            if cap is None:
                return
            internal_equity = cap.cash + sum(p.mtm_value() for p in self.broker.open_positions())
            anchored = getattr(cap, "anchored_at", None)
            ok, why = should_reanchor(
                # Fail-closed book resolution: `getattr(broker, "MODE", "paper")` treated
                # a broker that could not name its book as harmless, which is backwards.
                is_live=(self.book == execution_book.LIVE),
                real_equity=net or None,
                internal_equity=internal_equity,
                open_entry_cost=open_entry_cost,
                trades_today=self._today_trade_count(today),
                last_anchor_date=anchored.date() if anchored else None,
                today=today,
                tolerance=float(self.params.get("ledger_reanchor_tolerance",
                                                self.settings.ledger_reanchor_tolerance)),
                enabled=bool(self.params.get("ledger_auto_reanchor",
                                             self.settings.ledger_auto_reanchor)),
            )
            self._reanchor_reason = why
            if not ok:
                return
            new_state, notes = plan_reanchor(
                real_equity=net, cash=cap.cash, initial_capital=cap.initial_capital,
                realized_pnl=cap.realized_pnl, account_baseline=cap.account_baseline,
                open_entry_cost=0.0)
            # Write THROUGH the broker's own long-lived session so its cached `cap`
            # instance (identity-mapped, expire_on_commit=False) is updated in memory
            # immediately. Committing via a separate session would update the DB row
            # but leave broker.capital() stale — the next snapshot()/close_position()
            # would read+re-commit the stale synthetic values, clobbering the reanchor.
            cap.initial_capital = new_state["initial_capital"]
            cap.cash = new_state["cash"]
            cap.realized_pnl = new_state["realized_pnl"]
            cap.account_baseline = new_state["account_baseline"]
            cap.anchored_at = now
            self.broker.s.commit()
            self._reanchored = True
            log.info(f"RE-ANCHORED live ledger to real equity ₹{net:,.2f} "
                     f"(book flat, no trades today; {why}): " + "; ".join(notes),
                     event="LEDGER_AUTO_REANCHOR")
        except Exception as e:
            self._reanchor_reason = f"re-anchor failed: {e}"
            log.warn(f"auto-reanchor failed: {e}", event="LEDGER_AUTO_REANCHOR_FAIL")

    def _today_trade_count(self, today) -> int:
        """Trades CLOSED today — the gate that stops the anchor moving mid-session."""
        try:
            with SessionLocal() as s:
                return int(s.query(func.count(Trade.id)).filter(
                    Trade.mode == self.book,
                    Trade.exit_time >= dt.datetime.combine(today, dt.time.min),
                    Trade.exit_time < dt.datetime.combine(today, dt.time.max)).scalar() or 0)
        except Exception:
            return 1   # fail closed: unknown trade count must never allow a re-anchor

    def _maybe_prune_telemetry(self) -> None:
        """Once a day, with the book FLAT, age out the telemetry tables.

        Runs from the signal lane rather than a cron because the VPS has no scheduler the
        deploy owns, and an un-run prune is invisible until the disk fills. Gated on a
        flat book so a large DELETE can never contend with position management on a
        1 GB box — the same box two memory leaks have already OOM'd."""
        if not self.params.get("retention_enabled", True):
            return
        today = self.provider.now().date()
        if self._pruned_date == today:
            return
        if self.broker.open_positions():
            return                       # never prune while managing money
        self._pruned_date = today
        try:
            from app.engine.retention import RetentionPolicy, prune
            report = prune(self.provider.now(), RetentionPolicy(
                enabled=True,
                option_data_days=int(self.params.get("retention_option_data_days", 90)),
                signal_events_days=int(self.params.get("retention_signal_events_days", 90)),
                equity_full_days=int(self.params.get("retention_equity_full_days", 7)),
                equity_downsample_minutes=int(self.params.get(
                    "retention_equity_downsample_minutes", 15)),
            ))
            if any(report.values()):
                log.info("RETENTION pruned " + ", ".join(
                    f"{k} −{v:,}" for k, v in report.items() if v),
                    event="RETENTION")
        except Exception as e:
            log.error(f"retention prune failed: {e}", event="RETENTION_FAIL")

    def _maybe_check_ledger(self) -> None:
        """H10: run the cash-invariant self-check in production (it was only ever run by
        the offline dry-run). A nonzero diff means the ledger drifted from
        cash == initial + realized − Σ(open entry_cost) — a bad write or partial commit.
        Throttled; alerts once per drift episode (log + Telegram) and clears when it
        returns to balance. Detection only — it never mutates the ledger."""
        epoch = self.provider.now().timestamp()
        if epoch < self._next_ledger_epoch:
            return
        self._next_ledger_epoch = epoch + float(self.params.get("ledger_check_seconds", 60))
        rec = self.broker.reconcile()
        if abs(rec["diff"]) > 0.01:
            if not self._ledger_drift_alerted:
                log.error(f"LEDGER DRIFT ₹{rec['diff']} — cash {rec['cash']} vs expected "
                          f"{rec['expected_cash']} (realized {rec['realized_pnl']}, "
                          f"{rec['open']} open); invariant broken, investigate",
                          event="LEDGER_DRIFT")
                try:
                    self.notifier._emit(f"🚨 LEDGER DRIFT ₹{rec['diff']}: cash "
                                        f"{rec['cash']} vs expected {rec['expected_cash']} "
                                        f"— the bot's cash invariant is broken; verify.")
                except Exception:
                    pass
                self._ledger_drift_alerted = True
        else:
            self._ledger_drift_alerted = False

    def _persist_daily_snapshot(self, funds: dict) -> None:
        """Upsert today's (IST) account equity row for the Calendar view. Called from
        the throttled funds refresh, so it captures the latest balance of the day."""
        from app.db.models import DailyAccountSnapshot
        day = self.provider.now().date().isoformat()
        try:
            with SessionLocal() as s:
                row = s.get(DailyAccountSnapshot, (self.broker.broker_account_id, day))
                if row is None:
                    row = DailyAccountSnapshot(broker_account_id=self.broker.broker_account_id, day=day)
                    s.add(row)
                row.account_net = float(funds.get("net", 0.0) or 0.0)
                row.account_available = float(funds.get("available", 0.0) or 0.0)
                s.commit()
        except Exception as e:
            log.warn(f"daily snapshot persist failed: {e}")

    def _maybe_reconcile_orphans(self) -> None:
        """Throttled (~30s): book any bot position the live account no longer backs
        (e.g. its GTT fired while the bot was down). No-op on the paper broker."""
        now = self.provider.now()
        epoch = now.timestamp()
        if epoch >= self._next_reconcile_epoch:
            self._next_reconcile_epoch = epoch + 30.0
            try:
                # #17: first adopt any bot entry that filled after its poll window (a late
                # uncross / slow open), so it's booked + stopped rather than left orphaned.
                self.broker.adopt_pending_entries(now)
                reconciled = self.broker.reconcile_orphans(now) or []
            except Exception as e:
                log.error(f"orphan reconcile error: {e}")
                return
            # #2: a position that vanished from the account (manual Zerodha exit or a GTT
            # fire) is an exit the bot didn't initiate — block same-day re-entry so the
            # live signal can't immediately re-open it (the PAYTM/IREDA thrash).
            for k in reconciled:
                if k not in self.entry_blocks:
                    self.set_entries_blocked(k, True)
                    log.info("auto-blocked re-entry after external/reconciled exit",
                             instrument=k, event="AUTO_BLOCK")

    # ── option-chain research cache (whole watchlist, not just traded names) ─
    def cache_option_chains(self, now) -> int:
        """Snapshot the option chain of EVERY enabled, in-session, option-bearing
        instrument into the OptionData research dataset — not only the ones a
        signal happened to fire on. Kite sells no historical option chains / IV /
        OI / greeks, so anything not snapshotted live today is unrecoverable. Each
        write is deduped to `option_cache_snapshot_minutes` per instrument by
        `persist_chain`, so calling this often is cheap."""
        if not self.params.get("option_cache_enabled", True):
            return 0
        from app.options.cache import persist_chain
        snap_min = self.params.get("option_cache_snapshot_minutes", 15.0)
        written = 0
        for key in list(self.enabled):
            inst = get_instrument(key)
            if not inst.has_options or not self.provider.is_tradable_now(inst):
                continue
            try:
                chain = self.provider.get_option_chain(inst)
                if chain:
                    written += persist_chain(chain, inst, now, snap_min)
            except Exception as e:
                if self.health.should_log_failure("quote"):
                    log.error(f"option cache sweep failed: {e}", instrument=key)
        if written:
            log.info(f"option research cache +{written} rows across the watchlist",
                     event="OPTION_CACHE")
        return written

    def _maybe_cache_chains(self) -> None:
        """Throttled watchlist option-chain snapshot (cadence = snapshot minutes,
        floored at 60s). Off when option_cache_enabled is false."""
        if not self.params.get("option_cache_enabled", True):
            return
        now = self.provider.now()
        epoch = now.timestamp()
        if epoch < self._next_cache_sweep_epoch:
            return
        snap_min = self.params.get("option_cache_snapshot_minutes", 15.0)
        self._next_cache_sweep_epoch = epoch + max(60.0, snap_min * 60.0)
        try:
            self.cache_option_chains(now)
        except Exception as e:
            log.error(f"option cache sweep error: {e}")

    def _signal_iteration_blocking(self) -> None:
        # C5 — the body that can block: scan_signals fetches Kite candles per
        # instrument, and process_entries places a live order and polls it to a
        # terminal state (up to order_timeout_seconds). Runs OFF the event loop
        # (see _signal_iteration) so a slow entry never freezes the risk scheduler,
        # WS heartbeats, or the cockpit — the same guarantee the risk lane already has.
        iteration_started = time.perf_counter()
        self._shadow_seconds = 0.0     # L1 Stage 1 — per-iteration shadow cost
        self.refresh_params()          # pick up live Settings overrides
        self._maybe_refresh_funds()    # cache real account balance (live only)
        self._maybe_reconcile_orphans()
        self.scan_signals()
        self.process_entries()
        # NB: the watchlist option-chain sweep is intentionally NOT here — it runs OFF
        # the lock (see _signal_iteration). Its ~30s of Kite fetches under the shared
        # lock were starving the risk loop (2026-07-13 risk_loop_stalled). Fix F.
        self.handle_overnight(self.provider.now())   # no-op for mock
        self.broker.snapshot(self.provider.now())
        self._maybe_check_ledger()     # H10: periodic cash-invariant drift alarm
        self._maybe_prune_telemetry()  # bounded DB growth on a 1GB box (once a day, flat)
        self.tick_count += 1
        # L1 Stage 1 — what this iteration cost and how much of it was the shadow. Last,
        # so a measurement failure cannot skip any of the work above.
        try:
            self.shadow_metrics.loop(
                iteration_seconds=time.perf_counter() - iteration_started,
                shadow_seconds=self._shadow_seconds,
                budget_seconds=float(self.params.get(
                    "signal_loop_seconds", self.settings.signal_loop_seconds)))
        except Exception:
            pass

    async def _signal_iteration(self) -> None:
        # Offload the blocking body but keep the lock across it, so the single shared
        # DB session is only ever touched by one lane at a time (signal vs risk stay
        # serialised) — identical discipline to _risk_iteration.
        async with self._lock:
            try:
                await to_thread_drained(self._signal_iteration_blocking)
            except Exception:
                self._rollback_session()   # H3 — clean the session before releasing the lock
                raise
        # fix F: the watchlist option-chain sweep uses its OWN DB session (persist_chain
        # → SessionLocal) and touches only the provider + option_data — it needs no
        # shared-session lock. Run it OFF the lock and off the event loop so its ~30s of
        # Kite fetches can never starve the risk loop (2026-07-13 risk_loop_stalled 24×).
        try:
            await to_thread_drained(self._maybe_cache_chains)
        except Exception as e:
            log.error(f"option cache sweep error: {e}", event="OPTION_CACHE")
        self._beat_now("signal")           # P3 heartbeat
        self._maybe_watchdog()             # P3 — alert if the risk lane has stalled
        if self.on_update:
            try:
                await self.on_update(self.snapshot_state())
            except Exception:
                pass

    # ── async loops ───────────────────────────────────────────────────────
    async def run_risk_loop(self) -> None:
        """Fast lane: mark open positions, ratchet the trailing stop, fire SL/TP.
        Independent of the slower signal scan so positions are managed promptly."""
        while self.running:
            try:
                await self._risk_iteration()
            except Exception as e:
                log.error(f"risk loop error: {e}")
                self._alert_infra("risk_loop_error",   # M1 — no longer a silent failure
                                  f"risk loop error: {e} — open positions may be unmanaged")
            await asyncio.sleep(self.settings.position_loop_seconds)

    async def run_signal_loop(self) -> None:
        """Slow lane: recompute strategy on completed candles, open new entries."""
        self.running = True
        # Managed shadow deployments are loaded when the lane *starts*, not in the
        # constructor. Building an `EngineRunner` must not read the database: the suite
        # constructs hundreds of them around `init_db(reset=True)`, and adding a read to
        # every construction made an unrelated options-entry test fail three runs in four
        # — a flake that pointed at the wrong code entirely. Startup is the restart
        # boundary the requirement names, and it is where the read belongs.
        self.refresh_shadow_deployments()
        self.refresh_paper_authority()
        self.report_foreign_book_positions()
        log.info(f"engine started — provider={self.provider.name}, "
                 f"enabled={sorted(self.enabled)}")
        try:
            self.startup_account_reconcile()   # H14 — surface untracked real positions once
        except Exception as e:
            log.error(f"startup account reconcile failed: {e}")
        while self.running:
            try:
                if self.provider.name == "mock":
                    await self._signal_iteration()
                    if not self.provider.advance():
                        log.info("mock history exhausted — engine idling")
                        await asyncio.sleep(5)
                        continue
                    await asyncio.sleep(self.settings.mock_tick_seconds)
                else:
                    any_open = any(self.provider.is_tradable_now(get_instrument(k))
                                   for k in self.enabled)
                    if not any_open:
                        if not self._idle_logged:
                            log.info("all enabled markets closed — engine idling until next session")
                            self._idle_logged = True
                        # Even while idle (overnight / pre-market) keep the real account
                        # balance fresh and push a snapshot, so after the morning Kite
                        # re-login the cockpit reflects funds + LIVE/armed state within a
                        # minute — no restart, no waiting for the open.
                        self._maybe_refresh_funds()
                        if self.on_update:
                            try:
                                await self.on_update(self.snapshot_state())
                            except Exception:
                                pass
                        await asyncio.sleep(60)
                    else:
                        self._idle_logged = False
                        await self._signal_iteration()
                        await asyncio.sleep(self.settings.signal_loop_seconds)
            except Exception as e:
                log.error(f"signal loop error: {e}")
                self._alert_infra("signal_loop_error",   # M1 — no longer a silent failure
                                  f"signal loop error: {e} — new entries/scan may be stalled")
                await asyncio.sleep(self.settings.signal_loop_seconds)

    async def run(self) -> None:   # back-compat alias (signal lane)
        self.running = True
        await self.run_signal_loop()

    def stop(self) -> None:
        self.running = False

    # ── arm-to-trade + kill switch ────────────────────────────────────────
    def arm(self, value: bool) -> bool:
        """Owner control: arm (start auto-executing) or disarm (pause new entries —
        open positions are still managed and protected)."""
        self.armed = bool(value)
        # Mirror onto this deployment's own arm flag (Phase B runtime state). The
        # in-memory flag stays the master switch and is set FIRST: arming and — far
        # more importantly — DISARMING must never be able to fail because of a
        # database hiccup. The row is a durable record of what the master switch
        # says, not a second gate that could disagree with it.
        try:
            from app.core.deployments import set_armed as _set_deployment_armed
            with SessionLocal() as s:
                _set_deployment_armed(s, self.deployment_id, self.armed)
                s.commit()
        except Exception as e:
            log.warn(f"could not persist arm state for deployment "
                     f"{self.deployment_id}: {e} — the engine's own flag is "
                     f"authoritative and is set", event="ARM_PERSIST_FAIL")
        if self.armed and hasattr(self.broker, "order_fail_streak"):
            # #14: a deliberate re-arm is the owner saying the cause is fixed —
            # give the circuit breaker a clean slate.
            self.broker.order_fail_streak = 0
        log.info("engine ARMED — will auto-execute trades" if self.armed
                 else "engine DISARMED — no new entries (open positions still managed)",
                 event="ARM" if self.armed else "DISARM")
        if self.params.get("notify_enabled", True):
            self.notifier.armed(self.armed)
        return self.armed

    def kill(self, now=None, square_off: bool = True) -> list[str]:
        """Emergency stop: disarm immediately and (by default) square off every
        open position at its last mark. Used when things go south."""
        # BEST-EFFORT, NEVER ALL-OR-NOTHING. The kill switch is the control you
        # reach for when things are already going wrong, which is exactly when a
        # broker call is most likely to throw. Every step is isolated so one
        # failure cannot cancel the others, and the whole thing never raises at
        # the caller — it is wired to an API route and a UI button, and an
        # exception there tells the operator nothing about what was stopped
        # while leaving them believing they stopped it.
        try:
            now = now or self.provider.now()
        except Exception:
            now = dt.datetime.now()
        # Disarm FIRST and unconditionally: it is the one step that must not be
        # allowed to fail, because it is what stops the engine opening MORE
        # positions while the operator is trying to stop it.
        self.armed = False

        # H8: a hard stop must also cancel working/timed-out ENTRY orders — otherwise one
        # still resting at the exchange can fill AFTER the kill and leave an untracked,
        # stopless position. (No-op on paper.)
        cancelled: list = []
        try:
            cancelled = self.broker.cancel_working_entries() or []
        except Exception as e:            # noqa: BLE001
            log.error(f"KILL: cancelling working entries failed: {e} — continuing "
                      f"to the square-off anyway", event="KILL_PARTIAL")
        closed: list[str] = []
        if square_off:
            try:
                closed = self._square_off_all("KILL_SWITCH", now)
            except Exception as e:        # noqa: BLE001
                log.error(f"KILL: square-off failed: {e} — the engine is DISARMED but "
                          f"positions may still be open. Check the book.",
                          event="KILL_PARTIAL")
        log.info(f"KILL SWITCH — disarmed; cancelled {len(cancelled)} working order(s); "
                 f"squared off {len(closed)} position(s)", event="KILL")
        try:
            if self.params.get("notify_enabled", True):
                self.notifier.killed(closed)
        except Exception:
            pass          # a failed Telegram notify must never mask a kill
        return closed

    # ── snapshots for API/WS ──────────────────────────────────────────────
    def capital_dict(self) -> dict:
        cap = self.broker.capital()
        opens = self.broker.open_positions()
        # equity = cash + each open position's mark-to-market VALUE. For leveraged
        # MIS equity that's margin + unrealized P&L, not the full notional (mtm_value
        # handles the distinction); options stay premium × qty.
        mtm = sum(p.mtm_value() for p in opens)
        d = {
            "initial": cap.initial_capital, "cash": round(cap.cash, 2),
            "invested": round(sum(p.entry_cost for p in opens), 2),
            "equity": round(cap.cash + mtm, 2),
            "realized_pnl": round(cap.realized_pnl, 2),
            "open_count": len(opens),
        }
        # LIVE: surface the REAL account balance (cached margins) so the cockpit shows
        # the actual ~free funds, not the 50k paper-ledger seed. available = free cash
        # (not locked in your securities); net = total account equity. Paper mode omits
        # these and the UI keeps showing the ledger equity/cash.
        f = self._account_funds
        if caps.provider_supports(self.provider, caps.ACCOUNT_FUNDS) and f:
            d["account_available"] = round(f.get("available", 0.0), 2)
            d["account_net"] = round(f.get("net", 0.0), 2)
            # Ledger honesty: the difference between what the bot BELIEVES it is worth and
            # what the broker says the account is worth. Production ran ~₹27k adrift for
            # three weeks with nothing on screen saying so. Never hide this again — the UI
            # renders it as a warning whenever it exceeds the re-anchor tolerance.
            d["ledger_drift"] = round(d["equity"] - d["account_net"], 2)
            d["ledger_anchor_note"] = self._reanchor_reason
            cap_anchor = getattr(cap, "anchored_at", None)
            d["ledger_anchored_at"] = cap_anchor.isoformat() if cap_anchor else None
        return d

    def _market_open_by_segment(self) -> dict[str, bool]:
        """Per-segment open/closed for the operational screens. Mirrors the engine's
        own scan gate (scan_signals skips closed instruments via is_tradable_now), so
        the UI can render a closed market as a neutral 'market closed' instead of an
        amber 'stale' alarm when no candle can possibly print. Read-only / no network."""
        out: dict[str, bool] = {}
        for inst in (get_instrument(k) for k in self.enabled):
            if inst.segment not in out:
                out[inst.segment] = self.provider.is_tradable_now(inst)
        return out

    def snapshot_state(self) -> dict:
        market_open = self._market_open_by_segment()
        return {"tick": self.tick_count, "provider": self.provider.name,
                "time": self.provider.now().isoformat(),
                "broker_mode": getattr(self.broker, "MODE", "paper"),  # "paper" | "live"
                "armed": self.armed, "running": self.running,
                "halt": self.halt_status(self.provider.now()),
                "enabled": sorted(self.enabled), "states": self.state,
                "intervals": {k: self._interval_for(k) for k in self.enabled},
                "health": self.health.as_dict(),
                "market_open": market_open,                       # {segment: bool}
                "any_market_open": any(market_open.values()),     # feed-wide idle flag
                "position_ticks": self.position_ticks,
                "capital": self.capital_dict()}
