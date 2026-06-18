import { useEffect, useRef } from 'react'
import { useLive } from '../state/LiveContext'
import { time } from '../lib/format'

const levelColor = (l: string): string =>
  l === 'ERROR' ? 'text-down' : l === 'WARNING' ? 'text-yellow-400'
    : l === 'TRADE' ? 'text-up' : 'text-zinc-400'

export default function LogStream() {
  const { logs } = useLive()
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => { ref.current?.scrollTo(0, ref.current.scrollHeight) }, [logs])

  return (
    <div className="card p-3 flex flex-col min-h-0">
      <div className="stat-label mb-2">Live log ({logs.length})</div>
      <div ref={ref} className="flex-1 overflow-auto text-[11px] leading-relaxed space-y-0.5" style={{ maxHeight: '74vh' }}>
        {logs.length === 0 && <div className="text-muted">waiting for engine…</div>}
        {logs.map((l, i) => (
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
