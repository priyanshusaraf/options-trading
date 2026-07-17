const TOKEN = import.meta.env.VITE_PT_TOKEN as string | undefined

const j = (u: string) =>
  fetch(u, { headers: TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {} }).then((r) => r.json())
const post = (u: string, body: any) =>
  fetch(u, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
    },
    body: JSON.stringify(body),
  }).then((r) => r.json())
const put = (u: string, body: any) =>
  fetch(u, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
    },
    body: JSON.stringify(body),
  }).then((r) => r.json())
export const del = (path: string) =>
  fetch(path, { method: 'DELETE' }).then((r) => {
    if (!r.ok) throw new Error(`${r.status}`)
    return r.json()
  })

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
export const setOvertradeFlag = (key: string, flag: boolean) =>
  post(`/api/instruments/${key}/overtrade`, { flag })
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
export const getDashboard = (segment?: string, strategy?: string, period?: string) => {
  const q = new URLSearchParams()
  if (segment) q.set('segment', segment)
  if (strategy) q.set('strategy', strategy)
  if (period && period !== 'all') q.set('period', period)
  const qs = q.toString()
  return j(`/api/dashboard${qs ? `?${qs}` : ''}`)
}
export const getInstrumentDetail = (key: string, segment?: string, strategy?: string, period?: string) => {
  const q = new URLSearchParams()
  if (segment) q.set('segment', segment)
  if (strategy) q.set('strategy', strategy)
  if (period && period !== 'all') q.set('period', period)
  const qs = q.toString()
  return j(`/api/instrument/${key}${qs ? `?${qs}` : ''}`)
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
export const addBulkToPortfolio = (items: Array<{
  key: string; interval?: string; strategy_key?: string | null; product?: string; on_home?: boolean
}>) => post('/api/portfolio/add-bulk', { items })

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

// ── Portfolio: promotions (approve→deploy), watchlists, strategy archive ──────
export interface Promotion {
  id: number; run_id: number; status: string
  strategy_key: string; interval: string; params: Record<string, any>
  qualified_universe: string[]
  validated_universe: { instrument: string; dsr: number; scorecard?: any }[]
  best?: { instrument: string; dsr: number } | null
  generated: boolean
  composition?: any | null
  generated_source?: string | null
  explanation: {
    strategy_key: string; display_name: string; thesis: string
    primitives: string[]; rules: string[]; caveats: string; note?: string
  }
  created_at?: string | null
}
export interface Watchlist {
  id: number; name: string; strategy_key: string; status: string
  interval: string | null; instruments: string[]
}
export interface ArchiveStrategy {
  strategy_key: string; status: string; source: string
  deployed_watchlist_id: number | null; last_dsr: number | null; note: string
}

export const getPromotions = (): Promise<{ promotions: Promotion[] }> =>
  j('/api/portfolio/promotions')
export const deployPromotion = (
  id: number, body: { watchlist_name?: string; dry_run?: boolean } = {},
) => post(`/api/portfolio/promotions/${id}/deploy`, body)
export const getWatchlists = (): Promise<{ watchlists: Watchlist[] }> =>
  j('/api/portfolio/watchlists')
export const getArchive = (): Promise<{ strategies: ArchiveStrategy[] }> =>
  j('/api/portfolio/archive')
export const setWatchlistStatus = (name: string, status: string) =>
  post(`/api/portfolio/watchlists/${encodeURIComponent(name)}/status`, { status })
export const setArchiveStatus = (strategyKey: string, status: string) =>
  post(`/api/portfolio/archive/${encodeURIComponent(strategyKey)}/status`, { status })

// ── Trade journal (backend/app/journal — isolated from the engine) ─────────
export const getJournalInstruments = () => j('/api/journal/instruments')
export const getJournalTrades = (openOnly?: boolean) =>
  j(`/api/journal/trades${openOnly ? '?open_only=true' : ''}`)
export const getJournalOpenTradesMtm = () => j('/api/journal/trades/open-mtm')
export const addJournalTrade = (body: {
  symbol: string; direction: 'LONG' | 'SHORT'; lots: number; entry_price: number
  setup_tag?: string; notes?: string; view_id?: number
}) => post('/api/journal/trades', body)
export const closeJournalTrade = (
  id: number,
  body: { exit_price: number; manual_net_pnl?: number },
) => post(`/api/journal/trades/${id}/close`, body)
export const addJournalMissed = (body: {
  symbol: string; direction: 'LONG' | 'SHORT'; skip_reason: string
  setup_tag?: string; hypothetical_entry?: number; hypothetical_exit?: number
}) => post('/api/journal/missed', body)
export const getJournalMissed = () => j('/api/journal/missed')
export const getJournalStats = () => j('/api/journal/stats')
export const getJournalViews = () => j('/api/journal/views')
export const addJournalView = (body: { name: string; thesis?: string }) =>
  post('/api/journal/views', body)
export const getJournalFeed = (limit = 60): Promise<import('./types').JournalFeedDTO> =>
  j(`/api/journal/feed?limit=${limit}`)
export const upsertJournalDay = (body: { entry_date: string; market_view?: string; result?: string }) =>
  post('/api/journal/days', body)
export const addJournalNote = (body: { body: string; instrument_symbol?: string }) =>
  post('/api/journal/notes', body)
export const deleteJournalNote = (id: number) => del(`/api/journal/notes/${id}`)
export const getJournalBias = () => j('/api/journal/bias')
export const putJournalBias = (horizon: string, body: { stance?: string; note?: string }) =>
  put(`/api/journal/bias/${encodeURIComponent(horizon)}`, body)
