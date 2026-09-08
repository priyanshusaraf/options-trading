"""
Central settings. Everything tunable lives here and is overridable via a `.env`
file or `PT_*` environment variables (see `.env.example`).

The defaults encode every product decision the owner made:
  - 1 lot per trade, long-only (buy CE on long, buy PE on short)
  - INR 50,000 starting capital, persisted across restarts
  - -35% stop / +60% target on the option premium
  - delta-targeted (~0.50), liquidity-filtered option selection
  - 15-minute candles (30-minute allowed); nothing faster
"""
from __future__ import annotations

import os
import sys
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ALLOWED_INTERVALS = ("15minute", "30minute")


def _env_file_for_this_process() -> str | None:
    """`.env` for a real process; None under pytest.

    A test run must not be able to READ production configuration at all. Forcing
    individual variables in conftest is a denylist: it covered PT_PROVIDER,
    PT_EXECUTION, PT_LIVE_ACK and PT_DB_PATH, while `KITE_API_KEY` and
    `KITE_API_SECRET` kept resolving straight from `.env` — which is how the
    2026-07-28 incident could have made authenticated calls against the owner's
    real Kite account. Worse, a denylist is silently wrong for every setting added
    afterwards: a new secret inherits the exposure and nothing says so.

    Detaching the file makes it an allowlist. Under pytest the ONLY sources are
    process defaults and whatever a test sets explicitly, so a leak requires
    someone to write the leak.

    `"pytest" in sys.modules` is the signal deliberately, rather than a marker our
    own conftest sets: it holds for any test root, including one added later with
    no conftest of ours — which is exactly the failure mode that caused the
    incident. It is evaluated once, at class-definition time, so the decision is
    made before any Settings instance exists. The app never imports pytest, so
    this cannot fire in production; `PT_DISABLE_DOTENV=1` forces it for anything
    that needs the same isolation outside pytest.
    """
    if os.environ.get("PT_DISABLE_DOTENV") == "1":
        return None
    if "pytest" in sys.modules:
        return None
    return ".env"
LIVE_INTERVALS = ("5minute", "15minute", "30minute", "60minute")
DEFAULT_LIVE_INTERVAL = "15minute"


def normalize_live_interval(iv: str) -> str:
    """Clamp an arbitrary interval string to a supported live timeframe (15m default)."""
    return iv if iv in LIVE_INTERVALS else DEFAULT_LIVE_INTERVAL


class Settings(BaseSettings):
    # env_file is None under pytest — see _env_file_for_this_process(). Resolved once
    # here, at class-definition time, so every Settings() in the process agrees.
    model_config = SettingsConfigDict(
        env_prefix="PT_", env_file=_env_file_for_this_process(),
        env_file_encoding="utf-8", extra="ignore",
    )

    # Public capability/reachability profile. `standard` preserves the existing
    # application. `v0_research_signal` is fail-closed to execution authority.
    release_profile: str = "standard"
    # Current process role inside the V0 release profile. This is distinct from
    # `service_role`, which is the legacy auth/deployment posture.
    release_service_role: str = "api"

    # provider selection
    provider: str = "mock"  # "mock" | "kite" | "replay" | "upstox" (data only)
    # Which connection places the ORDERS. Empty (the default, and what production
    # runs) means "the same connection that serves prices" — one Kite login doing
    # data, account and execution, byte-identical to the pre-seam behaviour. Set it
    # to a different provider name to split the roles: prices from `provider`,
    # orders through this one (`providers/connection.py`). The pair is validated at
    # engine construction, and a connection that cannot execute refuses loudly
    # rather than falling back to paper.
    execution_provider: str = ""  # "" (same as provider) | "kite"
    # A DURABLE connection to place orders through, named by its scope and owned by
    # `owner_id`. Takes precedence over `execution_provider` because a stored connection is an
    # explicit act by an owner where the env var is a deployment default. Naming one that does
    # not exist REFUSES rather than falling back — see `providers/connection.py`.
    execution_connection: str = ""
    execution_worker: str = "auto"  # auto (local SQLite only) | api | worker
    execution_owner_id: str = ""
    execution_broker_account_id: str = ""
    execution_cell_id: str = ""
    # Whose resources this process serves. One owner today; the column exists so the tenancy
    # dimension is real rather than retrofitted. `LEGACY_OWNER_ID` in models.py is the same
    # value and the two must not drift.
    owner_id: str = "owner"
    # Encrypts stored broker credentials. Declared here so `PT_CREDENTIAL_KEY` in `backend/.env`
    # actually reaches `core/credential_vault.py` — pydantic-settings reads that file itself and
    # does NOT export to `os.environ`, so a vault reading only the environment silently ignored
    # the documented setup path. The vault still prefers a real environment variable.
    credential_key: str = ""
    # Replay mode: a recorded session re-run bar by bar (see providers/replay.py).
    # Diagnostic only — the provider reports is_authenticated() False, so the
    # live-order path is structurally unreachable from a replay.
    replay_path: str = "replay_session.json"

    # Kite credentials — note the explicit aliases: these env vars are NOT
    # PT_-prefixed (they're the names Kite/most examples use), so we bypass the
    # env_prefix with validation_alias. Used only when provider == "kite".
    kite_api_key: str = Field(default="", validation_alias="KITE_API_KEY")
    kite_api_secret: str = Field(default="", validation_alias="KITE_API_SECRET")

    # Telegram notifications (optional). Like the Kite creds these are NOT
    # PT_-prefixed. If either is empty, notifications are simply off.
    telegram_bot_token: str = Field(default="", validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", validation_alias="TELEGRAM_CHAT_ID")

    # capital & risk
    initial_capital: float = 50_000.0
    # LIVE ledger honesty: re-anchor the internal ledger to the REAL broker equity once a
    # day, before the day's first entry, when the book is flat and the two have drifted
    # beyond the tolerance. Without this the cockpit reports `initial_capital ± realized`
    # forever — production reported ₹49,833 against a real account worth a fraction of it.
    # ── telemetry retention (the DB grows ~5 MB/day on a 1 GB box) ────────────
    # The money record — trades, positions, order journal, capital state — is NEVER
    # pruned. Only regenerable telemetry ages out, and the equity curve is downsampled
    # rather than deleted so its shape survives at every age. A window of 0 means KEEP
    # FOREVER, never "delete everything".
    retention_enabled: bool = True
    retention_option_data_days: int = 90        # local option history (Kite sells no replacement)
    retention_signal_events_days: int = 90
    retention_equity_full_days: int = 7         # full-resolution equity-curve window
    retention_equity_downsample_minutes: int = 15   # older than that: ~1 row per N minutes

    ledger_auto_reanchor: bool = True
    ledger_reanchor_tolerance: float = 250.0   # ₹ drift below which the ledger is left alone
    stop_loss_pct: float = 0.30
    target_pct: float = 0.60

    # ── trader risk controls (additive entry guards; 0 = off, back-compat) ──
    max_open_positions: int = 0          # cap concurrent open positions (0 = unlimited)
    reentry_cooldown_minutes: float = 0.0  # block re-entry on an instrument this long after a stop-out
    max_capital_per_trade: float = 0.0   # skip a signal whose 1-lot cost exceeds this (0 = no cap)

    # capital sharing on the owner's real account — the owner's own trades take
    # priority. In live mode the bot is bounded by the real available margin minus
    # the reserve; the cap is an absolute ceiling on what the bot may ever deploy.
    bot_capital_cap: float = 0.0     # 0 = no extra cap beyond the ledger base
    capital_reserve: float = 0.0     # live: keep this much margin free for you

    # option picker
    target_delta: float = 0.50
    delta_band: float = 0.15
    min_oi: int = 500
    max_spread_pct: float = 0.03

    # strategy (mirrors the Pine inputs in the original strategy.py)
    interval: str = "15minute"
    ema_length: int = 50
    z_length: int = 50
    entry_z: float = 1.0
    slope_lookback: int = 5
    history_days: int = 30  # candle history pulled for warmup + signals

    # mock demo clock
    mock_tick_seconds: float = 3.0
    mock_seed: int = 7
    mock_history_days: int = 90

    # split-loop cadences (live mode)
    position_loop_seconds: float = 1.0   # fast risk lane target (Kite quote throttle bounds it ~2s)
    signal_loop_seconds: float = 2.5     # signal-scan scheduler tick

    # /api/health readiness budgets. Deliberately NOT in runtime_config.OVERRIDABLE:
    # these gate a safety probe, and a DB override that silences it is a footgun
    # with no upside. See app/engine/readiness.py.
    #   risk: fatal (non-200) — a stalled fast lane means SL/TP is not firing on
    #     real money. Much larger than the runner's 30s watchdog ALERT on purpose:
    #     one risk iteration can legitimately block for the live order-poll window,
    #     so the Telegram alert should be twitchy and the HTTP verdict should not.
    #   signal: degraded only, and only while a market is open — the lane
    #     legitimately stops beating overnight.
    health_risk_stale_seconds: float = 90.0
    health_signal_stale_seconds: float = 600.0
    health_startup_grace_seconds: float = 45.0   # before a never-beaten lane reads as dead

    # Manual-trade detection (journal). Read-only: polls the Kite orderbook for
    # trades the OWNER placed by hand and files them for reasoning. It never
    # places, modifies or cancels anything, and never writes the execution ledger.
    manual_detect_enabled: bool = True
    manual_detect_seconds: float = 30.0  # matches the proven positions() cadence
    max_stale_seconds: float = 30.0      # a mark older than this is stale -> no SL/TP fires on it

    # trailing stop-loss (ratchets the premium stop UP as profit thresholds are crossed)
    #   gentle 2.5% lock on the first +10% step, then trail exactly one step (10%)
    #   behind the high-water profit, with NO upper ceiling so a let-it-run winner
    #   keeps locking profit forever. Entry 400: SL 410 at +10%, 440 at +20%,
    #   480 at +30%, … 600 at +60%, 760 at +100%. Never loosens.
    trail_enabled: bool = True
    trail_trigger_pct: float = 0.10         # profit (fraction of entry) per ratchet step
    trail_first_step_lock_pct: float = 0.025  # gentle SL lock at the first (+10%) step
    trail_step_lock_pct: float = 0.10       # SL trails this fraction of entry behind each step >=2

    # ── reinforcement (a same-direction crossover while holding a winner) ───
    # Does NOT add quantity (no pyramiding). It strengthens management: ratchet
    # the stop to lock profit, optionally extend the target, count the confirm.
    reinforce_enabled: bool = True
    reinforce_min_profit_pct: float = 0.10   # position must be >= +10% before a reinforcement counts
    reinforce_lock_pct: float = 0.05         # SL floor = entry*(1 + count*lock); never loosens
    reinforce_extend_tp: bool = True
    reinforce_tp_extend_pct: float = 0.20    # +20% of entry added to target per reinforcement
    reinforce_tp_max_pct: float = 1.50       # target never extends beyond +150%
    reinforce_cooldown_minutes: float = 15.0 # min gap between counted reinforcements
    max_reinforcements: int = 3              # cap (theta makes endless management pointless)

    # ── overnight holding (option buying: theta/expiry are the real risks) ──
    overnight_enabled: bool = True
    overnight_auto_pct: float = 0.10         # positions <=10% of capital auto-hold overnight
    overnight_max_pct: float = 0.25          # >25% of capital never held overnight, even reinforced
    overnight_min_reinforcements: int = 1    # 10%–25% positions need >=1 reinforcement to hold
    overnight_min_days_to_expiry: int = 2    # force square-off if expiry within N days (theta cliff)
    entry_min_days_to_expiry: int = 3        # refuse to OPEN an option within N days of expiry (theta cliff): blocks 0/1/2-DTE. 0 = off
    # ── scheduled-event risk (owner, 2026-08-01) ──────────────────────────────
    # No new position in an instrument with a known event on the clock: the EIA gas
    # (Thu) / petroleum (Wed) releases, index weekday sit-outs, bullion options into
    # expiry, and any stock on its results date. The rule table lives in
    # `engine/event_risk.py` and is shared by the engine, the backtester and the UI.
    event_risk_enabled: bool = True
    # Also square off an OPEN position before a timed release, rather than only blocking
    # new ones — carrying a position into the print is the risk being avoided.
    event_risk_flatten: bool = True
    event_risk_flatten_lead_minutes: float = 2.0   # how early to be flat before the window

    intraday_block_weekday: int = 1        # sit out this weekday (Mon=0..Sun=6; 1=Tue/NIFTY-expiry; -1=off). Name kept for override back-compat
    expiry_day_block_keys: str = "NIFTY"     # WHICH instruments sit out that weekday: '*' = the whole book (pre-2026-07-28 behaviour); else a comma-separated key list. Blank fails safe to '*'
    intraday_override_date: str = ""         # 'YYYY-MM-DD' to allow entries despite the weekday block, that one day only (self-expires)
    max_signal_age_minutes: float = 5.0      # act on a crossover only within this long of its candle COMPLETING; older = history, never entered (#15). 0 = off
    entry_window_start: str = "09:30"        # no NEW entry before this IST wall-clock time (session opens 09:15; first minutes are erratic). blank = off
    # Nifty-50 opening-gap guard (fix D): if the index opens ≥ gap_pct from prior close,
    # the first hour is erratic — block ALL new entries until gap_resume. Exits unaffected.
    gap_guard_enabled: bool = True
    gap_guard_pct: float = 0.6               # |open−prev_close|/prev_close % that counts as a gap (0 = off)
    gap_guard_resume: str = "11:00"          # resume new entries at this IST wall-clock time after a gap
    gap_guard_index: str = "NIFTY"           # instrument key whose open/prev-close defines the market gap
    order_failure_disarm_count: int = 3      # DISARM after this many CONSECUTIVE live order failures (systemic: bad token/IP/margin) — re-arm manually after fixing (#14). 0 = off
    block_overnight_into_weekend: bool = False
    max_holding_days: int = 5                # hard cap on holding period (trading days)
    square_off_buffer_minutes: float = 15.0  # decide / square-off this long before session close

    # ── adaptive order routing (live execution safety) ─────────────────────
    # Don't market into a wide book (illiquid commodity options): route MARKET only
    # when tight + deep, a capped marketable-limit when moderate, and skip entries
    # uglier than this. SELL exits always go market (getting out beats slippage).
    entry_order_mode: str = "AUTO"              # "AUTO" | "MARKET" | "LIMIT"
    # ── MTF (funded delivery) segment (E3) — EVERY KNOB DEFAULTS INERT ──────
    # Multi-day, funded, interest-bearing. `mtf_enabled=False` means no candidate
    # is ever generated, so nothing below is reachable. Enabling it is an owner
    # decision that also requires deciding the LIFECYCLE questions this build
    # deliberately does not answer: how a funded position interacts with the
    # daily profit-lock, and whether it may ever be force-closed. The carry model
    # and the P&L are built and correct; the lifecycle is not assumed.
    mtf_enabled: bool = False
    mtf_annual_rate: float = 0.1499     # broker funding rate; verify vs a statement
    mtf_max_holding_days: int = 30      # a funded position is not a forever position

    # ── index-futures segment (E2) — EVERY KNOB DEFAULTS INERT ──────────────
    # The segment is fully built and switched OFF. `index_futures_enabled=False`
    # means no candidate is ever generated, so the entry/mark/exit paths are
    # unreachable in production regardless of the rest of these values.
    # Turning it on is an owner decision (roadmap E2 step 13: owner + Fable
    # review first), not something a deploy should be able to do by accident.
    index_futures_enabled: bool = False
    index_futures_max_positions: int = 1
    # ONE NIFTY lot is ~₹18 lakh of notional, so at the 12% estimate below it
    # blocks roughly ₹2.1 lakh of margin. An earlier ₹25,000 default could not
    # have bought a single lot — the segment would have looked BROKEN rather than
    # off, which is a worse failure than either. Sized so one lot is reachable
    # and a second is not; the flag still gates everything.
    index_futures_max_margin: float = 250_000.0  # target SPAN+exposure per position
    index_futures_min_margin: float = 50_000.0   # dust floor — below one lot, don't bother
    # Paper-mode SPAN+exposure ESTIMATE as a fraction of notional. A flagged
    # approximation: real SPAN is portfolio-scanned and instrument-specific, so
    # live sizing must use a broker order_margins() quote and this value is only
    # ever a paper/backtest stand-in.
    index_futures_margin_pct: float = 0.12
    index_futures_stop_loss_pct: float = 0.004   # tighter than cash: leverage is higher
    index_futures_target_pct: float = 0.008
    index_futures_square_off_buffer_minutes: float = 15.0
    # Delivery guard. Index futures are cash-settled so this is a no-op today;
    # it exists so a later commodity extension cannot trade through delivery.
    index_futures_delivery_guard: bool = True

    # Backtest execution cost. The SPOT backtester filled at the exact bar open
    # with ZERO cost until 2026-08-01, while premium.py had modelled a spread since
    # it was written. Against a 0.8% stop / 1.5% target — and a largest-ever
    # favourable excursion of 1.216% of notional — an unmodelled round trip is the
    # same order of magnitude as the edge being measured. Applied adversely to every
    # fill, half per side. Set to 0.0 to reproduce pre-2026-08-01 numbers exactly.
    backtest_slippage_pct: float = 0.0005      # 5 bps round trip (liquid NSE cash intraday)

    exec_market_max_spread_pct: float = 0.01   # spread <= this -> MARKET order ok
    exec_limit_max_spread_pct: float = 0.05    # above market_max..this -> capped LIMIT; beyond -> SKIP
    exec_max_slippage_pct: float = 0.01        # cap a marketable-limit this far off the mid
    exec_min_top_qty_lots: float = 1.0         # require this many lots of top-of-book depth for MARKET
    # live order lifecycle — place once, then poll to a terminal state. Bounded well
    # under 30s so a stuck poll can't hold the engine lock (the blocking poll is also
    # offloaded off the event loop, but a short ceiling keeps the worst case small).
    order_poll_seconds: float = 0.5            # gap between order-status polls
    order_timeout_seconds: float = 10.0        # give up polling after this; reconcile, never assume filled
    max_daily_profit: float = 0.0              # halt NEW entries at this session realized NET profit in INR (0 = off)
    max_daily_loss: float = 5000.0             # halt NEW entries for the day past this REALIZED loss (0 = off)
    max_round_trips_per_day: int = 9           # halt NEW entries after this many completed round trips today (0 = off)
    max_open_drawdown: float = 2_500.0         # halt NEW entries once today's REALIZED + UNREALIZED (open MTM) loss breaches this (0 = off; H15, enabled 2026-07-17 — half the ₹5k daily-loss halt since open MTM bleeds faster than realized)
    # daily profit-lock (E1) — give-back circuit breaker, the symmetric twin of the
    # loss halt above but on the upside: arm a floor once the day's P&L clears
    # `daily_profit_lock_pct` of the day's deployed capital, then if the day
    # retraces down to `daily_profit_giveback_frac` of its peak -> square off ALL
    # open positions and halt new entries for the rest of the session. 0 = off.
    daily_profit_lock_pct: float = 0.0         # arm threshold as a fraction of daily deployed capital (e.g. 0.02 = 2%); 0 = off
    daily_profit_giveback_frac: float = 0.5    # floor = this fraction of the peak day P&L once armed (e.g. 0.5 = give back at most half)
    gtt_stop_enabled: bool = True              # live: also place an exchange-side GTT stop (survives bot/laptop downtime)
    # market protection for every live MARKET order (entries + protective exits, all
    # segments incl. MCX). Mandatory since SEBI's 1-Apr-2026 rule: an unprotected
    # market order via API is REJECTED. -1 = automatic exchange-guideline protection
    # (compliant, self-adjusts per segment); >0..100 = an explicit cap %. 0 is coerced
    # to -1 at send time so we can never place an unprotected market order.
    market_protection_pct: float = -1.0
    # live: book a bot position closed only after the account feed shows it gone on
    # this many CONSECUTIVE reconcile reads — one transient positions() glitch (>60s)
    # must not phantom-close a still-open real position.
    orphan_confirm_count: int = 2

    # ── intraday equity segment (MIS; separate from the options segment) ──
    # Opt-in. Live orders are sized against Kite `order_margins` (real per-share MIS
    # margin, fix A 2026-07-14) so broker rejection is never a risk: qty is sized to
    # deploy the FULL target real margin (max_margin / purple_margin) and Zerodha's own
    # MIS multiplier decides the resulting notional (owner, 2026-07-21 — "put in 7k as
    # the margin and let the leverage aspect be figured out from their end; we're not
    # holding securities, we just care about maxing return"). The earlier artificial
    # `intraday_leverage` notional cap (Task 2, R2 2026-07-16) is REMOVED — it was
    # throttling real margin to ~4.5k. `intraday_leverage` now serves ONLY as the pure
    # fallback estimate for paper/mock or a failed margin quote (so keep it near
    # Zerodha's real ~5x). Concurrency is a HARD cap of 3 TOTAL (purple included).
    # Purple = a watchlist priority flag: those names always win selection and size at
    # purple_margin; other names compete for leftover slots by the higher-quantity
    # (cheaper-share) rule. When the cash left can't fund the full target, the trade is
    # NOT skipped — it deploys whatever remains (down to the min_margin dust floor). The
    # portfolio-wide 5k daily-loss halt (max_daily_loss, cost-inclusive) governs BOTH
    # segments — there is no separate intraday loss cap.
    intraday_enabled: bool = False
    intraday_max_positions: int = 3            # hard cap on concurrent intraday trades (purple included)
    intraday_min_margin: float = 2_500.0       # dust floor — kept low so a partial (leftover-cash) trade still opens
    intraday_max_margin: float = 7_000.0       # target REAL margin per (non-purple) intraday trade
    intraday_purple_margin: float = 10_000.0   # target REAL margin for a purple-flagged priority name
    # purple SL/TP tiering: purple names are higher-conviction and more volatile
    # than the rest of the watchlist (owner, 2026-07-17) — they get wider bands so
    # normal intraday noise doesn't stop them out. Kept STRICTLY wider than the normal
    # bands below (owner, 2026-07-21). Frozen onto Position.entry_sl_pct/entry_tp_pct
    # AT ENTRY (see equity_entry.py/broker.py) so a mid-trade purple-flag toggle never
    # reshapes an already-open position.
    intraday_purple_stop_loss_pct: float = 0.015   # purple equity SL, fraction of entry price (> normal 0.008)
    intraday_purple_target_pct: float = 0.045      # purple equity TP, fraction of entry price (> normal 0.03)
    # Pure fallback leverage estimate ONLY (the binding notional cap was removed
    # 2026-07-21): used to size paper/mock entries and a failed live margin quote.
    # Keep near Zerodha's real MIS multiplier (~5x) so the estimate is realistic.
    intraday_leverage: float = 5.0
    intraday_square_off_buffer_minutes: float = 15.0  # force all intraday positions flat this long before close
    # don't OPEN a new intraday trade once we're this close to close — must exceed
    # the square-off buffer above, or a fresh entry can be force-flattened seconds
    # later (2026-07-15: NCC entered 15:15:16, squared off 15:15:17, -₹67.7 on
    # charges/spread alone). Default = buffer + 10, so a new position always has
    # >=10 minutes to actually work before the force-flat fires.
    intraday_entry_cutoff_minutes: float = 25.0
    # exit geometry widened + the profit-lock loosened (owner, 2026-07-21 — PAYTM short
    # @1321 was ratcheted out near break-even while price was still falling toward the
    # real target; approved interim params from docs/ROADMAP.md Workstream C). Wider
    # target lets winners run; a higher lock threshold + smaller lock fraction stop a
    # normal pullback from surrendering a live position too early.
    intraday_stop_loss_pct: float = 0.008      # equity SL as a fraction of entry price (tight — not the option 35%)
    intraday_target_pct: float = 0.03          # equity TP as a fraction of entry price
    # lockstep band: once an equity position is in profit, slide BOTH the stop and
    # target together by one step per `trigger_pct` of margin, ratchet-only, with a
    # break-even floor. On by default.
    intraday_lockstep_enabled: bool = True
    intraday_lockstep_trigger_pct: float = 0.03  # profit per lockstep, as a fraction of deployed margin
    # C-P2 (2026-08-01): retuned from the excursion telemetry of 22 replayable real
    # trades (`scripts/exit_sweep.py`, report in docs/reports/2026-08-01-exit-sweep.md). The old
    # ₹600 threshold sat ABOVE the p75 peak of the actual book (median peak ₹164), so the
    # lock almost never armed — it fired on 1 of 22 trades. At ₹150 × 0.7 the same 22
    # trades turn −₹913 into +₹268. Small sample: a direction, not a proven setting.
    intraday_profit_lock_threshold: float = 150.0  # #6: once unrealized profit clears this (₹), lock a positive buffer above costs
    intraday_profit_lock_frac: float = 0.7         # #6: fraction of the favourable move to lock once past the threshold

    # overtrading guard (advisory red-flag suggestion — no engine effect)
    overtrade_today_threshold: int = 5      # suggest red when an instrument fires >= this many signals today
    overtrade_rolling_threshold: int = 15   # ...or >= this many over the rolling window
    overtrade_rolling_days: int = 7         # rolling window length, in days

    # ── notifications (Telegram) ───────────────────────────────────────────
    notify_enabled: bool = True              # master switch (no-op anyway if creds unset)
    notify_on_signal: bool = False           # also ping on every fresh entry signal (noisy)
    alert_proximity_pct: float = 0.10        # warn when premium is within this fraction of the SL/TP level

    # ── option-data research cache (persistent, growing dataset) ────────────
    option_cache_enabled: bool = True
    option_cache_snapshot_minutes: float = 15.0  # persist a chain snapshot at most this often

    # ── research plane (frozen by default) ───────────────────────────────────
    # Master switch for the autonomous research plane: the nightly research run,
    # startup registration of generated (builder) strategies, and the
    # /api/portfolio promotions/watchlists/archive/deploy surface. OFF (the
    # default) freezes the plane without deleting it: the nightly entry point
    # no-ops, nothing is registered at startup (a stale gen_* assignment
    # fail-safes to the default strategy), the portfolio routes answer 403, and
    # the cockpit hides the Portfolio tab. Flip via env PT_RESEARCH_ENABLED=1
    # (restart to re-register generated strategies). The core universe
    # endpoints (/api/portfolio/add|remove|add-bulk|home) and the option-data
    # research cache above are NOT part of the plane and ignore this flag.
    research_enabled: bool = False

    # ── L1 Stage 1: the Component IR shadow lane (ADR 0011) ──
    # OFF by default and fail-closed. When on, the signal lane additionally evaluates the
    # IR mirror of an instrument's authoritative strategy on the same frame and records
    # where the two disagree. It is an OBSERVER: it reaches no order, position, ledger or
    # capital seam (tests/test_ir_shadow_isolation.py), and the hand-written strategy
    # remains the sole execution authority. Runtime-overridable so it can be switched off
    # on a live box without a deploy or a restart.
    ir_shadow_enabled: bool = False

    # ── live execution gate (BOTH required, on top of kite-provider + ARM) ──
    # Settings-backed so the SINGLE source of truth is .env (no shell exports
    # needed each session). broker_factory still also honours a real exported
    # PT_EXECUTION/PT_LIVE_ACK as a fallback. The ack string must match exactly.
    execution: str = ""    # "live" to permit real orders   (env: PT_EXECUTION)
    live_ack: str = ""     # must equal the ack phrase       (env: PT_LIVE_ACK)

    # where to send the browser after a successful Kite OAuth login. The Kite app's
    # registered redirect points at the BACKEND (/api/session); once the token is
    # captured we bounce the browser back to the FRONTEND so the user lands on the UI.
    frontend_url: str = "http://localhost:5173"   # env: PT_FRONTEND_URL

    # ── production SPA serving (single-process deploy) ──────────────────────
    # When true and frontend_dist is a real directory, FastAPI serves the built
    # React bundle at / (and as SPA fallback) alongside /api and /ws — one origin,
    # one process. Off by default so dev/tests keep the two-process Vite setup.
    serve_frontend: bool = False          # env: PT_SERVE_FRONTEND
    frontend_dist: str = ""               # env: PT_FRONTEND_DIST (abs path to dist/)

    # ── API auth + CORS ───────────────────────────────────────────────────────
    # Optional one-time bootstrap input for the legacy shared credential.  It is
    # hashed into a legacy UserSession at boot and never acts as runtime auth
    # authority after that bridge.
    api_token: str = ""
    # Shared by every API replica to sign tenant-bound durable resume cursors.
    # Production requires a dedicated value stable across replicas/restarts.
    event_cursor_secret: str = ""
    # The explicit service posture.  Empty authentication is only valid for a
    # development or test process; production-like roles refuse to boot instead
    # of accidentally exposing the shared execution API.
    service_role: str = "development"
    # Deliberately explicit.  Only development/test roles may set this; a
    # production process resolves durable UserSessions even with no legacy token.
    # None retains the legacy setting behaviour during migration: a configured
    # PT_API_TOKEN enables auth and an empty one disables it in development.
    # New production deployments must set this explicitly to false.
    auth_disabled: bool | None = None
    browser_auth_enabled: bool = False
    browser_auth_origin: str = ""
    browser_auth_counter_secret: str = Field(default="", repr=False)
    # env PT_CORS_ORIGINS, comma-separated browser origins allowed with credentials.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # misc
    risk_free_rate: float = 0.065
    # PT_DATABASE_URL is the execution-plane authority. PT_DB_PATH remains only
    # for a local SQLite deployment that has not supplied a database URL.
    database_url: str = ""
    research_database_url: str = ""
    ledger_database_url: str = ""
    production: bool = False
    # Deployment-owned restore approval. `quarantined` blocks every role;
    # `verified` binds boot to one retained verifier report and generation.
    # `normal` is the non-restore path and preserves existing deployments.
    restore_safety_state: str = "normal"
    restore_generation_id: str = ""
    restore_verification_address: str = ""
    restore_old_primary_isolated: bool = False
    db_path: str = "paper_trader.db"
    research_db_path: str = "research.db"
    ledger_db_path: str = ""
    # Local content-addressed backtest dataset store (env PT_BACKTEST_DATASET_DIR).
    # A filesystem directory, NOT the ledger database: the 10,000 × 5 tier is
    # ~50,000 datasets and tens of GB of candle bytes, which must never enter
    # paper_trader.db. The store owns its own request index inside this directory.
    backtest_dataset_dir: str = "backtest_datasets"

    # Sweep fan-out (env PT_BACKTEST_SWEEP_WORKERS). Cells are independent — no
    # cross-cell reduction — so the cell arithmetic is identical whichever process
    # runs it, and `tests/test_backtest_parallel.py` gates that as bit-identity.
    #
    # The default is 1 — the SERIAL reference path — on purpose, and it is not
    # timidity. The process that runs sweeps today is the live trading backend on
    # a 1 GB VPS, where a spawned worker costs ~200 MB of resident pandas/scipy
    # before it does any work; 8 of them is the 2026-07-23 OOM again, this time
    # taking the money path down with it. Raise it where the sweep has a box of
    # its own. Bounded by `sweep.MAX_SWEEP_WORKERS` and the CPU count.
    backtest_sweep_workers: int = 1
    # Durable research admission. These are host/workload limits, deliberately
    # not a product user-count limit. Operators choose them from measured memory,
    # CPU, database lock wait and provider capacity for the deployment tier.
    backtest_host_active_jobs: int = 2
    backtest_owner_active_jobs: int = 1
    backtest_owner_queued_jobs: int = 4
    backtest_host_requested_cells: int = 100_000
    backtest_host_worker_slots: int = 8
    backtest_claim_lease_seconds: int = 30
    # Conservative no-I/O admission estimate for a request whose broker universe
    # has not been resolved yet.  This bounds work before a provider dump/read.
    backtest_full_universe_upper_bound: int = 20_000
    backtest_liquid_universe_upper_bound: int = 1_000

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def candle_minutes(self) -> int:
        return 30 if self.interval == "30minute" else 15

    @property
    def delta_low(self) -> float:
        return self.target_delta - self.delta_band

    @property
    def delta_high(self) -> float:
        return self.target_delta + self.delta_band


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.interval not in ALLOWED_INTERVALS:
        # strategy is only valid on 15m/30m — clamp anything else.
        s.interval = "15minute"
    return s


class BootConfigError(RuntimeError):
    """The resolved configuration is not one a real process may run on."""


_UNSET = object()


def effective_auth_enabled(settings: Settings) -> bool:
    """Whether this deployment requires durable bearer-session authentication."""
    if settings.auth_disabled is True:
        return False
    if settings.auth_disabled is False:
        return True
    return bool(settings.api_token)


def assert_boot_config(settings: Settings, *, env_file=_UNSET, under_test=_UNSET,
                       warn=None) -> None:
    """Refuse to start on a configuration that only LOOKS healthy.

    `_env_file_for_this_process()` detaches `.env` whenever `"pytest" in
    sys.modules`. That is the correct isolation control — but pytest lives in the
    same venv production runs from, so any stray import detaches `.env` from a
    REAL process. Settings then fall back to their defaults, `provider` becomes
    "mock", and the engine trades a synthetic market while `/api/health` returns
    200 and the dashboard renders. Nothing anywhere says the market is fake.

    So the boot path asserts POSITIVELY: the config it needs must be present and
    identifiable, not merely un-refused.

    `"pytest" in sys.modules` cannot be the discriminator — it is the signal under
    suspicion. `PYTEST_CURRENT_TEST` is set by pytest only while a test is
    actually running; importing pytest does not set it. It is the independent
    signal, and `broker_factory.make_broker()` already relies on it for the same
    reason.

    Args are injectable so the guard can be tested in both directions from inside
    a test run — where the ambient values are, necessarily, the passing ones.
    """
    if env_file is _UNSET:
        env_file = type(settings).model_config.get("env_file")
    if under_test is _UNSET:
        under_test = "PYTEST_CURRENT_TEST" in os.environ
    if warn is None:
        from app.core.logging import log
        warn = lambda m: log.warn(m, event="BOOT_CONFIG")  # noqa: E731

    if settings.browser_auth_enabled:
        from app.accounts.browser_auth import validate_configuration
        if not validate_configuration(settings):
            raise BootConfigError("browser authentication requires V0 API, effective auth, exact HTTPS origin and dedicated 32-byte counter key")

    if settings.service_role not in {"development", "test"} and not effective_auth_enabled(settings):
        raise BootConfigError(
            "REFUSING TO START: authentication is disabled for a production-like service role. "
            "Enable durable authentication or use an explicit development/test PT_SERVICE_ROLE."
        )
    if (settings.service_role not in {"development", "test"}
            and len(settings.event_cursor_secret.strip()) < 32):
        raise BootConfigError(
            "PT_EVENT_CURSOR_SECRET must contain at least 32 characters for a production "
            "deployment so every API replica verifies the same resume cursor")
    from app.core.release_profile import ReleaseProfileConfigurationError, validate_boot
    try:
        validate_boot(settings)
    except ReleaseProfileConfigurationError as exc:
        raise BootConfigError(str(exc)) from exc

    role = settings.execution_worker.strip().lower()
    if role not in {"auto", "api", "worker"}:
        raise BootConfigError("PT_EXECUTION_WORKER must be exactly auto, api, or worker")
    if role == "auto" and settings.database_url.strip():
        from sqlalchemy.engine import make_url
        try:
            backend = make_url(settings.database_url.strip()).get_backend_name()
        except Exception as exc:
            raise BootConfigError("PT_DATABASE_URL is not a valid SQLAlchemy URL") from exc
        if backend == "postgresql":
            raise BootConfigError(
                "shared PostgreSQL requires explicit PT_EXECUTION_WORKER=api or worker")
    if role == "worker":
        identities = (settings.execution_owner_id.strip(),
                      settings.execution_broker_account_id.strip(),
                      settings.execution_cell_id.strip())
        if any(not value for value in identities) or len(identities[2]) > 96:
            raise BootConfigError(
                "execution worker requires bounded PT_EXECUTION_OWNER_ID, "
                "PT_EXECUTION_BROKER_ACCOUNT_ID, and PT_EXECUTION_CELL_ID")
    restore_state = settings.restore_safety_state.strip().lower()
    if restore_state not in {"normal", "quarantined", "verified"}:
        raise BootConfigError(
            "PT_RESTORE_SAFETY_STATE must be exactly normal, quarantined, or verified")
    if restore_state == "quarantined":
        raise BootConfigError(
            "restore target is quarantined until the three-plane verifier approves it")
    if restore_state == "verified":
        address = settings.restore_verification_address.strip()
        generation = settings.restore_generation_id.strip()
        if (not generation or len(generation) > 128 or not address.startswith("sha256:")
                or len(address) != 71
                or any(character not in "0123456789abcdef" for character in address[7:])):
            raise BootConfigError(
                "verified restore boot requires a bounded restore generation and verifier "
                "report content address")
        if not settings.restore_old_primary_isolated:
            raise BootConfigError(
                "verified restore boot requires PT_RESTORE_OLD_PRIMARY_ISOLATED=1")

    # 1. Config must be attached. An explicit PT_DISABLE_DOTENV=1 is an
    #    operator-typed opt-out and takes its own path; the heuristic misfiring
    #    on its own is the failure this exists to catch.
    explicit_optout = os.environ.get("PT_DISABLE_DOTENV") == "1"
    if not under_test and env_file is None and not explicit_optout:
        raise BootConfigError(
            "REFUSING TO START: env_file resolved to None outside a test run.\n"
            "  `pytest` is in sys.modules, so config.py detached `.env` — but "
            "PYTEST_CURRENT_TEST is not set, so this is NOT a test run.\n"
            "  This process has NO configuration: PT_PROVIDER has fallen back to "
            "its default and the engine would trade a SYNTHETIC market while every "
            "health check stayed green.\n"
            "  Find what imported pytest (pytest lives in the same venv as the "
            "app), or set PT_DISABLE_DOTENV=1 if config-less boot is genuinely "
            "intended."
        )

    # 2. Selecting the real broker means the real credentials must actually be
    #    there. Enforced even under test: a suite that resolves half a credential
    #    set is a suite reaching for the owner's account.
    if settings.provider == "kite":
        missing = [n for n, v in (("KITE_API_KEY", settings.kite_api_key),
                                  ("KITE_API_SECRET", settings.kite_api_secret))
                   if not (v or "").strip()]
        if missing:
            raise BootConfigError(
                f"REFUSING TO START: PT_PROVIDER=kite but {' and '.join(missing)} "
                f"is empty.\n"
                f"  Empty credentials do not fail loudly at boot — they fail at the "
                f"first authenticated call, mid-session, with positions open.\n"
                f"  env_file={env_file!r}. If that is None, `.env` was detached and "
                f"the credentials were never read at all."
            )

    # 3. A real process on the synthetic market is legitimate (dryrun.py,
    #    backtest_smoke.py) but must never be quiet about it — a silent mock
    #    provider in production is indistinguishable from a working engine.
    if not under_test and settings.provider != "kite":
        warn(f"PT_PROVIDER={settings.provider!r} outside a test run — this engine is "
             f"running against a SYNTHETIC market. No quote, fill, or P&L figure it "
             f"reports is real.")
