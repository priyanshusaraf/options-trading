export interface Capital {
  initial: number; cash: number; invested: number;
  equity: number; realized_pnl: number; open_count: number
  // live mode only: the REAL Kite account balance (cached margins). available =
  // free cash not locked in your securities; net = total account equity.
  account_available?: number; account_net?: number
}

export interface PositionDTO {
  id: number; instrument_key: string; direction: string; option_type: string
  tradingsymbol: string; strike: number; expiry: string; lot_size: number; qty: number
  entry_premium: number; entry_cost: number; entry_time: string; entry_reason: string
  stop_price: number; target_price: number; last_premium: number; last_spot: number
  last_mark_time?: string | null; high_water_premium?: number
  reinforcement_count?: number; held_overnight?: boolean
  unrealized_pnl: number
  mode?: 'paper' | 'live'
  segment?: 'options' | 'equity_intraday'; strategy_key?: string | null
  live_premium?: number | null; live_spot?: number | null
  stale?: boolean; stale_age?: number | null
  dist_to_stop?: number; dist_to_target?: number
}

export interface InstrState {
  instrument: string; name: string; segment: string; time: number
  close: number; ema: number; z: number; z_prev: number | null; slope: number; std: number
  trend: string; signal: string; long_exit: boolean; short_exit: boolean
  position: PositionDTO | null
  interval?: string; has_options?: boolean; entries_blocked?: boolean
}

export interface CatHealth {
  last_ok: string | null; consecutive_failures: number; last_error: string
  auth_error?: boolean   // last failure was a Kite session/token expiry (C1)
}
export interface ProviderHealth { quote: CatHealth; candle: CatHealth }

// Daily-loss / open-drawdown circuit-breaker status on the WS snapshot (C2).
export interface HaltStatus {
  halted: boolean; reason: '' | 'realized' | 'open_drawdown'
  realized: number; open_unrealized: number
  max_daily_loss: number; max_open_drawdown: number
}

export interface PositionTick {
  instrument: string; tradingsymbol: string; option_premium: number | null; spot: number | null
  unrealized_pnl: number; stop_price: number; target_price: number; high_water_premium: number
  stale: boolean; stale_age: number | null; last_mark_time: string | null
}

export interface LiveState {
  tick: number; provider: string; time: string; enabled: string[]
  states: Record<string, InstrState>; capital: Capital
  intervals?: Record<string, string>; health?: ProviderHealth
  position_ticks?: Record<string, PositionTick>
  broker_mode?: 'paper' | 'live'
  // authoritative engine status (C2)
  armed?: boolean; running?: boolean; halt?: HaltStatus
  // market session, per segment + feed-wide (OPS-R2-1): lets the screens tell
  // "market closed, all fine" apart from a broken feed, so staleness doesn't
  // false-alarm 16+ hours a day.
  market_open?: Record<string, boolean>; any_market_open?: boolean
}

export interface LiveTick {
  time: string; spot: number | null; option_premium: number | null
  tradingsymbol: string | null
}

export interface SignalRow {
  key: string; name: string; segment: string; enabled: boolean
  interval: string; signal: string; trend: string | null; z: number | null
  close: number | null; last_candle_time: number | null
  has_position: boolean; has_options: boolean; entries_blocked: boolean; stale: boolean
  market_open?: boolean   // OPS-R2-1: closed market -> stale is benign idle, not broken
  pinned?: boolean        // in the curated portfolio (Watchlist "pinned only" filter)
  // dual-segment / multi-strategy per-instrument config (Phase 3)
  product?: 'options' | 'equity_intraday'
  priority_flag?: boolean      // watchlist "purple" intraday priority
  strategy_key?: string | null // assigned strategy (null = default)
  signals_today?: number
  signals_rolling?: number
  overtrade_flag?: boolean       // red "overtrading" flag (advisory)
  overtrade_suggested?: boolean  // count crossed a threshold -> suggest red
}

export interface PositionRow extends PositionDTO {
  high_water_premium: number; last_mark_time: string | null
  live_premium: number | null; live_spot: number | null
  stale: boolean; stale_age: number | null; dist_to_stop: number; dist_to_target: number
  manual_target?: boolean; no_take_profit?: boolean
}

export interface LogEntry {
  seq: number; ts: string; level: string; instrument: string | null; msg: string
  event?: string
}

export interface InstrumentMeta {
  key: string; name: string; segment: string; priority: number; lot_size: number
  enabled: boolean; signal: string; trend: string | null; z: number | null
  close: number | null; position: PositionDTO | null
}

export interface Candidate {
  tradingsymbol: string; strike: number; option_type: string; ltp: number; oi: number
  spread_pct: number; iv: number | null; delta: number | null
  passed_liquidity: boolean; in_delta_band: boolean; eligible: boolean
}

export interface OptionsCalc {
  time?: string; direction?: string; reason: string; spot?: number; expiry?: string
  chosen?: any; candidates: Candidate[]
}

export interface TradeDTO {
  id: number; instrument_key: string; direction: string; option_type: string
  tradingsymbol: string; strike: number; qty: number; entry_premium: number
  exit_premium: number; entry_time: string; exit_time: string; exit_reason: string
  gross_pnl: number; charges_total: number; net_pnl: number; return_pct: number
  holding_minutes: number; win: boolean
  entry_spot: number | null; exit_spot: number | null
  spot_move_pct: number | null; premium_move_pct: number | null
  held_overnight?: boolean
  mode?: 'paper' | 'live'
}

export interface InstrumentStatBlock {
  trades: number; wins: number; win_rate: number; net: number; gross: number
  charges: number; avg_pnl: number; avg_win: number; avg_loss: number
  expectancy: number; avg_holding_minutes: number; best: number; worst: number
}
export interface InstrumentDetailDTO {
  key: string; name: string; segment: string | null
  stats: InstrumentStatBlock; trades: TradeDTO[]; period: string
}

// ── backtest ────────────────────────────────────────────────────────────────
export interface BacktestRun {
  id: number; created_at: string; status: string; scope: string
  intervals: string[]; capital: number; total: number; done: number
  progress: number; note: string; window?: string; instruments?: string[]
  strategies?: string[]
}

export interface StrategyMeta { key: string; display_name: string; default_params: Record<string, any> }

export interface BTResult {
  id: number; run_id: number; instrument_key: string; name: string
  segment: string; strategy_key: string; interval: string; trades: number; wins: number
  win_rate: number; profit_factor: number | null; max_drawdown_pct: number
  return_pct: number; net_pnl: number; gross_pnl: number; charges: number
  expectancy: number; cagr: number | null; bars: number; from_cache?: boolean; error: string
  calmar: number | null; consistency: number | null; sharpe: number | null
  max_consec_losses: number; time_underwater_pct: number
  // fixed 1-lot sizing: notional = base capital (1-lot underlying); option_cost =
  // est. ATM option entry cost. affordable_* are budget-relative (payload layer).
  notional: number; lots: number; affordable: boolean
  option_cost?: number; budget?: number
  affordable_futures?: boolean; affordable_options?: boolean
  // tail risk (BT-8) + intra-trade pain (BT-4)
  worst_trade_pnl: number; worst_mae_pct: number
  // realised vs marked-to-last open (BT-5)
  open_at_end: boolean; win_rate_realised: number; return_pct_realised: number
  // benchmark (BT-6)
  bh_return_pct: number | null
  // true per-cell coverage (BT-3, DV-2)
  first_ts: number; last_ts: number; effective_days: number; clamped: boolean
}

export interface BTInstrument { key: string; name: string; segment: string; has_options: boolean }

export interface BTTradeDTO {
  direction: string; entry_time: number; entry_price: number; exit_time: number
  exit_price: number; qty: number; gross_pnl: number; charges: number
  net_pnl: number; return_pct: number; reason: string; bars_held: number; win: boolean
  mae_pct?: number; notional?: number; lots?: number
}

export interface SettingRow { key: string; type: 'bool' | 'int' | 'float' | 'str'; default: any; value: any }

export interface AnalyticsAgg { trades: number; wins: number; win_rate: number; net_pnl: number; charges?: number }
export interface AnalyticsSplit {
  intraday: AnalyticsAgg; overnight: AnalyticsAgg; overnight_gap_pnl: number
  reinforced_trades: number
  option_dataset: { rows: number; instruments: number; first_ts: string | null; last_ts: string | null }
  by_segment?: { options: AnalyticsAgg; equity_intraday: AnalyticsAgg }
}

export interface HomeInstrument {
  key: string; name: string; segment: string; has_options: boolean
  enabled: boolean; signal: string; trend: string | null
  z: number | null; close: number | null; position: PositionDTO | null
}
