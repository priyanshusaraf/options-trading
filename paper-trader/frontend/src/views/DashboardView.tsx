import { useEffect, useState } from 'react'
import { useLive } from '../state/LiveContext'
import { getDashboard, getAccountPnl } from '../lib/api'
import { LineChart, MultiLineChart } from '../components/Charts'
import { inr, signedInr, pnlColor, num, dt } from '../lib/format'
import { colorFor } from '../lib/constants'
import type { TradeDTO } from '../lib/types'

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
  useEffect(() => {
    const load = () => getDashboard().then(setD)
    load()
    const t = setInterval(load, 5000)
    return () => clearInterval(t)
  }, [])

  if (!d) return <div className="card p-8 text-center text-muted">loading analytics…</div>
  const s = d.summary, cap = d.capital
  const isLive = (state?.provider || 'mock') === 'kite'
  // charge drag: how much of the gross edge is eaten by commissions
  const grossMag = Math.abs(s.gross_pnl) || 1
  const chargeDrag = (s.charges / grossMag) * 100
  const avgCharge = s.trades ? s.charges / s.trades : 0
  const equity = (d.equity_curve || []).map((x: any) => ({ time: x.time, value: x.equity }))
  const curves = Object.entries(d.instrument_curves || {})
    .map(([k, v]) => ({ name: k, data: v as any[], color: colorFor(k) }))
  const perInst = Object.entries(s.per_instrument || {})
    .sort((a: any, b: any) => b[1].net - a[1].net) as [string, any][]

  return (
    <div className="flex flex-col gap-3">
      <BotVsYou />
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
        {/* portfolio equity curve */}
        <div className="card p-3">
          <div className="stat-label mb-1">Portfolio equity curve</div>
          {equity.length ? <LineChart data={equity} height={260} color="#2ebd85"
            priceLines={[{ price: cap.initial, color: '#8b93a7', title: 'start' }]} />
            : <div className="text-muted text-xs py-10 text-center">no snapshots yet</div>}
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

      {/* per-instrument equity curves */}
      <div className="card p-3">
        <div className="stat-label mb-1">Per-instrument equity curves (cumulative realized P&L)</div>
        {curves.length ? <MultiLineChart series={curves} height={280} />
          : <div className="text-muted text-xs py-10 text-center">no closed trades yet</div>}
        <div className="flex flex-wrap gap-3 mt-2">
          {curves.map((c) => (
            <span key={c.name} className="flex items-center gap-1 text-[11px] text-muted">
              <span className="w-3 h-0.5 inline-block" style={{ background: c.color }} />{c.name}
            </span>
          ))}
        </div>
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
                <tr key={k} className="border-t border-edge [&>td]:py-1 [&>td]:pr-3 tabular-nums">
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
          <div className="stat-label mb-2">Recent trades</div>
          <table className="w-full text-xs">
            <thead className="text-muted text-left"><tr className="[&>th]:py-1 [&>th]:pr-3">
              <th>Exit</th><th>Instrument</th><th>Contract</th><th>Dir</th><th>Reason</th><th>Ret%</th><th>Net</th></tr></thead>
            <tbody>
              {(d.recent_trades || []).length === 0 && <tr><td colSpan={7} className="py-4 text-center text-muted">no trades yet</td></tr>}
              {(d.recent_trades || []).map((t: TradeDTO) => (
                <tr key={t.id} className="border-t border-edge [&>td]:py-1 [&>td]:pr-3 tabular-nums">
                  <td className="text-muted">{dt(t.exit_time)}</td>
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
    </div>
  )
}
