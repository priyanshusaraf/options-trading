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

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ALLOWED_INTERVALS = ("15minute", "30minute")
LIVE_INTERVALS = ("5minute", "15minute", "30minute", "60minute")
DEFAULT_LIVE_INTERVAL = "15minute"


def normalize_live_interval(iv: str) -> str:
    """Clamp an arbitrary interval string to a supported live timeframe (15m default)."""
    return iv if iv in LIVE_INTERVALS else DEFAULT_LIVE_INTERVAL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PT_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # provider selection
    provider: str = "mock"  # "mock" | "kite"

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
    intraday_block_weekday: int = 1          # block ALL new entries on this weekday (Mon=0..Sun=6; 1=Tue/NIFTY-expiry; -1=off). Name kept for override back-compat
    intraday_override_date: str = ""         # 'YYYY-MM-DD' to allow entries despite the weekday block, that one day only (self-expires)
    max_signal_age_minutes: float = 5.0      # act on a crossover only within this long of its candle COMPLETING; older = history, never entered (#15). 0 = off
    entry_window_start: str = "09:30"        # no NEW entry before this IST wall-clock time (session opens 09:15; first minutes are erratic). blank = off
    order_failure_disarm_count: int = 3      # DISARM after this many CONSECUTIVE live order failures (systemic: bad token/IP/margin) — re-arm manually after fixing (#14). 0 = off
    block_overnight_into_weekend: bool = False
    max_holding_days: int = 5                # hard cap on holding period (trading days)
    square_off_buffer_minutes: float = 15.0  # decide / square-off this long before session close

    # ── adaptive order routing (live execution safety) ─────────────────────
    # Don't market into a wide book (illiquid commodity options): route MARKET only
    # when tight + deep, a capped marketable-limit when moderate, and skip entries
    # uglier than this. SELL exits always go market (getting out beats slippage).
    exec_market_max_spread_pct: float = 0.01   # spread <= this -> MARKET order ok
    exec_limit_max_spread_pct: float = 0.05    # above market_max..this -> capped LIMIT; beyond -> SKIP
    exec_max_slippage_pct: float = 0.01        # cap a marketable-limit this far off the mid
    exec_min_top_qty_lots: float = 1.0         # require this many lots of top-of-book depth for MARKET
    # live order lifecycle — place once, then poll to a terminal state. Bounded well
    # under 30s so a stuck poll can't hold the engine lock (the blocking poll is also
    # offloaded off the event loop, but a short ceiling keeps the worst case small).
    order_poll_seconds: float = 0.5            # gap between order-status polls
    order_timeout_seconds: float = 10.0        # give up polling after this; reconcile, never assume filled
    max_daily_loss: float = 5000.0             # halt NEW entries for the day past this REALIZED loss (0 = off)
    max_round_trips_per_day: int = 9           # halt NEW entries after this many completed round trips today (0 = off)
    max_open_drawdown: float = 0.0             # halt NEW entries once today's REALIZED + UNREALIZED (open MTM) loss breaches this (0 = off)
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

    # ── intraday equity segment (MIS, 5x; separate from the options segment) ──
    # Opt-in. Sizing is by MARGIN deployed per trade (not notional): 7–10k of margin
    # controls ~35–50k of stock at 5x. qty = floor(margin × leverage / share_price).
    # Concurrency is a HARD cap of 3 TOTAL (purple included). Purple = a watchlist
    # priority flag: those names always win selection and size at purple_margin;
    # other names compete for leftover slots by the higher-quantity (cheaper-share)
    # rule. The portfolio-wide 5k daily-loss halt (max_daily_loss, cost-inclusive)
    # governs BOTH segments — there is no separate intraday loss cap.
    intraday_enabled: bool = False
    intraday_max_positions: int = 3            # hard cap on concurrent intraday trades (purple included)
    intraday_min_margin: float = 7_000.0       # don't open an intraday trade with less margin than this
    intraday_max_margin: float = 10_000.0      # target margin per (non-purple) intraday trade
    intraday_purple_margin: float = 10_000.0   # margin for a purple-flagged priority name
    intraday_leverage: float = 5.0             # Zerodha MIS equity leverage
    intraday_square_off_buffer_minutes: float = 15.0  # force all intraday positions flat this long before close
    intraday_stop_loss_pct: float = 0.01       # equity SL as a fraction of entry price (tight — not the option 35%)
    intraday_target_pct: float = 0.02          # equity TP as a fraction of entry price
    # lockstep band: once an equity position is in profit, slide BOTH the stop and
    # target together by one step per `trigger_pct` of margin (default 2% = ₹200 on a
    # ₹10k margin), ratchet-only, with a break-even floor. On by default.
    intraday_lockstep_enabled: bool = True
    intraday_lockstep_trigger_pct: float = 0.02  # profit per lockstep, as a fraction of deployed margin
    intraday_profit_lock_threshold: float = 200.0  # #6: once unrealized profit clears this (₹), lock a positive buffer above costs
    intraday_profit_lock_frac: float = 0.5         # #6: fraction of the favourable move to lock once past the threshold

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

    # ── API auth + CORS ───────────────────────────────────────────────────────
    # env PT_API_TOKEN; when non-empty every REST/WS call (except OAuth redirect
    # endpoints and /api/health) must present it; empty = auth disabled (dev/mock/tests).
    api_token: str = ""
    # env PT_CORS_ORIGINS, comma-separated browser origins allowed with credentials.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # misc
    risk_free_rate: float = 0.065
    db_path: str = "paper_trader.db"

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
