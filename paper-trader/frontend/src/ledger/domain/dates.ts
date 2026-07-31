/* Date helpers. The day is the atomic unit (§0.7), so everything here works
   in local calendar days and IST session clocks — never UTC instants. */

import type { DateStr, Instrument, Mode, Timestamp } from './types'

export const MS_DAY = 86_400_000

export function toDateStr(d: Date | Timestamp): DateStr {
  const date = typeof d === 'number' ? new Date(d) : d
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export function fromDateStr(s: DateStr): Date {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, m - 1, d)
}

export function today(): DateStr {
  return toDateStr(new Date())
}

export function addDays(s: DateStr, n: number): DateStr {
  const d = fromDateStr(s)
  d.setDate(d.getDate() + n)
  return toDateStr(d)
}

export function addMonths(s: DateStr, n: number): DateStr {
  const d = fromDateStr(s)
  d.setMonth(d.getMonth() + n)
  return toDateStr(d)
}

const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MON = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
]

export function weekday(s: DateStr): string {
  return DOW[fromDateStr(s).getDay()]
}

export function monthName(s: DateStr): string {
  return MON[fromDateStr(s).getMonth()]
}

/** `29 Jul 2026` */
export function formatDate(s: DateStr, withYear = true): string {
  const d = fromDateStr(s)
  const base = `${String(d.getDate()).padStart(2, '0')} ${MON[d.getMonth()]}`
  return withYear ? `${base} ${d.getFullYear()}` : base
}

/** `09:34:02` — timestamps are on everything in Live mode. §2.1 */
export function formatTime(t: Timestamp, seconds = true): string {
  const d = new Date(t)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  if (!seconds) return `${hh}:${mm}`
  return `${hh}:${mm}:${String(d.getSeconds()).padStart(2, '0')}`
}

/** `32m`, `2h 14m` — hold time. */
export function formatDuration(ms: number): string {
  const min = Math.round(ms / 60000)
  if (min < 60) return `${min}m`
  const h = Math.floor(min / 60)
  return `${h}h ${min % 60}m`
}

/** "last changed 11 days ago" — quietly shames stale convictions. §5.2 */
export function relativeDays(t: Timestamp, now = Date.now()): string {
  const days = Math.floor((now - t) / MS_DAY)
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 30) return `${days} days ago`
  const months = Math.floor(days / 30)
  if (months < 12) return `${months} month${months > 1 ? 's' : ''} ago`
  return `${Math.floor(months / 12)}y ago`
}

/** Monday-start week key, used by the weekly review. §2.5 */
export function weekStart(s: DateStr): DateStr {
  const d = fromDateStr(s)
  const shift = (d.getDay() + 6) % 7
  d.setDate(d.getDate() - shift)
  return toDateStr(d)
}

export function monthStart(s: DateStr): DateStr {
  return s.slice(0, 7) + '-01'
}

export function quarterOf(s: DateStr): number {
  return Math.floor(fromDateStr(s).getMonth() / 3) + 1
}

function minutesOfDay(hhmm: string): number {
  const [h, m] = hhmm.split(':').map(Number)
  return h * 60 + m
}

/** §2.1 The mode engine is per-instrument, so Crude can be Live at 21:00
 *  while Nifty is in Review. This suggests; the user always overrides. */
export function suggestedMode(inst: Instrument, at = new Date()): Mode {
  const now = at.getHours() * 60 + at.getMinutes()
  const open = minutesOfDay(inst.hours.open)
  const close = minutesOfDay(inst.hours.close)
  if (now >= open && now <= close) return 'live'
  if (now < open) return 'prep'
  return 'review'
}

/** Minutes until an `HH:MM` event today; negative once passed. §6.4 EventClock */
export function minutesUntil(hhmm: string, at = new Date()): number {
  return minutesOfDay(hhmm) - (at.getHours() * 60 + at.getMinutes())
}

/** §4.3 The palette's `/` prefix jumps to a date in natural language. */
export function parseDateExpression(raw: string, from = today()): DateStr | null {
  const q = raw.trim().toLowerCase()
  if (!q) return null
  if (q === 'today') return from
  if (q === 'yesterday') return addDays(from, -1)
  if (q === 'tomorrow') return addDays(from, 1)

  if (/^\d{4}-\d{2}-\d{2}$/.test(q)) return q
  if (/^\d{4}-\d{2}$/.test(q)) return q + '-01'

  const lastDow = q.match(/^last\s+(\w+)$/)
  if (lastDow) {
    const idx = DOW.findIndex((d) => d.toLowerCase().startsWith(lastDow[1].slice(0, 3)))
    if (idx >= 0) {
      let cur = addDays(from, -1)
      for (let i = 0; i < 14; i++) {
        if (fromDateStr(cur).getDay() === idx) return cur
        cur = addDays(cur, -1)
      }
    }
  }

  const nDaysAgo = q.match(/^(\d+)\s*d(ays?)?\s*ago$/)
  if (nDaysAgo) return addDays(from, -Number(nDaysAgo[1]))

  const monthIdx = MON.findIndex((m) => m.toLowerCase() === q.slice(0, 3))
  if (monthIdx >= 0 && q.length <= 9) {
    const year = fromDateStr(from).getFullYear()
    return `${year}-${String(monthIdx + 1).padStart(2, '0')}-01`
  }
  return null
}
