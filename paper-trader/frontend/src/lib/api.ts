const j = (u: string) => fetch(u).then((r) => r.json())
const post = (u: string, body: any) =>
  fetch(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    .then((r) => r.json())

export const getStatus = () => j('/api/status')
export const getExecState = () => j('/api/execution/state')
export const armBot = (armed: boolean) => post('/api/execution/arm', { armed })
export const killBot = () => post('/api/execution/kill', {})
export const getInstruments = () => j('/api/instruments')
export const getSignals = () => j('/api/signals')
export const getPositions = (segment?: string) =>
  j(`/api/positions${segment ? `?segment=${segment}` : ''}`)
export const getProviderHealth = () => j('/api/provider-health')
export const setLiveInterval = (key: string, interval: string) =>
  post(`/api/instruments/${key}/interval`, { interval })
export const blockEntries = (key: string, blocked: boolean) =>
  post(`/api/instruments/${key}/block-entries`, { blocked })
// dual-segment / multi-strategy per-instrument controls (Phase 3)
export const getStrategies = () => j('/api/strategies')
export const setProduct = (key: string, product: string) =>
  post(`/api/instruments/${key}/product`, { product })
export const setPriorityFlag = (key: string, priority_flag: boolean) =>
  post(`/api/instruments/${key}/priority`, { priority_flag })
export const setInstrumentStrategy = (key: string, strategy_key: string | null) =>
  post(`/api/instruments/${key}/strategy`, { strategy_key })
export const closePosition = (key: string) => post(`/api/positions/${key}/close`, {})
export const setPositionSLTP = (
  key: string,
  body: { stop_price?: number; target_price?: number; stop_pct?: number; target_pct?: number },
) => post(`/api/positions/${key}/sltp`, body)
export const setNoTakeProfit = (key: string, enabled: boolean) =>
  post(`/api/positions/${key}/no-take-profit`, { enabled })
export const manualOpen = (key: string, direction: string) =>
  post('/api/positions/manual-open', { key, direction })
export const getSettings = () => j('/api/settings')
export const setSetting = (key: string, value: any) => post('/api/settings', { key, value })
export const resetSetting = (key: string) => post('/api/settings/reset', { key })
export const getAnalytics = (segment?: string) =>
  j(`/api/analytics${segment ? `?segment=${segment}` : ''}`)
export const getCandles = (key: string) => j(`/api/candles/${key}`)
export const getOptionCandles = (key: string) => j(`/api/option-candles/${key}`)
export const getOptionsCalc = (key: string) => j(`/api/options-calc/${key}`)
export const getDashboard = (segment?: string, strategy?: string) => {
  const q = new URLSearchParams()
  if (segment) q.set('segment', segment)
  if (strategy) q.set('strategy', strategy)
  const qs = q.toString()
  return j(`/api/dashboard${qs ? `?${qs}` : ''}`)
}
export const getAccountPnl = () => j('/api/account-pnl')
export const getTrades = (n = 1000) => j(`/api/trades?limit=${n}`)
export const getCalendar = (days = 120) => j(`/api/calendar?days=${days}`)
export const getLogs = (n = 300) => j(`/api/logs?limit=${n}`)

export const toggleInstrument = (key: string, enabled: boolean) =>
  post(`/api/instruments/${key}/toggle`, { enabled })

// ── customizable homepage / portfolio universe ──────────────────────────────
export const getHome = () => j('/api/portfolio/home')
export const addToPortfolio = (key: string, on_home = true, interval?: string) =>
  post('/api/portfolio/add', { key, on_home, interval })
export const removeFromPortfolio = (key: string) =>
  post('/api/portfolio/remove', { key, on_home: false })

// ── backtest sweep ──────────────────────────────────────────────────────────
export interface SweepOpts {
  instruments?: string[]; lookback_days?: number | null
  start_date?: string; end_date?: string; strategies?: string[]
}
export const startSweep = (scope: string, intervals: string[], capital = 50000,
  opts: SweepOpts = {}) =>
  post('/api/backtest/sweep', { scope, intervals, capital, ...opts })
export const getSweepInstruments = (scope = 'liquid') =>
  j(`/api/backtest/instruments?scope=${scope}`)
export const getSweepStatus = (runId?: number) =>
  j(`/api/backtest/status${runId ? `?run_id=${runId}` : ''}`)
export const getSweepRuns = () => j('/api/backtest/runs')
export const sweepExportUrl = (runId?: number) =>
  `/api/backtest/export${runId ? `?run_id=${runId}` : ''}`

export interface ResultFilters {
  run_id?: number; interval?: string; strategy?: string
  min_win_rate?: number; min_profit_factor?: number
  max_drawdown?: number; min_return?: number; min_trades?: number; sort?: string
}
export const getSweepResults = (f: ResultFilters = {}) => {
  const q = new URLSearchParams()
  Object.entries(f).forEach(([k, v]) => { if (v !== undefined && v !== '') q.set(k, String(v)) })
  return j(`/api/backtest/results?${q.toString()}`)
}
export const getSweepResult = (key: string, interval: string, runId?: number, strategy?: string) => {
  const q = new URLSearchParams()
  if (runId) q.set('run_id', String(runId))
  if (strategy) q.set('strategy', strategy)
  const qs = q.toString()
  return j(`/api/backtest/result/${key}/${interval}${qs ? `?${qs}` : ''}`)
}
