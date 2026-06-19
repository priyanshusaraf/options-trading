export interface Capital {
  initial: number; cash: number; invested: number;
  equity: number; realized_pnl: number; open_count: number
}

export interface PositionDTO {
  id: number; instrument_key: string; direction: string; option_type: string
  tradingsymbol: string; strike: number; expiry: string; lot_size: number; qty: number
  entry_premium: number; entry_cost: number; entry_time: string; entry_reason: string
  stop_price: number; target_price: number; last_premium: number; last_spot: number
  unrealized_pnl: number
}

export interface InstrState {
  instrument: string; name: string; segment: string; time: number
  close: number; ema: number; z: number; z_prev: number | null; slope: number; std: number
  trend: string; signal: string; long_exit: boolean; short_exit: boolean
  position: PositionDTO | null
}

export interface LiveState {
  tick: number; provider: string; time: string; enabled: string[]
  states: Record<string, InstrState>; capital: Capital
}

export interface LiveTick {
  time: string; spot: number | null; option_premium: number | null
  tradingsymbol: string | null
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
}

// ── backtest ────────────────────────────────────────────────────────────────
export interface BacktestRun {
  id: number; created_at: string; status: string; scope: string
  intervals: string[]; capital: number; total: number; done: number
  progress: number; note: string
}

export interface BTResult {
  id: number; run_id: number; instrument_key: string; name: string
  segment: string; interval: string; trades: number; wins: number
  win_rate: number; profit_factor: number | null; max_drawdown_pct: number
  return_pct: number; net_pnl: number; gross_pnl: number; charges: number
  expectancy: number; cagr: number | null; bars: number; error: string
}

export interface BTTradeDTO {
  direction: string; entry_time: number; entry_price: number; exit_time: number
  exit_price: number; qty: number; gross_pnl: number; charges: number
  net_pnl: number; return_pct: number; reason: string; bars_held: number; win: boolean
}

export interface HomeInstrument {
  key: string; name: string; segment: string; has_options: boolean
  enabled: boolean; signal: string; trend: string | null
  z: number | null; close: number | null; position: PositionDTO | null
}
