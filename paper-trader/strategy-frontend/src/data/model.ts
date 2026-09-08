export type HealthState =
  | 'healthy'
  | 'stale'
  | 'degraded'
  | 'provider-limited'
  | 'execution-degraded'
  | 'protection-degraded'
  | 'suspended'
  | 'recovering'

export type Mode = 'research-only' | 'signal-only' | 'paper' | 'live'

export type VersionState = 'draft' | 'tested' | 'validated' | 'approved' | 'deployed'

export type Role =
  | 'SELF'
  | 'BENCHMARK'
  | 'HEDGE'
  | 'SIGNAL_MARKET'
  | 'UNDERLYING'
  | 'EXECUTION_MARKET'
  | 'PEER_A'
  | 'PEER_B'

export type NodeKind = 'data' | 'indicator' | 'logic' | 'risk' | 'execution' | 'options' | 'state'

export interface GNode {
  id: string
  x: number
  y: number
  w?: number
  title: string
  kind: NodeKind
  sub?: string
  fields?: [string, string][]
  badge?: string
}

export interface GEdge {
  from: string
  to: string
  kind?: 'data' | 'signal' | 'order'
  label?: string
}

export interface Version {
  id: string
  state: VersionState
  changedAt: string
  summary: string
  drift?: string[]
}

export interface Trade {
  id: string
  side: 'LONG' | 'SHORT'
  instrument: string
  entryAt: string
  exitAt: string
  entryPx: number
  exitPx: number
  qty: number
  pnl: number
  pnlPct: number
  mae: number
  mfe: number
  holdMins: number
  entryWhy: string
  exitWhy: string
}

export interface Costs {
  brokerage: number
  stt: number
  slippage: number
  other: number
}

export interface Backtest {
  id: string
  label: string
  versionId: string
  period: string
  bar: string
  capital: number
  netPct: number
  grossPct: number
  costPct: number
  maxDD: number
  sharpe: number
  trades: number
  winRate: number
  profitFactor: number
  avgHoldMins: number
  oosPct: number
  longTrades: number
  shortTrades: number
  equity: number[]
  monthly: number[]
  costs: Costs
  tradesSample: Trade[]
}

export interface BiasCheck {
  name: string
  verdict: 'pass' | 'warn' | 'fail'
  note: string
}

export interface SweepRun {
  id: string
  type: 'sweep'
  title: string
  status: 'completed' | 'running' | 'failed'
  xLabel: string
  yLabel: string
  zLabel: string
  xs: number[]
  ys: number[]
  grid: number[][]
  best: { x: number; y: number; z: number }
  current: { x: number; y: number }
  findings: string[]
  biasChecks: BiasCheck[]
}

export interface WalkForwardRun {
  id: string
  type: 'walkforward'
  title: string
  status: 'completed' | 'running' | 'failed'
  folds: {
    label: string
    isSharpe: number
    oosSharpe: number
    isReturn: number
    oosReturn: number
    oosTrades: number
  }[]
  findings: string[]
}

export interface MonteCarloRun {
  id: string
  type: 'montecarlo'
  title: string
  status: 'completed' | 'running' | 'failed'
  paths: number
  horizonDays: number
  p5: number[]
  p50: number[]
  p95: number[]
  medianFinal: number
  p5Final: number
  ruinProb: number
  findings: string[]
}

export interface ComparisonRow {
  name: string
  netPct: number
  maxDD: number
  sharpe: number
  trades: number
  verdict: 'keep' | 'review' | 'reject'
}

export interface ComparisonRun {
  id: string
  type: 'comparison'
  title: string
  status: 'completed' | 'running' | 'failed'
  rows: ComparisonRow[]
  findings: string[]
}

export type ResearchRun = SweepRun | WalkForwardRun | MonteCarloRun | ComparisonRun

export interface Hypothesis {
  text: string
  status: 'open' | 'supported' | 'rejected' | 'dormant'
}

export interface ResearchProgram {
  conclusion: string
  updated: string
  hypotheses: Hypothesis[]
  runs: ResearchRun[]
}

export type RefusalCode =
  | 'ADMISSION_REQUIRED'
  | 'ARTEFACT_MISMATCH'
  | 'RECEIPT_STALE'
  | 'CAPABILITY_MISSING'
  | 'INSTRUMENT_UNRESOLVED'
  | 'RISK_INVALID'

export interface Blocker {
  code: RefusalCode
  severity: 'blocker' | 'warning'
  human: string
  detail: string
}

export interface Deployment {
  id: string
  strategyId: string
  strategyName: string
  versionId: string
  mode: Mode
  provider: string
  broker: string
  account: string
  capital: number
  schedule: string
  health: HealthState
  armed: boolean
  lifecycle: 'staged' | 'paper_active' | 'paused' | 'retired'
  bindings: { role: Role; instrument: string }[]
  blockers: Blocker[]
  dayPnl: number
  note?: string
}

export interface Position {
  id: string
  deploymentId: string
  strategyName: string
  versionId: string
  instrument: string
  side: 'LONG' | 'SHORT'
  qty: number
  avgPx: number
  ltp: number
  unrealized: number
  realizedToday: number
  greeks?: { delta: number; theta: number; vega: number }
  protection: string
  openedAt: string
}

export interface OrderRecord {
  id: string
  ts: string
  deploymentId: string
  strategyName: string
  instrument: string
  side: 'BUY' | 'SELL'
  type: 'MARKET' | 'LIMIT' | 'SL-M' | 'SL'
  qty: number
  status: 'FILLED' | 'OPEN' | 'REJECTED' | 'CANCELLED'
  px?: number
  note?: string
}

export interface Connection {
  id: string
  provider: string
  roles: ('market-data' | 'execution' | 'account' | 'instrument-resolution')[]
  auth: 'connected' | 'expiring' | 'error'
  health: HealthState
  latencyMs: number
  lastTick: string
  capabilities: string[]
  accounts: string[]
  note: string
}

export interface ActivityEvent {
  id: string
  ts: string
  channel: 'research' | 'validation' | 'deployment' | 'execution' | 'risk' | 'provider' | 'config'
  severity: 'info' | 'warn' | 'critical'
  title: string
  detail: string
  provenance?: string[]
}

export interface Strategy {
  id: string
  name: string
  code: string
  tagline: string
  thesis: string
  instruments: string[]
  roles: { role: Role; instrument: string }[]
  watchlist: string[]
  versions: Version[]
  draftId: string
  testedId?: string
  validatedId?: string
  deployedId?: string
  overview: {
    what: string
    how: string
    marketsResearched: string[]
    validationHealth: number
    attention: { tone: 'info' | 'warn' | 'bad' | 'good'; text: string }[]
  }
  graph: { nodes: GNode[]; edges: GEdge[] }
  backtests: Backtest[]
  research: ResearchProgram
}

export interface PortfolioSummary {
  equity: number
  equityCurve: number[]
  dayPnl: number
  dayPct: number
  openRisk: number
  capitalDeployed: number
  capitalTotal: number
  gross: number
  chargesToday: number
}
