/* Timeline — §5.5, `gl`
 *
 * Three zoom levels on one surface; ⌘scroll or −/+ moves between them.
 *   Year   dense grid, one cell per session, cell fill = R, border amber if
 *          unreviewed, plus a hairline equity curve in R below.
 *   Month  one row per session, 34px. "Reading a month in ten seconds is the
 *          entire point."
 *   Day    the session stream expanded.
 */

import { useEffect, useMemo, useState } from 'react'
import { useDB, useInstrument, useStream, useTrades } from '../data/hooks'
import { navigate, setCursor, useUI } from '../app/uiState'
import { EquityTrack, Heatmap, fmtR, signClass, type HeatCell } from '../components/data'
import { Button, Empty, Segment } from '../components/primitives'
import { StreamRow } from '../components/domain'
import { equityCurve, realisedR } from '../domain/metrics'
import { formatDate, formatTime, monthName, weekday } from '../domain/dates'
import { sessionKey } from '../data/actions'
import { registerListNav } from './listNav'
import './surfaces.css'

type Zoom = 'year' | 'month' | 'day'

interface DayRow {
  date: string
  r: number
  trades: number
  wins: number
  losses: number
  summary: string
  reviewed: boolean
  mistakes: number
  screenshots: number
  grades: string[]
}

export function Timeline() {
  const ui = useUI()
  const db = useDB()
  const inst = useInstrument(ui.route.instrumentId)
  const trades = useTrades(ui.route.instrumentId)
  const [zoom, setZoom] = useState<Zoom>((ui.route.zoom as Zoom) ?? 'month')

  const rows = useMemo<DayRow[]>(() => {
    if (!inst) return []
    const byDate = new Map<string, DayRow>()
    for (const s of db.sessions.filter((x) => x.instrumentId === inst.id)) {
      byDate.set(s.date, {
        date: s.date,
        r: 0, trades: 0, wins: 0, losses: 0,
        summary: s.review?.oneLineForTomorrow || s.thesis.split('\n')[0] || '',
        reviewed: Boolean(s.review?.completedAt),
        mistakes: 0,
        screenshots: db.artifacts.filter((a) => a.sessionId === s.id).length,
        grades: [],
      })
    }
    for (const t of trades) {
      const row = byDate.get(t.date) ?? {
        date: t.date, r: 0, trades: 0, wins: 0, losses: 0, summary: '',
        reviewed: false, mistakes: 0, screenshots: 0, grades: [],
      }
      const r = realisedR(t, inst) ?? 0
      row.r += r
      row.trades++
      if (r > 0) row.wins++
      else if (r < 0) row.losses++
      row.mistakes += t.mistakes.length + t.autoTags.length
      if (t.grade) row.grades.push(t.grade)
      byDate.set(t.date, row)
    }
    return [...byDate.values()].sort((a, b) => b.date.localeCompare(a.date))
  }, [db.sessions, db.artifacts, trades, inst])

  const cursorIndex = rows.findIndex((r) => r.date === ui.route.date)
  useEffect(
    () =>
      registerListNav({
        move: (delta) => {
          const next = Math.max(
            0,
            Math.min(rows.length - 1, (cursorIndex < 0 ? 0 : cursorIndex) + delta),
          )
          if (rows[next]) {
            navigate({ date: rows[next].date }, { replace: true })
            setCursor(rows[next].date)
          }
        },
        open: () => navigate({ surface: 'cockpit' }),
        top: () => rows[0] && navigate({ date: rows[0].date }, { replace: true }),
        bottom: () =>
          rows.length &&
          navigate({ date: rows[rows.length - 1].date }, { replace: true }),
      }),
    [rows, cursorIndex],
  )

  // ⌘scroll and −/+ move between zoom levels. §5.5
  useEffect(() => {
    const onWheel = (e: WheelEvent) => {
      if (!e.metaKey && !e.ctrlKey) return
      e.preventDefault()
      const order: Zoom[] = ['year', 'month', 'day']
      const i = order.indexOf(zoom)
      const next = order[Math.max(0, Math.min(2, i + (e.deltaY > 0 ? -1 : 1)))]
      setZoom(next)
    }
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') return
      const order: Zoom[] = ['year', 'month', 'day']
      const i = order.indexOf(zoom)
      if (e.key === '-') setZoom(order[Math.max(0, i - 1)])
      if (e.key === '+' || e.key === '=') setZoom(order[Math.min(2, i + 1)])
    }
    window.addEventListener('wheel', onWheel, { passive: false })
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('wheel', onWheel)
      window.removeEventListener('keydown', onKey)
    }
  }, [zoom])

  if (!inst) return null

  return (
    <div className="surface">
      <div className="surface__head">
        <span className="surface__title">Timeline · {inst.name}</span>
        <span className="surface__spacer" />
        <Segment
          value={zoom}
          onChange={(z) => {
            setZoom(z)
            navigate({ zoom: z }, { replace: true })
          }}
          options={[
            { value: 'year', label: 'Year' },
            { value: 'month', label: 'Month' },
            { value: 'day', label: 'Day' },
          ]}
        />
        <span className="faint" style={{ fontSize: 'var(--t-11)' }}>
          ⌘scroll or − / +
        </span>
      </div>

      <div className="surface__body">
        {zoom === 'year' && <YearView rows={rows} trades={trades} inst={inst} />}
        {zoom === 'month' && <MonthView rows={rows} activeDate={ui.route.date} />}
        {zoom === 'day' && <DayView />}
      </div>
    </div>
  )
}

// ── Year ──────────────────────────────────────────────────────────────────
// §5.5 "A dense grid — one cell per session, 12 columns of ~21 rows."

function YearView({
  rows,
  trades,
  inst,
}: {
  rows: DayRow[]
  trades: ReturnType<typeof useTrades>
  inst: NonNullable<ReturnType<typeof useInstrument>>
}) {
  const year = rows[0]?.date.slice(0, 4) ?? String(new Date().getFullYear())
  const byDate = new Map(rows.map((r) => [r.date, r]))

  // 12 columns of ~21 rows: month down each column, trading days only.
  const columns: HeatCell[][] = []
  for (let m = 0; m < 12; m++) {
    const col: HeatCell[] = []
    const monthStr = `${year}-${String(m + 1).padStart(2, '0')}`
    for (let d = 1; d <= 31; d++) {
      const date = `${monthStr}-${String(d).padStart(2, '0')}`
      const row = byDate.get(date)
      if (!row) continue
      col.push({
        key: date,
        value: row.r,
        flagged: !row.reviewed && row.trades > 0,
        label: `${formatDate(date)} · ${fmtR(row.r)} · ${row.summary.slice(0, 60)}`,
      })
    }
    columns.push(col)
  }

  const maxRows = Math.max(1, ...columns.map((c) => c.length))
  // Fill column-major into a row-major grid so months read downward.
  const cells: HeatCell[] = []
  for (let r = 0; r < maxRows; r++) {
    for (let c = 0; c < 12; c++) {
      cells.push(columns[c][r] ?? { key: `pad_${r}_${c}`, value: null })
    }
  }

  const curve = equityCurve(trades, inst)

  return (
    <div className="tl-year">
      <div className="tl-year__months label">
        {Array.from({ length: 12 }, (_, m) => (
          <span key={m}>{monthName(`${year}-${String(m + 1).padStart(2, '0')}-01`)}</span>
        ))}
      </div>
      <Heatmap
        cells={cells}
        columns={12}
        cellSize={13}
        gap={3}
        onSelect={(key) => {
          if (!key.startsWith('pad_')) navigate({ date: key, surface: 'cockpit' })
        }}
      />
      <div className="tl-year__equity">
        <span className="label">Equity, in R</span>
        <EquityTrack values={curve} height={90} />
      </div>
    </div>
  )
}

// ── Month ─────────────────────────────────────────────────────────────────
// §5.5 One row per session, 34px. Date · day R · trade dots coloured by
// outcome · the review's one-line summary · mistake flag · screenshot count ·
// grades.

function MonthView({
  rows,
  activeDate,
}: {
  rows: DayRow[]
  activeDate: string
}) {
  if (!rows.length) return <Empty>No sessions yet.</Empty>
  return (
    <div className="tl-month">
      {rows.map((row) => (
        <button
          key={row.date}
          className={`tl-row ${row.date === activeDate ? 'is-active' : ''}`}
          onClick={() => navigate({ date: row.date, surface: 'cockpit' })}
        >
          <span className="tl-row__date mono">
            {weekday(row.date)} {formatDate(row.date, false)}
          </span>
          <span className={`tl-row__r num ${signClass(row.r)}`}>
            {row.trades ? fmtR(row.r) : 'flat'}
          </span>
          <span className="tl-row__dots mono">
            {row.trades === 0
              ? '—'
              : [
                  ...Array(row.wins).fill('●'),
                  ...Array(row.losses).fill('○'),
                ].join('')}
          </span>
          <span className="tl-row__summary">
            {row.summary ? `“${row.summary}”` : ''}
          </span>
          {row.mistakes > 0 && <span className="tl-row__flag attn">⚠︎</span>}
          {row.screenshots > 0 && (
            <span className="tl-row__shots mono faint">
              {'▣'.repeat(Math.min(3, row.screenshots))}
            </span>
          )}
          <span className="tl-row__grades mono">{row.grades.join(' ')}</span>
          {!row.reviewed && row.trades > 0 && (
            <span className="tl-row__unrev attn" title="No review">
              ·
            </span>
          )}
          {row.reviewed && row.trades === 0 && (
            <span className="tl-row__check faint">✓</span>
          )}
        </button>
      ))}
    </div>
  )
}

// ── Day ───────────────────────────────────────────────────────────────────
// §5.5 The session stream expanded. The optional price track above it needs
// intraday data the workstation would supply; without it, the stream stands
// alone rather than being faked.

function DayView() {
  const ui = useUI()
  const db = useDB()
  const sessionId = sessionKey(ui.route.instrumentId, ui.route.date)
  const stream = useStream(sessionId)
  const session = db.sessions.find((s) => s.id === sessionId)

  if (!session) return <Empty>No session on this date.</Empty>

  return (
    <div className="tl-day">
      <div className="tl-day__head">
        <span className="mono">{formatDate(ui.route.date)}</span>
        {session.lockedAt && (
          <span className="lock-stamp">locked {formatTime(session.lockedAt)}</span>
        )}
        <Button
          variant="quiet"
          onClick={() => navigate({ surface: 'cockpit' })}
        >
          open cockpit
        </Button>
      </div>
      <div className="tl-day__notice faint">
        A price track would sit here if the workstation supplied intraday data,
        with observations and fills under the bar they refer to.
      </div>
      {stream.length === 0 ? (
        <Empty>Nothing was recorded on this day.</Empty>
      ) : (
        stream.map((e) => (
          <StreamRow
            key={e.id}
            event={e}
            trade={db.trades.find((t) => t.id === e.tradeId)}
            onOpen={
              e.tradeId
                ? () => navigate({ surface: 'trade', objectId: e.tradeId })
                : undefined
            }
          />
        ))
      )}
    </div>
  )
}
