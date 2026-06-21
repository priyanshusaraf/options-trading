import { useEffect, useState } from 'react'
import { useLive } from '../state/LiveContext'
import { getHome, getInstruments, addToPortfolio, removeFromPortfolio } from '../lib/api'
import InstrumentTile from '../components/InstrumentTile'
import SessionBanner from '../components/SessionBanner'
import ModeChip from '../components/ModeChip'
import { Expanded } from './Monitor'
import type { HomeInstrument, InstrState, InstrumentMeta } from '../lib/types'

export default function HomeView() {
  const { state, liveTicks } = useLive()
  const [home, setHome] = useState<HomeInstrument[]>([])
  const [universe, setUniverse] = useState<InstrumentMeta[]>([])
  const [expanded, setExpanded] = useState<string | null>(null)
  const [adding, setAdding] = useState('')
  const [busy, setBusy] = useState(false)

  const load = () => {
    getHome().then((d) => setHome(d.instruments || []))
    getInstruments().then((d) => setUniverse(d.instruments || []))
  }
  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t) }, [])

  const add = async (key: string) => {
    if (!key.trim()) return
    setBusy(true)
    const res = await addToPortfolio(key.trim().toUpperCase(), true)
    setBusy(false)
    if (res.error) { alert(res.error); return }
    setAdding(''); load()
  }
  const remove = async (key: string) => { await removeFromPortfolio(key); load() }

  const states = state?.states || {}
  const onHomeKeys = new Set(home.map((h) => h.key))
  const quickAdd = universe.filter((u) => !onHomeKeys.has(u.key))

  return (
    <div className="flex flex-col gap-3">
      {/* OPS-R2-2: a Kite session expiry must be loud on the DEFAULT landing page,
          not just on Engine/Monitor. SessionBanner self-hides when healthy. */}
      <SessionBanner />

      {/* add / pin controls */}
      <div className="card p-3 flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="stat-label">Your portfolio universe — pinned instruments are traded live (F&amp;O) or tracked</div>
            <ModeChip mode={state?.broker_mode} />
          </div>
          <span className="text-[11px] text-muted">add a name from a backtest winner or by symbol</span>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <input value={adding} onChange={(e) => setAdding(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && add(adding)}
            placeholder="instrument key (e.g. RELIANCE, NIFTY)"
            className="bg-panel2 border border-edge rounded px-2 py-1 text-xs w-64" />
          <button onClick={() => add(adding)} disabled={busy || !adding.trim()}
            className="btn border-up/50 text-up">{busy ? 'adding…' : '+ add'}</button>
          {quickAdd.length > 0 && <span className="stat-label ml-2">quick add:</span>}
          {quickAdd.slice(0, 12).map((u) => (
            <button key={u.key} onClick={() => add(u.key)}
              className="badge bg-zinc-700/40 text-muted hover:text-zinc-200">+ {u.key}</button>
          ))}
        </div>
      </div>

      {home.length === 0 ? (
        <div className="card p-8 text-center text-muted">
          No instruments pinned yet — add some above, or promote a winner from the Backtests tab.
        </div>
      ) : (
        <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(330px, 1fr))' }}>
          {home.map((h) => {
            const st: InstrState = states[h.key] || {
              instrument: h.key, name: h.name, segment: h.segment, time: 0, close: h.close || 0,
              ema: 0, z: h.z || 0, z_prev: null, slope: 0, std: 0, trend: h.trend || 'flat',
              signal: h.signal || 'NONE', long_exit: false, short_exit: false, position: h.position,
            }
            return (
              <div key={h.key} className="relative">
                {!h.has_options && (
                  <span className="absolute top-2 left-2 z-10 badge bg-amber-400/15 text-amber-400">tracking only</span>
                )}
                <button onClick={() => remove(h.key)} title="remove from portfolio"
                  className="absolute top-2 right-2 z-10 badge bg-down/15 text-down hover:bg-down/30">✕</button>
                <InstrumentTile st={st} onExpand={setExpanded} liveTick={liveTicks[h.key]} />
              </div>
            )
          })}
        </div>
      )}

      {expanded && <Expanded k={expanded} st={states[expanded]} onClose={() => setExpanded(null)} />}
    </div>
  )
}
