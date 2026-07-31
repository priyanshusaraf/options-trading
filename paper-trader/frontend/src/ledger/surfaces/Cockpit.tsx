/* Cockpit — §5.1, `gd`
 *
 * "The home surface. Text-first, no widgets. In Prep it is a writing surface
 *  with context; in Live it is a stream with a header."
 *
 * §2.1 Live mode hides analytics, collapses P&L to a single glyph, and leaves
 * only the ticket, observation stream, levels and scenario invalidation.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  useDB,
  useInbox,
  useInstrument,
  useLevels,
  useMacroEvents,
  useOpenPositions,
  usePlaybook,
  useRegime,
  useSession,
  useSessionTrades,
  useStream,
  useUnresolved,
} from '../data/hooks'
import {
  appendToSession,
  closeTrade,
  ensureSession,
  lockBlockers,
  lockThesis,
  observe,
  removeScenario,
  resolveScenario,
  riskStatus,
  setRisk,
  setThesis,
  tagLevel,
  triageEvent,
  upsertScenario,
  type LockBlocker,
} from '../data/actions'
import { navigate, openOverlay, toast, useUI, closeOverlay } from '../app/uiState'
import { Button, Chip, Divider, Empty, Kbd, Rule } from '../components/primitives'
import { BlockEditor } from '../components/editor/BlockEditor'
import {
  ConfirmRail,
  LevelLadder,
  LockBar,
  ScenarioBlock,
  TemplatePicker,
} from '../components/editor/blocks'
import {
  EventClock,
  PositionStrip,
  RiskEnvelopeBar,
  StreamRow,
  TradeTicket,
} from '../components/domain'
import { fmtR, fmtRupees, signClass } from '../components/data'
import { formatDate, formatTime, relativeDays, weekday } from '../domain/dates'
import { netPnl, realisedR } from '../domain/metrics'
import { useTicketCommit } from './useTicketCommit'
import './surfaces.css'

export function Cockpit() {
  const ui = useUI()
  const db = useDB()
  const { instrumentId, date } = ui.route
  const inst = useInstrument(instrumentId)
  const session = useSession(instrumentId, date)
  const levels = useLevels(instrumentId)
  const events = useMacroEvents(instrumentId, date)
  const positions = useOpenPositions(instrumentId)
  const trades = useSessionTrades(session?.id ?? '')
  const stream = useStream(session?.id ?? '')
  const inbox = useInbox(instrumentId)
  const unresolved = useUnresolved(instrumentId).filter((s) => s.date !== date)
  const regime = useRegime(instrumentId)
  const playbook = usePlaybook(instrumentId)

  const [observing, setObserving] = useState(false)
  const [appending, setAppending] = useState(false)
  const [focusField, setFocusField] = useState<LockBlocker | null>(null)
  const [sealing, setSealing] = useState(false)
  const obsRef = useRef<HTMLInputElement>(null)
  const commitTicket = useTicketCommit()

  // Create the session lazily — opening a date should not litter the store
  // with empty sessions the user never wrote in.
  useEffect(() => {
    if (!session && inst) ensureSession(instrumentId, date)
  }, [session, inst, instrumentId, date])

  // `O` arms observation capture from the keymap.
  useEffect(() => {
    if (ui.pendingPrefix === 'observe') {
      setObserving(true)
      requestAnimationFrame(() => obsRef.current?.focus())
    }
  }, [ui.pendingPrefix])

  useEffect(() => {
    if (observing) obsRef.current?.focus()
  }, [observing])

  const blockers = useMemo(
    () => (session ? lockBlockers(session) : []),
    [session],
  )
  const risk = useMemo(
    () => (session ? riskStatus(session.id) : null),
    // riskStatus reads the store directly, so it must re-run when trades move.
    [session, db.trades],
  )

  if (!inst || !session) return null

  const locked = session.lockedAt != null
  const live = ui.mode === 'live'
  const dayR = trades.reduce((a, t) => a + (realisedR(t, inst) ?? 0), 0)
  const dayRupees = trades.reduce((a, t) => a + (netPnl(t) ?? 0), 0)

  function doLock() {
    const errs = lockThesis(session!.id)
    if (errs.length) {
      setFocusField(errs[0])
      toast(errs[0].message)
      return
    }
    setSealing(true)
    setTimeout(() => setSealing(false), 260)
    toast('Thesis locked. Everything after this is an append.', true)
    closeOverlay()
  }

  return (
    <div className="surface">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="surface__head cockpit__head">
        <span className="surface__title">
          {inst.name} · Session {formatDate(date)} · {weekday(date)}
        </span>
        <Chip tone={regime ? 'neutral' : 'attention'} title={regime?.note}>
          {regime ? `regime ${regime.state}` : 'no regime set'}
        </Chip>
        <span className="surface__spacer" />
        {/* §2.1 In Live, P&L is collapsed to a single glyph unless expanded. */}
        {live && !ui.pnlRevealed ? (
          <button
            className="cockpit__pnlglyph mono"
            onClick={() => openOverlay(null)}
            title="P&L hidden in Live mode · ⌘E to reveal"
          >
            •••••
          </button>
        ) : (
          <span className="mono cockpit__pnl">
            <span className={signClass(dayR)}>{fmtR(dayR)}</span>
            <span className="faint"> · {fmtRupees(dayRupees)}</span>
          </span>
        )}
        <LockBar
          session={session}
          blockers={blockers}
          onLock={() => (blockers.length ? setFocusField(blockers[0]) : openOverlay('confirm-lock'))}
          onBlockerClick={setFocusField}
        />
      </div>

      <div className="surface__body cockpit">
        {/* §5.1 "the top two rows are the only place the app ever nags you,
            and they disappear when empty." */}
        {inbox.length > 0 && (
          <button className="cockpit__nag" onClick={() => navigate({ surface: 'inbox' })}>
            <span className="label">Inbox ({inbox.length})</span>
            <span>› triage</span>
            <Kbd>⌥I</Kbd>
          </button>
        )}
        {unresolved.length > 0 && (
          <button
            className="cockpit__nag cockpit__nag--attn"
            onClick={() => navigate({ surface: 'review', date: unresolved[0].date })}
          >
            <span className="label">Unresolved</span>
            <span>
              › {formatDate(unresolved[0].date, false)} session has no review
            </span>
            <Kbd>⌥U</Kbd>
          </button>
        )}

        {/* ── Confirm rail — the only confirmation in the product ────── */}
        {ui.overlay === 'confirm-lock' && (
          <div style={{ margin: '12px 0' }}>
            <ConfirmRail
              title="Lock the thesis?"
              body={`This freezes the thesis, ${session.scenarios.length} scenarios and the risk envelope. You will be able to append, but never revise.`}
              confirmLabel="Lock"
              onConfirm={doLock}
              onCancel={closeOverlay}
            />
          </div>
        )}

        {/* ── Thesis ─────────────────────────────────────────────────── */}
        <Rule right={locked ? <span className="mono">locked {formatTime(session.lockedAt!)}</span> : undefined}>
          Thesis
        </Rule>

        {locked ? (
          <div className={`locked-block paper ${sealing ? 'is-sealing' : ''}`}>
            <div className="prose measure">{session.thesis}</div>
            {/* §0.1 You can append, never revise. */}
            {session.appends.map((a) => (
              <div className="append" key={a.id}>
                <div className="lock-stamp">appended {formatTime(a.at)}</div>
                <div className="prose measure">{a.text}</div>
              </div>
            ))}
            {appending ? (
              <AppendBox
                onCommit={(text) => {
                  appendToSession(session.id, text)
                  setAppending(false)
                  toast('Appended', true)
                }}
                onCancel={() => setAppending(false)}
              />
            ) : (
              <Button variant="quiet" onClick={() => setAppending(true)}>
                Append
              </Button>
            )}
          </div>
        ) : (
          <>
            <BlockEditor
              value={session.thesis}
              onChange={(v) => setThesis(session.id, v)}
              placeholder="What do you believe about today, and what would make you wrong?"
              savedAt={session.updatedAt}
              autoFocus={focusField?.field === 'thesis'}
              commands={[
                {
                  id: 'scenario',
                  label: '/scenario',
                  hint: 'name · trigger · invalidation · target · p',
                  run: () => upsertScenario(session.id, {}),
                },
                {
                  id: 'levels',
                  label: '/levels',
                  hint: 'insert the level ladder',
                  run: () => navigate({ surface: 'notebook' }),
                },
              ]}
            />
            <TemplatePicker
              onPick={(body) => setThesis(session.id, session.thesis + body)}
            />
          </>
        )}

        {/* ── Scenarios ──────────────────────────────────────────────── */}
        <Rule
          right={
            !locked ? (
              <Button variant="quiet" onClick={() => upsertScenario(session.id, {})}>
                + scenario
              </Button>
            ) : undefined
          }
        >
          Scenarios
        </Rule>
        {session.scenarios.length === 0 ? (
          <Empty>
            A thesis needs at least two scenarios. The third is optional and
            titled “what would make me wrong.”
          </Empty>
        ) : (
          session.scenarios.map((sc, i) => (
            <ScenarioBlock
              key={sc.id}
              scenario={sc}
              locked={locked}
              focusField={focusField?.scenarioId === sc.id ? focusField.field : null}
              onChange={(patch) => upsertScenario(session.id, { id: sc.id, ...patch })}
              onRemove={() => removeScenario(session.id, sc.id)}
              onResolve={
                locked
                  ? (status) => {
                      resolveScenario(session.id, sc.id, status)
                      toast(`Scenario ${sc.letter} · ${status} · ⌥${i + 1}`, true)
                    }
                  : undefined
              }
            />
          ))
        )}

        {/* ── Levels · Events · Positions ────────────────────────────── */}
        <div className="cockpit__cols">
          <div>
            <Rule>Levels</Rule>
            <LevelLadder
              levels={levels}
              onTag={(id, outcome) => {
                tagLevel(id, outcome)
                toast(`Level ${outcome}`, true)
              }}
            />
          </div>
          <div>
            <Rule>Events</Rule>
            {events.length ? (
              <EventClock events={events} />
            ) : (
              <span className="faint" style={{ fontSize: 'var(--t-12)' }}>
                Nothing scheduled.
              </span>
            )}
          </div>
          <div>
            <Rule>Positions</Rule>
            <PositionStrip
              positions={positions}
              instrument={inst}
              onOpen={(id) => navigate({ surface: 'trade', objectId: id })}
              onClose={(id) => {
                const price = window.prompt('Exit price?')
                if (price && !Number.isNaN(Number(price))) {
                  closeTrade(id, Number(price))
                  toast('Trade closed', true)
                }
              }}
            />
          </div>
        </div>

        {/* ── Risk envelope ──────────────────────────────────────────── */}
        {risk && (
          <>
            <Divider />
            <RiskEnvelopeBar session={session} status={risk} />
            {!locked && (
              <div className="cockpit__riskedit">
                <label>
                  max trades
                  <input
                    type="number"
                    min={1}
                    value={session.risk.maxTrades}
                    onChange={(e) =>
                      setRisk(session.id, {
                        ...session.risk,
                        maxTrades: Number(e.target.value),
                      })
                    }
                  />
                </label>
                <label>
                  max loss (R)
                  <input
                    type="number"
                    step="0.5"
                    value={session.risk.maxLossR}
                    onChange={(e) =>
                      setRisk(session.id, {
                        ...session.risk,
                        maxLossR: Number(e.target.value),
                      })
                    }
                  />
                </label>
                <label>
                  concurrent
                  <input
                    type="number"
                    min={1}
                    value={session.risk.maxConcurrent}
                    onChange={(e) =>
                      setRisk(session.id, {
                        ...session.risk,
                        maxConcurrent: Number(e.target.value),
                      })
                    }
                  />
                </label>
              </div>
            )}
          </>
        )}

        {/* ── Stream ─────────────────────────────────────────────────── */}
        <Rule
          right={
            <span className="cockpit__streamkeys">
              <Kbd>T</Kbd> trade · <Kbd>O</Kbd> observe
            </span>
          }
        >
          Stream
        </Rule>

        {ui.overlay === 'ticket' && (
          <div style={{ marginBottom: 8 }}>
            <TradeTicket
              instrument={inst}
              ctx={{
                instruments: db.instruments,
                playbook,
                defaultInstrumentId: instrumentId,
                defaultQty: inst.lotSize,
                emotions: db.settings.emotions.map((e) => e.label),
              }}
              onCommit={(line) => {
                commitTicket(line)
                closeOverlay()
              }}
              onCancel={closeOverlay}
            />
          </div>
        )}

        {observing && (
          <div className="cockpit__obs glass">
            <span className="label">obs</span>
            <input
              ref={obsRef}
              className="cockpit__obsinput"
              placeholder="What do you see? Timestamped, no other fields required."
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  const v = (e.target as HTMLInputElement).value
                  if (v.trim()) {
                    observe(session.id, instrumentId, v)
                    toast('Observation logged', true)
                  }
                  ;(e.target as HTMLInputElement).value = ''
                  setObserving(false)
                }
                if (e.key === 'Escape') setObserving(false)
              }}
              onBlur={() => setObserving(false)}
            />
            <Kbd>⏎</Kbd>
          </div>
        )}

        <div className="cockpit__stream">
          {stream.length === 0 ? (
            <Empty kbd="O">Nothing recorded yet today.</Empty>
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
      </div>
    </div>
  )
}

function AppendBox({
  onCommit,
  onCancel,
}: {
  onCommit: (text: string) => void
  onCancel: () => void
}) {
  const [text, setText] = useState('')
  return (
    <div className="append append--editing">
      <BlockEditor
        value={text}
        onChange={setText}
        placeholder="Append — the original stays as written."
        autoFocus
        minRows={3}
      />
      <div className="cockpit__appendactions">
        <Button variant="quiet" onClick={onCancel}>
          Cancel
        </Button>
        <Button variant="default" onClick={() => onCommit(text)} disabled={!text.trim()}>
          Append
        </Button>
      </div>
    </div>
  )
}

/** Used by the Inbox surface too. §4.4 */
export function triage(eventId: string, keep: boolean) {
  triageEvent(eventId, keep)
  toast(keep ? 'Moved into the session' : 'Dismissed', true)
}

export { relativeDays }
