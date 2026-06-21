import { useEffect, useMemo, useState } from 'react'
import { LineChart, MultiLineChart } from '../components/Charts'
import {
  startSweep, getSweepStatus, getSweepResults, getSweepResult,
  addToPortfolio, getSweepRuns, sweepExportUrl, getSweepInstruments, type SweepOpts,
} from '../lib/api'
import { inr, signedInr, pnlColor, num, dt } from '../lib/format'
import { colorFor } from '../lib/constants'
import type { BacktestRun, BTResult, BTTradeDTO, BTInstrument } from '../lib/types'

// display label -> Kite interval name
const INTERVALS: [string, string][] = [
  ['1m', 'minute'], ['5m', '5minute'], ['15m', '15minute'],
  ['30m', '30minute'], ['1h', '60minute'], ['1D', 'day'],
]
// preset lookback windows (label -> days; null = entire available history)
const PRESETS: [string, number | null][] = [
  ['1w', 7], ['2w', 14], ['1m', 30], ['3m', 90], ['6m', 180],
  ['1y', 365], ['3y', 1095], ['7y', 2555], ['10y', 3650], ['Entire history', null],
]

// per-row span label "DD Mon → DD Mon" from the true first/last candle epochs.
function spanLabel(r: BTResult): string {
  if (!r.first_ts || !r.last_ts) return '—'
  const f = dt(new Date(r.first_ts * 1000).toISOString())
  const t = dt(new Date(r.last_ts * 1000).toISOString())
  return `${f} → ${t}`
}

function Num({ label, value, set, step = 1 }:
  { label: string; value: number; set: (n: number) => void; step?: number }) {
  return (
    <label className="flex flex-col gap-0.5">
      <span className="stat-label">{label}</span>
      <input type="number" step={step} value={value}
        onChange={(e) => set(parseFloat(e.target.value) || 0)}
        className="w-24 bg-panel2 border border-edge rounded px-2 py-1 text-xs tabular-nums" />
    </label>
  )
}

export default function BacktestsView() {
  const [picked, setPicked] = useState<Set<string>>(new Set(['15minute', '30minute', 'day']))
  const [scope, setScope] = useState<'liquid' | 'full'>('liquid')
  const [run, setRun] = useState<BacktestRun | null>(null)
  const [running, setRunning] = useState(false)
  const [rows, setRows] = useState<BTResult[]>([])
  // survivorship disclosure: cells excluded from / flagged in the visible set
  const [skipped, setSkipped] = useState(0)
  const [unaffordable, setUnaffordable] = useState(0)
  const [drill, setDrill] = useState<BTResult | null>(null)
  const [added, setAdded] = useState<Set<string>>(new Set())
  // browse history: null = latest run
  const [runsList, setRunsList] = useState<any[]>([])
  const [viewRunId, setViewRunId] = useState<number | undefined>(undefined)

  // window selection: a preset (days, null=max) OR a custom date range
  const [preset, setPreset] = useState<number | null>(null)
  const [useCustom, setUseCustom] = useState(false)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  // instrument selection (empty = whole scope universe)
  const [universe, setUniverse] = useState<BTInstrument[]>([])
  const [selInst, setSelInst] = useState<Set<string>>(new Set())
  const [instQuery, setInstQuery] = useState('')

  // filters (client-side for snappy UX)
  const [minWin, setMinWin] = useState(0)
  const [minPF, setMinPF] = useState(0)
  const [maxDD, setMaxDD] = useState(100)
  const [minRet, setMinRet] = useState(-1e9)
  const [fInterval, setFInterval] = useState('')
  const [sort, setSort] = useState<keyof BTResult>('return_pct')

  const loadResults = () => getSweepResults({ min_trades: 1, run_id: viewRunId })
    .then((d) => {
      setRows(d.results || [])
      setSkipped(d.skipped ?? 0)
      setUnaffordable(d.unaffordable ?? 0)
    })
  const loadRuns = () => getSweepRuns().then((d) => setRunsList(d.runs || []))

  useEffect(() => {
    getSweepStatus().then((d) => { setRun(d.run); setRunning(d.running) })
    loadRuns()
  }, [])

  // (re)load the instrument universe for the picker when the scope changes
  useEffect(() => {
    getSweepInstruments(scope).then((d) => setUniverse(d.instruments || [])).catch(() => {})
  }, [scope])

  // reload results whenever the browsed run changes (undefined = latest)
  useEffect(() => { loadResults() }, [viewRunId])

  // poll while a sweep runs
  useEffect(() => {
    if (!running) return
    const t = setInterval(() => {
      getSweepStatus().then((d) => {
        setRun(d.run); setRunning(d.running)
        if (!d.running) { clearInterval(t); loadResults(); loadRuns() }
      })
    }, 1500)
    return () => clearInterval(t)
  }, [running])

  const toggleInterval = (iv: string) =>
    setPicked((s) => { const n = new Set(s); n.has(iv) ? n.delete(iv) : n.add(iv); return n })
  const toggleInst = (k: string) =>
    setSelInst((s) => { const n = new Set(s); n.has(k) ? n.delete(k) : n.add(k); return n })

  const instMatches = useMemo(() => {
    const q = instQuery.trim().toUpperCase()
    if (!q) return universe.slice(0, 60)
    return universe.filter((i) => i.key.toUpperCase().includes(q) || i.name.toUpperCase().includes(q)).slice(0, 60)
  }, [universe, instQuery])

  const windowLabel = useCustom && (startDate || endDate)
    ? `${startDate || '…'}→${endDate || 'now'}`
    : (PRESETS.find(([, d]) => d === preset)?.[0] ?? 'Max')

  const launch = async () => {
    const intervals = INTERVALS.map(([, v]) => v).filter((v) => picked.has(v))
    if (!intervals.length) return
    const opts: SweepOpts = {}
    if (selInst.size) opts.instruments = [...selInst]
    if (useCustom && (startDate || endDate)) {
      opts.start_date = startDate || undefined
      opts.end_date = endDate || undefined
    } else opts.lookback_days = preset
    const r = await startSweep(scope, intervals, 50000, opts)
    if (r.error) { alert(r.error); return }
    setViewRunId(undefined)   // show the new (latest) run as it streams in
    setRunning(true)
    getSweepStatus(r.run_id).then((d) => setRun(d.run))
  }

  const add = async (r: BTResult) => {
    const res = await addToPortfolio(r.instrument_key, true, r.interval)
    if (res.error) { alert(res.error); return }
    if (res.interval_warning) alert(res.interval_warning)
    setAdded((s) => new Set(s).add(r.instrument_key))
  }

  // apply filters + sort. lower-is-better metrics sort ascending.
  const ASC = new Set<keyof BTResult>(['max_drawdown_pct', 'charges', 'max_consec_losses', 'time_underwater_pct'])
  const view = rows
    .filter((r) => !r.error && r.win_rate >= minWin
      && (r.profit_factor == null || r.profit_factor >= minPF)
      && r.max_drawdown_pct <= maxDD && r.return_pct >= minRet
      && (!fInterval || r.interval === fInterval))
    .sort((a, b) => {
      const av = (a[sort] ?? -1e18) as number, bv = (b[sort] ?? -1e18) as number
      return ASC.has(sort) ? av - bv : bv - av
    })

  // scan-level win/loss tally + total Net P&L over the VISIBLE set — so a
  // winners-on-top sort (or survivorship) can't be misread as "the strategy
  // never loses". Counts on Net P&L over every traded (1-lot) row.
  const tradable = view.filter((r) => r.trades > 0)
  const winCount = tradable.filter((r) => r.net_pnl > 0).length
  const lossCount = tradable.filter((r) => r.net_pnl < 0).length
  const totalNet = tradable.reduce((s, r) => s + (r.net_pnl || 0), 0)

  const Th = ({ k, children, right, title }: { k?: keyof BTResult; children: any; right?: boolean; title?: string }) => (
    <th title={title} onClick={() => k && setSort(k)}
      className={`py-1 pr-3 ${right ? 'text-right' : 'text-left'} ${k ? 'cursor-pointer hover:text-zinc-200' : ''} ${sort === k ? 'text-zinc-100' : ''}`}>
      {children}{sort === k ? ' ▾' : ''}
    </th>
  )

  return (
    <div className="flex flex-col gap-3">
      {/* what this backtest actually is — so the numbers are read correctly */}
      <div className="card p-3 border-amber-400/40 bg-amber-400/5 text-[11px] leading-relaxed text-amber-200/90">
        <span className="font-semibold text-amber-300">How to read this:</span> this is a
        <b> signal-quality screen on the underlying</b> (futures/cash, bought outright — <b>no leverage</b>),
        net of the full charge stack, with pure strategy-reversal exits. It does <b>NOT</b> model the
        option premium, theta decay, or the live SL/TP — so it is <b>not a live options-P&amp;L forecast</b>.
        <b> Sizing:</b> every position is a <b>fixed 1 lot</b>; the base capital is the cost to enter that one
        lot (e.g. ₹2.5L), and <b>Return% = total net P&amp;L ÷ that base</b> (additive, <b>no compounding</b>) — so
        ₹2.5L→₹5L reads <b>+100%</b>, never the +1000% a tiny 50k base would fake. Names are never skipped for
        cost: each shows whether you can afford it as a <b>future</b> vs as an <b>ATM option</b> (far cheaper)
        at your real budget, so a promising-but-pricey edge stays on the radar. Drawdown / Underwater% are
        <b> close-to-close</b> (intra-trade excursion not modelled — see <b>worst-trade</b> for tail risk).
        <b> Consistency</b> is a <b>per-trade hit ratio (not annualised — not a Sharpe)</b>; <b>Sharpe</b> is the
        annualised, cross-timeframe-comparable ratio. Every row also shows <b>buy-and-hold</b> over the same span
        so a real edge is distinguishable from beta. Prefer <b>smooth, consistent curves</b> that beat hold.
      </div>

      {/* sweep controls */}
      <div className="card p-3 flex flex-col gap-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="stat-label">Strategy sweep — EMA50 + z-score on the underlying, net of all charges</div>
          <span className="text-[11px] text-muted">sized to capital, no leverage · pure-strategy exits</span>
        </div>
        <div className="flex items-end gap-4 flex-wrap">
          <div className="flex flex-col gap-1">
            <span className="stat-label">Timeframes</span>
            <div className="flex gap-1">
              {INTERVALS.map(([label, v]) => (
                <button key={v} onClick={() => toggleInterval(v)}
                  className={`badge ${picked.has(v) ? 'bg-blue-500/25 text-blue-300' : 'bg-zinc-700/40 text-muted'}`}>
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <span className="stat-label">Universe</span>
            <div className="flex gap-1">
              <button onClick={() => setScope('liquid')}
                className={`badge ${scope === 'liquid' ? 'bg-up/20 text-up' : 'bg-zinc-700/40 text-muted'}`}>LIQUID</button>
              <button onClick={() => setScope('full')}
                className={`badge ${scope === 'full' ? 'bg-up/20 text-up' : 'bg-zinc-700/40 text-muted'}`}>FULL MARKET</button>
            </div>
          </div>
          <button onClick={launch} disabled={running || picked.size === 0}
            className={`btn ${running ? 'opacity-50' : 'border-up/50 text-up'}`}>
            {running ? 'sweep running…' : '▶ Run sweep'}
          </button>
          {scope === 'full' && <span className="text-[11px] text-down">full-market = thousands of names; slow.</span>}
        </div>

        {/* lookback window: presets + custom range */}
        <div className="flex flex-col gap-1 border-t border-edge/50 pt-2">
          <span className="stat-label">Lookback window
            <span className="ml-1 text-muted/70 normal-case">— clamped to Kite's max per timeframe (e.g. 15m ≈ 200d, 1h ≈ 400d, 1D ≈ 2000d)</span>
          </span>
          <div className="flex items-center gap-1 flex-wrap">
            {PRESETS.map(([label, days]) => (
              <button key={label} onClick={() => { setUseCustom(false); setPreset(days) }}
                className={`badge ${!useCustom && preset === days ? 'bg-blue-500/25 text-blue-300' : 'bg-zinc-700/40 text-muted'}`}>
                {label}
              </button>
            ))}
            <button onClick={() => setUseCustom(true)}
              className={`badge ${useCustom ? 'bg-blue-500/25 text-blue-300' : 'bg-zinc-700/40 text-muted'}`}>
              Custom…
            </button>
            {useCustom && (
              <span className="flex items-center gap-1 ml-1">
                <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
                  className="bg-panel2 border border-edge rounded px-2 py-1 text-xs" />
                <span className="text-muted text-xs">→</span>
                <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
                  className="bg-panel2 border border-edge rounded px-2 py-1 text-xs" />
              </span>
            )}
            <span className="ml-2 text-[11px] text-muted">window: <b className="text-zinc-300">{windowLabel}</b></span>
          </div>
        </div>

        {/* instrument picker (empty = whole scope) */}
        <div className="flex flex-col gap-1 border-t border-edge/50 pt-2">
          <span className="stat-label">Instruments
            <span className="ml-1 text-muted/70 normal-case">— leave empty to sweep the whole {scope} universe; or pick specific names (e.g. GOLD, SILVER, COPPER)</span>
          </span>
          {selInst.size > 0 && (
            <div className="flex items-center gap-1 flex-wrap">
              {[...selInst].map((k) => (
                <button key={k} onClick={() => toggleInst(k)}
                  className="badge bg-blue-500/25 text-blue-300" title="click to remove">{k} ✕</button>
              ))}
              <button onClick={() => setSelInst(new Set())} className="badge bg-zinc-700/40 text-muted">clear all</button>
            </div>
          )}
          <div className="flex items-center gap-2 flex-wrap">
            <input value={instQuery} onChange={(e) => setInstQuery(e.target.value)}
              placeholder={universe.length ? `search ${universe.length} instruments…` : 'loading universe…'}
              className="bg-panel2 border border-edge rounded px-2 py-1 text-xs w-56" />
            <span className="text-[11px] text-muted">
              {selInst.size ? `${selInst.size} selected` : 'all instruments'}
            </span>
          </div>
          {instQuery && (
            <div className="flex items-center gap-1 flex-wrap max-h-24 overflow-auto">
              {instMatches.map((i) => (
                <button key={i.key} onClick={() => toggleInst(i.key)}
                  className={`badge ${selInst.has(i.key) ? 'bg-up/20 text-up' : 'bg-zinc-700/40 text-muted hover:text-zinc-200'}`}
                  title={`${i.name} · ${i.segment}`}>
                  {i.key}
                </button>
              ))}
              {!instMatches.length && <span className="text-[11px] text-muted">no match</span>}
            </div>
          )}
        </div>

        {run && (
          <div className="flex items-center gap-3">
            <div className="flex-1 h-2 bg-panel2 rounded overflow-hidden">
              <div className="h-full bg-up transition-all" style={{ width: `${run.progress}%` }} />
            </div>
            <span className="text-[11px] text-muted tabular-nums">
              {run.status} · {run.done}/{run.total} · {run.note}
            </span>
          </div>
        )}
        <div className="flex items-center gap-2 flex-wrap border-t border-edge/50 pt-2">
          <span className="stat-label">History</span>
          <select value={viewRunId ?? ''}
            onChange={(e) => setViewRunId(e.target.value ? Number(e.target.value) : undefined)}
            title="Browse a past sweep — stored results are never lost or overwritten"
            className="bg-panel2 border border-edge rounded px-2 py-1 text-xs max-w-[460px]">
            <option value="">latest run</option>
            {runsList.map((r) => (
              <option key={r.id} value={r.id}>
                #{r.id} · {r.scope} · {r.window || 'max'} · {r.result_count} results · {r.status} · {dt(r.created_at)}
              </option>
            ))}
          </select>
          <a href={sweepExportUrl(viewRunId)} download className="btn">⬇ Export CSV</a>
          {viewRunId != null && <span className="text-[11px] text-amber-400/80">viewing a past run (read-only)</span>}
          <span className="ml-auto text-[11px] text-muted">stored sweeps are cached — reruns are instant & nothing is lost</span>
        </div>
      </div>

      {/* filters */}
      <div className="card p-3 flex items-end gap-4 flex-wrap">
        <Num label="Min win %" value={minWin} set={setMinWin} step={5} />
        <Num label="Min profit factor" value={minPF} set={setMinPF} step={0.1} />
        <Num label="Max drawdown %" value={maxDD} set={setMaxDD} step={5} />
        <Num label="Min return %" value={minRet === -1e9 ? 0 : minRet} set={setMinRet} step={5} />
        <label className="flex flex-col gap-0.5">
          <span className="stat-label">Timeframe</span>
          <select value={fInterval} onChange={(e) => setFInterval(e.target.value)}
            className="bg-panel2 border border-edge rounded px-2 py-1 text-xs">
            <option value="">all</option>
            {INTERVALS.map(([label, v]) => <option key={v} value={v}>{label}</option>)}
          </select>
        </label>
        <span className="ml-auto text-[11px] text-muted self-center flex items-center gap-2 flex-wrap justify-end">
          <span>{view.length} of {rows.length} shown</span>
          <span className="text-zinc-400">·</span>
          <span><b className="text-up">{winCount} win</b> / <b className="text-down">{lossCount} loss</b></span>
          <span className="text-zinc-400">·</span>
          <span>net <b className={pnlColor(totalNet)}>{signedInr(totalNet)}</b></span>
          {unaffordable > 0 && (<><span className="text-zinc-400">·</span>
            <span className="text-amber-400/80" title="can't afford 1 lot of the ATM option at your current budget — still shown, on your radar for later">{unaffordable} over budget</span></>)}
          {skipped > 0 && (<><span className="text-zinc-400">·</span>
            <span className="text-amber-400/80" title="cells excluded: insufficient history / out-of-range / errored / below filters">{skipped} skipped</span></>)}
        </span>
      </div>

      {/* results table */}
      <div className="card p-3 overflow-auto">
        <table className="w-full text-xs">
          <thead className="text-muted border-b border-edge">
            <tr>
              <Th k="instrument_key">Instrument</Th>
              <Th k="interval">TF</Th>
              <Th k="effective_days" right title="actual first→last candle span for THIS interval (clamped per Kite's per-timeframe ceiling) — never compare timeframes on different spans">Span</Th>
              <Th k="trades" right>Trades</Th>
              <Th k="win_rate" right>Win%</Th>
              <Th k="profit_factor" right>PF</Th>
              <Th k="max_drawdown_pct" right title="close-to-close drawdown (intra-trade excursion not modelled)">Max DD%</Th>
              <Th k="calmar" right title="CAGR ÷ max drawdown — return per unit of pain (higher = smoother)">Calmar</Th>
              <Th k="sharpe" right title="annualised Sharpe = (mean/std)×√(trades/year) — cross-timeframe comparable">Sharpe</Th>
              <Th k="time_underwater_pct" right title="% of the curve spent below its prior peak (lower = smoother)">U/W%</Th>
              <Th k="max_consec_losses" right title="longest losing streak (lower = smoother)">Streak</Th>
              <Th k="return_pct" right>Return%</Th>
              <Th k="bh_return_pct" right title="buy-and-hold return of the underlying over the same span — beat this to show real edge over beta">vs hold</Th>
              <Th k="net_pnl" right title="net P&L of a fixed 1-lot position over the whole span (real rupees)">Net P&L</Th>
              <Th k="notional" right title="capital to enter 1 lot of the underlying — the base the return is measured against">1-lot ₹</Th>
              <Th k="option_cost" right title="estimated cost to buy 1 lot of an ATM option (how you'd actually trade it) — green if it fits your budget">Option ₹</Th>
              <Th k="worst_trade_pnl" right title="single most-negative trade (tail risk at a glance)">Worst</Th>
              <th className="py-1 text-right">Add</th>
            </tr>
          </thead>
          <tbody>
            {view.length === 0 && (
              <tr><td colSpan={18} className="py-8 text-center text-muted">
                {running ? 'sweep running — results stream in…' : 'no results — run a sweep above'}</td></tr>
            )}
            {view.map((r) => {
              const optUnaff = r.affordable_options === false   // can't afford the OPTION at the current budget
              return (
              <tr key={r.id} onClick={() => setDrill(r)}
                className="border-t border-edge tabular-nums cursor-pointer hover:bg-panel2/50 [&>td]:py-1 [&>td]:pr-3">
                <td className="font-semibold text-zinc-100">{r.instrument_key}
                  {r.from_cache && <span className="badge bg-blue-500/15 text-blue-300 ml-1" title="reused from cache — not recomputed">cached</span>}
                  {optUnaff && <span className="badge bg-amber-500/20 text-amber-300 ml-1" title="can't afford 1 lot of the ATM option at your current budget — kept visible, on your radar for later">over budget</span>}</td>
                <td className="text-muted">{r.interval.replace('minute', 'm').replace('1m', '1D')}</td>
                <td className="text-right text-muted whitespace-nowrap" title={r.first_ts ? `${dt(new Date(r.first_ts * 1000).toISOString())} → ${dt(new Date(r.last_ts * 1000).toISOString())}` : ''}>
                  {spanLabel(r)}
                  {r.clamped && <span className="badge bg-amber-500/15 text-amber-300 ml-1" title="requested span exceeded Kite's per-timeframe ceiling — coverage was clamped">clamped</span>}
                </td>
                <td className="text-right">{r.trades}</td>
                <td className="text-right">{num(r.win_rate, 0)}</td>
                <td className="text-right">{r.profit_factor == null ? 'n/a' : num(r.profit_factor, 2)}</td>
                <td className="text-right text-down">{num(r.max_drawdown_pct, 1)}</td>
                <td className={`text-right ${(r.calmar ?? 0) >= 1 ? 'text-up' : 'text-zinc-300'}`}>{r.calmar == null ? '—' : num(r.calmar, 2)}</td>
                <td className="text-right text-muted">{r.sharpe == null ? '—' : num(r.sharpe, 2)}</td>
                <td className="text-right text-muted">{r.time_underwater_pct == null ? '—' : num(r.time_underwater_pct, 0)}</td>
                <td className="text-right text-muted">{r.max_consec_losses ?? '—'}</td>
                <td className={`text-right ${pnlColor(r.return_pct)}`}>{num(r.return_pct, 1)}</td>
                <td className={`text-right ${r.bh_return_pct == null ? 'text-muted' : pnlColor(r.bh_return_pct)}`}>{r.bh_return_pct == null ? '—' : num(r.bh_return_pct, 1)}</td>
                <td className={`text-right ${pnlColor(r.net_pnl)}`}>{signedInr(r.net_pnl)}</td>
                <td className="text-right text-muted">{r.notional ? inr(r.notional) : '—'}</td>
                <td className={`text-right ${optUnaff ? 'text-amber-300' : 'text-up/80'}`} title={optUnaff ? 'over your budget' : 'fits your budget'}>{r.option_cost ? inr(r.option_cost) : '—'}</td>
                <td className={`text-right ${r.worst_trade_pnl < 0 ? 'text-down' : 'text-muted'}`}>{!r.worst_trade_pnl ? '—' : signedInr(r.worst_trade_pnl)}</td>
                <td className="text-right">
                  <button onClick={(e) => { e.stopPropagation(); add(r) }}
                    className={`badge ${added.has(r.instrument_key) ? 'bg-up/20 text-up' : 'bg-zinc-700/40 text-muted hover:text-zinc-200'}`}>
                    {added.has(r.instrument_key) ? '✓ added' : '+ add'}
                  </button>
                </td>
              </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {drill && <Drill r={drill} onClose={() => setDrill(null)} onAdd={() => add(drill)}
        added={added.has(drill.instrument_key)} />}
    </div>
  )
}

function Drill({ r, onClose, onAdd, added }:
  { r: BTResult; onClose: () => void; onAdd: () => void; added: boolean }) {
  const [detail, setDetail] = useState<any>(null)
  useEffect(() => { getSweepResult(r.instrument_key, r.interval, r.run_id).then(setDetail) }, [r])
  const curve = (detail?.equity_curve || []).map((p: any) => ({ time: p.time, value: p.value }))
  // buy-and-hold overlay, re-based to the equity curve's start so both lines
  // share an index origin and the strategy's edge-vs-beta is visible.
  const bhRaw = (detail?.bh_curve || []) as { time: number; value: number }[]
  const startVal = curve[0]?.value ?? 0
  const bhBase = bhRaw[0]?.value ?? 0
  const bhCurve = (bhBase && startVal)
    ? bhRaw.map((p) => ({ time: p.time, value: (p.value / bhBase) * startVal }))
    : []
  const trades: BTTradeDTO[] = detail?.trades || []
  // the live engine runs 5m/15m/30m/60m candles (per-instrument); 1m & 1D are not live-tradable
  const liveTradable = ['5minute', '15minute', '30minute', '60minute'].includes(r.interval)

  // biggest winners / losers (by net P&L) — the worst N ACTUAL losers and best N
  // actual winners (BT-8 fix: a global bottom-3 slice could drop the 4th-worst
  // still-negative trade or include non-losers).
  const byPnl = [...trades].sort((a, b) => b.net_pnl - a.net_pnl)
  const winners = byPnl.filter((t) => t.net_pnl > 0).slice(0, 3)
  const losers = byPnl.filter((t) => t.net_pnl < 0).slice(-3).reverse()
  // actual history span the curve covers (lookback disclosure)
  const span = curve.length
    ? `${dt(new Date(curve[0].time * 1000).toISOString())} → ${dt(new Date(curve[curve.length - 1].time * 1000).toISOString())}`
    : ''

  const TradeRow = ({ t }: { t: BTTradeDTO }) => (
    <div className="flex items-center justify-between gap-2 tabular-nums">
      <span className="text-muted whitespace-nowrap">
        {dt(new Date(t.entry_time * 1000).toISOString())} <span className="opacity-50">→</span> {dt(new Date(t.exit_time * 1000).toISOString())}
      </span>
      <span className={t.direction === 'LONG' ? 'text-up' : 'text-down'}>{t.direction}</span>
      <span className={`font-semibold ${pnlColor(t.net_pnl)}`}>{signedInr(t.net_pnl)}</span>
    </div>
  )

  // Compact trades list for the LEFT column — each trade stacked so it fits a
  // narrow rail beside the rest of the analysis (newest first).
  const TradesList = () => (
    <div className="card p-3 flex flex-col min-h-0">
      <div className="stat-label mb-2 shrink-0">Trades ({trades.length}) — 1 lot each, net of charges</div>
      <div className="flex flex-col gap-1 overflow-auto pr-1">
        {!trades.length && <div className="py-4 text-center text-muted text-xs">loading trades…</div>}
        {trades.slice().reverse().map((t, i) => (
          <div key={i} className="border-b border-edge/60 pb-1 text-[11px] tabular-nums">
            <div className="flex items-center justify-between">
              <span className={t.direction === 'LONG' ? 'text-up' : 'text-down'}>{t.direction}</span>
              <span className={`font-semibold ${pnlColor(t.net_pnl)}`}>{signedInr(t.net_pnl)}</span>
            </div>
            <div className="flex items-center justify-between text-muted">
              <span className="whitespace-nowrap">{dt(new Date(t.entry_time * 1000).toISOString())} <span className="opacity-50">→</span> {dt(new Date(t.exit_time * 1000).toISOString())}</span>
            </div>
            <div className="flex items-center justify-between text-muted">
              <span>{num(t.entry_price, 1)} → {num(t.exit_price, 1)} · {t.qty}</span>
              <span className="opacity-70">{t.reason === 'OPEN_AT_END' ? 'open' : 'exit'}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )

  const optCost = r.option_cost ?? 0
  const budget = r.budget ?? 0

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="card w-full max-w-6xl p-4 flex flex-col gap-3 max-h-[92vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-lg font-semibold text-zinc-100">{r.name || r.instrument_key}</span>
            <span className="badge bg-zinc-700/40 text-muted">{r.interval}</span>
            <span className="badge bg-zinc-700/40 text-muted">{r.segment}</span>
          </div>
          <div className="flex gap-2">
            <button onClick={onAdd} className={`btn ${added ? 'text-up border-up/50' : 'border-up/50 text-up'}`}>
              {added ? '✓ in portfolio' : '+ add to portfolio'}
            </button>
            <button onClick={onClose} className="btn">✕ close</button>
          </div>
        </div>
        {span && (
          <div className="text-[11px] text-muted shrink-0">
            History tested: <b className="text-zinc-300">{span}</b> · {r.bars} bars · fixed <b className="text-zinc-300">1 lot</b>, additive (no compounding)
          </div>
        )}

        {/* Affordability — futures vs options, against your real budget */}
        <div className="flex items-center gap-2 flex-wrap text-[11px] shrink-0">
          <span className="badge bg-zinc-700/40 text-muted" title="capital to hold 1 lot of the underlying (the return base)">
            1-lot capital {r.notional ? inr(r.notional) : '—'}
          </span>
          <span className={`badge ${r.affordable_futures ? 'bg-up/15 text-up' : 'bg-zinc-700/40 text-muted'}`}
            title="can you afford one lot of the FUTURE at your current budget?">
            futures {r.affordable_futures ? 'affordable' : 'over budget'}
          </span>
          <span className={`badge ${r.affordable_options ? 'bg-up/15 text-up' : 'bg-amber-500/20 text-amber-300'}`}
            title="estimated cost to buy 1 lot of an ATM option (BS at realised vol) vs your budget — this is how you'd actually trade it">
            options ≈ {optCost ? inr(optCost) : '—'} {r.affordable_options ? '· affordable now' : '· over budget'}
          </span>
          {budget > 0 && <span className="text-muted">budget {inr(budget)}</span>}
        </div>

        {!liveTradable && (
          <div className="text-[11px] text-amber-400/90 bg-amber-400/10 rounded px-2 py-1 shrink-0">
            Note: the live engine runs 5m / 15m / 30m / 60m candles (set per instrument on the Watchlist page).
            This {r.interval} edge is informational — adding pins it to the watchlist and trades it on the
            configured live interval.
          </div>
        )}

        {/* LEFT: the trades list as its own column · RIGHT: metrics + winners/losers + curve */}
        <div className="grid gap-3 min-h-0 flex-1" style={{ gridTemplateColumns: 'minmax(230px, 280px) minmax(0,1fr)' }}>
          <TradesList />

          <div className="flex flex-col gap-3 min-h-0 overflow-auto pr-1">
            <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(110px,1fr))' }}>
              <Mini label="Trades" v={r.open_at_end ? `${r.trades} (incl. 1 open)` : String(r.trades)} />
              <Mini label="Win rate" v={num(r.win_rate, 0) + '%'} />
              <Mini label="Win rate (realised)" v={r.open_at_end ? num(r.win_rate_realised, 0) + '%' : num(r.win_rate, 0) + '%'}
                cls={r.open_at_end ? 'text-amber-300' : ''} />
              <Mini label="Profit factor" v={r.profit_factor == null ? 'n/a' : num(r.profit_factor, 2)} />
              <Mini label="Return (on 1-lot capital)" v={num(r.return_pct, 1) + '%'} cls={pnlColor(r.return_pct)} />
              <Mini label="Return (realised)" v={r.open_at_end ? num(r.return_pct_realised, 1) + '%' : num(r.return_pct, 1) + '%'}
                cls={r.open_at_end ? 'text-amber-300' : pnlColor(r.return_pct_realised)} />
              <Mini label="vs buy & hold" v={r.bh_return_pct == null ? '—' : num(r.bh_return_pct, 1) + '%'}
                cls={r.bh_return_pct == null ? '' : pnlColor(r.bh_return_pct)} />
              <Mini label="Max DD (close-to-close)" v={num(r.max_drawdown_pct, 1) + '%'} cls="text-down" />
              <Mini label="Worst MAE (intra-trade)" v={r.worst_mae_pct == null ? '—' : num(r.worst_mae_pct, 1) + '%'} cls="text-down" />
              <Mini label="Calmar" v={r.calmar == null ? '—' : num(r.calmar, 2)} cls={(r.calmar ?? 0) >= 1 ? 'text-up' : ''} />
              <Mini label="Consistency (per-trade)" v={r.consistency == null ? '—' : num(r.consistency, 2)} />
              <Mini label="Sharpe (annualised)" v={r.sharpe == null ? '—' : num(r.sharpe, 2)} />
              <Mini label="Underwater" v={r.time_underwater_pct == null ? '—' : num(r.time_underwater_pct, 0) + '%'} />
              <Mini label="Loss streak" v={r.max_consec_losses == null ? '—' : String(r.max_consec_losses)} />
              <Mini label="Net P&L (1 lot)" v={signedInr(r.net_pnl)} cls={pnlColor(r.net_pnl)} />
              <Mini label="Worst trade" v={r.worst_trade_pnl ? signedInr(r.worst_trade_pnl) : '—'} cls={r.worst_trade_pnl < 0 ? 'text-down' : ''} />
              <Mini label="Charges" v={inr(r.charges)} cls="text-down" />
              <Mini label="CAGR" v={r.cagr == null ? '—' : num(r.cagr, 1) + '%'} />
            </div>

            {(winners.length > 0 || losers.length > 0) && (
              <div className="grid gap-3" style={{ gridTemplateColumns: '1fr 1fr' }}>
                <div className="card p-3">
                  <div className="stat-label mb-1 text-up">Biggest winners (1 lot)</div>
                  <div className="flex flex-col gap-1 text-xs">
                    {winners.length ? winners.map((t, i) => <TradeRow key={i} t={t} />)
                      : <span className="text-muted">none</span>}
                  </div>
                </div>
                <div className="card p-3">
                  <div className="stat-label mb-1 text-down">Biggest losers (1 lot)</div>
                  <div className="flex flex-col gap-1 text-xs">
                    {losers.length ? losers.map((t, i) => <TradeRow key={i} t={t} />)
                      : <span className="text-muted">none</span>}
                  </div>
                </div>
              </div>
            )}

            <div className="card p-3">
              <div className="stat-label mb-1 flex items-center gap-3 flex-wrap">
                <span>Equity curve — ₹ from a fixed 1-lot position (base + cumulative net P&amp;L), net of charges</span>
                {bhCurve.length > 1 && (
                  <span className="flex items-center gap-3 normal-case text-[10px]">
                    <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5" style={{ background: colorFor(r.instrument_key) }} /> strategy</span>
                    <span className="flex items-center gap-1"><span className="inline-block w-3 h-0.5 bg-[#8b93a7]" /> buy &amp; hold</span>
                  </span>
                )}
              </div>
              {curve.length
                ? (bhCurve.length > 1
                    ? <MultiLineChart height={240} series={[
                        { name: 'strategy', data: curve, color: colorFor(r.instrument_key) },
                        { name: 'buy & hold', data: bhCurve, color: '#8b93a7' },
                      ]} />
                    : <LineChart data={curve} height={240} color={colorFor(r.instrument_key)}
                        priceLines={[{ price: curve[0]?.value ?? startVal, color: '#8b93a7', title: 'start' }]} />)
                : <div className="text-muted text-xs py-10 text-center">loading…</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function Mini({ label, v, cls = '' }: { label: string; v: string; cls?: string }) {
  return <div className="card p-2"><div className="stat-label">{label}</div>
    <div className={`text-sm font-semibold tabular-nums ${cls}`}>{v}</div></div>
}
