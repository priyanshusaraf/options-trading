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

    # capital & risk
    initial_capital: float = 50_000.0
    stop_loss_pct: float = 0.35
    target_pct: float = 0.60

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

    # misc
    risk_free_rate: float = 0.065
    db_path: str = "paper_trader.db"

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
