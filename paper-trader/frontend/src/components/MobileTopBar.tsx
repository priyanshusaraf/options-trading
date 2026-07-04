import { useEffect, useState } from 'react'
import { useLive } from '../state/LiveContext'
import { getStatus } from '../lib/api'
import { inr, signedInr, pnlColor } from '../lib/format'
import { ExecutionControls, ArmBanner } from './TopBar'

// Compact, right-aligned stat for the phone strip.
function MStat({ label, v, cls = '' }: { label: string; v: string; cls?: string }) {
  return (
    <div className="flex flex-col items-end shrink-0">
      <span className="stat-label">{label}</span>
      <span className={`text-xs font-semibold tabular-nums ${cls}`}>{v}</span>
    </div>
  )
}

// Phone-only header (rendered below md in App). The desktop TopBar is unchanged;
// this mirrors its controls in a stacked, thumb-friendly layout with a slide-out
// drawer for navigation. Backtests is intentionally omitted — desktop-only.
export default function MobileTopBar({ tab, setTab, tabs }:
  { tab: string; setTab: (t: string) => void; tabs: [string, string][] }) {
  const { state, connected } = useLive()
  const [status, setStatus] = useState<any>(null)
  const [open, setOpen] = useState(false)
  useEffect(() => {
    getStatus().then(setStatus)
    const t = setInterval(() => getStatus().then(setStatus), 5000)
    return () => clearInterval(t)
  }, [])

  const cap = state?.capital
  const live = state?.broker_mode === 'live' && cap?.account_available != null
  const navTabs = tabs.filter(([id]) => id !== 'backtests')
  const select = (id: string) => { setTab(id); setOpen(false) }

  return (
    <header className="border-b border-edge bg-panel sticky top-0 z-40">
      {/* row 1: menu · identity · status · trading controls */}
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 px-3 py-2">
        <button onClick={() => setOpen(true)} aria-label="Open menu"
          className="btn px-2 py-1 text-base leading-none">☰</button>
        <span className="font-semibold text-zinc-100 text-sm">⟁</span>
        {state?.broker_mode === 'live'
          ? <span className="badge bg-down/20 text-down border border-down/40 font-semibold">🔴 LIVE</span>
          : <span className="badge bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">📝 PAPER</span>}
        <span className={`flex items-center gap-1 text-[11px] ${connected ? 'text-up' : 'text-down'}`}
          title={connected ? 'Live feed connected' : 'Feed offline'}>
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-up animate-pulse' : 'bg-down'}`} />
        </span>
        <div className="ml-auto flex items-center gap-1.5">
          {status && !status.authenticated && status.login_url &&
            <a className="btn border-amber-400/60 text-amber-400" href="/api/login">Connect</a>}
          <ExecutionControls compact />
        </div>
      </div>

      {/* row 2: horizontally scrollable stat strip */}
      <div className="flex items-center gap-4 px-3 pb-2 overflow-x-auto">
        {live ? (
          <>
            <MStat label="Acct eq" v={inr(cap?.account_net)} />
            <MStat label="Free" v={inr(cap?.account_available)} />
          </>
        ) : (
          <>
            <MStat label="Equity" v={inr(cap?.equity)} />
            <MStat label="Cash" v={inr(cap?.cash)} />
          </>
        )}
        <MStat label="Invested" v={inr(cap?.invested)} />
        <MStat label="Realized" v={signedInr(cap?.realized_pnl)} cls={pnlColor(cap?.realized_pnl)} />
        <MStat label="Open" v={String(cap?.open_count ?? '—')} />
        <MStat label="Tick" v={String(state?.tick ?? '—')} />
      </div>

      <ArmBanner />

      {/* slide-out navigation drawer — from the LEFT (where ☰ is), animated.
          Always mounted so the panel can transition; hidden via opacity + pointer-events. */}
      <div onClick={() => setOpen(false)}
        className={`fixed inset-0 z-50 transition-opacity duration-200 ${open ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
        <div className="absolute inset-0 bg-black/60" />
        <nav onClick={(e) => e.stopPropagation()}
          className={`absolute top-0 left-0 h-full w-64 max-w-[80%] bg-panel border-r border-edge p-3 flex flex-col gap-1 overflow-y-auto transform transition-transform duration-200 ease-out ${open ? 'translate-x-0' : '-translate-x-full'}`}>
          <div className="flex items-center justify-between mb-2">
            <span className="font-semibold text-zinc-100">Menu</span>
            <button onClick={() => setOpen(false)} className="btn px-2 py-1" aria-label="Close menu">✕</button>
          </div>
          {navTabs.map(([id, label]) => (
            <button key={id} onClick={() => select(id)}
              className={`text-left px-3 py-2 rounded text-sm transition-colors ${tab === id
                ? 'bg-panel2 text-zinc-100 border border-edge' : 'text-muted hover:text-zinc-300'}`}>
              {label}
            </button>
          ))}
          <p className="text-[11px] text-muted mt-3 px-1 leading-snug">
            Backtests is desktop-only — open it on your Mac.
          </p>
        </nav>
      </div>
    </header>
  )
}
