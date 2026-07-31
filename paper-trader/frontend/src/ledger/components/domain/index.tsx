/* Domain components — §6.4 */

import { useEffect, useMemo, useRef, useState } from 'react'
import type {
  Grade,
  Instrument,
  Level,
  MacroEvent,
  PlaybookEntry,
  Scenario,
  Session,
  StreamEvent,
  Trade,
} from '../../domain/types'
import { Badge, Button, Chip, Kbd, Tag } from '../primitives'
import { BlockSpark, NumericCell, RMeter, StatCell, fmtR, fmtRupees, signClass } from '../data'
import { formatTime, minutesUntil } from '../../domain/dates'
import { parseTicket, describeTicket, type ParseContext } from '../../domain/ticketGrammar'
import type { RiskStatus } from '../../data/actions'
import type { Stat } from '../../domain/metrics'
import './domain.css'

// ── Direction glyph ───────────────────────────────────────────────────────
// §7.2 Direction is *always* also carried by a glyph (▲▼), never by hue alone.

export function DirGlyph({ direction }: { direction: 'long' | 'short' }) {
  return (
    <span
      className={`dirglyph ${direction === 'long' ? 'pos' : 'neg'}`}
      title={direction}
    >
      {direction === 'long' ? '▲' : '▼'}
    </span>
  )
}

// ── ConfidenceMeter ───────────────────────────────────────────────────────
// §6.4 Five discrete marks, keyboard 1–5, locked after commit and rendered
// thereafter with a lock hairline.

export function ConfidenceMeter({
  value,
  onChange,
  locked,
}: {
  value: number
  onChange?: (v: number) => void
  locked?: boolean
}) {
  return (
    <span className={`confmeter ${locked ? 'is-locked' : ''}`} title={`Confidence ${value}/5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <button
          key={i}
          className={`confmeter__mark ${i <= value ? 'is-on' : ''}`}
          disabled={locked || !onChange}
          onClick={() => onChange?.(i)}
          aria-label={`Confidence ${i}`}
        />
      ))}
    </span>
  )
}

// ── GradePill ─────────────────────────────────────────────────────────────
// §6.4 A–F, monochrome. "Grades are not good/bad in colour terms — colour here
// would encourage grade inflation."

export function GradePill({
  grade,
  onChange,
}: {
  grade: Grade | null
  onChange?: (g: Grade) => void
}) {
  if (!onChange) {
    return grade ? (
      <span className="gradepill">{grade}</span>
    ) : (
      <span className="gradepill gradepill--empty">—</span>
    )
  }
  return (
    <span className="gradeset">
      {(['A', 'B', 'C', 'D', 'F'] as Grade[]).map((g, i) => (
        <button
          key={g}
          className={`gradepill gradepill--btn ${grade === g ? 'is-on' : ''}`}
          onClick={() => onChange(g)}
          title={`Grade ${g} · ⌘${i + 1}`}
        >
          {g}
        </button>
      ))}
    </span>
  )
}

// ── MistakeChip ───────────────────────────────────────────────────────────
// §6.4 Tag with a cost tooltip: "early-exit · 11 trades · −₹18,400 attributed".

export function MistakeChip({
  mistake,
  cost,
  count,
  onRemove,
  onClick,
  auto,
}: {
  mistake: string
  cost?: number
  count?: number
  onRemove?: () => void
  onClick?: () => void
  /** System-applied tags are shown but not removable. §1.2 */
  auto?: boolean
}) {
  const title =
    count != null && cost != null
      ? `${mistake} · ${count} trades · ${fmtRupees(-cost)} attributed`
      : mistake
  return (
    <Chip
      tone="attention"
      onRemove={auto ? undefined : onRemove}
      onClick={onClick}
      title={title}
    >
      {auto && <span className="faint">auto·</span>}
      {mistake}
    </Chip>
  )
}

/** §5.3 The `M` mistake-density glyph column: zero to three dots. "Scanning it
 *  down the page is how you find your leaks in five seconds." */
export function MistakeDots({ count }: { count: number }) {
  if (count <= 0) return <span className="faint" />
  return (
    <span className="mistakedots attn" title={`${count} mistake${count > 1 ? 's' : ''}`}>
      {'●'.repeat(Math.min(3, count))}
    </span>
  )
}

// ── RiskEnvelope ──────────────────────────────────────────────────────────
// §6.4 used vs allowed, in R. §2.2.4 the commitment device.

export function RiskEnvelopeBar({
  session,
  status,
}: {
  session: Session
  status: RiskStatus
}) {
  return (
    <div className={`risk ${status.breached ? 'is-breached' : ''}`}>
      <span className="label">Risk envelope</span>
      <span className="risk__terms mono">
        max {session.risk.maxTrades} trades · max {session.risk.maxLossR.toFixed(1)}R ·{' '}
        {session.risk.maxConcurrent} concurrent
      </span>
      <span className="risk__used mono">
        used <span className={signClass(status.rUsed)}>{fmtR(status.rUsed)}</span>
        <span className="faint"> · {status.tradesUsed}/{session.risk.maxTrades}</span>
      </span>
      {status.breached && (
        <Badge tone="attention">{status.reasons[0]}</Badge>
      )}
    </div>
  )
}

// ── EventClock ────────────────────────────────────────────────────────────
// §6.4 next event countdown, amber inside 5 minutes.

export function EventClock({ events }: { events: MacroEvent[] }) {
  const [, tick] = useState(0)
  useEffect(() => {
    const t = setInterval(() => tick((v) => v + 1), 30_000)
    return () => clearInterval(t)
  }, [])

  if (!events.length) return null
  const upcoming = events
    .map((e) => ({ e, mins: minutesUntil(e.time) }))
    .filter((x) => x.mins > -30)
    .sort((a, b) => a.mins - b.mins)

  return (
    <div className="events">
      {upcoming.map(({ e, mins }) => (
        <div
          key={e.id}
          className={`events__row ${mins >= 0 && mins <= 5 ? 'attn' : ''}`}
        >
          <span className="mono events__time">{e.time}</span>
          <span className="events__title">{e.title}</span>
          {mins >= 0 && mins <= 60 && (
            <span className="mono faint">in {mins}m</span>
          )}
        </div>
      ))}
    </div>
  )
}

// ── PositionStrip ─────────────────────────────────────────────────────────

export function PositionStrip({
  positions,
  instrument,
  onOpen,
  onClose,
}: {
  positions: Trade[]
  instrument: Instrument
  onOpen?: (id: string) => void
  onClose?: (id: string) => void
}) {
  if (!positions.length) {
    return <div className="faint" style={{ fontSize: 'var(--t-12)' }}>— flat</div>
  }
  return (
    <div className="positions">
      {positions.map((p) => (
        <div className="positions__row" key={p.id} onClick={() => onOpen?.(p.id)}>
          <DirGlyph direction={p.direction} />
          <span className="mono">
            {p.contract === 'OPT' ? `${p.strike} ${p.optionType}` : p.contract}
          </span>
          <span className="mono faint">×{p.qty}</span>
          <span className="mono faint">
            {formatTime(p.openedAt, false)}
          </span>
          {onClose && (
            <Button
              variant="quiet"
              onClick={(e) => {
                e.stopPropagation()
                onClose(p.id)
              }}
            >
              close
            </Button>
          )}
        </div>
      ))}
      <span className="faint mono" style={{ fontSize: 'var(--t-11)' }}>
        lot {instrument.lotSize}
      </span>
    </div>
  )
}

// ── StreamEvent ───────────────────────────────────────────────────────────
// §6.4 polymorphic row for the day stream. §2.3 the day's black box recorder.

const KIND_GLYPH: Record<string, string> = {
  'session-open': '▸',
  observation: 'obs',
  trade: '▲',
  fill: '·',
  screenshot: '▣',
  scenario: '◆',
  'limit-breach': '!',
  'thesis-lock': '⊟',
  note: '¶',
  question: '?',
  'mistake-note': '!',
  'regime-change': '◈',
}

export function StreamRow({
  event,
  trade,
  onOpen,
  onDelete,
}: {
  event: StreamEvent
  trade?: Trade
  onOpen?: () => void
  onDelete?: () => void
}) {
  const glyph =
    event.kind === 'trade' && trade
      ? trade.direction === 'long' ? '▲' : '▼'
      : KIND_GLYPH[event.kind] ?? '·'

  return (
    <div
      className={`streamrow streamrow--${event.kind}`}
      onClick={onOpen}
      role={onOpen ? 'button' : undefined}
    >
      {/* §2.1 Timestamps on everything, in Live mode especially. */}
      <span className="streamrow__time mono">{formatTime(event.at)}</span>
      <span
        className={`streamrow__glyph mono ${
          event.kind === 'trade' && trade
            ? trade.direction === 'long' ? 'pos' : 'neg'
            : event.kind === 'limit-breach' ? 'attn' : ''
        }`}
      >
        {glyph}
      </span>
      <span className="streamrow__text">{event.text}</span>
      {event.tags.map((t) => (
        <Tag key={t}>{t}</Tag>
      ))}
      {onDelete && (
        <button
          className="streamrow__x"
          onClick={(e) => {
            e.stopPropagation()
            onDelete()
          }}
          title="Delete (undoable)"
        >
          ×
        </button>
      )}
    </div>
  )
}

// ── ThesisDiff ────────────────────────────────────────────────────────────
// §6.4 side-by-side locked belief vs outcome, with scenario resolution
// controls. §2.4.1 this produces the day's market read score.

export function ThesisDiff({
  session,
  onResolve,
  onPaid,
}: {
  session: Session
  onResolve: (scenarioId: string, status: Scenario['status']) => void
  onPaid: (scenarioId: string, paid: boolean) => void
}) {
  return (
    <div className="thesisdiff">
      <div className="thesisdiff__col">
        <div className="label">What I believed {session.lockedAt && `· ${formatTime(session.lockedAt)}`}</div>
        <div className="locked-block paper" style={{ marginTop: 8 }}>
          {session.thesis || <span className="faint">No thesis was written.</span>}
        </div>
      </div>
      <div className="thesisdiff__col">
        <div className="label">What happened</div>
        <div className="thesisdiff__scenarios">
          {session.scenarios.map((sc) => (
            <div className="thesisdiff__sc" key={sc.id}>
              <div className="thesisdiff__schead">
                <span className="mono">{sc.letter}</span>
                <span>{sc.name}</span>
                <span className="mono faint">p {sc.probability.toFixed(2)}</span>
              </div>
              <div className="thesisdiff__controls">
                {(['hit', 'missed', 'invalidated'] as const).map((s) => (
                  <button
                    key={s}
                    className={`thesisdiff__btn ${sc.status === s ? 'is-on' : ''}`}
                    onClick={() => onResolve(sc.id, s)}
                  >
                    {s}
                  </button>
                ))}
                {sc.status === 'hit' && (
                  <label className="thesisdiff__paid">
                    <input
                      type="checkbox"
                      checked={Boolean(sc.paid)}
                      onChange={(e) => onPaid(sc.id, e.target.checked)}
                    />
                    {/* §5.7 "whether you read the market or just the tape" */}
                    did it pay?
                  </label>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── PlaybookRow ───────────────────────────────────────────────────────────
// §5.6 "One card per setup, but a card in the Linear sense — a dense row that
// expands."

export function PlaybookRow({
  entry,
  expectancy,
  winRate,
  adherence,
  spark,
  expanded,
  onToggle,
  children,
}: {
  entry: PlaybookEntry
  expectancy: Stat
  winRate: Stat
  adherence: Stat
  spark: number[]
  expanded: boolean
  onToggle: () => void
  children?: React.ReactNode
}) {
  const insufficient = expectancy.state === 'insufficient'
  return (
    <div className={`pbrow ${insufficient ? 'is-insufficient' : ''}`}>
      <button className="pbrow__head" onClick={onToggle}>
        <span className="pbrow__name">{entry.name}</span>
        <span className="pbrow__code mono faint">{entry.code}</span>
        <span className="pbrow__stat mono">n={expectancy.n}</span>
        <span className="pbrow__stat mono">
          exp{' '}
          {insufficient ? (
            <span className="faint">░░░</span>
          ) : (
            <span className={signClass(expectancy.value)}>
              {fmtR(expectancy.value, 2)}
            </span>
          )}
        </span>
        <span className="pbrow__stat mono">
          win {insufficient ? <span className="faint">░░</span> : `${(winRate.value * 100).toFixed(0)}%`}
        </span>
        <span className="pbrow__stat mono">
          adh {adherence.n ? `${(adherence.value * 100).toFixed(0)}%` : '—'}
        </span>
        <span className="pbrow__spark faint">
          {insufficient ? '░░░░░' : <BlockSpark values={spark} />}
        </span>
        {insufficient && <Badge>n&lt;20</Badge>}
      </button>
      {expanded && <div className="pbrow__body">{children}</div>}
    </div>
  )
}

// ── ScreenshotTile ────────────────────────────────────────────────────────
// §5.9 Untagged screenshots surface first — a screenshot with no context is a
// note you failed to finish.

export function ScreenshotTile({
  src,
  name,
  untagged,
  onClick,
}: {
  src: string
  name: string
  untagged?: boolean
  onClick?: () => void
}) {
  return (
    <button
      className={`shot ${untagged ? 'is-untagged' : ''}`}
      onClick={onClick}
      title={name}
    >
      {src ? (
        <img src={src} alt={name} />
      ) : (
        <span className="shot__placeholder mono">▣</span>
      )}
      <span className="shot__name">{name}</span>
    </button>
  )
}

// ── TradeTicket ───────────────────────────────────────────────────────────
// §6.4 "Inline, single-row-first, expands only when needed."
// §2.3 "Log a trade in under four seconds."

export function TradeTicket({
  ctx,
  onCommit,
  onCancel,
  instrument,
}: {
  ctx: ParseContext
  onCommit: (line: string) => void
  onCancel: () => void
  instrument: Instrument
}) {
  const [line, setLine] = useState('')
  const ref = useRef<HTMLInputElement>(null)
  useEffect(() => ref.current?.focus(), [])

  const parsed = useMemo(() => parseTicket(line, ctx), [line, ctx])
  const ready = parsed.missing.length === 0 && parsed.ambiguous.length === 0

  return (
    <div className="ticket glass">
      <span className="ticket__inst mono">{instrument.code}</span>
      <input
        ref={ref}
        className="ticket__input mono"
        value={line}
        placeholder="bnf 52200ce b 60 @248.5 x51900 orb c4 calm"
        onChange={(e) => setLine(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            e.preventDefault()
            onCancel()
          }
          if (e.key === 'Enter' && ready) {
            e.preventDefault()
            onCommit(line)
          }
        }}
      />
      {/* §9.6 "anything ambiguous highlights that token and waits.
          No dialog appears." */}
      <span className="ticket__preview mono">
        {parsed.ambiguous.length > 0 ? (
          <span className="attn">
            {parsed.ambiguous[0].text} — {parsed.ambiguous[0].reason}
          </span>
        ) : parsed.missing.length ? (
          <span className="faint">needs {parsed.missing.join(', ')}</span>
        ) : (
          <span>{describeTicket(parsed, ctx)}</span>
        )}
      </span>
      <Kbd>⏎</Kbd>
    </div>
  )
}

// ── TradeSummaryRow ───────────────────────────────────────────────────────
// The `Σ` line under the blotter. §5.3

export function BlotterSummary({
  count,
  expectancy,
  adherence,
  goodGrades,
}: {
  count: number
  expectancy: Stat
  adherence: Stat
  goodGrades: Stat
}) {
  return (
    <>
      <span>Σ {count} trades</span>
      <span>·</span>
      <StatCell stat={expectancy} format="R" label="" compact />
      <span>·</span>
      <span>
        adherence{' '}
        {adherence.n ? `${(adherence.value * 100).toFixed(0)}%` : '—'}
      </span>
      <span>·</span>
      <span>
        A/B grades{' '}
        {goodGrades.n ? `${(goodGrades.value * 100).toFixed(0)}%` : '—'}
      </span>
    </>
  )
}

export { RMeter, NumericCell }
export type { Level }
