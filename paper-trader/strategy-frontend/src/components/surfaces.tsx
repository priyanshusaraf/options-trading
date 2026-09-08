/* oxlint-disable react/only-export-components -- surface registry and routed views are one design-system module */
import { lazy, Suspense, useState, type ReactNode } from 'react'
import {
  Activity, AlertTriangle, ArrowRight, ArrowUpRight, BarChart3, Bell,
  BookOpenCheck, Boxes, CalendarClock, Check, CheckCircle2, ChevronRight, CircleDot,
  Columns3, Copy, Eye, FlaskConical, GitBranch, GripVertical, History,
  LayoutDashboard, Layers3, ListFilter, LockKeyhole, Maximize2, MonitorDot,
  PanelRightOpen, Play, PlugZap, Plus, Radio, ReceiptText, Rocket, Search, Settings2,
  ShieldCheck, Smartphone, Sparkles, SquareArrowOutUpRight, TableProperties, Target,
  WalletCards, Workflow, X, Zap,
} from 'lucide-react'
import type { DirectionId } from '../data/directions'
import {
  activity, comparisonRows, connections, deployments, orders, portfolio, positions,
  primaryStrategy, strategies, workspaceWidgets, type WorkspaceWidget,
} from '../data/fixtures'
import type { Deployment, ResearchRun, Strategy, Trade } from '../data/model'
import { fmtINR, fmtINRShort, fmtNum, fmtPct } from '../data/utils'
import { EquityChart, Heatmap, MiniBars, MonteCarloChart, Sparkline } from './charts'
import {
  Badge, Button, Disclosure, EmptyState, IconButton, KeyValue, Metric, Notice, Panel,
  PanelHeader, Progress, Segmented, Table, cx, type Tone,
} from './ui'

export type SurfaceId =
  | 'home' | 'strategies' | 'overview' | 'build' | 'backtest' | 'research'
  | 'deploy' | 'live' | 'portfolio' | 'workspace' | 'connections' | 'mobile'
  | 'activity' | 'settings'

export const surfaceMeta: Record<SurfaceId, { label: string; short: string; icon: typeof Activity; group: 'global' | 'strategy' | 'operate' | 'system' }> = {
  home: { label: 'Home', short: 'Home', icon: LayoutDashboard, group: 'global' },
  strategies: { label: 'Strategies', short: 'Strategies', icon: Layers3, group: 'global' },
  overview: { label: 'Strategy overview', short: 'Overview', icon: BookOpenCheck, group: 'strategy' },
  build: { label: 'Build · node graph', short: 'Build', icon: Workflow, group: 'strategy' },
  backtest: { label: 'Backtest', short: 'Backtest', icon: BarChart3, group: 'strategy' },
  research: { label: 'Research · validate', short: 'Validate', icon: FlaskConical, group: 'strategy' },
  deploy: { label: 'Deploy · preflight', short: 'Deploy', icon: Rocket, group: 'strategy' },
  live: { label: 'Live · execution', short: 'Live', icon: Radio, group: 'operate' },
  portfolio: { label: 'Portfolio', short: 'Portfolio', icon: WalletCards, group: 'operate' },
  workspace: { label: 'Workspace editor', short: 'Workspace', icon: Columns3, group: 'global' },
  connections: { label: 'Connections', short: 'Connections', icon: PlugZap, group: 'system' },
  mobile: { label: 'Mobile companion', short: 'Mobile', icon: Smartphone, group: 'system' },
  activity: { label: 'Activity', short: 'Activity', icon: Activity, group: 'global' },
  settings: { label: 'Settings', short: 'Settings', icon: Settings2, group: 'system' },
}

export const strategyStageIds: SurfaceId[] = ['overview', 'build', 'backtest', 'research', 'deploy', 'live']
export const allSurfaceIds = Object.keys(surfaceMeta) as SurfaceId[]

const NodeBuilder = lazy(() => import('./graph').then((module) => ({ default: module.NodeBuilder })))

export interface SurfaceProps {
  direction: DirectionId
  strategy: Strategy
  onStrategyChange: (strategy: Strategy) => void
  onNavigate: (surface: SurfaceId) => void
  openEvidence?: () => void
}

function toneForHealth(health: string): Tone {
  if (health === 'healthy') return 'good'
  if (health === 'stale' || health.includes('degraded')) return 'warn'
  if (health === 'suspended') return 'bad'
  return 'info'
}

function toneForState(state: string): Tone {
  if (state === 'validated' || state === 'approved') return 'good'
  if (state === 'deployed') return 'info'
  if (state === 'draft') return 'warn'
  return 'violet'
}

function SurfaceHeading({ eyebrow, title, copy, actions }: { eyebrow: string; title: string; copy: string; actions?: ReactNode }) {
  return (
    <header className="surface-heading">
      <div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{copy}</p></div>
      {actions ? <div className="surface-heading__actions">{actions}</div> : null}
    </header>
  )
}

function LifecycleMini({ strategy, current, onNavigate }: { strategy: Strategy; current?: SurfaceId; onNavigate: (surface: SurfaceId) => void }) {
  const facts = [
    ['Build', strategy.draftId, 'build'], ['Backtest', strategy.testedId ?? 'Not run', 'backtest'],
    ['Validate', strategy.validatedId ?? 'Not admitted', 'research'], ['Deploy', strategy.deployedId ?? 'None', 'deploy'],
  ] as const
  return (
    <div className="lifecycle-mini">
      {facts.map(([label, value, surface], index) => (
        <button key={label} type="button" onClick={() => onNavigate(surface)} className={cx('lifecycle-mini__step', current === surface && 'is-current')}>
          <span>{String(index + 1).padStart(2, '0')}</span><div><strong>{label}</strong><small>{value}</small></div><ChevronRight size={14} />
        </button>
      ))}
    </div>
  )
}

function StatusStrip() {
  return (
    <div className="status-strip">
      <span><i className="status-dot status-dot--warn" />NSE receipt stale · 38s</span>
      <span><i className="status-dot status-dot--good" />Paper adapter healthy</span>
      <span>21 Aug 2026 · 14:09 IST</span>
      <Badge tone="violet">STATIC FIXTURE</Badge>
    </div>
  )
}

export function HomeSurface({ strategy, onNavigate }: SurfaceProps) {
  return (
    <div className="surface surface-home">
      <SurfaceHeading eyebrow="Today · Friday, 21 August" title="Good afternoon, Priyanshu" copy="Research, paper operations and portfolio risk in one verified view." actions={<><Badge tone="warn" dot>1 attention item</Badge><Button onClick={() => onNavigate('build')} variant="primary"><Plus size={14} /> New strategy</Button></>} />
      <StatusStrip />
      <div className="metric-grid metric-grid--four">
        <Metric label="Portfolio equity" value={fmtINRShort(portfolio.equity)} sub={`${fmtPct(portfolio.dayPct)} today`} tone="good" />
        <Metric label="Open paper risk" value={fmtINRShort(portfolio.openRisk)} sub="1.74% of capital" />
        <Metric label="Active deployments" value="2" sub="1 paper · 1 signal" tone="info" />
        <Metric label="Evidence due" value="3" sub="1 rejection required" tone="warn" />
      </div>
      <div className="home-grid">
        <Panel className="home-grid__strategy">
          <PanelHeader eyebrow="Resume work" title={strategy.name} action={<Button onClick={() => onNavigate('overview')}>Open strategy <ArrowRight size={14} /></Button>} />
          <div className="strategy-resume">
            <div><Badge tone="warn">Draft {strategy.draftId}</Badge><h2>{strategy.tagline}</h2><p>{strategy.thesis}</p></div>
            <div className="strategy-resume__chart"><Sparkline values={strategy.backtests[0].equity.slice(-70)} height={96} /><div><strong>{fmtPct(strategy.backtests[0].netPct)}</strong><span>net backtest</span></div></div>
          </div>
          <LifecycleMini strategy={strategy} onNavigate={onNavigate} />
        </Panel>
        <Panel className="home-grid__risk">
          <PanelHeader eyebrow="Operating state" title="Entry admission gated" action={<Badge tone="warn" dot>Degraded</Badge>} />
          <Notice tone="warn" title="Fresh data required">New paper entries are gated. Risk-reducing exits stay available.</Notice>
          <div className="compact-kvs"><KeyValue label="Affected deployment" value="DEP-PAPER-042" mono /><KeyValue label="Current position" value="+25 NIFTY AUG FUT" /><KeyValue label="Protection" value="24,792.0 · active" /></div>
          <Button onClick={() => onNavigate('live')}>Open paper cockpit <PanelRightOpen size={14} /></Button>
        </Panel>
        <Panel className="home-grid__curve">
          <PanelHeader eyebrow="Portfolio" title="Equity and risk budget" action={<Button variant="ghost" onClick={() => onNavigate('portfolio')}>Full portfolio <ArrowRight size={14} /></Button>} />
          <EquityChart values={portfolio.equityCurve} height={170} />
        </Panel>
        <Panel className="home-grid__activity">
          <PanelHeader eyebrow="Causal record" title="Latest activity" action={<IconButton label="Open activity" onClick={() => onNavigate('activity')}><ArrowRight size={15} /></IconButton>} />
          <div className="event-list event-list--compact">{activity.slice(0, 5).map((event) => <div className="event-row" key={event.id}><i className={cx('event-mark', `event-mark--${event.severity}`)} /><time>{event.ts}</time><div><strong>{event.title}</strong><small>{event.channel} · {event.provenance?.join(' · ')}</small></div></div>)}</div>
        </Panel>
      </div>
    </div>
  )
}

export function StrategiesSurface({ strategy, onStrategyChange, onNavigate }: SurfaceProps) {
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<'all' | 'draft' | 'deployed'>('all')
  const visible = strategies.filter((item) => {
    const queryMatch = `${item.name} ${item.code}`.toLowerCase().includes(query.toLowerCase())
    const stateMatch = filter === 'all' || (filter === 'draft' ? Boolean(item.draftId) : Boolean(item.deployedId))
    return queryMatch && stateMatch
  })
  return (
    <div className="surface">
      <SurfaceHeading eyebrow="Strategy registry" title="Strategies" copy="Definitions, evidence maturity and deployment facts remain distinct." actions={<Button variant="primary" onClick={() => onNavigate('build')}><Plus size={14} /> Create strategy</Button>} />
      <div className="filter-row"><label className="input-shell input-shell--wide"><Search size={14} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search name, code or instrument" /></label><Segmented value={filter} onChange={setFilter} ariaLabel="Strategy filter" items={[{ value: 'all', label: 'All' }, { value: 'draft', label: 'With draft' }, { value: 'deployed', label: 'Deployed' }]} /><span className="result-count">{visible.length} objects</span></div>
      <div className="strategy-list">
        {visible.map((item) => {
          const latest = item.versions[0]
          const isSelected = item.id === strategy.id
          return (
            <button type="button" className={cx('strategy-row', isSelected && 'is-selected')} key={item.id} onClick={() => { onStrategyChange(item); onNavigate('overview') }}>
              <span className="strategy-row__monogram">{item.name.split(' ').slice(0, 2).map((word) => word[0]).join('')}</span>
              <span className="strategy-row__main"><span><strong>{item.name}</strong><Badge tone={toneForState(latest.state)}>{latest.state}</Badge></span><small>{item.code} · {item.tagline}</small></span>
              <span className="strategy-row__fact"><small>Draft</small><strong>{item.draftId}</strong></span>
              <span className="strategy-row__fact"><small>Validated</small><strong>{item.validatedId ?? 'None'}</strong></span>
              <span className="strategy-row__fact"><small>Deployed</small><strong>{item.deployedId ?? 'None'}</strong></span>
              <span className="strategy-row__health"><Progress value={item.overview.validationHealth} /><small>{item.overview.validationHealth}% evidence health</small></span>
              <ChevronRight size={16} />
            </button>
          )
        })}
      </div>
      <Panel className="registry-footnote"><ShieldCheck size={20} /><div><strong>One immutable strategy definition, several projections</strong><p>Form, graph, tree and code views address the same draft identity. A deployment binds a separately validated version to instruments and a mode.</p></div></Panel>
    </div>
  )
}

export function OverviewSurface({ strategy, onNavigate, openEvidence }: SurfaceProps) {
  return (
    <div className="surface">
      <SurfaceHeading eyebrow={`${strategy.code} · strategy object`} title={strategy.name} copy={strategy.tagline} actions={<><Button onClick={openEvidence}><ReceiptText size={14} /> Evidence</Button><Button variant="primary" onClick={() => onNavigate('build')}>Open builder <Workflow size={14} /></Button></>} />
      <div className="object-factbar"><Badge tone="warn">Draft {strategy.draftId}</Badge><Badge tone="good">Validated {strategy.validatedId ?? 'None'}</Badge><Badge tone="info">Deployed {strategy.deployedId ?? 'None'}</Badge><span>These IDs may differ by design.</span></div>
      <LifecycleMini strategy={strategy} current="overview" onNavigate={onNavigate} />
      <div className="overview-grid">
        <Panel className="overview-grid__thesis"><PanelHeader eyebrow="Strategy thesis" title="What it claims" /><blockquote>{strategy.thesis}</blockquote><div className="overview-copy"><div><span className="label">What</span><p>{strategy.overview.what}</p></div><div><span className="label">How</span><p>{strategy.overview.how}</p></div></div></Panel>
        <Panel><PanelHeader eyebrow="Evidence" title="Validation health" action={<strong className="score-big">{strategy.overview.validationHealth}</strong>} /><Progress value={strategy.overview.validationHealth} label="Evidence completeness" /><div className="compact-kvs"><KeyValue label="Backtest runs" value={strategy.backtests.length} /><KeyValue label="Research runs" value={strategy.research.runs.length} /><KeyValue label="Latest conclusion" value="20 Aug · reviewed" /></div><Button onClick={() => onNavigate('research')}>Review evidence <ArrowRight size={14} /></Button></Panel>
        <Panel className="overview-grid__attention"><PanelHeader eyebrow="Needs attention" title="Current facts" />{strategy.overview.attention.map((item) => <Notice key={item.text} tone={item.tone} title={item.tone === 'bad' ? 'Blocked' : item.tone === 'warn' ? 'Review required' : item.tone === 'good' ? 'Verified' : 'Context'}>{item.text}</Notice>)}</Panel>
        <Panel><PanelHeader eyebrow="Instrument roles" title="Instrument semantics" />{strategy.roles.map(({ role, instrument }) => <div className="role-row" key={role}><Badge tone="neutral">{role}</Badge><span>{instrument}</span></div>)}<p className="panel-note">Strategy OS owns role meaning. A provider supplies data; an execution broker is a separate binding.</p></Panel>
        <Panel className="overview-grid__versions"><PanelHeader eyebrow="Lineage" title="Version history" action={<Button variant="ghost"><History size={14} /> Compare</Button>} /><div className="version-list">{strategy.versions.map((version) => <div key={version.id}><i className={cx('version-dot', `version-dot--${version.state}`)} /><div><strong>{version.id}</strong><p>{version.summary}</p><small>{version.changedAt}</small></div><Badge tone={toneForState(version.state)}>{version.state}</Badge></div>)}</div></Panel>
      </div>
    </div>
  )
}

export function BuildSurface({ strategy }: SurfaceProps) {
  return (
    <div className="surface surface-build">
      <SurfaceHeading eyebrow={`${strategy.code} · ${strategy.draftId}`} title="Build the strategy" copy="Compose one typed definition through graph, form, tree or read-only code projections." actions={<><Button><GitBranch size={14} /> Compare v1.8.0</Button><Button variant="primary">Save draft</Button></>} />
      <Suspense fallback={<div className="builder-loading"><Workflow size={20} /><span>Loading visual builder…</span></div>}><NodeBuilder strategy={strategy} /></Suspense>
    </div>
  )
}

type BacktestTab = 'summary' | 'trades' | 'costs' | 'explain'

function TradeExplainer({ trade }: { trade: Trade }) {
  return (
    <div className="trade-explainer">
      <div className="trade-explainer__path"><span><CircleDot size={14} />09:15 Session opens</span><i /><span><CheckCircle2 size={14} />09:30 Range complete</span><i /><span><Zap size={14} />{trade.entryAt.split('·')[1]} Entry</span><i /><span><Target size={14} />{trade.exitAt.split('·')[1]} Exit</span></div>
      <div className="trade-explainer__grid"><div><span className="label">Entry reason</span><p>{trade.entryWhy}</p></div><div><span className="label">Exit reason</span><p>{trade.exitWhy}</p></div><Metric label="Result" value={fmtINR(trade.pnl)} sub={fmtPct(trade.pnlPct)} tone={trade.pnl >= 0 ? 'good' : 'bad'} compact /><Metric label="Excursion" value={`${fmtPct(trade.mae)} / ${fmtPct(trade.mfe)}`} sub="MAE / MFE" compact /></div>
      <Notice tone="info" title="Causal explanation">Every decision shown here was evaluated on completed bars from the selected backtest artefact.</Notice>
    </div>
  )
}

export function BacktestSurface({ strategy }: SurfaceProps) {
  const [tab, setTab] = useState<BacktestTab>('summary')
  const [selectedRun, setSelectedRun] = useState(strategy.backtests[0]?.id)
  const [selectedTrade, setSelectedTrade] = useState(strategy.backtests[0]?.tradesSample[0]?.id)
  const run = strategy.backtests.find((item) => item.id === selectedRun) ?? strategy.backtests[0]
  const trade = run?.tradesSample.find((item) => item.id === selectedTrade) ?? run?.tradesSample[0]
  if (!run) return <EmptyState title="No backtest artefact">Create a research run from the current draft.</EmptyState>
  return (
    <div className="surface">
      <SurfaceHeading eyebrow={`${strategy.code} · deterministic replay`} title="Backtest results" copy="Net-of-charges outcomes, trade causality and version lineage." actions={<><select aria-label="Backtest run" value={run.id} onChange={(e) => setSelectedRun(e.target.value)}>{strategy.backtests.map((item) => <option key={item.id} value={item.id}>{item.id} · {item.versionId}</option>)}</select><Button variant="primary"><Play size={14} /> Run draft</Button></>} />
      <div className="artefact-strip"><span><Badge tone="good">Completed</Badge>{run.id}</span><span>Version <b>{run.versionId}</b></span><span>{run.period}</span><span>{run.bar}</span><span>Capital {fmtINRShort(run.capital)}</span></div>
      <div className="metric-grid metric-grid--six"><Metric label="Net return" value={fmtPct(run.netPct)} tone="good" sub={`Gross ${fmtPct(run.grossPct)}`} /><Metric label="Max drawdown" value={fmtPct(run.maxDD)} tone="warn" /><Metric label="Sharpe" value={fmtNum(run.sharpe)} /><Metric label="Trades" value={run.trades.toLocaleString('en-IN')} /><Metric label="Win rate" value={fmtPct(run.winRate, 1, false)} /><Metric label="Profit factor" value={fmtNum(run.profitFactor)} /></div>
      <Panel className="backtest-main"><div className="backtest-main__head"><Segmented value={tab} onChange={setTab} ariaLabel="Backtest detail" items={[{ value: 'summary', label: 'Performance' }, { value: 'trades', label: 'Trades' }, { value: 'costs', label: 'Costs' }, { value: 'explain', label: 'Explain trade' }]} /><div><Badge tone="violet">OOS {run.oosPct}%</Badge><Button variant="ghost"><Maximize2 size={14} /> Expand</Button></div></div>
        {tab === 'summary' ? <div className="backtest-summary"><EquityChart values={run.equity} benchmark={strategy.backtests[1]?.equity} height={250} /><aside><span className="label">Monthly net returns</span><MiniBars values={run.monthly} labels={run.monthly.map((_, index) => `M${index + 1}`)} /><div className="compact-kvs"><KeyValue label="Long / short" value={`${run.longTrades} / ${run.shortTrades}`} /><KeyValue label="Avg hold" value={`${run.avgHoldMins} min`} /><KeyValue label="Charges" value={fmtINR(run.costs.brokerage + run.costs.stt + run.costs.slippage + run.costs.other)} /></div></aside></div> : null}
        {tab === 'trades' ? <Table compact><thead><tr><th>Trade</th><th>Side</th><th>Instrument</th><th>Entry</th><th>Hold</th><th>MAE</th><th>MFE</th><th className="right">Net P&amp;L</th></tr></thead><tbody>{run.tradesSample.map((item) => <tr key={item.id} onClick={() => { setSelectedTrade(item.id); setTab('explain') }}><td className="mono linkish">{item.id}</td><td><Badge tone={item.side === 'LONG' ? 'good' : 'info'}>{item.side}</Badge></td><td>{item.instrument}</td><td>{item.entryAt}</td><td>{item.holdMins}m</td><td className="negative">{fmtPct(item.mae)}</td><td className="positive">{fmtPct(item.mfe)}</td><td className={cx('right', item.pnl >= 0 ? 'positive' : 'negative')}>{fmtINR(item.pnl)}</td></tr>)}</tbody></Table> : null}
        {tab === 'costs' ? <div className="cost-grid">{Object.entries(run.costs).map(([key, value]) => <Metric key={key} label={key} value={fmtINR(value)} compact />)}<Panel><PanelHeader title="Net reconciliation" eyebrow="Required" compact /><KeyValue label="Gross return" value={fmtPct(run.grossPct)} /><KeyValue label="All charges" value={fmtPct(-run.costPct)} /><KeyValue label="Net return" value={fmtPct(run.netPct)} /></Panel></div> : null}
        {tab === 'explain' && trade ? <><div className="trade-picker">{run.tradesSample.map((item) => <button type="button" key={item.id} className={cx(item.id === trade.id && 'is-active')} onClick={() => setSelectedTrade(item.id)}>{item.id}<span className={item.pnl >= 0 ? 'positive' : 'negative'}>{fmtINR(item.pnl)}</span></button>)}</div><TradeExplainer trade={trade} /></> : null}
      </Panel>
    </div>
  )
}

function RunCard({ run, selected, onClick }: { run: ResearchRun; selected: boolean; onClick: () => void }) {
  const Icon = run.type === 'sweep' ? TableProperties : run.type === 'walkforward' ? CalendarClock : run.type === 'montecarlo' ? Sparkles : Columns3
  return <button type="button" className={cx('run-card', selected && 'is-selected')} onClick={onClick}><Icon size={17} /><span><strong>{run.title}</strong><small>{run.id} · {run.type}</small></span><Badge tone={run.status === 'completed' ? 'good' : 'warn'} dot>{run.status}</Badge><ChevronRight size={14} /></button>
}

export function ResearchSurface({ strategy, openEvidence }: SurfaceProps) {
  const [runId, setRunId] = useState(strategy.research.runs[0]?.id)
  const [view, setView] = useState<'visual' | 'findings' | 'bias'>('visual')
  const run = strategy.research.runs.find((item) => item.id === runId) ?? strategy.research.runs[0]
  return (
    <div className="surface surface-research">
      <SurfaceHeading eyebrow={`${strategy.code} · research programme`} title="Reject weak claims before admission" copy={strategy.research.conclusion} actions={<><Button onClick={openEvidence}><ReceiptText size={14} /> Evidence lineage</Button><Button variant="primary"><Plus size={14} /> New experiment</Button></>} />
      <div className="research-layout">
        <Panel className="research-sidebar"><PanelHeader title="Experiments" eyebrow="4 completed" compact action={<IconButton label="Filter experiments"><ListFilter size={14} /></IconButton>} /><div className="run-list">{strategy.research.runs.map((item) => <RunCard key={item.id} run={item} selected={run?.id === item.id} onClick={() => { setRunId(item.id); setView('visual') }} />)}</div><div className="hypothesis-list"><span className="label">Hypotheses</span>{strategy.research.hypotheses.map((item) => <div key={item.text}><Badge tone={item.status === 'supported' ? 'good' : item.status === 'rejected' ? 'bad' : 'neutral'}>{item.status}</Badge><p>{item.text}</p></div>)}</div></Panel>
        <Panel className="research-result"><div className="research-result__head"><div><div className="eyebrow">{run?.id} · {run?.type}</div><h2>{run?.title}</h2></div><Segmented value={view} onChange={setView} ariaLabel="Research view" items={[{ value: 'visual', label: 'Visual' }, { value: 'findings', label: 'Findings' }, { value: 'bias', label: 'Bias checks' }]} /></div>
          {run && view === 'visual' ? <ResearchVisual run={run} /> : null}
          {run && view === 'findings' ? <div className="finding-stack">{run.findings.map((finding, index) => <div key={finding}><span>{String(index + 1).padStart(2, '0')}</span><p>{finding}</p></div>)}</div> : null}
          {run && view === 'bias' ? <BiasView run={run} /> : null}
        </Panel>
      </div>
    </div>
  )
}

function ResearchVisual({ run }: { run: ResearchRun }) {
  if (run.type === 'sweep') return <div className="research-visual"><div className="research-visual__chart"><div className="axis-label">{run.yLabel} ↓ · {run.xLabel} →</div><Heatmap xs={run.xs} ys={run.ys} grid={run.grid} current={run.current} /></div><aside><Metric label="Best net Sharpe" value={fmtNum(run.best.z)} tone="good" /><KeyValue label="Best point" value={`${run.best.x}m × ${run.best.y} ATR`} mono /><KeyValue label="Current point" value={`${run.current.x}m × ${run.current.y} ATR`} mono /><Notice tone="warn" title="Rejected corner">The 1.2 ATR row is isolated and fragile after charges.</Notice></aside></div>
  if (run.type === 'walkforward') return <div className="walkforward"><Table><thead><tr><th>Fold</th><th>IS Sharpe</th><th>OOS Sharpe</th><th>IS return</th><th>OOS return</th><th>OOS trades</th></tr></thead><tbody>{run.folds.map((fold) => <tr key={fold.label}><td><strong>{fold.label}</strong></td><td>{fmtNum(fold.isSharpe)}</td><td className={fold.oosSharpe > 1 ? 'positive' : 'negative'}>{fmtNum(fold.oosSharpe)}</td><td>{fmtPct(fold.isReturn)}</td><td>{fmtPct(fold.oosReturn)}</td><td>{fold.oosTrades}</td></tr>)}</tbody></Table><div className="fold-bars">{run.folds.map((fold) => <div key={fold.label}><span>{fold.label}</span><i style={{ width: `${fold.isSharpe / 1.8 * 100}%` }} /><i className="oos" style={{ width: `${fold.oosSharpe / 1.8 * 100}%` }} /></div>)}</div></div>
  if (run.type === 'montecarlo') return <div className="research-visual"><div className="research-visual__chart"><MonteCarloChart p5={run.p5} p50={run.p50} p95={run.p95} /></div><aside><Metric label="Median final" value={fmtPct(run.medianFinal)} tone="good" /><Metric label="5th percentile" value={fmtPct(run.p5Final)} /><Metric label="Ruin probability" value={fmtPct(run.ruinProb, 1, false)} tone="warn" /></aside></div>
  return <Table><thead><tr><th>Definition</th><th>Net</th><th>Max DD</th><th>Sharpe</th><th>Trades</th><th>Decision</th></tr></thead><tbody>{run.rows.map((row) => <tr key={row.name}><td><strong>{row.name}</strong></td><td>{fmtPct(row.netPct)}</td><td className="negative">{fmtPct(row.maxDD)}</td><td>{fmtNum(row.sharpe)}</td><td>{row.trades}</td><td><Badge tone={row.verdict === 'keep' ? 'good' : row.verdict === 'reject' ? 'bad' : 'warn'}>{row.verdict}</Badge></td></tr>)}</tbody></Table>
}

function BiasView({ run }: { run: ResearchRun }) {
  if (run.type !== 'sweep') return <div className="bias-generic"><ShieldCheck size={32} /><h3>Run-level review attached</h3><p>Open the evidence drawer for source data, method, artefact hash and reviewer decision.</p><Button>Open evidence packet</Button></div>
  return <div className="bias-checks">{run.biasChecks.map((check) => <div key={check.name}><span className={cx('check-icon', `check-icon--${check.verdict}`)}>{check.verdict === 'pass' ? <Check size={14} /> : <AlertTriangle size={14} />}</span><div><strong>{check.name}</strong><p>{check.note}</p></div><Badge tone={check.verdict === 'pass' ? 'good' : check.verdict === 'fail' ? 'bad' : 'warn'}>{check.verdict}</Badge></div>)}</div>
}

type DeployMode = 'research-only' | 'signal-only' | 'paper' | 'live'

export function DeploySurface({ strategy, onNavigate }: SurfaceProps) {
  const [mode, setMode] = useState<DeployMode>('paper')
  const [ack, setAck] = useState(false)
  const checks = [
    { label: 'Validated strategy version selected', detail: `${strategy.validatedId ?? 'No admitted version'}`, pass: Boolean(strategy.validatedId) },
    { label: 'Resolved instruments', detail: '3 roles · expiry and lot size pinned', pass: true },
    { label: 'Provider capability confirmed', detail: 'Completed bars · market data only', pass: true },
    { label: 'Execution binding isolated', detail: mode === 'paper' ? 'Synthetic paper adapter' : 'No execution capability', pass: mode !== 'live' },
    { label: 'Risk budget within portfolio floor', detail: 'Strategy 9% · global floor 12%', pass: true },
    { label: 'Fresh market-data receipt', detail: '38 seconds stale · new entries gated', pass: false },
  ]
  const blockers = checks.filter((check) => !check.pass)
  return (
    <div className="surface">
      <SurfaceHeading eyebrow={`${strategy.code} · deployment binding`} title="Preflight a deployment" copy="Bind one validated definition to mode, instruments and capabilities. The strategy definition stays unchanged." actions={<Button onClick={() => onNavigate('live')}>View existing deployment <ArrowRight size={14} /></Button>} />
      <div className="deploy-layout">
        <Panel className="deploy-config"><PanelHeader eyebrow="Requested assignment" title="Deployment binding" />
          <label className="field"><span>Validated version</span><select defaultValue={strategy.validatedId ?? ''} disabled={!strategy.validatedId}><option>{strategy.validatedId ?? 'No validated version'}</option></select></label>
          <div className="mode-cards">{(['research-only', 'signal-only', 'paper', 'live'] as DeployMode[]).map((item) => <button type="button" aria-label={item === 'live' ? 'Live mode unavailable' : `${item} mode`} disabled={item === 'live'} className={cx(mode === item && 'is-selected', item === 'live' && 'is-disabled')} onClick={() => setMode(item)} key={item}><span>{item === 'research-only' ? <FlaskConical /> : item === 'signal-only' ? <Bell /> : item === 'paper' ? <MonitorDot /> : <LockKeyhole />}</span><strong>{item}</strong><small>{item === 'research-only' ? 'No signals or orders' : item === 'signal-only' ? 'Emit records only' : item === 'paper' ? 'Synthetic fills only' : 'Unavailable in prototype'}</small></button>)}</div>
          <div className="binding-grid"><label className="field"><span>Market data</span><select><option>TrueData Market Data · fixture</option></select></label><label className="field"><span>Execution broker</span><select><option>{mode === 'paper' ? 'Zerodha Kite · paper adapter' : 'None'}</option></select></label><label className="field"><span>Account</span><select><option>{mode === 'paper' ? 'PAPER-IND-02' : 'Not applicable'}</option></select></label><label className="field"><span>Capital assignment</span><input value="₹7,50,000" readOnly /></label></div>
          <Disclosure summary="Resolved instrument roles" meta="3 bindings" defaultOpen>{strategy.roles.map((role) => <KeyValue key={role.role} label={role.role} value={role.instrument} mono />)}</Disclosure>
          <label className="ack-row"><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /><span>I understand this creates a synthetic, non-authoritative paper binding only.</span></label>
        </Panel>
        <Panel className="preflight"><PanelHeader eyebrow="Admission gates" title="Preflight results" action={<Badge tone={blockers.length ? 'bad' : 'good'} dot>{blockers.length} blocker{blockers.length === 1 ? '' : 's'}</Badge>} />
          <div className="preflight-list">{checks.map((check) => <div key={check.label}><span className={cx('check-icon', check.pass ? 'check-icon--pass' : 'check-icon--fail')}>{check.pass ? <Check size={14} /> : <X size={14} />}</span><div><strong>{check.label}</strong><small>{check.detail}</small></div><Badge tone={check.pass ? 'good' : 'bad'}>{check.pass ? 'pass' : 'block'}</Badge></div>)}</div>
          <Notice tone="bad" title="Cannot stage this request">RECEIPT_STALE: wait for a fresh completed-bar receipt. Existing exit protection remains available.</Notice>
          <Button variant="primary" disabled={!ack || blockers.length > 0}><LockKeyhole size={14} /> Stage paper deployment</Button>
          <p className="panel-note">This prototype contains no live authority, credentials, provider session or order route.</p>
        </Panel>
      </div>
    </div>
  )
}

type LiveTab = 'positions' | 'orders' | 'events'

function DeploymentCard({ deployment, selected, onSelect }: { deployment: Deployment; selected: boolean; onSelect: () => void }) {
  return <button type="button" className={cx('deployment-card', selected && 'is-selected')} onClick={onSelect}><span className={cx('deployment-card__mark', `health--${deployment.health}`)} /><div><strong>{deployment.strategyName}</strong><small>{deployment.id} · {deployment.versionId}</small></div><Badge tone={deployment.mode === 'paper' ? 'violet' : 'info'}>{deployment.mode}</Badge><Badge tone={toneForHealth(deployment.health)} dot>{deployment.health}</Badge><span className={deployment.dayPnl >= 0 ? 'positive' : 'negative'}>{fmtINR(deployment.dayPnl)}</span></button>
}

export function LiveSurface({ onNavigate }: SurfaceProps) {
  const [deploymentId, setDeploymentId] = useState(deployments[0].id)
  const [tab, setTab] = useState<LiveTab>('positions')
  const deployment = deployments.find((item) => item.id === deploymentId) ?? deployments[0]
  const filteredPositions = positions.filter((item) => item.deploymentId === deployment.id || deployment.id === deployments[0].id)
  const filteredOrders = orders.filter((item) => item.deploymentId === deployment.id)
  return (
    <div className="surface surface-live">
      <SurfaceHeading eyebrow="Operations · synthetic only" title="Paper & signal cockpit" copy="Requested assignment, resolved binding, operating health and money records stay separately attributable." actions={<><Badge tone="warn" dot>Entries gated</Badge><Button onClick={() => onNavigate('deploy')}><Rocket size={14} /> Preflight</Button></>} />
      <StatusStrip />
      <div className="deployment-switcher">{deployments.map((item) => <DeploymentCard key={item.id} deployment={item} selected={item.id === deployment.id} onSelect={() => setDeploymentId(item.id)} />)}</div>
      <Notice tone="warn" title="Market-data receipt stale">New entries are suspended for {deployment.id}. Risk-reducing exits and protection remain available.</Notice>
      <div className="live-grid">
        <Panel className="live-grid__chart"><PanelHeader eyebrow={`${deployment.id} · ${deployment.versionId}`} title="Synthetic equity & open state" action={<Badge tone={toneForHealth(deployment.health)} dot>{deployment.health}</Badge>} /><EquityChart values={portfolio.equityCurve.slice(-64)} height={220} /><div className="metric-grid metric-grid--three"><Metric compact label="Day P&L" value={fmtINR(deployment.dayPnl)} tone="good" /><Metric compact label="Capital bound" value={fmtINRShort(deployment.capital)} /><Metric compact label="Mode" value={deployment.mode} tone="violet" /></div></Panel>
        <Panel className="live-grid__authority"><PanelHeader eyebrow="Authority resolution" title="What may happen" /><div className="authority-map"><div><span>Requested</span><strong>{deployment.mode}</strong></div><ArrowRight size={15} /><div><span>Resolved</span><strong>{deployment.mode === 'paper' ? 'paper intents' : 'signal records'}</strong></div><ArrowRight size={15} /><div><span>Money</span><strong>{deployment.mode === 'paper' ? 'synthetic' : 'none'}</strong></div></div>{deployment.blockers.map((blocker) => <Notice key={blocker.code} tone={blocker.severity === 'blocker' ? 'bad' : 'warn'} title={blocker.code}>{blocker.human}</Notice>)}<div className="compact-kvs"><KeyValue label="Provider" value={deployment.provider} /><KeyValue label="Broker" value={deployment.broker} /><KeyValue label="Account" value={deployment.account} mono /><KeyValue label="Schedule" value={deployment.schedule} /></div></Panel>
        <Panel className="live-grid__records"><div className="records-tabs"><Segmented value={tab} onChange={setTab} ariaLabel="Operating records" items={[{ value: 'positions', label: `Positions ${filteredPositions.length}` }, { value: 'orders', label: `Orders ${filteredOrders.length}` }, { value: 'events', label: 'Events' }]} /><span>As of 14:09:00 IST</span></div>
          {tab === 'positions' ? <Table compact><thead><tr><th>Strategy / version</th><th>Instrument</th><th>Side</th><th>Qty</th><th>Avg / LTP</th><th>Protection</th><th className="right">Unrealised</th></tr></thead><tbody>{filteredPositions.map((position) => <tr key={position.id}><td><strong>{position.strategyName}</strong><small>{position.versionId} · {position.id}</small></td><td className="mono">{position.instrument}</td><td><Badge tone={position.side === 'LONG' ? 'good' : 'info'}>{position.side}</Badge></td><td>{position.qty.toLocaleString('en-IN')}</td><td>{position.avgPx.toLocaleString('en-IN')} / {position.ltp.toLocaleString('en-IN')}</td><td><ShieldCheck size={13} className="inline-icon positive" /> {position.protection}</td><td className="right positive">{fmtINR(position.unrealized)}</td></tr>)}</tbody></Table> : null}
          {tab === 'orders' ? <Table compact><thead><tr><th>Time</th><th>Order</th><th>Instrument</th><th>Side / type</th><th>Qty</th><th>Status</th><th>Price</th></tr></thead><tbody>{filteredOrders.map((order) => <tr key={order.id}><td className="mono">{order.ts}</td><td className="mono">{order.id}</td><td>{order.instrument}</td><td>{order.side} · {order.type}</td><td>{order.qty}</td><td><Badge tone={order.status === 'FILLED' ? 'good' : order.status === 'REJECTED' ? 'bad' : 'neutral'}>{order.status}</Badge></td><td>{order.px?.toLocaleString('en-IN') ?? '—'}</td></tr>)}</tbody></Table> : null}
          {tab === 'events' ? <div className="event-list">{activity.slice(0, 6).map((event) => <div className="event-row" key={event.id}><i className={cx('event-mark', `event-mark--${event.severity}`)} /><time>{event.ts}</time><div><strong>{event.title}</strong><p>{event.detail}</p><small>{event.provenance?.join(' · ')}</small></div></div>)}</div> : null}
        </Panel>
      </div>
    </div>
  )
}

export function PortfolioSurface(): ReactNode {
  const allocation = [34, 22, 18, 14, 12]
  return (
    <div className="surface">
      <SurfaceHeading eyebrow="Portfolio · synthetic book" title="Capital, exposure and strategy attribution" copy="Portfolio-wide limits override looser strategy settings. All values are static fixtures." actions={<Button><SquareArrowOutUpRight size={14} /> Export snapshot</Button>} />
      <div className="metric-grid metric-grid--six"><Metric label="Equity" value={fmtINRShort(portfolio.equity)} sub={`${fmtPct(portfolio.dayPct)} today`} tone="good" /><Metric label="Day P&L" value={fmtINR(portfolio.dayPnl)} tone="good" /><Metric label="Capital deployed" value={fmtINRShort(portfolio.capitalDeployed)} sub={`${Math.round(portfolio.capitalDeployed / portfolio.capitalTotal * 100)}% assigned`} /><Metric label="Open risk" value={fmtINRShort(portfolio.openRisk)} tone="warn" /><Metric label="Gross exposure" value={fmtINRShort(portfolio.gross)} /><Metric label="Charges today" value={fmtINR(portfolio.chargesToday)} /></div>
      <div className="portfolio-grid">
        <Panel className="portfolio-grid__curve"><PanelHeader eyebrow="All strategies" title="Portfolio equity" /><EquityChart values={portfolio.equityCurve} height={240} /></Panel>
        <Panel><PanelHeader eyebrow="Risk budget" title="Portfolio floors" /><Progress label="Capital assigned" value={portfolio.capitalDeployed / portfolio.capitalTotal * 100} /><Progress label="Daily loss budget used" value={28} tone="warn" /><Progress label="Drawdown budget used" value={41} tone="violet" /><Notice tone="info" title="Precedence">Global max drawdown is 12%. A strategy may request a stricter limit, never a looser one.</Notice></Panel>
        <Panel><PanelHeader eyebrow="Allocation" title="By strategy" /><div className="allocation-list">{['NIFTY Opening Range', 'NIFTY Close Reversion', 'USDINR Carry Filter', 'BANKNIFTY Research', 'Unassigned'].map((label, index) => <div key={label}><span>{label}</span><div><i style={{ width: `${allocation[index]}%` }} /></div><strong>{allocation[index]}%</strong></div>)}</div></Panel>
        <Panel className="portfolio-grid__positions"><PanelHeader eyebrow="Exact attribution" title="Open paper positions" /><Table compact><thead><tr><th>Position</th><th>Strategy</th><th>Version</th><th>Deployment</th><th>Protection</th><th className="right">P&L</th></tr></thead><tbody>{positions.map((position) => <tr key={position.id}><td className="mono">{position.id}</td><td>{position.strategyName}</td><td className="mono">{position.versionId}</td><td className="mono">{position.deploymentId}</td><td>{position.protection}</td><td className="right positive">{fmtINR(position.unrealized + position.realizedToday)}</td></tr>)}</tbody></Table></Panel>
      </div>
    </div>
  )
}

function WidgetPreview({ widget, onRemove }: { widget: WorkspaceWidget; onRemove: () => void }) {
  return <Panel className={cx('workspace-widget', `workspace-widget--${widget.size}`)}><div className="workspace-widget__head"><GripVertical size={14} /><div><strong>{widget.name}</strong><small>{widget.category}</small></div><IconButton label={`Remove ${widget.name}`} onClick={onRemove}><X size={13} /></IconButton></div>{widget.id === 'equity' ? <Sparkline values={portfolio.equityCurve.slice(-40)} height={72} /> : widget.id === 'watchlist' ? <div className="tiny-watch"><span>NIFTY <b className="positive">+0.42%</b></span><span>BANKNIFTY <b className="negative">−0.18%</b></span><span>INDIA VIX <b>12.84</b></span></div> : widget.id === 'deployments' ? <div className="tiny-health"><Badge tone="warn" dot>Paper degraded</Badge><Badge tone="good" dot>Signal healthy</Badge></div> : <div className="widget-placeholder"><i /><i /><i /></div>}</Panel>
}

export function WorkspaceSurface(): ReactNode {
  const [active, setActive] = useState<string[]>(['equity', 'deployments', 'watchlist', 'activity'])
  const [layout, setLayout] = useState<'grid' | 'focus' | 'split'>('grid')
  return (
    <div className="surface">
      <SurfaceHeading eyebrow="Personal workspace" title="Compose a working view" copy="Layout changes presentation only. They never enter strategy identity or deployment authority." actions={<><Button><Copy size={14} /> Duplicate</Button><Button variant="primary">Save workspace</Button></>} />
      <div className="workspace-editor">
        <Panel className="widget-catalog"><PanelHeader title="Widget library" eyebrow="Presentation only" compact /><label className="input-shell"><Search size={14} /><input placeholder="Find a widget" /></label>{workspaceWidgets.map((widget) => <button type="button" key={widget.id} disabled={active.includes(widget.id)} onClick={() => setActive((items) => [...items, widget.id])}><span><strong>{widget.name}</strong><small>{widget.description}</small></span><Plus size={14} /></button>)}</Panel>
        <div className="workspace-stage"><div className="workspace-stage__toolbar"><Segmented value={layout} onChange={setLayout} ariaLabel="Workspace layout" items={[{ value: 'grid', label: 'Grid' }, { value: 'focus', label: 'Focus' }, { value: 'split', label: 'Split' }]} /><span>{active.length} widgets · drag handles shown</span></div><div className={cx('workspace-canvas', `workspace-canvas--${layout}`)}>{active.map((id) => { const widget = workspaceWidgets.find((item) => item.id === id); return widget ? <WidgetPreview key={id} widget={widget} onRemove={() => setActive((items) => items.filter((item) => item !== id))} /> : null })}{!active.length ? <EmptyState icon={<Columns3 size={26} />} title="Empty workspace" action={<Button onClick={() => setActive(['equity'])}>Add portfolio equity</Button>}>Add a widget from the library.</EmptyState> : null}</div></div>
      </div>
    </div>
  )
}

export function ConnectionsSurface(): ReactNode {
  const [selected, setSelected] = useState(connections[0].id)
  const connection = connections.find((item) => item.id === selected) ?? connections[0]
  return (
    <div className="surface">
      <SurfaceHeading eyebrow="Provider boundary" title="Connections & capabilities" copy="Market data, instrument resolution, accounts and execution remain separate roles." actions={<Button variant="primary"><Plus size={14} /> Add fixture</Button>} />
      <Notice tone="info" title="Prototype boundary">No credentials are accepted or stored. These connections are static capability fixtures.</Notice>
      <div className="connections-grid"><div className="connection-list">{connections.map((item) => <button type="button" key={item.id} className={cx(item.id === selected && 'is-selected')} onClick={() => setSelected(item.id)}><span className="provider-monogram">{item.provider.split(' ').slice(0, 2).map((part) => part[0]).join('')}</span><div><strong>{item.provider}</strong><small>{item.roles.join(' · ')}</small></div><Badge tone={toneForHealth(item.health)} dot>{item.health}</Badge><ChevronRight size={15} /></button>)}</div><Panel className="connection-detail"><PanelHeader eyebrow={connection.id} title={connection.provider} action={<Badge tone={connection.auth === 'connected' ? 'good' : 'warn'} dot>{connection.auth}</Badge>} /><div className="connection-health"><Metric label="Health" value={connection.health} tone={toneForHealth(connection.health)} /><Metric label="Fixture latency" value={`${connection.latencyMs.toLocaleString('en-IN')} ms`} /><Metric label="Last receipt" value={connection.lastTick.split('·').at(-1)?.trim() ?? connection.lastTick} /></div><span className="label">Resolved roles</span><div className="chip-row">{connection.roles.map((role) => <Badge key={role} tone="violet">{role}</Badge>)}</div><span className="label">Capabilities</span><div className="capability-list">{connection.capabilities.map((capability) => <div key={capability}><CheckCircle2 size={14} /><span>{capability}</span></div>)}</div><Disclosure summary="Accounts" meta={`${connection.accounts.length} exposed`} defaultOpen>{connection.accounts.length ? connection.accounts.map((account) => <KeyValue key={account} label="Synthetic account" value={account} mono />) : <p>No account capability is exposed by this provider.</p>}</Disclosure><Notice tone="neutral" title="Fixture note">{connection.note}</Notice></Panel></div>
    </div>
  )
}

type MobileTab = 'today' | 'live' | 'activity'

export function MobileSurface(): ReactNode {
  const [tab, setTab] = useState<MobileTab>('today')
  return (
    <div className="surface mobile-showcase">
      <SurfaceHeading eyebrow="Companion, not control plane" title="Mobile Today & Live" copy="A narrow view for awareness, evidence and paper-state review. Authoritative changes stay on desktop." />
      <div className="mobile-showcase__grid">
        <div className="phone-frame"><div className="phone-status"><span>14:09</span><span><Radio size={11} /> Wi-Fi · 86%</span></div><div className="phone-head"><div><span className="eyebrow">STRATEGY OS</span><strong>{tab === 'today' ? 'Today' : tab === 'live' ? 'Paper live' : 'Activity'}</strong></div><IconButton label="Notifications"><Bell size={16} /></IconButton></div><div className="phone-body">
          {tab === 'today' ? <><div className="phone-hero"><small>Portfolio equity</small><strong>{fmtINRShort(portfolio.equity)}</strong><span className="positive"><ArrowUpRight size={13} />{fmtPct(portfolio.dayPct)} today</span><Sparkline values={portfolio.equityCurve.slice(-40)} height={70} /></div><div className="phone-card phone-card--warn"><AlertTriangle size={16} /><div><strong>Entries gated</strong><small>Data receipt 38s stale. Exits available.</small></div><ChevronRight size={14} /></div><div className="phone-section"><span>Deployments</span>{deployments.map((item) => <div className="phone-line" key={item.id}><i className={cx('status-dot', item.health === 'healthy' ? 'status-dot--good' : 'status-dot--warn')} /><div><strong>{item.strategyName}</strong><small>{item.mode} · {item.versionId}</small></div><span>{fmtINR(item.dayPnl)}</span></div>)}</div></> : null}
          {tab === 'live' ? <><div className="phone-card"><div className="phone-card__between"><Badge tone="violet">PAPER</Badge><Badge tone="warn" dot>degraded</Badge></div><h3>NIFTY Opening Range</h3><small>DEP-PAPER-042 · v1.7.2</small><div className="phone-pnl"><span>Day P&amp;L</span><strong className="positive">{fmtINR(4_820)}</strong></div></div><div className="phone-section"><span>Open position</span><div className="phone-position"><strong>+25 NIFTY AUG FUT</strong><span className="positive">{fmtINR(647.5)}</span><small>Protection 24,792.0 · active</small></div></div><Notice tone="info" title="Read-only companion">No order or authority controls are available here.</Notice></> : null}
          {tab === 'activity' ? <div className="phone-section"><span>Causal activity</span>{activity.slice(0, 6).map((event) => <div className="phone-event" key={event.id}><i className={cx('event-mark', `event-mark--${event.severity}`)} /><div><small>{event.ts} · {event.channel}</small><strong>{event.title}</strong><p>{event.detail}</p></div></div>)}</div> : null}
        </div><nav className="phone-nav">{([{ id: 'today', icon: LayoutDashboard, label: 'Today' }, { id: 'live', icon: Radio, label: 'Live' }, { id: 'activity', icon: Activity, label: 'Activity' }] as const).map((item) => <button type="button" key={item.id} className={tab === item.id ? 'is-active' : ''} onClick={() => setTab(item.id)}><item.icon size={17} /><span>{item.label}</span></button>)}</nav></div>
        <div className="mobile-notes"><Panel><PanelHeader eyebrow="Phone principle" title="Awareness without accidental authority" /><div className="principle-list"><div><Eye size={17} /><span><strong>Review paper state</strong>See health, positions and evidence.</span></div><div><Bell size={17} /><span><strong>Receive causal alerts</strong>Every alert names its strategy, version and deployment.</span></div><div><LockKeyhole size={17} /><span><strong>No live control</strong>Desktop owner gates remain required for material authority.</span></div></div></Panel><Panel><PanelHeader eyebrow="390 px" title="True companion layout" /><p className="muted-copy">The same responsive shell also collapses every direction into a usable bottom-navigation pattern at phone width.</p><div className="device-ruler"><span>390</span><i /><span>844</span></div></Panel></div>
      </div>
    </div>
  )
}

export function ActivitySurface(): ReactNode {
  const [channel, setChannel] = useState('all')
  const visible = channel === 'all' ? activity : activity.filter((event) => event.channel === channel)
  return (
    <div className="surface">
      <SurfaceHeading eyebrow="Immutable causal record" title="Activity" copy="Research, validation, configuration, deployment, provider and money events retain exact provenance." actions={<Button><SquareArrowOutUpRight size={14} /> Export record</Button>} />
      <div className="filter-row"><label className="input-shell input-shell--wide"><Search size={14} /><input placeholder="Search activity or provenance ID" /></label><select value={channel} onChange={(event) => setChannel(event.target.value)} aria-label="Activity channel"><option value="all">All channels</option>{Array.from(new Set(activity.map((item) => item.channel))).map((item) => <option value={item} key={item}>{item}</option>)}</select><Badge tone="neutral">{visible.length} records</Badge></div>
      <Panel className="activity-ledger"><div className="event-list">{visible.map((event) => <Disclosure key={event.id} summary={<div className="ledger-summary"><i className={cx('event-mark', `event-mark--${event.severity}`)} /><time>{event.ts}</time><Badge tone="neutral">{event.channel}</Badge><strong>{event.title}</strong></div>} meta={event.id}><p>{event.detail}</p><div className="chip-row">{event.provenance?.map((item) => <Badge key={item} tone="violet">{item}</Badge>)}</div></Disclosure>)}</div></Panel>
    </div>
  )
}

type SettingsSection = 'components' | 'general' | 'execution'

export function SettingsSurface(): ReactNode {
  const [section, setSection] = useState<SettingsSection>('general')
  return (
    <div className="surface">
      <SurfaceHeading eyebrow="Policy & presentation" title="Settings" copy="Global policies form a floor. Strategy and deployment settings may become stricter, never silently weaker." actions={<Button variant="primary">Save local preferences</Button>} />
      <div className="settings-layout"><Panel className="settings-nav"><PanelHeader eyebrow="Scope" title="Strategy settings" compact />{([{ id: 'components', icon: Boxes, label: 'Components' }, { id: 'general', icon: Settings2, label: 'General' }, { id: 'execution', icon: Zap, label: 'Execution' }] as const).map((item) => <button type="button" key={item.id} onClick={() => setSection(item.id)} className={section === item.id ? 'is-active' : ''}><item.icon size={15} /><span>{item.label}</span><ChevronRight size={14} /></button>)}</Panel><Panel className="settings-detail"><PanelHeader eyebrow={`${section} · NIFTY Opening Range`} title={section === 'general' ? 'Strategy-specific conditions' : section === 'execution' ? 'Protection & intent defaults' : 'Component defaults'} action={<Badge tone="violet">Overrides visible</Badge>} />
        {section === 'general' ? <div className="settings-form"><label className="field"><span>Trading sessions</span><input value="NSE regular · 09:15–15:20 IST" readOnly /></label><label className="field"><span>Maximum strategy drawdown</span><input value="9%" readOnly /><small>Stricter than the global 12% floor.</small></label><label className="field"><span>Daily loss limit</span><input value="2.5%" readOnly /></label><label className="field"><span>Time zone</span><input value="Asia/Kolkata" readOnly /></label></div> : null}
        {section === 'execution' ? <div className="settings-form"><label className="field"><span>Initial protection</span><input value="2.0 ATR" readOnly /></label><label className="field"><span>Trailing protection</span><input value="1.6 ATR after +0.8 ATR" readOnly /></label><label className="field"><span>Take profit</span><input value="None · trailing exit owns closure" readOnly /></label><label className="field"><span>Conflict rule</span><input value="Risk-reducing intent wins" readOnly /></label><Notice tone="warn" title="No portfolio override">Per-trade protection cannot weaken the global portfolio loss or drawdown floor.</Notice></div> : null}
        {section === 'components' ? <div className="component-settings">{primaryStrategy.graph.nodes.map((node) => <div key={node.id}><Badge tone="neutral">{node.kind}</Badge><div><strong>{node.title}</strong><small>{node.sub}</small></div><Button variant="ghost">Edit defaults</Button></div>)}</div> : null}
        <div className="precedence-map"><span>Global policy</span><ArrowRight size={14} /><span>Strategy override</span><ArrowRight size={14} /><span>Deployment binding</span><strong>Effective value = strictest valid rule</strong></div>
      </Panel></div>
    </div>
  )
}

export function SurfaceRouter(props: SurfaceProps & { surface: SurfaceId }): ReactNode {
  switch (props.surface) {
    case 'home': return <HomeSurface {...props} />
    case 'strategies': return <StrategiesSurface {...props} />
    case 'overview': return <OverviewSurface {...props} />
    case 'build': return <BuildSurface {...props} />
    case 'backtest': return <BacktestSurface {...props} />
    case 'research': return <ResearchSurface {...props} />
    case 'deploy': return <DeploySurface {...props} />
    case 'live': return <LiveSurface {...props} />
    case 'portfolio': return <PortfolioSurface />
    case 'workspace': return <WorkspaceSurface />
    case 'connections': return <ConnectionsSurface />
    case 'mobile': return <MobileSurface />
    case 'activity': return <ActivitySurface />
    case 'settings': return <SettingsSurface />
  }
}

export function DirectionComparisonInline(): ReactNode {
  return <Table compact><thead><tr><th>Criterion</th><th>Calm</th><th>Workstation</th><th>Lifecycle</th><th>Progressive</th><th>Evidence</th><th>Synthesis</th></tr></thead><tbody>{comparisonRows.map((row) => <tr key={row.criterion}><td><strong>{row.criterion}</strong></td><td>{row.calm}</td><td>{row.adaptive}</td><td>{row.lifecycle}</td><td>{row.progressive}</td><td>{row.evidence}</td><td className="synthesis-cell">{row.synthesis}</td></tr>)}</tbody></Table>
}
