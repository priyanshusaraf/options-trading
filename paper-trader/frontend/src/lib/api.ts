const j = (u: string) => fetch(u).then((r) => r.json())
const post = (u: string, body: any) =>
  fetch(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    .then((r) => r.json())

export const getStatus = () => j('/api/status')
export const getInstruments = () => j('/api/instruments')
export const getCandles = (key: string) => j(`/api/candles/${key}`)
export const getOptionCandles = (key: string) => j(`/api/option-candles/${key}`)
export const getOptionsCalc = (key: string) => j(`/api/options-calc/${key}`)
export const getDashboard = () => j('/api/dashboard')
export const getLogs = (n = 300) => j(`/api/logs?limit=${n}`)

export const toggleInstrument = (key: string, enabled: boolean) =>
  post(`/api/instruments/${key}/toggle`, { enabled })

// ── customizable homepage / portfolio universe ──────────────────────────────
export const getHome = () => j('/api/portfolio/home')
export const addToPortfolio = (key: string, on_home = true) =>
  post('/api/portfolio/add', { key, on_home })
export const removeFromPortfolio = (key: string) =>
  post('/api/portfolio/remove', { key, on_home: false })

// ── backtest sweep ──────────────────────────────────────────────────────────
export const startSweep = (scope: string, intervals: string[], capital = 50000) =>
  post('/api/backtest/sweep', { scope, intervals, capital })
export const getSweepStatus = (runId?: number) =>
  j(`/api/backtest/status${runId ? `?run_id=${runId}` : ''}`)

export interface ResultFilters {
  run_id?: number; interval?: string; min_win_rate?: number; min_profit_factor?: number
  max_drawdown?: number; min_return?: number; min_trades?: number; sort?: string
}
export const getSweepResults = (f: ResultFilters = {}) => {
  const q = new URLSearchParams()
  Object.entries(f).forEach(([k, v]) => { if (v !== undefined && v !== '') q.set(k, String(v)) })
  return j(`/api/backtest/results?${q.toString()}`)
}
export const getSweepResult = (key: string, interval: string, runId?: number) =>
  j(`/api/backtest/result/${key}/${interval}${runId ? `?run_id=${runId}` : ''}`)
