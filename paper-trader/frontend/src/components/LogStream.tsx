import { useEffect, useMemo, useRef, useState } from 'react'
import { useLive } from '../state/LiveContext'
import { time } from '../lib/format'

const levelColor = (l: string): string =>
  l === 'ERROR' ? 'text-down' : l === 'WARNING' ? 'text-yellow-400'
    : l === 'TRADE' ? 'text-up' : 'text-zinc-400'

type LevelFilter = 'ALL' | 'ERROR' | 'WARNING' | 'TRADE'
const LEVELS: LevelFilter[] = ['ALL', 'ERROR', 'WARNING', 'TRADE']

export default function LogStream() {
  const { logs } = useLive()
  const ref = useRef<HTMLDivElement>(null)
  const [level, setLevel] = useState<LevelFilter>('ALL')
  const [q, setQ] = useState('')
  const [paused, setPaused] = useState(false)

  const view = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return logs.filter((l) => {
      if (level !== 'ALL' && l.level !== level) return false
      if (needle) {
        const hay = `${l.msg} ${l.instrument || ''} ${l.event || ''}`.toLowerCase()
        if (!hay.includes(needle)) return false
      }
      return true
    })
  }, [logs, level, q])

  // Autoscroll to the newest line unless the trader has paused to read.
  useEffect(() => { if (!paused) ref.current?.scrollTo(0, ref.current.scrollHeight) }, [view, paused])

  return (
    <div className="card p-3 flex flex-col min-h-0">
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        <span className="stat-label mr-1">Live log ({view.length}{view.length !== logs.length ? ` / ${logs.length}` : ''})</span>
        {LEVELS.map((lv) => (
          <button key={lv} onClick={() => setLevel(lv)}
            className={`badge ${level === lv ? 'bg-blue-500/25 text-blue-300' : 'bg-zinc-700/40 text-muted hover:text-zinc-200'}`}>
            {lv}
          </button>
        ))}
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="search msg / instrument"
          className="bg-panel2 border border-edge rounded px-2 py-0.5 text-[11px] w-44" />
        <button onClick={() => setPaused((p) => !p)}
          title="Pause autoscroll so a line doesn't scroll away while you read it"
          className={`badge ml-auto ${paused ? 'bg-amber-400/20 text-amber-400' : 'bg-zinc-700/40 text-muted hover:text-zinc-200'}`}>
          {paused ? '▶ resume scroll' : '⏸ pause scroll'}
        </button>
      </div>
      <div ref={ref} className="flex-1 overflow-auto text-[11px] leading-relaxed space-y-0.5" style={{ maxHeight: '74vh' }}>
        {view.length === 0 && <div className="text-muted">{logs.length === 0 ? 'waiting for engine…' : 'no log lines match the filter'}</div>}
        {view.map((l, i) => (
          <div key={l.seq || i} className="flex gap-2">
            <span className="text-muted shrink-0">{time(l.ts)}</span>
            {l.instrument && <span className="text-blue-300 shrink-0">[{l.instrument}]</span>}
            <span className={levelColor(l.level)}>{l.msg}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
