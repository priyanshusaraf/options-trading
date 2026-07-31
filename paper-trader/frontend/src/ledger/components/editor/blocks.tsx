/* ScenarioBlock · LevelLadder · LockBar · ConfirmRail · TemplatePicker — §6.3 */

import { useEffect, useRef, useState } from 'react'
import type { Level, Scenario, ScenarioStatus, Session } from '../../domain/types'
import { Button, Chip, Kbd } from '../primitives'
import { formatTime, relativeDays } from '../../domain/dates'
import type { LockBlocker } from '../../data/actions'
import { TEMPLATES } from '../../domain/taxonomy'

// ── ScenarioBlock ─────────────────────────────────────────────────────────
// §6.3 name · trigger · invalidation · target · probability, with a live
// status chip (pending / playing out / invalidated / hit).

const STATUS_TONE: Record<ScenarioStatus, 'neutral' | 'attention' | 'interactive' | 'long'> = {
  pending: 'neutral',
  'playing-out': 'interactive',
  invalidated: 'attention',
  hit: 'long',
  missed: 'neutral',
}

export function ScenarioBlock({
  scenario,
  locked,
  onChange,
  onRemove,
  onResolve,
  focusField,
}: {
  scenario: Scenario
  locked: boolean
  onChange?: (patch: Partial<Scenario>) => void
  onRemove?: () => void
  onResolve?: (status: ScenarioStatus) => void
  /** §8 the cursor jumps to the field the error names. */
  focusField?: string | null
}) {
  const nameRef = useRef<HTMLInputElement>(null)
  const invalRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (focusField === 'name') nameRef.current?.focus()
    if (focusField === 'invalidation') invalRef.current?.focus()
  }, [focusField])

  if (locked) {
    return (
      <div className="scenario">
        <div className="scenario__letter">{scenario.letter}</div>
        <div>
          <div className="scenario__head">
            <span className="scenario__name">{scenario.name}</span>
            <Chip tone={STATUS_TONE[scenario.status]}>{scenario.status}</Chip>
            <span className="scenario__prob">
              p {scenario.probability.toFixed(2)}
            </span>
          </div>
          <div className="scenario__fields">
            {scenario.trigger && (
              <span className="scenario__field">
                trig <b>{scenario.trigger}</b>
              </span>
            )}
            {scenario.invalidation && (
              <span className="scenario__field">
                inval <b>{scenario.invalidation}</b>
              </span>
            )}
            {scenario.target && (
              <span className="scenario__field">
                target <b>{scenario.target}</b>
              </span>
            )}
          </div>
          {onResolve && scenario.status === 'pending' && (
            <div className="scenario__fields" style={{ paddingTop: 6 }}>
              <Button variant="quiet" onClick={() => onResolve('playing-out')}>
                playing out
              </Button>
              <Button variant="quiet" onClick={() => onResolve('hit')}>
                hit
              </Button>
              <Button variant="quiet" onClick={() => onResolve('invalidated')}>
                invalidated
              </Button>
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="scenario">
      <div className="scenario__letter">{scenario.letter}</div>
      <div>
        <div className="scenario__head">
          <input
            ref={nameRef}
            className="scenario__input scenario__input--wide"
            placeholder="Scenario name"
            value={scenario.name}
            onChange={(e) => onChange?.({ name: e.target.value })}
          />
          <input
            className="scenario__input"
            style={{ width: 52 }}
            type="number"
            step="0.05"
            min="0"
            max="1"
            value={scenario.probability}
            onChange={(e) =>
              onChange?.({ probability: Number(e.target.value) })
            }
          />
          {onRemove && (
            <Button variant="quiet" onClick={onRemove} title="Remove scenario">
              ×
            </Button>
          )}
        </div>
        <div className="scenario__fields">
          <input
            className="scenario__input"
            placeholder="trigger"
            value={scenario.trigger}
            onChange={(e) => onChange?.({ trigger: e.target.value })}
          />
          <input
            ref={invalRef}
            className="scenario__input"
            placeholder="invalidation"
            value={scenario.invalidation}
            onChange={(e) => onChange?.({ invalidation: e.target.value })}
          />
          <input
            className="scenario__input"
            placeholder="target"
            value={scenario.target}
            onChange={(e) => onChange?.({ target: e.target.value })}
          />
        </div>
      </div>
    </div>
  )
}

// ── LevelLadder ───────────────────────────────────────────────────────────
// §6.3 sortable numeric table with price, type, age, source, respect counter.

export function LevelLadder({
  levels,
  onTag,
  onRemove,
  compact,
}: {
  levels: Level[]
  onTag?: (id: string, outcome: 'held' | 'broken') => void
  onRemove?: (id: string) => void
  compact?: boolean
}) {
  if (!levels.length) {
    return <div className="faint" style={{ fontSize: 'var(--t-12)' }}>No levels.</div>
  }
  return (
    <table className="ladder">
      {!compact && (
        <thead>
          <tr>
            <th style={{ textAlign: 'right' }}>Price</th>
            <th>Type</th>
            <th>Age</th>
            <th>Record</th>
            <th>Source</th>
            {(onTag || onRemove) && <th />}
          </tr>
        </thead>
      )}
      <tbody>
        {levels.map((l) => {
          const days = Math.max(
            0,
            Math.floor((Date.now() - l.createdAt) / 86_400_000),
          )
          // §5.1 Levels show age and a respect counter, which is more
          // decision-relevant than the price alone.
          const record =
            l.broken > 0 && l.brokenAt
              ? `broken ${relativeDays(l.brokenAt)}`
              : l.held > 0
                ? `×${l.held} held`
                : 'untested'
          return (
            <tr key={l.id}>
              <td className="price">{l.price.toLocaleString('en-IN')}</td>
              <td>{l.type}</td>
              <td className="faint">{days}d</td>
              <td className={l.broken > 0 ? 'attn' : ''}>{record}</td>
              {!compact && <td className="faint">{l.source}</td>}
              {(onTag || onRemove) && (
                <td>
                  <span className="ladder__actions">
                    {onTag && (
                      <>
                        <button
                          className="ladder__tiny"
                          onClick={() => onTag(l.id, 'held')}
                          title="Mark respected"
                        >
                          held
                        </button>
                        <button
                          className="ladder__tiny"
                          onClick={() => onTag(l.id, 'broken')}
                          title="Mark broken"
                        >
                          broke
                        </button>
                      </>
                    )}
                    {onRemove && (
                      <button
                        className="ladder__tiny"
                        onClick={() => onRemove(l.id)}
                        title="Remove level"
                      >
                        ×
                      </button>
                    )}
                  </span>
                </td>
              )}
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

// ── LockBar ───────────────────────────────────────────────────────────────
// §6.3 "The commit affordance. Shows what will be frozen, requires confirm,
// then renders the timestamp stamp permanently."

export function LockBar({
  session,
  blockers,
  onLock,
  onBlockerClick,
}: {
  session: Session
  blockers: LockBlocker[]
  onLock: () => void
  onBlockerClick?: (b: LockBlocker) => void
}) {
  if (session.lockedAt) {
    return (
      <div className="lock-stamp">
        <span>locked {formatTime(session.lockedAt)}</span>
        <span className="faint">· append-only</span>
      </div>
    )
  }

  const blocked = blockers.length > 0
  return (
    <div className={`lockbar ${blocked ? 'lockbar--blocked' : ''}`}>
      <span className="lockbar__what">
        {blocked ? (
          // §8 Errors are directions — the message names the field and
          // clicking it moves the cursor there.
          <span
            className="lockbar__error"
            onClick={() => onBlockerClick?.(blockers[0])}
          >
            {blockers[0].message}
          </span>
        ) : (
          <>
            Locks the thesis, {session.scenarios.length} scenarios, and the risk
            envelope. Everything after this is an append.
          </>
        )}
      </span>
      <Button variant="primary" onClick={onLock} disabled={blocked} kbd="⌘⏎">
        Lock thesis
      </Button>
    </div>
  )
}

/** §6.5 ConfirmRail — used exactly once, for thesis lock. §2.2.5 the only
 *  confirmation dialog in the product. */
export function ConfirmRail({
  title,
  body,
  confirmLabel,
  onConfirm,
  onCancel,
}: {
  title: string
  body: string
  confirmLabel: string
  onConfirm: () => void
  onCancel: () => void
}) {
  const ref = useRef<HTMLButtonElement>(null)
  useEffect(() => ref.current?.focus(), [])
  return (
    <div className="confirm-rail" role="alertdialog" aria-label={title}>
      <div className="confirm-rail__body">
        <strong className="confirm-rail__title">{title}</strong>
        {body}
      </div>
      <Button variant="quiet" onClick={onCancel}>
        Cancel <Kbd>esc</Kbd>
      </Button>
      <button ref={ref} className="btn btn--primary" onClick={onConfirm}>
        {confirmLabel} <Kbd>⏎</Kbd>
      </button>
    </div>
  )
}

/** §6.3 TemplatePicker — morning, review, weekly, monthly, per-setup
 *  pre-trade checklist. */
export function TemplatePicker({
  onPick,
}: {
  onPick: (body: string) => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <span style={{ position: 'relative' }}>
      <Button variant="quiet" onClick={() => setOpen((v) => !v)} kbd="⌘⇧T">
        Template
      </Button>
      {open && (
        <div className="slash glass" style={{ width: 200 }}>
          {Object.keys(TEMPLATES).map((k) => (
            <button
              key={k}
              className="slash__item"
              onMouseDown={(e) => {
                e.preventDefault()
                onPick(TEMPLATES[k])
                setOpen(false)
              }}
            >
              <span className="slash__label mono">{k}</span>
            </button>
          ))}
        </div>
      )}
    </span>
  )
}
