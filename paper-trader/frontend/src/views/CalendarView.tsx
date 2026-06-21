import { useEffect, useMemo, useState } from 'react'
import { getCalendar } from '../lib/api'
import { signedInr, inr } from '../lib/format'

// Calendar of daily P&L — each day is a block split in two halves: YOUR
// discretionary trades (top) and the BOT's trades (bottom). Green = profit,
// red = loss, grey = neutral / no activity. Data builds forward from go-live, so
// past days (before the bot traded) read grey — that's expected, not a bug.

interface DayRec { day: string; bot_pnl: number | null; my_pnl: number | null; bot_trades: number }

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December']

// P&L -> half-cell colour. null/0 is neutral grey; sign drives green/red.
function half(v: number | null | undefined): string {
  if (v == null || v === 0) return 'bg-zinc-700/30'
  return v > 0 ? 'bg-up/55' : 'bg-down/55'
}

function parse(d: string): Date {
  const [y, m, dd] = d.split('-').map(Number)
  return new Date(y, m - 1, dd)
}

export default function CalendarView() {
  const [days, setDays] = useState<DayRec[]>([])
  const [sel, setSel] = useState<DayRec | null>(null)

  useEffect(() => { getCalendar(150).then((d) => setDays(d.days || [])).catch(() => {}) }, [])

  const byDay = useMemo(() => {
    const m: Record<string, DayRec> = {}
    for (const r of days) m[r.day] = r
    return m
  }, [days])

  // months present in the range, newest first
  const months = useMemo(() => {
    const seen = new Set<string>()
    const out: { y: number; m: number }[] = []
    for (const r of days) {
      const dt = parse(r.day)
      const key = `${dt.getFullYear()}-${dt.getMonth()}`
      if (!seen.has(key)) { seen.add(key); out.push({ y: dt.getFullYear(), m: dt.getMonth() }) }
    }
    return out.reverse()
  }, [days])

  const totals = useMemo(() => {
    let mine = 0, bot = 0
    for (const r of days) { mine += r.my_pnl || 0; bot += r.bot_pnl || 0 }
    return { mine, bot }
  }, [days])

  return (
    <div className="flex flex-col gap-3">
      <div className="card p-3 flex items-center gap-4 flex-wrap">
        <span className="font-semibold text-zinc-100">Daily P&amp;L calendar</span>
        <span className="flex items-center gap-1.5 text-xs text-muted">
          <span className="inline-block w-3 h-3 rounded-sm bg-up/55" /> profit
          <span className="inline-block w-3 h-3 rounded-sm bg-down/55 ml-2" /> loss
          <span className="inline-block w-3 h-3 rounded-sm bg-zinc-700/30 ml-2" /> neutral / no trades
        </span>
        <span className="ml-auto flex items-center gap-4 text-xs">
          <span>You: <b className={totals.mine >= 0 ? 'text-up' : 'text-down'}>{signedInr(totals.mine)}</b></span>
          <span>Bot: <b className={totals.bot >= 0 ? 'text-up' : 'text-down'}>{signedInr(totals.bot)}</b></span>
        </span>
      </div>

      <div className="card p-3 text-[11px] text-muted">
        Each day is split — <b className="text-zinc-300">top = your trades</b>, <b className="text-zinc-300">bottom = the bot&rsquo;s</b>.
        Your side is the day-over-day change in your Kite account minus the bot&rsquo;s booked P&amp;L; the bot&rsquo;s side is
        its live trade ledger. History accrues from go-live, so earlier days read grey.
      </div>

      {months.length === 0 && (
        <div className="card p-8 text-center text-muted">no data yet — it starts filling in once the bot trades live and a daily account snapshot is taken</div>
      )}

      <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' }}>
        {months.map(({ y, m }) => <MonthGrid key={`${y}-${m}`} y={y} m={m} byDay={byDay} onSelect={setSel} sel={sel} />)}
      </div>

      {sel && (
        <div className="card p-3 flex items-center gap-6 flex-wrap">
          <span className="font-semibold text-zinc-100">{sel.day}</span>
          <span>You: <b className={(sel.my_pnl ?? 0) >= 0 ? 'text-up' : 'text-down'}>{sel.my_pnl == null ? '— no snapshot' : signedInr(sel.my_pnl)}</b></span>
          <span>Bot: <b className={(sel.bot_pnl ?? 0) >= 0 ? 'text-up' : 'text-down'}>{sel.bot_pnl == null ? '— no trades' : signedInr(sel.bot_pnl)}</b>
            {sel.bot_trades > 0 && <span className="text-muted"> · {sel.bot_trades} trade{sel.bot_trades === 1 ? '' : 's'}</span>}</span>
        </div>
      )}
    </div>
  )
}

function MonthGrid({ y, m, byDay, onSelect, sel }:
  { y: number; m: number; byDay: Record<string, DayRec>; onSelect: (d: DayRec) => void; sel: DayRec | null }) {
  // Monday-first grid. JS getDay(): 0=Sun..6=Sat -> shift so Mon=0.
  const first = new Date(y, m, 1)
  const lead = (first.getDay() + 6) % 7
  const daysInMonth = new Date(y, m + 1, 0).getDate()
  const cells: (DayRec | null)[] = []
  for (let i = 0; i < lead; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) {
    const ds = `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    cells.push(byDay[ds] || { day: ds, bot_pnl: null, my_pnl: null, bot_trades: 0 })
  }

  return (
    <div className="card p-3">
      <div className="stat-label mb-2">{MONTHS[m]} {y}</div>
      <div className="grid grid-cols-7 gap-1 text-[9px] text-muted mb-1">
        {WEEKDAYS.map((w) => <div key={w} className="text-center">{w}</div>)}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((c, i) => {
          if (!c) return <div key={i} />
          const dnum = Number(c.day.split('-')[2])
          const active = sel?.day === c.day
          const title = `${c.day}\nYou: ${c.my_pnl == null ? 'no snapshot' : signedInr(c.my_pnl)}\nBot: ${c.bot_pnl == null ? 'no trades' : signedInr(c.bot_pnl)}`
          return (
            <button key={i} onClick={() => onSelect(c)} title={title}
              className={`relative aspect-square rounded overflow-hidden border ${active ? 'border-blue-400' : 'border-edge/50'} hover:border-zinc-400`}>
              <div className={`absolute inset-x-0 top-0 h-1/2 ${half(c.my_pnl)}`} />
              <div className={`absolute inset-x-0 bottom-0 h-1/2 ${half(c.bot_pnl)}`} />
              <span className="absolute inset-0 flex items-center justify-center text-[9px] text-zinc-200/90 font-medium">{dnum}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
