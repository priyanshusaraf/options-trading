/**
 * Presentation logic for /api/storage.
 *
 * The database reached 108 MB on a 1 GB droplet before anyone noticed, because
 * nothing in the product ever reported its size — the growth was only visible by
 * SSH-ing in. Retention was built in response; this is the other half, so the
 * cost of the option-chain sweep (a DELIBERATE cost: Kite sells no historical
 * chains, so an unsnapshotted day is gone forever) is a decision the owner can
 * see rather than discover from an OOM.
 *
 * Pure, so the thresholds below are testable — they are the part that decides
 * whether anyone acts.
 */

export interface StorageTable {
  name: string
  rows: number
  rows_last_24h: number
  pruned: boolean
}

export interface Storage {
  db_path?: string
  size_mb?: number
  tables?: StorageTable[]
  retention?: {
    enabled?: boolean
    option_data_days?: number
    signal_events_days?: number
    equity_full_days?: number
    equity_downsample_minutes?: number
    last_run?: string | null
  }
  option_cache_enabled?: boolean
}

/** The box is 1 GB with no resize coming, and the engine needs headroom. */
export const WARN_MB = 300
export const CRITICAL_MB = 600

export function sizeTone(mb: number | undefined): 'good' | 'warn' | 'bad' {
  if (mb === undefined || mb === null) return 'warn'   // unknown is not "fine"
  if (mb >= CRITICAL_MB) return 'bad'
  if (mb >= WARN_MB) return 'warn'
  return 'good'
}

export function sizeLabel(mb: number | undefined): string {
  if (mb === undefined || mb === null) return '—'
  if (mb >= 1024) return `${(mb / 1024).toFixed(2)} GB`
  return `${mb.toFixed(1)} MB`
}

/**
 * Tables ordered by what they added in the LAST 24 HOURS, not by total size.
 *
 * Total rows tell you what happened; daily growth tells you what is about to.
 * A huge table that stopped growing is a solved problem — surfacing it above a
 * small one doubling every day would point attention at the wrong thing.
 */
export function growthLeaders(s: Storage | null | undefined, limit = 4): StorageTable[] {
  const tables = s?.tables ?? []
  return [...tables]
    .filter((t) => (t.rows_last_24h ?? 0) > 0)
    .sort((a, b) => (b.rows_last_24h ?? 0) - (a.rows_last_24h ?? 0))
    .slice(0, limit)
}

/** A short sentence, or empty when there is nothing worth saying. */
export function storageWarning(s: Storage | null | undefined): string {
  if (!s) return ''
  const mb = s.size_mb
  if (mb !== undefined && mb >= CRITICAL_MB) {
    return `${sizeLabel(mb)} on a 1 GB box — this is how the 2026-07 OOM started. ` +
      `Run scripts/prune_db.py, or turn the option-chain sweep off.`
  }
  if (s.retention?.enabled === false) {
    return 'Retention is OFF. Telemetry will grow without bound on a box with no resize coming.'
  }
  if (mb !== undefined && mb >= WARN_MB) {
    return `${sizeLabel(mb)} and growing. Retention is on, but worth watching.`
  }
  return ''
}
