import { useEffect, useState } from 'react'
import { useLive } from '../state/LiveContext'
import { getStatus, getExecState, armBot, killBot } from '../lib/api'
import { inr, signedInr, pnlColor } from '../lib/format'

function Stat({ label, v, cls = '' }: { label: string; v: string; cls?: string }) {
  return <div className="text-right"><div className="stat-label">{label}</div>
    <div className={`text-sm font-semibold tabular-nums ${cls}`}>{v}</div></div>
}

function ExecutionControls() {
  const [armed, setArmed] = useState<boolean | null>(null)
  const [busy, setBusy] = useState(false)
  const refresh = () => getExecState().then((s) => setArmed(s.armed)).catch(() => {})
  useEffect(() => { refresh(); const t = setInterval(refresh, 5000); return () => clearInterval(t) }, [])
  const toggle = async () => { setBusy(true); const s = await armBot(!armed); setArmed(s.armed); setBusy(false) }
  const kill = async () => {
    if (!window.confirm('KILL SWITCH — disarm the bot and square off ALL open positions at market right now?')) return
    setBusy(true)
    const res = await killBot()
    setArmed(false); setBusy(false)
    const done = (res?.squared_off || []) as string[]
    window.alert(`Kill switch fired — bot disarmed.\nSquared off ${done.length} position(s)${done.length ? ': ' + done.join(', ') : ''}.\nVerify Active Positions shows none remaining.`)
  }
  return (
    <div className="flex items-center gap-1.5">
      <button disabled={busy} onClick={toggle}
        title="Armed = the bot may auto-execute trades. Disarmed = it watches & alerts but opens nothing."
        className={`btn ${armed ? 'border-up/60 text-up bg-up/10' : 'border-amber-400/60 text-amber-400'}`}>
        {armed === null ? '…' : armed ? '● ARMED' : '○ ARM TO TRADE'}
      </button>
      <button disabled={busy} onClick={kill}
        title="Emergency stop: disarm and square off everything now"
        className="btn border-down/60 text-down hover:bg-down/15">⛔ KILL</button>
    </div>
  )
}

function ArmBanner() {
  const [armed, setArmed] = useState<boolean | null>(null)
  useEffect(() => {
    const f = () => getExecState().then((s) => {
      setArmed(s.armed)
      document.title = `${s.armed ? '● ARMED' : '○ disarmed'} · Options Paper Trader`
    }).catch(() => {})
    f(); const t = setInterval(f, 5000); return () => clearInterval(t)
  }, [])
  if (armed === null) return null
  return (
    <div className={`text-center text-[11px] font-semibold py-1 tracking-wide ${armed
      ? 'bg-up/15 text-up' : 'bg-amber-400/15 text-amber-400'}`}>
      {armed
        ? '● ARMED — the bot may auto-execute trades on fresh signals'
        : '○ DISARMED — watching & alerting only · no new entries (open positions are still managed & protected)'}
    </div>
  )
}

export default function TopBar({ tab, setTab, tabs }:
  { tab: string; setTab: (t: string) => void; tabs: [string, string][] }) {
  const { state, connected } = useLive()
  const [status, setStatus] = useState<any>(null)
  useEffect(() => {
    getStatus().then(setStatus)
    const t = setInterval(() => getStatus().then(setStatus), 5000)
    return () => clearInterval(t)
  }, [])
  const cap = state?.capital
  // LIVE: show the REAL Kite account balance (free funds ≈ what the bot may deploy),
  // not the paper-ledger 50k. Falls back to the ledger until the first margins poll.
  const live = state?.broker_mode === 'live' && cap?.account_available != null

  return (
    <header className="border-b border-edge bg-panel sticky top-0 z-40">
      <div className="flex items-center justify-between px-4 pt-2">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-zinc-100">⟁ Options Paper Trader</span>
          <span className="badge bg-zinc-700/40 text-muted">{state?.provider?.toUpperCase() || '—'}</span>
          {state?.broker_mode === 'live'
            ? <span className="badge bg-down/20 text-down border border-down/40 font-semibold"
                title="REAL-MONEY execution: the bot can place live Kite orders. Trades are logged under the Live ledger.">
                🔴 LIVE MONEY</span>
            : <span className="badge bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                title="Paper mode: simulated fills only, no real orders. Trades are logged under the Paper ledger.">
                📝 PAPER</span>}
          <span className={`flex items-center gap-1 text-xs ${connected ? 'text-up' : 'text-down'}`}>
            <span className={`w-2 h-2 rounded-full ${connected ? 'bg-up animate-pulse' : 'bg-down'}`} />
            {connected ? 'LIVE' : 'OFFLINE'}
          </span>
          {status && !status.authenticated && status.login_url &&
            <a className="btn" href="/api/login">Connect Kite</a>}
          <ExecutionControls />
        </div>
        <div className="flex items-center gap-5">
          {live ? (
            <>
              <Stat label="Acct equity" v={inr(cap?.account_net)} />
              <Stat label="Free funds" v={inr(cap?.account_available)} />
            </>
          ) : (
            <>
              <Stat label="Equity" v={inr(cap?.equity)} />
              <Stat label="Cash" v={inr(cap?.cash)} />
            </>
          )}
          <Stat label="Invested" v={inr(cap?.invested)} />
          <Stat label="Realized P&L" v={signedInr(cap?.realized_pnl)} cls={pnlColor(cap?.realized_pnl)} />
          <Stat label="Open" v={String(cap?.open_count ?? '—')} />
          <Stat label="Tick" v={String(state?.tick ?? '—')} />
        </div>
      </div>
      <nav className="flex gap-1 px-3 py-2">
        {tabs.map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`px-3 py-1.5 rounded text-xs transition-colors ${tab === id
              ? 'bg-panel2 text-zinc-100 border border-edge' : 'text-muted hover:text-zinc-300'}`}>
            {label}
          </button>
        ))}
      </nav>
      <ArmBanner />
    </header>
  )
}
