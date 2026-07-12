import { useEffect, useState } from 'react'
import * as api from '../lib/api'
import type { Promotion, Watchlist, ArchiveStrategy } from '../lib/api'

// The approve→deploy cockpit: review what research (and the code-gen builder) proposes,
// read exactly what each strategy does, and stage a validated universe into a live
// watchlist. Deploy writes declarative config only — it never places an order, and the
// engine stays disarmed until you re-ARM after the next restart.

function Explanation({ ex }: { ex: Promotion['explanation'] }) {
  return (
    <div className="flex flex-col gap-2 text-xs">
      <div>
        <div className="stat-label">Thesis</div>
        <div className="text-zinc-300">{ex.thesis}</div>
      </div>
      {ex.primitives?.length > 0 && (
        <div className="flex items-center gap-1 flex-wrap">
          {ex.primitives.map((p) => (
            <span key={p} className="badge bg-zinc-700/40 text-muted">{p}</span>
          ))}
        </div>
      )}
      <div>
        <div className="stat-label">The exact logic it used</div>
        <ol className="list-decimal ml-4 flex flex-col gap-0.5 text-zinc-300">
          {ex.rules.map((r, i) => <li key={i}>{r}</li>)}
        </ol>
      </div>
      {ex.note && <div className="text-amber-400/80">{ex.note}</div>}
      <div className="text-[11px] text-muted">{ex.caveats}</div>
    </div>
  )
}

function PromotionCard({ p, onChange }: { p: Promotion; onChange: () => void }) {
  const [name, setName] = useState(p.strategy_key)
  const [showLogic, setShowLogic] = useState(true)
  const [showSource, setShowSource] = useState(false)
  const [preview, setPreview] = useState<any | null>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  const doPreview = async () => {
    setBusy(true); setMsg('')
    const r = await api.deployPromotion(p.id, { watchlist_name: name, dry_run: true })
    setPreview(r); setBusy(false)
  }
  const doDeploy = async () => {
    setBusy(true); setMsg('')
    const r = await api.deployPromotion(p.id, { watchlist_name: name })
    setBusy(false)
    if (r.error) { setMsg(r.error); return }
    setMsg(`Staged → watchlist "${name}". ${r.note || ''}`)
    onChange()
  }

  return (
    <div className="card p-3 flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-zinc-200">{p.strategy_key}</span>
          <span className="badge bg-zinc-700/40 text-muted">{p.interval}</span>
          {p.generated && (
            <span className="badge bg-purple-500/20 text-purple-300">bot-generated</span>
          )}
        </div>
        <button className="btn" onClick={() => setShowLogic((s) => !s)}>
          {showLogic ? 'Hide logic' : 'How it works'}
        </button>
      </div>

      {showLogic && <Explanation ex={p.explanation} />}

      {p.generated && p.generated_source && (
        <div className="flex flex-col gap-1">
          <button className="btn self-start" onClick={() => setShowSource((s) => !s)}>
            {showSource ? 'Hide' : 'View'} generated Python
          </button>
          {showSource && (
            <pre className="bg-panel2 border border-edge rounded p-2 text-[11px] overflow-x-auto text-zinc-300">
              {p.generated_source}
            </pre>
          )}
        </div>
      )}

      <div>
        <div className="stat-label">Validated universe (what deploy will assign)</div>
        <div className="flex flex-col gap-0.5 text-xs">
          {p.validated_universe.map((v) => (
            <div key={v.instrument} className="flex items-center justify-between">
              <span className="text-zinc-300">{v.instrument}</span>
              <span className="text-muted">DSR {v.dsr.toFixed(3)}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-2 flex-wrap border-t border-edge/50 pt-2">
        <input
          className="bg-panel2 border border-edge rounded px-2 py-1 text-xs"
          value={name} onChange={(e) => setName(e.target.value)} placeholder="watchlist name"
        />
        <button className="btn" disabled={busy} onClick={doPreview}>Preview</button>
        <button className="btn border-up/60 text-up" disabled={busy} onClick={doDeploy}>
          Approve &amp; Deploy
        </button>
      </div>

      {preview && (
        <div className="text-[11px] text-muted flex flex-col gap-0.5">
          <div>Would assign: {preview.accepted?.join(', ') || '—'}</div>
          {preview.rejected?.length > 0 && (
            <div className="text-amber-400/80">
              Blocked (incumbents): {preview.rejected.map((r: any) => `${r.instrument} (${r.reason})`).join(', ')}
            </div>
          )}
        </div>
      )}
      {msg && <div className="text-[11px] text-up">{msg}</div>}
    </div>
  )
}

function WatchlistsPanel({ watchlists, onChange }: { watchlists: Watchlist[]; onChange: () => void }) {
  const toggle = async (w: Watchlist) => {
    await api.setWatchlistStatus(w.name, w.status === 'active' ? 'paused' : 'active')
    onChange()
  }
  return (
    <div className="card p-3 flex flex-col gap-2">
      <div className="stat-label">Watchlists — each runs ONE strategy</div>
      {watchlists.length === 0 && <div className="text-muted text-xs">No watchlists yet.</div>}
      {watchlists.map((w) => (
        <div key={w.id} className="flex items-center justify-between gap-2 text-xs border-t border-edge/50 pt-2">
          <div className="flex flex-col gap-0.5">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-zinc-200">{w.name}</span>
              <span className="badge bg-zinc-700/40 text-muted">{w.strategy_key}</span>
              <span className={`badge ${w.status === 'active' ? 'bg-up/20 text-up' : 'bg-zinc-700/40 text-muted'}`}>
                {w.status}
              </span>
            </div>
            <span className="text-muted">{w.instruments.join(', ') || '(empty)'}</span>
          </div>
          <button className="btn" onClick={() => toggle(w)}>
            {w.status === 'active' ? 'Pause' : 'Activate'}
          </button>
        </div>
      ))}
    </div>
  )
}

const ARCHIVE_ACTIONS: Record<string, string[]> = {
  running: ['probation', 'on_hold'],
  probation: ['running', 'on_hold', 'retired'],
  on_hold: ['running', 'retired'],
  candidate: ['on_hold'],
  retired: ['candidate'],
}

function ArchivePanel({ archive, onChange }: { archive: ArchiveStrategy[]; onChange: () => void }) {
  const act = async (s: ArchiveStrategy, status: string) => {
    await api.setArchiveStatus(s.strategy_key, status)
    onChange()
  }
  return (
    <div className="card p-3 flex flex-col gap-2">
      <div className="stat-label">Strategy archive — running · probation · on-hold · retired (revivable)</div>
      {archive.length === 0 && <div className="text-muted text-xs">No strategies recorded yet.</div>}
      {archive.map((s) => (
        <div key={s.strategy_key} className="flex items-center justify-between gap-2 text-xs border-t border-edge/50 pt-2">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-zinc-200">{s.strategy_key}</span>
            <span className="badge bg-zinc-700/40 text-muted">{s.status}</span>
            <span className="badge bg-zinc-700/40 text-muted">{s.source}</span>
            {s.last_dsr != null && <span className="text-muted">DSR {s.last_dsr.toFixed(3)}</span>}
          </div>
          <div className="flex gap-1 flex-wrap">
            {(ARCHIVE_ACTIONS[s.status] || []).map((next) => (
              <button key={next} className="btn" onClick={() => act(s, next)}>{next}</button>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function PortfolioView() {
  const [promotions, setPromotions] = useState<Promotion[]>([])
  const [watchlists, setWatchlists] = useState<Watchlist[]>([])
  const [archive, setArchive] = useState<ArchiveStrategy[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = async () => {
    const [p, w, a] = await Promise.all([api.getPromotions(), api.getWatchlists(), api.getArchive()])
    setPromotions(p.promotions || [])
    setWatchlists(w.watchlists || [])
    setArchive(a.strategies || [])
    setLoading(false)
  }
  useEffect(() => { refresh() }, [])

  return (
    <div className="grid gap-4 max-w-5xl">
      <div className="card p-3 flex flex-col gap-2">
        <div className="stat-label">Research promotions — awaiting your approval</div>
        <div className="text-[11px] text-muted">
          Approving stages the validated universe into a watchlist. It writes config only — no
          order is placed, and the engine stays disarmed until you restart and re-ARM.
        </div>
        {loading && <div className="text-muted text-xs">Loading…</div>}
        {!loading && promotions.length === 0 && (
          <div className="text-muted text-xs">No pending promotions. Run the research pipeline to surface candidates.</div>
        )}
        {promotions.map((p) => <PromotionCard key={p.id} p={p} onChange={refresh} />)}
      </div>
      <WatchlistsPanel watchlists={watchlists} onChange={refresh} />
      <ArchivePanel archive={archive} onChange={refresh} />
    </div>
  )
}
