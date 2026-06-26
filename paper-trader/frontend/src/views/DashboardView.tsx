import { useEffect, useState } from 'react'
import { useLive } from '../state/LiveContext'
import { getDashboard, getAccountPnl, getStrategies } from '../lib/api'
import InstrumentDetailModal from './InstrumentDetailModal'
import { LineChart, MultiLineChart } from '../components/Charts'
import { inr, signedInr, pnlColor, num, dt } from '../lib/format'
import { colorFor } from '../lib/constants'
import type { TradeDTO, StrategyMeta } from '../lib/types'

type Seg = 'all' | 'options' | 'equity_intraday'
const SEG_TABS: [Seg, string][] = [
  ['all', 'Portfolio'], ['options', 'Options'], ['equity_intraday', 'Outrights'],
]

function Legend({ series }: { series: { name: string; color: string }[] }) {
  if (!series.length) return null
  return (
    <div className="flex flex-wrap gap-3 mt-2">
      {series.map((c) => (
        <span key={c.name} className="flex items-center gap-1 text-[11px] text-muted">
          <span className="w-3 h-0.5 inline-block" style={{ background: c.color }} />{c.name}
        </span>
      ))}
    </div>
  )
}

function Card({ label, v, cls = '', sub }: { label: string; v: string; cls?: string; sub?: string }) {
  return (
    <div className="card p-3">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${cls}`}>{v}</div>
      {sub && <div className="text-[11px] text-muted mt-0.5">{sub}</div>}
    </div>
  )
}

function BotVsYou() {
  const [a, setA] = useState<any>(null)
  useEffect(() => {
    const f = () => getAccountPnl().then(setA).catch(() => {})
    f(); const t = setInterval(f, 5000); return () => clearInterval(t)
  }, [])
  if (!a || !a.available) return null   // live account only
  return (
    <div className="card p-3 grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(150px,1fr))' }}>
      <div className="stat-label col-span-full">Bot vs You — your real Kite account, since the bot's baseline</div>
      <Card label="Account equity" v={inr(a.account_equity)} />
      <Card label="Account change" v={signedInr(a.account_change)} cls={pnlColor(a.account_change)} />
      <Card label="Bot P&L (tracked)" v={signedInr(a.bot_pnl)} cls={pnlColor(a.bot_pnl)} sub="what the bot did" />
      <Card label="Your P&L (unrecorded)" v={signedInr(a.your_pnl_unrecorded)} cls={pnlColor(a.your_pnl_unrecorded)} sub="your own trades" />
    </div>
  )
}

export default function DashboardView() {
  const { state } = useLive()
  const [d, setD] = useState<any>(null)
  const [seg, setSeg] = useState<Seg>('all')
  const [strat, setStrat] = useState<string>('')   // '' = all strategies
  const [strategies, setStrategies] = useState<StrategyMeta[]>([])
  const [period, setPeriod] = useState<'all' | 'today' | '7d' | '30d'>('all')
  const [detailKey, setDetailKey] = useState<string | null>(null)
  useEffect(() => { getStrategies().then((x) => setStrategies(x.strategies || [])).catch(() => {}) }, [])
  useEffect(() => {
    const load = () => getDashboard(seg === 'all' ? undefined : seg, strat || undefined, period).then(setD)
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [seg, strat, period])

  const stratLabel = (k: string) => strategies.find((x) => x.key === k)?.display_name || k

  if (!d) return <div className="card p-8 text-center text-muted">loading analytics…</div>
  const s = d.summary, cap = d.capital
  const isLive = (state?.provider || 'mock') === 'kite'
  // charge drag: how much of the gross edge is eaten by commissions
  const grossMag = Math.abs(s.gross_pnl) || 1
  const chargeDrag = (s.charges / grossMag) * 100
  const avgCharge = s.trades ? s.charges / s.trades : 0
  // unfiltered curve is MTM ({time,equity}); a filtered slice is realized ({time,value})
  const equity = (d.equity_curve || []).map((x: any) => ({ time: x.time, value: x.equity ?? x.value }))
  const curves = Object.entries(d.instrument_curves || {})
    .map(([k, v]) => ({ name: k, data: v as any[], color: colorFor(k) }))
  const perInst = Object.entries(s.per_instrument || {})
    .sort((a: any, b: any) => b[1].net - a[1].net) as [string, any][]
  // per-segment + per-strategy realized overlays (Phase 4)
  const segCurves = Object.entries(d.segment_curves || {})
    .filter(([, v]) => (v as any[]).length)
    .map(([k, v]) => ({ name: k === 'equity_intraday' ? 'Outrights' : 'Options', data: v as any[], color: colorFor(k) }))
  const strategyCurves = Object.entries(d.strategy_curves || {})
    .filter(([, v]) => (v as any[]).length)
    .map(([k, v]) => ({ name: stratLabel(k), data: v as any[], color: colorFor(k) }))
  const segName = SEG_TABS.find(([k]) => k === seg)?.[1] || 'Portfolio'

  return (
    <div className="flex flex-col gap-3">
      <BotVsYou />
      {/* segment + strategy selector — slice the whole dashboard */}
      <div className="card p-3 flex items-center gap-2 flex-wrap">
        <span className="stat-label mr-1">View</span>
        {SEG_TABS.map(([k, label]) => (
          <button key={k} onClick={() => setSeg(k)}
            className={`badge ${seg === k ? 'bg-purple-500/25 text-purple-200 border border-purple-400/40' : 'bg-zinc-700/40 text-muted hover:text-zinc-200'}`}>
            {label}
          </button>
        ))}
        <span className="stat-label mx-1">Strategy</span>
        <select value={strat} onChange={(e) => setStrat(e.target.value)}
          className="bg-panel2 border border-edge rounded px-2 py-1 text-xs">
          <option value="">all strategies</option>
          {strategies.map((x) => <option key={x.key} value={x.key}>{x.display_name}</option>)}
        </select>
        <span className="stat-label mx-1">Period</span>
        {(['all', 'today', '7d', '30d'] as const).map((p) => (
          <button key={p} onClick={() => setPeriod(p)}
            className={`badge ${period === p ? 'bg-purple-500/25 text-purple-200 border border-purple-400/40' : 'bg-zinc-700/40 text-muted hover:text-zinc-200'}`}>
            {p === 'all' ? 'All-time' : p}
          </button>
        ))}
        <span className="ml-auto text-[11px] text-muted">
          showing <b className="text-zinc-300">{segName}</b>{strat ? ` · ${stratLabel(strat)}` : ''} — net of all costs
        </span>
      </div>
      {/* capital + headline stats */}
      <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(130px,1fr))' }}>
        <Card label="Equity (MTM)" v={inr(cap.equity)} />
        <Card label="Cash" v={inr(cap.cash)} />
        <Card label="Realized P&L" v={signedInr(cap.realized_pnl)} cls={pnlColor(cap.realized_pnl)} />
        <Card label="Net P&L" v={signedInr(s.net_pnl)} cls={pnlColor(s.net_pnl)} sub={`gross ${signedInr(s.gross_pnl)}`} />
        <Card label="Win rate" v={s.trades ? s.win_rate + '%' : '—'} sub={`${s.wins}W / ${s.losses}L`} />
        <Card label="Expectancy" v={s.trades ? signedInr(s.expectancy) : '—'} cls={pnlColor(s.expectancy)} sub="per trade" />
        <Card label="Trades" v={String(s.trades)} sub={`${cap.open_count} open`} />
        <Card label="Charges paid" v={inr(s.charges)} cls="text-down" />
      </div>

      {/* commissions / cost-honesty strip — net is always after the full charge stack */}
      <div className="card p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="stat-label">Commissions &amp; cost — all figures are NET of brokerage, STT/CTT, exchange, SEBI, GST &amp; stamp</div>
          <span className="text-[11px] text-muted">no smooth-curve self-deception</span>
        </div>
        <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(130px,1fr))' }}>
          <Card label="Gross P&L" v={signedInr(s.gross_pnl)} cls={pnlColor(s.gross_pnl)} sub="before charges" />
          <Card label="Charges paid" v={inr(s.charges)} cls="text-down" sub={`avg ${inr(avgCharge)}/trade`} />
          <Card label="Net P&L" v={signedInr(s.net_pnl)} cls={pnlColor(s.net_pnl)} sub="after charges" />
          <Card label="Charge drag" v={s.trades ? num(chargeDrag, 1) + '%' : '—'} cls="text-down" sub="of gross edge" />
        </div>
      </div>

      <div className="grid gap-3" style={{ gridTemplateColumns: 'minmax(0,1.4fr) minmax(0,1fr)' }}>
        {/* equity / realized curve for the current selection */}
        <div className="card p-3">
          <div className="stat-label mb-1">
            {seg === 'all' && !strat ? 'Portfolio equity curve (mark-to-market)'
              : `${segName}${strat ? ` · ${stratLabel(strat)}` : ''} — cumulative realized P&L`}
          </div>
          {equity.length ? <LineChart data={equity} height={260} color="#2ebd85"
            priceLines={[{ price: seg === 'all' && !strat ? cap.initial : 0, color: '#8b93a7', title: 'start' }]} />
            : <div className="text-muted text-xs py-10 text-center">no data yet for this view</div>}
        </div>
        {/* avg win/loss + best/worst */}
        <div className="card p-3 flex flex-col gap-3">
          <div className="grid grid-cols-2 gap-3">
            <Card label="Avg win" v={signedInr(s.avg_win)} cls="text-up" />
            <Card label="Avg loss" v={signedInr(s.avg_loss)} cls="text-down" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Card label="Best instrument" v={s.best || '—'} cls="text-up" />
            <Card label="Worst instrument" v={s.worst || '—'} cls="text-down" />
          </div>
          <div className="text-[11px] text-muted">
            Initial capital {inr(cap.initial)} · invested {inr(cap.invested)} ·{' '}
            {isLive
              ? 'live Kite market data — paper fills only, net of the full Zerodha charge stack.'
              : 'provider mock = synthetic data (dev stand-in, not indicative of real performance).'}
          </div>
        </div>
      </div>

      {/* portfolio split: options vs outrights (cumulative realized) */}
      <div className="grid gap-3" style={{ gridTemplateColumns: 'minmax(0,1fr) minmax(0,1fr)' }}>
        <div className="card p-3">
          <div className="stat-label mb-1">By segment — Options vs Outrights (cumulative realized P&L)</div>
          {segCurves.length ? <MultiLineChart series={segCurves} height={240} />
            : <div className="text-muted text-xs py-10 text-center">no closed trades yet</div>}
          <Legend series={segCurves} />
        </div>
        <div className="card p-3">
          <div className="stat-label mb-1">
            By strategy{seg !== 'all' ? ` · within ${segName}` : ''} (cumulative realized P&L)
          </div>
          {strategyCurves.length ? <MultiLineChart series={strategyCurves} height={240} />
            : <div className="text-muted text-xs py-10 text-center">no closed trades yet</div>}
          <Legend series={strategyCurves} />
        </div>
      </div>

      {/* per-instrument equity curves */}
      <div className="card p-3">
        <div className="stat-label mb-1">Per-instrument equity curves (cumulative realized P&L)</div>
        {curves.length ? <MultiLineChart series={curves} height={280} />
          : <div className="text-muted text-xs py-10 text-center">no closed trades yet</div>}
        <Legend series={curves} />
      </div>

      <div className="grid gap-3" style={{ gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.3fr)' }}>
        {/* per-instrument table */}
        <div className="card p-3 overflow-auto">
          <div className="stat-label mb-2">Per-instrument performance</div>
          <table className="w-full text-xs">
            <thead className="text-muted text-left"><tr className="[&>th]:py-1 [&>th]:pr-3">
              <th>Instrument</th><th>Trades</th><th>Win%</th><th>Net P&L</th></tr></thead>
            <tbody>
              {perInst.length === 0 && <tr><td colSpan={4} className="py-4 text-center text-muted">—</td></tr>}
              {perInst.map(([k, v]) => (
                <tr key={k} onClick={() => setDetailKey(k)}
                  className="border-t border-edge [&>td]:py-1 [&>td]:pr-3 tabular-nums cursor-pointer hover:bg-panel2/50">
                  <td className="font-semibold text-zinc-100">{k}</td>
                  <td>{v.trades}</td>
                  <td>{v.win_rate}%</td>
                  <td className={pnlColor(v.net)}>{signedInr(v.net)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* recent trades */}
        <div className="card p-3 overflow-auto">
          <div className="stat-label mb-2">Recent trades — 📝 paper vs 🔴 real are tagged per row</div>
          <table className="w-full text-xs">
            <thead className="text-muted text-left"><tr className="[&>th]:py-1 [&>th]:pr-3">
              <th>Exit</th><th>Ledger</th><th>Instrument</th><th>Contract</th><th>Dir</th><th>Reason</th><th>Ret%</th><th>Net</th></tr></thead>
            <tbody>
              {(d.recent_trades || []).length === 0 && <tr><td colSpan={8} className="py-4 text-center text-muted">no trades yet</td></tr>}
              {(d.recent_trades || []).map((t: TradeDTO) => (
                <tr key={t.id} className="border-t border-edge [&>td]:py-1 [&>td]:pr-3 tabular-nums">
                  <td className="text-muted">{dt(t.exit_time)}</td>
                  <td>
                    <span className={`badge ${t.mode === 'live' ? 'bg-down/20 text-down' : 'bg-emerald-500/15 text-emerald-300'}`}>
                      {t.mode === 'live' ? 'REAL' : 'PAPER'}</span>
                  </td>
                  <td className="font-semibold">{t.instrument_key}</td>
                  <td className="font-mono text-[10px]">{t.tradingsymbol}</td>
                  <td className={t.direction === 'LONG' ? 'text-up' : 'text-down'}>{t.option_type}</td>
                  <td className="text-muted">{t.exit_reason}</td>
                  <td className={pnlColor(t.return_pct)}>{num(t.return_pct, 1)}</td>
                  <td className={pnlColor(t.net_pnl)}>{signedInr(t.net_pnl)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {detailKey && (
        <InstrumentDetailModal instrumentKey={detailKey}
          segment={seg === 'all' ? undefined : seg} strategy={strat || undefined} period={period}
          onClose={() => setDetailKey(null)} />
      )}
    </div>
  )
}
