import { useEffect, useState } from 'react'
import { getStorage } from '../lib/api'
import {
  growthLeaders, sizeLabel, sizeTone, storageWarning, type Storage,
} from '../lib/storage'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

/**
 * Database size and what is growing.
 *
 * The DB reached 108 MB on a 1 GB droplet before anyone noticed, because nothing
 * in the product ever reported it — the growth was only visible by SSH-ing in,
 * and the 2026-07 OOM is what made it visible. Retention was the fix; this is
 * the other half, so the cost of keeping option chains is a decision the owner
 * can see rather than discover from an outage.
 *
 * Polls slowly: size moves in megabytes per day, not per second.
 */
const TONE = { good: 'text-emerald-400', warn: 'text-amber-400', bad: 'text-rose-400' } as const

export default function StoragePanel() {
  const [s, setS] = useState<Storage | null>(null)
  const [read, setRead] = useState(false)

  useEffect(() => {
    let alive = true
    const load = () =>
      getStorage().then((d) => {
        if (!alive) return
        setS(d)
        setRead(true)
      })
    load()
    const t = setInterval(load, 60_000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [])

  const tone = read ? sizeTone(s?.size_mb) : 'warn'
  const warning = read ? storageWarning(s) : ''
  const leaders = growthLeaders(s)

  return (
    <Card className="p-3 space-y-2">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="stat-label">Storage</span>
          <span className={cn('text-sm font-semibold', TONE[tone])}>
            {read ? sizeLabel(s?.size_mb) : 'unknown'}
          </span>
        </div>
        <div className="text-[11px] text-muted">
          retention {s?.retention?.enabled === false ? 'OFF' : 'on'}
          {s?.option_cache_enabled === false ? ' · option sweep off' : ''}
        </div>
      </div>

      {leaders.length > 0 && (
        <div className="text-[11px]">
          <div className="stat-label">growing fastest (rows / 24h)</div>
          <ul className="ml-3 list-disc">
            {leaders.map((t) => (
              <li key={t.name}>
                <span className="font-semibold">{t.name}</span>{' '}
                +{t.rows_last_24h.toLocaleString()}
                {t.pruned ? '' : ' (never pruned — money record)'}
              </li>
            ))}
          </ul>
        </div>
      )}

      {warning && (
        <div className={cn('text-[11px] leading-relaxed', TONE[tone])}>{warning}</div>
      )}
    </Card>
  )
}
