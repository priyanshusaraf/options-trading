import { useEffect, useState } from 'react'
import { LineChart } from '../components/Charts'
import {
  startSweep, getSweepStatus, getSweepResults, getSweepResult,
  addToPortfolio, getSweepRuns, sweepExportUrl,
} from '../lib/api'
import { inr, signedInr, pnlColor, num, dt } from '../lib/format'
import { colorFor } from '../lib/constants'
import type { BacktestRun, BTResult, BTTradeDTO } from '../lib/types'

// display label -> Kite interval name
const INTERVALS: [string, string][] = [
  ['1m', 'minute'], ['5m', '5minute'], ['15m', '15minute'],
  ['30m', '30minute'], ['1h', '60minute'], ['1D', 'day'],
]
const LIVE_INTERVALS = new Set(['15minute', '30minute'])

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
  const [drill, setDrill] = useState<BTResult | null>(null)
  const [added, setAdded] = useState<Set<string>>(new Set())
  // browse history: null = latest run
  const [runsList, setRunsList] = useState<any[]>([])
  const [viewRunId, setViewRunId] = useState<number | undefined>(undefined)

  // filters (client-side for snappy UX)
  const [minWin, setMinWin] = useState(0)
  const [minPF, setMinPF] = useState(0)
  const [maxDD, setMaxDD] = useState(100)
  const [minRet, setMinRet] = useState(-1e9)
  const [fInterval, setFInterval] = useState('')
  const [sort, setSort] = useState<keyof BTResult>('return_pct')

  const loadResults = () => getSweepResults({ min_trades: 1, run_id: viewRunId })
    .then((d) => setRows(d.results || []))
  const loadRuns = () => getSweepRuns().then((d) => setRunsList(d.runs || []))

  useEffect(() => {
    getSweepStatus().then((d) => { setRun(d.run); setRunning(d.running) })
    loadRuns()
  }, [])

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

  const launch = async () => {
    const intervals = INTERVALS.map(([, v]) => v).filter((v) => picked.has(v))
    if (!intervals.length) return
    const r = await startSweep(scope, intervals, 50000)
    if (r.error) { alert(r.error); return }
    setViewRunId(undefined)   // show the new (latest) run as it streams in
    setRunning(true)
    getSweepStatus(r.run_id).then((d) => setRun(d.run))
  }

  const add = async (r: BTResult) => {
    // carry the winning timeframe into the live instrument when supported
    const res = await addToPortfolio(r.instrument_key, true, r.interval)
    if (res.error) { alert(res.error); return }
    if (res.interval_warning) alert(res.interval_warning)
    setAdded((s) => new Set(s).add(r.instrument_key))
  }

  // apply filters + sort
  const view = rows
    .filter((r) => !r.error && r.win_rate >= minWin
      && (r.profit_factor == null || r.profit_factor >= minPF)
      && r.max_drawdown_pct <= maxDD && r.return_pct >= minRet
      && (!fInterval || r.interval === fInterval))
    .sort((a, b) => {
      const av = (a[sort] ?? -1e18) as number, bv = (b[sort] ?? -1e18) as number
      return sort === 'max_drawdown_pct' ? av - bv : bv - av
    })

  const Th = ({ k, children, right }: { k?: keyof BTResult; children: any; right?: boolean }) => (
    <th onClick={() => k && setSort(k)}
      className={`py-1 pr-3 ${right ? 'text-right' : 'text-left'} ${k ? 'cursor-pointer hover:text-zinc-200' : ''} ${sort === k ? 'text-zinc-100' : ''}`}>
      {children}{sort === k ? ' ▾' : ''}
    </th>
  )

  return (
    <div className="flex flex-col gap-3">
      {/* sweep controls */}
      <div className="card p-3 flex flex-col gap-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="stat-label">Strategy sweep — EMA50 + z-score on the underlying, net of all charges</div>
          <span className="text-[11px] text-muted">1 lot · ₹50,000 base · pure-strategy exits</span>
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
            className="bg-panel2 border border-edge rounded px-2 py-1 text-xs max-w-[420px]">
            <option value="">latest run</option>
            {runsList.map((r) => (
              <option key={r.id} value={r.id}>
                #{r.id} · {r.scope} · {r.result_count} results · {r.status} · {dt(r.created_at)}
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
        <span className="ml-auto text-[11px] text-muted self-center">{view.length} of {rows.length} results</span>
      </div>

      {/* results table */}
      <div className="card p-3 overflow-auto">
        <table className="w-full text-xs">
          <thead className="text-muted border-b border-edge">
            <tr>
              <Th k="instrument_key">Instrument</Th>
              <Th k="interval">TF</Th>
              <Th k="trades" right>Trades</Th>
              <Th k="win_rate" right>Win%</Th>
              <Th k="profit_factor" right>PF</Th>
              <Th k="max_drawdown_pct" right>Max DD%</Th>
              <Th k="return_pct" right>Return%</Th>
              <Th k="net_pnl" right>Net P&L</Th>
              <Th k="charges" right>Charges</Th>
              <th className="py-1 text-right">Add</th>
            </tr>
          </thead>
          <tbody>
            {view.length === 0 && (
              <tr><td colSpan={10} className="py-8 text-center text-muted">
                {running ? 'sweep running — results stream in…' : 'no results — run a sweep above'}</td></tr>
            )}
            {view.map((r) => (
              <tr key={r.id} onClick={() => setDrill(r)}
                className="border-t border-edge tabular-nums cursor-pointer hover:bg-panel2/50 [&>td]:py-1 [&>td]:pr-3">
                <td className="font-semibold text-zinc-100">{r.instrument_key}
                  {r.from_cache && <span className="badge bg-blue-500/15 text-blue-300 ml-1" title="reused from cache — not recomputed">cached</span>}</td>
                <td className="text-muted">{r.interval.replace('minute', 'm').replace('1m', '1D')}</td>
                <td className="text-right">{r.trades}</td>
                <td className="text-right">{num(r.win_rate, 0)}</td>
                <td className="text-right">{r.profit_factor == null ? '∞' : num(r.profit_factor, 2)}</td>
                <td className="text-right text-down">{num(r.max_drawdown_pct, 1)}</td>
                <td className={`text-right ${pnlColor(r.return_pct)}`}>{num(r.return_pct, 1)}</td>
                <td className={`text-right ${pnlColor(r.net_pnl)}`}>{signedInr(r.net_pnl)}</td>
                <td className="text-right text-down">{inr(r.charges)}</td>
                <td className="text-right">
                  <button onClick={(e) => { e.stopPropagation(); add(r) }}
                    className={`badge ${added.has(r.instrument_key) ? 'bg-up/20 text-up' : 'bg-zinc-700/40 text-muted hover:text-zinc-200'}`}>
                    {added.has(r.instrument_key) ? '✓ added' : '+ add'}
                  </button>
                </td>
              </tr>
            ))}
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
  const trades: BTTradeDTO[] = detail?.trades || []
  const liveTradable = r.interval === '15minute' || r.interval === '30minute'

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="card w-full max-w-5xl p-4 flex flex-col gap-3 max-h-[92vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
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
        {!liveTradable && (
          <div className="text-[11px] text-amber-400/90 bg-amber-400/10 rounded px-2 py-1">
            Note: the live engine trades only 15m/30m. This {r.interval} edge is informational —
            adding pins it to the homepage and trades it on the configured live interval.
          </div>
        )}

        <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(110px,1fr))' }}>
          <Mini label="Trades" v={String(r.trades)} />
          <Mini label="Win rate" v={num(r.win_rate, 0) + '%'} />
          <Mini label="Profit factor" v={r.profit_factor == null ? '∞' : num(r.profit_factor, 2)} />
          <Mini label="Return" v={num(r.return_pct, 1) + '%'} cls={pnlColor(r.return_pct)} />
          <Mini label="Max DD" v={num(r.max_drawdown_pct, 1) + '%'} cls="text-down" />
          <Mini label="Net P&L" v={signedInr(r.net_pnl)} cls={pnlColor(r.net_pnl)} />
          <Mini label="Gross P&L" v={signedInr(r.gross_pnl)} />
          <Mini label="Charges" v={inr(r.charges)} cls="text-down" />
          <Mini label="CAGR" v={r.cagr == null ? '—' : num(r.cagr, 1) + '%'} />
        </div>

        <div className="card p-3">
          <div className="stat-label mb-1">Equity curve (₹50,000 base · net of charges)</div>
          {curve.length ? <LineChart data={curve} height={260} color={colorFor(r.instrument_key)}
            priceLines={[{ price: 50000, color: '#8b93a7', title: 'start' }]} />
            : <div className="text-muted text-xs py-10 text-center">loading…</div>}
        </div>

        <div className="card p-3 overflow-auto">
          <div className="stat-label mb-2">Trades ({trades.length})</div>
          <table className="w-full text-xs">
            <thead className="text-muted text-left border-b border-edge">
              <tr className="[&>th]:py-1 [&>th]:pr-3">
                <th>Entry</th><th>Exit</th><th>Dir</th><th>Entry₹</th><th>Exit₹</th>
                <th>Qty</th><th>Net</th><th>Charges</th><th>Reason</th></tr>
            </thead>
            <tbody>
              {trades.slice().reverse().map((t, i) => (
                <tr key={i} className="border-t border-edge tabular-nums [&>td]:py-1 [&>td]:pr-3">
                  <td className="text-muted">{dt(new Date(t.entry_time * 1000).toISOString())}</td>
                  <td className="text-muted">{dt(new Date(t.exit_time * 1000).toISOString())}</td>
                  <td className={t.direction === 'LONG' ? 'text-up' : 'text-down'}>{t.direction}</td>
                  <td>{num(t.entry_price, 2)}</td>
                  <td>{num(t.exit_price, 2)}</td>
                  <td>{t.qty}</td>
                  <td className={pnlColor(t.net_pnl)}>{signedInr(t.net_pnl)}</td>
                  <td className="text-down">{inr(t.charges)}</td>
                  <td className="text-muted">{t.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function Mini({ label, v, cls = '' }: { label: string; v: string; cls?: string }) {
  return <div className="card p-2"><div className="stat-label">{label}</div>
    <div className={`text-sm font-semibold tabular-nums ${cls}`}>{v}</div></div>
}
