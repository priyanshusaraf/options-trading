import { useEffect, useState } from 'react'
import { useLive } from '../state/LiveContext'
import { getStatus } from '../lib/api'
import { inr, signedInr, pnlColor } from '../lib/format'

function Stat({ label, v, cls = '' }: { label: string; v: string; cls?: string }) {
  return <div className="text-right"><div className="stat-label">{label}</div>
    <div className={`text-sm font-semibold tabular-nums ${cls}`}>{v}</div></div>
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

  return (
    <header className="border-b border-edge bg-panel sticky top-0 z-40">
      <div className="flex items-center justify-between px-4 pt-2">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-zinc-100">⟁ Options Paper Trader</span>
          <span className="badge bg-zinc-700/40 text-muted">{state?.provider?.toUpperCase() || '—'}</span>
          <span className={`flex items-center gap-1 text-xs ${connected ? 'text-up' : 'text-down'}`}>
            <span className={`w-2 h-2 rounded-full ${connected ? 'bg-up animate-pulse' : 'bg-down'}`} />
            {connected ? 'LIVE' : 'OFFLINE'}
          </span>
          {status && !status.authenticated && status.login_url &&
            <a className="btn" href="/api/login">Connect Kite</a>}
        </div>
        <div className="flex items-center gap-5">
          <Stat label="Equity" v={inr(cap?.equity)} />
          <Stat label="Cash" v={inr(cap?.cash)} />
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
    </header>
  )
}
