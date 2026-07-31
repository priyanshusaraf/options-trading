/* Session Review — §5.8, §2.4, `gr`
 *
 * "Full-width, single column, 68ch measure, serif, no chrome except a progress
 *  rail on the left. One step at a time. P&L masked until step 4."
 *
 * §1.2 "The product should be pleasant to open at 15:35 after a losing day."
 * That is why this surface is the warmest and least numeric in the product,
 * and why the number comes at the end rather than the beginning.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  useDB,
  useInstrument,
  useSession,
  useSessionTrades,
} from '../data/hooks'
import { getUI, navigate, setUI, toast, togglePnl, useUI } from '../app/uiState'
import {
  completeReview,
  ensureSession,
  resolveScenario,
  setScenarioPaid,
  updateReview,
  updateTradeJudgement,
} from '../data/actions'
import { BlockEditor } from '../components/editor/BlockEditor'
import { ConfidenceMeter, GradePill, MistakeChip, ThesisDiff } from '../components/domain'
import { Button, Chip, Empty, Kbd } from '../components/primitives'
import { EquityTrack, StatCell, fmtR, fmtRupees, signClass } from '../components/data'
import {
  decisionOutcome,
  equityCurve,
  ledger,
  marketReadScore,
  netPnl,
  realisedR,
} from '../domain/metrics'
import { formatDate, formatTime, weekday } from '../domain/dates'
import type { Grade } from '../domain/types'
import './surfaces.css'

const STEPS = [
  { n: 1, label: 'Reconcile' },
  { n: 2, label: 'Grade each trade' },
  { n: 3, label: 'MFE / MAE' },
  { n: 4, label: 'Reveal' },
  { n: 5, label: 'One line for tomorrow' },
]

export function Review() {
  const ui = useUI()
  const db = useDB()
  const inst = useInstrument(ui.route.instrumentId)
  const session = useSession(ui.route.instrumentId, ui.route.date)
  const trades = useSessionTrades(session?.id ?? '')
  const [step, setStep] = useState(session?.review?.step ?? 1)
  const maskedFor = useRef<string | null>(null)

  // §2.4 / §5.8 P&L is hidden until step 4. Opening a review re-arms the mask
  // once per session, so it is the default state rather than something the
  // user has to ask for — but ⌘E still lifts it, because it is a nudge and
  // not a wall.
  useEffect(() => {
    const key = session?.id ?? ''
    if (!key || maskedFor.current === key) return
    maskedFor.current = key
    if (getUI().pnlRevealed) setUI({ pnlRevealed: false })
  }, [session?.id])

  const read = useMemo(
    () => marketReadScore(session?.scenarios ?? []),
    [session],
  )
  const l = useMemo(
    () => (inst ? ledger(trades, inst, db.settings.evidenceThreshold) : null),
    [trades, inst, db.settings.evidenceThreshold],
  )

  if (!inst) return null
  if (!session) {
    return (
      <Empty kbd="gd">
        No session on {formatDate(ui.route.date)}.{' '}
        <Button
          variant="quiet"
          onClick={() => ensureSession(ui.route.instrumentId, ui.route.date)}
        >
          Start one
        </Button>
      </Empty>
    )
  }

  // §2.4 P&L is hidden until step 4. The mask is a nudge, not a wall — ⌘E.
  const masked = step < 4 && !ui.pnlRevealed
  const dayR = trades.reduce((a, t) => a + (realisedR(t, inst) ?? 0), 0)
  const dayRupees = trades.reduce((a, t) => a + (netPnl(t) ?? 0), 0)

  function go(n: number) {
    setStep(n)
    updateReview(session!.id, { step: n })
  }

  return (
    <div className="surface review">
      {/* §5.8 no chrome except a progress rail on the left. */}
      <nav className="review__rail">
        {STEPS.map((s) => (
          <button
            key={s.n}
            className={`review__step ${step === s.n ? 'is-active' : ''} ${
              step > s.n ? 'is-done' : ''
            }`}
            onClick={() => go(s.n)}
          >
            <span className="review__stepnum mono">{s.n}</span>
            <span className="review__steplabel">{s.label}</span>
          </button>
        ))}
      </nav>

      <div className="review__body scroll">
        <header className="review__head">
          <h1 className="review__title">
            {inst.name} · {formatDate(session.date)} · {weekday(session.date)}
          </h1>
          {session.review?.completedAt ? (
            <span className="lock-stamp">
              reviewed {formatTime(session.review.completedAt)}
            </span>
          ) : (
            <span className="faint">Ten minutes. One question at a time.</span>
          )}
        </header>

        {/* ── 1 Reconcile ─────────────────────────────────────────────── */}
        {step === 1 && (
          <section className="review__section">
            <h2 className="review__q">What did you believe, and what happened?</h2>
            {session.lockedAt ? (
              <ThesisDiff
                session={session}
                onResolve={(id, status) => resolveScenario(session.id, id, status)}
                onPaid={(id, paid) => setScenarioPaid(session.id, id, paid)}
              />
            ) : (
              <p className="review__prose">
                This session was never locked, so there is no belief to
                reconcile against. Every trade in it carries a{' '}
                <code>no-thesis</code> tag — which is itself the finding.
              </p>
            )}
            <div className="review__score">
              <span className="label">Market read</span>
              <span className="mono">
                {read.resolved
                  ? `${(read.score * 100).toFixed(0)}% of ${read.resolved} resolved`
                  : 'nothing resolved'}
              </span>
              <span className="faint">— independent of money.</span>
            </div>
            <NextButton onClick={() => go(2)} label="Grade the trades" />
          </section>
        )}

        {/* ── 2 Grade each trade ──────────────────────────────────────── */}
        {step === 2 && (
          <section className="review__section">
            <h2 className="review__q">
              For each trade — and the important one: would you take it again
              given only what you knew at entry?
            </h2>
            {trades.length === 0 ? (
              <p className="review__prose">
                No trades today. Staying out is a decision, and it belongs in
                the record too — say why in step 5.
              </p>
            ) : (
              trades.map((t) => (
                <div className="review__trade" key={t.id}>
                  <div className="review__tradehead">
                    <span className="mono">
                      {formatTime(t.openedAt, false)} ·{' '}
                      {t.contract === 'OPT'
                        ? `${t.strike} ${t.optionType}`
                        : t.contract}{' '}
                      · {t.direction}
                    </span>
                    {/* P&L stays masked here — grading must not be
                        contaminated by the result. §2.4 */}
                    <span className="mono faint">
                      {masked ? '•••••' : fmtR(realisedR(t, inst))}
                    </span>
                    <ConfidenceMeter value={t.confidence} locked />
                  </div>
                  <div className="review__tradecontrols">
                    <GradePill
                      grade={t.grade}
                      onChange={(g: Grade) => updateTradeJudgement(t.id, { grade: g })}
                    />
                    <span className="review__again">
                      <button
                        className={`thesisdiff__btn ${t.takeAgain === true ? 'is-on' : ''}`}
                        onClick={() => updateTradeJudgement(t.id, { takeAgain: true })}
                      >
                        take again
                      </button>
                      <button
                        className={`thesisdiff__btn ${t.takeAgain === false ? 'is-on' : ''}`}
                        onClick={() => updateTradeJudgement(t.id, { takeAgain: false })}
                      >
                        no
                      </button>
                    </span>
                    <select
                      className="td__add"
                      value=""
                      onChange={(e) => {
                        if (!e.target.value) return
                        updateTradeJudgement(t.id, {
                          mistakes: [...new Set([...t.mistakes, e.target.value])],
                        })
                      }}
                    >
                      <option value="">+ mistake</option>
                      {db.settings.mistakes
                        .filter((m) => !m.retired)
                        .map((m) => (
                          <option key={m.id} value={m.label}>
                            {m.label}
                          </option>
                        ))}
                    </select>
                    {[...t.autoTags, ...t.mistakes].map((m) => (
                      <MistakeChip
                        key={m}
                        mistake={m}
                        auto={t.autoTags.includes(m)}
                      />
                    ))}
                  </div>
                  <BlockEditor
                    value={t.exitNote}
                    onChange={(v) => updateTradeJudgement(t.id, { exitNote: v })}
                    placeholder="Execution notes"
                    minRows={2}
                  />
                </div>
              ))
            )}
            <NextButton onClick={() => go(3)} label="MFE / MAE" />
          </section>
        )}

        {/* ── 3 MFE / MAE ─────────────────────────────────────────────── */}
        {step === 3 && (
          <section className="review__section">
            <h2 className="review__q">
              How far did each trade go for you, and against you?
            </h2>
            <p className="review__prose review__prose--small">
              This yields exit quality, which is where most discretionary
              traders actually leak. Entered by hand here — the workstation
              would fill it from market data if it had it.
            </p>
            {trades.map((t) => (
              <div className="review__mfe" key={t.id}>
                <span className="mono">
                  {formatTime(t.openedAt, false)} ·{' '}
                  {t.contract === 'OPT' ? `${t.strike} ${t.optionType}` : t.contract}
                </span>
                <label>
                  MFE
                  <input
                    type="number" step="0.1"
                    value={t.mfeR ?? ''}
                    onChange={(e) =>
                      updateTradeJudgement(t.id, {
                        mfeR: e.target.value === '' ? null : Number(e.target.value),
                      })
                    }
                  />
                </label>
                <label>
                  MAE
                  <input
                    type="number" step="0.1"
                    value={t.maeR ?? ''}
                    onChange={(e) =>
                      updateTradeJudgement(t.id, {
                        maeR: e.target.value === '' ? null : Number(e.target.value),
                      })
                    }
                  />
                </label>
              </div>
            ))}
            <NextButton onClick={() => go(4)} label="Reveal" />
          </section>
        )}

        {/* ── 4 Reveal ────────────────────────────────────────────────── */}
        {step === 4 && l && (
          <section className="review__section">
            <h2 className="review__q">Now the number.</h2>
            <div className="review__reveal">
              <div className="review__big">
                <span className={`num ${signClass(dayR)}`}>{fmtR(dayR)}</span>
                <span className={`review__rupees num ${signClass(dayRupees)}`}>
                  {fmtRupees(dayRupees)}
                </span>
              </div>
              <EquityTrack values={equityCurve(trades, inst)} height={70} />
            </div>

            <h3 className="review__sub">Where today’s trades landed</h3>
            <ReviewQuadrants trades={trades} inst={inst} />

            <div className="review__stats">
              <StatCell label="Today’s expectancy" stat={l.expectancy} format="R" />
              <StatCell label="Would take again" stat={l.takeAgainRate} format="%" />
              <StatCell label="Capture" stat={l.captureRate} format="%" />
            </div>
            <NextButton onClick={() => go(5)} label="One line for tomorrow" />
          </section>
        )}

        {/* ── 5 One line ──────────────────────────────────────────────── */}
        {step === 5 && (
          <section className="review__section">
            <h2 className="review__q">
              One line for tomorrow.
            </h2>
            <p className="review__prose review__prose--small">
              It becomes the first item in tomorrow’s Prep. Nothing else about
              this review is required; this is.
            </p>
            <input
              className="review__oneline"
              value={session.review?.oneLineForTomorrow ?? ''}
              placeholder="Wait for the retest. Every single time."
              autoFocus
              onChange={(e) =>
                updateReview(session.id, { oneLineForTomorrow: e.target.value })
              }
            />
            <BlockEditor
              value={session.review?.notes ?? ''}
              onChange={(v) => updateReview(session.id, { notes: v })}
              placeholder="Anything else, if you want it. Optional."
              minRows={5}
            />
            <div className="review__finish">
              <Button
                variant="primary"
                onClick={() => {
                  const err = completeReview(session.id)
                  if (err) return toast(err)
                  toast('Review closed', true)
                  navigate({ surface: 'cockpit' })
                }}
                disabled={!session.review?.oneLineForTomorrow?.trim()}
              >
                Close review
              </Button>
              {!session.review?.oneLineForTomorrow?.trim() && (
                <span className="faint">
                  {/* §8 friction where it belongs — this is one of the two
                      places the product is deliberately slow. */}
                  The one line is required.
                </span>
              )}
            </div>
          </section>
        )}
      </div>

      {/* The mask is a nudge, not a wall. §5.8 */}
      {masked && (
        <button className="review__unmask" onClick={togglePnl}>
          P&L hidden until step 4 · <Kbd>⌘E</Kbd> to unmask
        </button>
      )}
    </div>
  )
}

function NextButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <div className="review__next">
      <Button variant="primary" onClick={onClick}>
        {label} →
      </Button>
    </div>
  )
}

function ReviewQuadrants({
  trades,
  inst,
}: {
  trades: ReturnType<typeof useSessionTrades>
  inst: NonNullable<ReturnType<typeof useInstrument>>
}) {
  const q = decisionOutcome(trades, inst)
  const box = (label: string, n: number, emphasis?: boolean) => (
    <div className={`quad ${emphasis ? 'is-emphasis' : ''}`}>
      <span className="label">{label}</span>
      <span className="quad__n mono">{n}</span>
    </div>
  )
  return (
    <div className="quads quads--review">
      {box('good · win', q.goodWin.length)}
      {box('good · loss', q.goodLoss.length, true)}
      {box('bad · win', q.badWin.length, true)}
      {box('bad · loss', q.badLoss.length)}
    </div>
  )
}

export { Chip }
