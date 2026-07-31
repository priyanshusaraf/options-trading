/* Inbox (§4.4) · Weekly and Monthly reviews (§2.5, §2.6) · Settings (§5.11) */

import { useMemo, useState } from 'react'
import {
  useDB,
  useInbox,
  useInstrument,
  useInstruments,
  useSetupLookup,
  useTrades,
} from '../data/hooks'
import { navigate, toast, useUI } from '../app/uiState'
import {
  addTaxonomyItem,
  deleteQuery,
  restoreTrades,
  retireTaxonomyItem,
  triageEvent,
  updateInstrument,
  updateSettings,
  upsertPeriodReview,
} from '../data/actions'
import { clearSnapshot } from '../data/idb'
import { Button, Chip, Divider, Empty, Rule, Segment, Toggle } from '../components/primitives'
import { BlockEditor } from '../components/editor/BlockEditor'
import { StatCell, fmtPct, fmtR, fmtRupees, signClass } from '../components/data'
import { MistakeChip, StreamRow } from '../components/domain'
import {
  calibration,
  ledger,
  mistakeExtinction,
  mistakeLedger,
  realisedR,
  teachingTrades,
} from '../domain/metrics'
import {
  addDays,
  formatDate,
  monthStart,
  relativeDays,
  today,
  weekStart,
} from '../domain/dates'
import type { RBasis } from '../domain/types'
import './surfaces.css'

// ── Inbox ─────────────────────────────────────────────────────────────────
// §4.4 Everything quick-captured lands here, and Prep mode's first block is
// "triage inbox (3)".

export function Inbox() {
  const ui = useUI()
  const db = useDB()
  const items = useInbox(ui.route.instrumentId)

  return (
    <div className="surface">
      <div className="surface__head">
        <span className="surface__title">Inbox</span>
        <span className="faint">
          Captured away from the desk. Triage is the first act of Prep.
        </span>
      </div>
      <div className="surface__body">
        {items.length === 0 ? (
          <Empty kbd="⌘⇧Space">
            Nothing waiting. Observations die within ninety seconds of
            occurring — capture them from anywhere.
          </Empty>
        ) : (
          items.map((e) => (
            <div className="inbox__row" key={e.id}>
              <StreamRow
                event={e}
                trade={db.trades.find((t) => t.id === e.tradeId)}
              />
              <div className="inbox__actions">
                {e.capturedFrom && (
                  <Chip title="Stamped with the module you were looking at">
                    from {e.capturedFrom}
                  </Chip>
                )}
                <Button
                  variant="quiet"
                  onClick={() => {
                    triageEvent(e.id, true)
                    toast('Moved into the session', true)
                  }}
                >
                  keep
                </Button>
                <Button
                  variant="quiet"
                  onClick={() => {
                    triageEvent(e.id, false)
                    toast('Dismissed', true)
                  }}
                >
                  dismiss
                </Button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// ── Weekly / Monthly ──────────────────────────────────────────────────────
// §2.5 "You write the prose; the system supplies the evidence."
// §2.6 The Evolution surface — a comparison of you against you.

export function PeriodReview() {
  const ui = useUI()
  const db = useDB()
  const inst = useInstrument(ui.route.instrumentId)
  const allTrades = useTrades(ui.route.instrumentId)
  const [kind, setKind] = useState<'weekly' | 'monthly'>('weekly')

  const periodStart =
    kind === 'weekly' ? weekStart(ui.route.date) : monthStart(ui.route.date)
  const periodEnd =
    kind === 'weekly' ? addDays(periodStart, 6) : addDays(monthStart(addDays(periodStart, 32)), -1)

  const trades = useMemo(
    () => allTrades.filter((t) => t.date >= periodStart && t.date <= periodEnd),
    [allTrades, periodStart, periodEnd],
  )
  // §2.6 Rolling 3-month comparison — you against you.
  const priorTrades = useMemo(() => {
    const priorStart = kind === 'weekly' ? addDays(periodStart, -7) : monthStart(addDays(periodStart, -1))
    return allTrades.filter((t) => t.date >= priorStart && t.date < periodStart)
  }, [allTrades, periodStart, kind])

  const existing = db.periodReviews.find(
    (r) => r.kind === kind && r.periodStart === periodStart && r.instrumentId === (inst?.id ?? null),
  )
  const [body, setBody] = useState(existing?.body ?? '')

  const l = inst ? ledger(trades, inst, db.settings.evidenceThreshold) : null
  const prior = inst ? ledger(priorTrades, inst, db.settings.evidenceThreshold) : null
  const mistakes = inst ? mistakeLedger(trades, inst) : []
  const teaching = inst ? teachingTrades(trades, inst) : null
  const extinction = useMemo(() => mistakeExtinction(allTrades), [allTrades])

  const editedDocs = db.docs.filter(
    (d) =>
      d.instrumentId === ui.route.instrumentId &&
      new Date(d.updatedAt).toISOString().slice(0, 10) >= periodStart,
  )

  if (!inst || !l || !prior) return null

  return (
    <div className="surface">
      <div className="surface__head">
        <span className="surface__title">
          {kind === 'weekly' ? 'Weekly review' : 'Evolution'} · {formatDate(periodStart)} →{' '}
          {formatDate(periodEnd)}
        </span>
        <span className="surface__spacer" />
        <Segment
          value={kind}
          onChange={setKind}
          options={[
            { value: 'weekly', label: 'Weekly' },
            { value: 'monthly', label: 'Monthly' },
          ]}
        />
      </div>

      {/* §2.6 Monthly is the one surface allowed to be beautiful in a slow,
          editorial way — it is read, not scanned. */}
      <div
        className={`surface__body ${kind === 'monthly' ? 'surface__body--prose' : ''} period`}
      >
        <div className="period__evidence">
          <Rule>The evidence</Rule>
          <div className="period__stats">
            <StatCell label="Expectancy" stat={l.expectancy} format="R" />
            <StatCell label="Adherence" stat={l.adherence} format="%" />
            <StatCell label="Would take again" stat={l.takeAgainRate} format="%" />
            <StatCell label="Capture" stat={l.captureRate} format="%" />
          </div>
          <div className="period__delta">
            <span className="label">vs previous {kind === 'weekly' ? 'week' : 'month'}</span>
            <span className={`num ${signClass(l.expectancy.value - prior.expectancy.value)}`}>
              {fmtR(l.expectancy.value - prior.expectancy.value, 2)} expectancy
            </span>
            <span className={`num ${signClass(l.adherence.value - prior.adherence.value)}`}>
              {fmtPct(l.adherence.value - prior.adherence.value)} adherence
            </span>
            <span className="faint">
              n={l.count} vs n={prior.count}
            </span>
          </div>

          <Rule>Mistakes, ranked by cost</Rule>
          {mistakes.length ? (
            <div className="period__mistakes">
              {mistakes.map((m) => (
                <MistakeChip
                  key={m.mistake}
                  mistake={m.mistake}
                  count={m.count}
                  cost={m.totalRupees}
                  onClick={() =>
                    navigate({ surface: 'blotter', query: `mistake:${m.mistake}` })
                  }
                />
              ))}
            </div>
          ) : (
            <span className="faint">None tagged this period.</span>
          )}

          {/* §2.5 the week's worst-graded winner and best-graded loser —
              these two trades teach more than any other. */}
          {teaching && (teaching.worstGradedWinner || teaching.bestGradedLoser) && (
            <>
              <Rule>The two that teach</Rule>
              <div className="period__teaching">
                {teaching.worstGradedWinner && (
                  <button
                    className="period__teach"
                    onClick={() =>
                      navigate({ surface: 'trade', objectId: teaching.worstGradedWinner!.id })
                    }
                  >
                    <span className="label">Worst-graded winner</span>
                    <span className="mono">
                      {formatDate(teaching.worstGradedWinner.date, false)} ·{' '}
                      grade {teaching.worstGradedWinner.grade} ·{' '}
                      {fmtR(realisedR(teaching.worstGradedWinner, inst))}
                    </span>
                    <span className="faint">
                      You got paid for a decision you would not repeat.
                    </span>
                  </button>
                )}
                {teaching.bestGradedLoser && (
                  <button
                    className="period__teach"
                    onClick={() =>
                      navigate({ surface: 'trade', objectId: teaching.bestGradedLoser!.id })
                    }
                  >
                    <span className="label">Best-graded loser</span>
                    <span className="mono">
                      {formatDate(teaching.bestGradedLoser.date, false)} ·{' '}
                      grade {teaching.bestGradedLoser.grade} ·{' '}
                      {fmtR(realisedR(teaching.bestGradedLoser, inst))}
                    </span>
                    <span className="faint">
                      You did the right thing and lost. Do it again.
                    </span>
                  </button>
                )}
              </div>
            </>
          )}

          {kind === 'monthly' && (
            <>
              {/* §2.6 mistake-class extinction — which errors you have
                  actually stopped making. */}
              <Rule>Mistake extinction</Rule>
              <div className="period__extinction">
                {extinction.map((m) => {
                  const days = m.lastSeen
                    ? Math.floor((Date.now() - m.lastSeen) / 86_400_000)
                    : null
                  return (
                    <div className="period__extrow" key={m.mistake}>
                      <span className={days != null && days > 60 ? 'pos' : ''}>
                        {m.mistake}
                      </span>
                      <span className="mono faint">×{m.count}</span>
                      <span className="mono faint">
                        {m.lastSeen ? `last ${relativeDays(m.lastSeen)}` : '—'}
                      </span>
                    </div>
                  )
                })}
              </div>

              <Rule>Calibration</Rule>
              <div className="period__calib">
                {calibration(trades, inst, db.settings.evidenceThreshold).map((c) => (
                  <div className="stats__line" key={c.confidence}>
                    <span className="label">conf {c.confidence}</span>
                    <StatCell stat={c.winRate} format="%" compact />
                  </div>
                ))}
              </div>

              {/* §2.6 a rendered "what I believed then" excerpt from three
                  months ago placed next to what you believe now. */}
              <Rule>What I believed then</Rule>
              <ThenAndNow />
            </>
          )}

          {editedDocs.length > 0 && (
            <>
              <Rule>Notebook edits</Rule>
              <div className="period__docs">
                {editedDocs.map((d) => (
                  <button
                    key={d.id}
                    className="period__doc"
                    onClick={() => navigate({ surface: 'notebook', objectId: d.id })}
                  >
                    {d.title}
                    <span className="faint"> · {relativeDays(d.updatedAt)}</span>
                  </button>
                ))}
              </div>
            </>
          )}

          <Rule>Playbook performance</Rule>
          <div className="period__setups">
            {db.playbook
              .filter((p) => !p.archived)
              .map((p) => {
                const ts = trades.filter((t) => t.setupId === p.id)
                const pl = ledger(ts, inst, db.settings.evidenceThreshold)
                return (
                  <div className="stats__line" key={p.id}>
                    <button
                      className="stats__key"
                      onClick={() =>
                        navigate({ surface: 'blotter', query: `setup:${p.code}` })
                      }
                    >
                      {p.name}
                    </button>
                    <StatCell stat={pl.expectancy} format="R" compact />
                  </div>
                )
              })}
          </div>
        </div>

        <div className="period__prose">
          <Rule>Your write-up</Rule>
          <BlockEditor
            value={body}
            onChange={(v) => {
              setBody(v)
              upsertPeriodReview(kind, periodStart, inst.id, v)
            }}
            placeholder={
              kind === 'weekly'
                ? 'What does the evidence above actually say, and what are you changing?'
                : 'Three months ago you believed something. Do you still?'
            }
            minRows={14}
          />
        </div>
      </div>
    </div>
  )
}

function ThenAndNow() {
  const ui = useUI()
  const db = useDB()
  const doc = db.docs.find(
    (d) => d.instrumentId === ui.route.instrumentId && d.title === 'Market opinion',
  )
  if (!doc) return null
  // The oldest version still retained is the closest thing to "three months
  // ago" the local history can honestly offer.
  const then = doc.versions[0]
  return (
    <div className="period__thennow">
      <div>
        <span className="label">
          {then ? relativeDays(then.at) : 'no earlier version retained'}
        </span>
        <div className="prose">
          {then?.body || (
            <span className="faint">
              No earlier version of your market opinion has been retained yet.
              This panel fills itself as you revise.
            </span>
          )}
        </div>
      </div>
      <div>
        <span className="label">now · {relativeDays(doc.updatedAt)}</span>
        <div className="prose">{doc.body}</div>
      </div>
    </div>
  )
}

// ── Settings / Schema ─────────────────────────────────────────────────────
// §5.11 "Schema edits are versioned so historical data is never silently
// re-interpreted."

export function Settings() {
  const db = useDB()
  const instruments = useInstruments()
  const s = db.settings
  const [newMistake, setNewMistake] = useState('')
  const [newEmotion, setNewEmotion] = useState('')

  const deleted = db.trades.filter((t) => t.deletedAt != null)

  return (
    <div className="surface">
      <div className="surface__head">
        <span className="surface__title">Settings &amp; schema</span>
        <span className="faint">schema v{s.schemaVersion}</span>
      </div>

      <div className="surface__body settings">
        <section>
          <Rule>Appearance</Rule>
          <div className="settings__row">
            <span>Theme</span>
            <Segment
              value={s.theme}
              onChange={(theme) => updateSettings({ theme })}
              options={[
                { value: 'dark', label: 'Dark' },
                { value: 'light', label: 'Light' },
              ]}
            />
          </div>
          <div className="settings__row">
            <span>Density</span>
            <Segment
              value={s.density}
              onChange={(density) => updateSettings({ density })}
              options={[
                { value: 'compact', label: 'Compact' },
                { value: 'comfortable', label: 'Comfortable' },
              ]}
            />
          </div>
          <div className="settings__row">
            <span>
              Colourblind-safe palette
              <span className="faint"> — long/short become periwinkle/amber</span>
            </span>
            <Toggle checked={s.cvdSafe} onChange={(cvdSafe) => updateSettings({ cvdSafe })} />
          </div>
          <div className="settings__row">
            <span>
              Sound
              <span className="faint"> — one tick on commit, two tones on lock</span>
            </span>
            <Toggle checked={s.sound} onChange={(sound) => updateSettings({ sound })} />
          </div>
        </section>

        <section>
          <Rule>Evidence threshold</Rule>
          <div className="settings__row">
            <span>
              Below this n, metrics render with no number at all
              <span className="faint">
                {' '}
                — the design argues hard for 20. Lowering it is how you end up
                revising a strategy on nine observations.
              </span>
            </span>
            <input
              type="number"
              min={2}
              className="settings__num"
              value={s.evidenceThreshold}
              onChange={(e) =>
                updateSettings({ evidenceThreshold: Number(e.target.value) })
              }
            />
          </div>
        </section>

        <section>
          <Rule>Default risk envelope</Rule>
          <div className="settings__row">
            <span>Max trades / max loss (R) / max concurrent</span>
            <span className="settings__triple">
              <input
                type="number"
                value={s.defaultRisk.maxTrades}
                onChange={(e) =>
                  updateSettings({
                    defaultRisk: { ...s.defaultRisk, maxTrades: Number(e.target.value) },
                  })
                }
              />
              <input
                type="number" step="0.5"
                value={s.defaultRisk.maxLossR}
                onChange={(e) =>
                  updateSettings({
                    defaultRisk: { ...s.defaultRisk, maxLossR: Number(e.target.value) },
                  })
                }
              />
              <input
                type="number"
                value={s.defaultRisk.maxConcurrent}
                onChange={(e) =>
                  updateSettings({
                    defaultRisk: {
                      ...s.defaultRisk,
                      maxConcurrent: Number(e.target.value),
                    },
                  })
                }
              />
            </span>
          </div>
        </section>

        {/* §11.2 R is defined per instrument and must be one thing. */}
        <section>
          <Rule>Instruments · R definition and session hours</Rule>
          {instruments.map((inst) => (
            <div className="settings__inst" key={inst.id}>
              <span className="mono settings__instcode">{inst.code}</span>
              <span className="settings__instname">{inst.name}</span>
              <select
                value={inst.rBasis}
                onChange={(e) =>
                  updateInstrument(inst.id, { rBasis: e.target.value as RBasis })
                }
              >
                <option value="initial-stop">R = initial stop</option>
                <option value="fixed-rupee">R = fixed rupee risk</option>
                <option value="account-pct">R = account %</option>
              </select>
              {inst.rBasis === 'fixed-rupee' && (
                <input
                  type="number"
                  value={inst.fixedRisk ?? 0}
                  onChange={(e) =>
                    updateInstrument(inst.id, { fixedRisk: Number(e.target.value) })
                  }
                  title="Rupees per R"
                />
              )}
              {inst.rBasis === 'account-pct' && (
                <>
                  <input
                    type="number"
                    value={inst.accountEquity ?? 0}
                    onChange={(e) =>
                      updateInstrument(inst.id, { accountEquity: Number(e.target.value) })
                    }
                    title="Account equity"
                  />
                  <input
                    type="number" step="0.1"
                    value={inst.accountRiskPct ?? 0}
                    onChange={(e) =>
                      updateInstrument(inst.id, { accountRiskPct: Number(e.target.value) })
                    }
                    title="Risk % per trade"
                  />
                </>
              )}
              <input
                className="settings__time"
                value={inst.hours.open}
                onChange={(e) =>
                  updateInstrument(inst.id, {
                    hours: { ...inst.hours, open: e.target.value },
                  })
                }
              />
              <input
                className="settings__time"
                value={inst.hours.close}
                onChange={(e) =>
                  updateInstrument(inst.id, {
                    hours: { ...inst.hours, close: e.target.value },
                  })
                }
              />
            </div>
          ))}
        </section>

        <section>
          <Rule>Mistake taxonomy</Rule>
          <div className="settings__tax">
            {s.mistakes.map((m) => (
              <Chip
                key={m.id}
                tone={m.retired ? 'neutral' : 'attention'}
                onClick={() => retireTaxonomyItem('mistakes', m.id)}
                title={m.retired ? 'Retired — click to restore' : 'Click to retire'}
              >
                {m.retired ? <s>{m.label}</s> : m.label}
              </Chip>
            ))}
          </div>
          <div className="settings__add">
            <input
              value={newMistake}
              placeholder="new mistake"
              onChange={(e) => setNewMistake(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && newMistake.trim()) {
                  addTaxonomyItem('mistakes', newMistake.trim())
                  setNewMistake('')
                }
              }}
            />
            <span className="faint">
              Retiring keeps historical rows resolvable — nothing is
              re-interpreted.
            </span>
          </div>
        </section>

        <section>
          <Rule>Emotion taxonomy</Rule>
          <div className="settings__tax">
            {s.emotions.map((m) => (
              <Chip
                key={m.id}
                onClick={() => retireTaxonomyItem('emotions', m.id)}
              >
                {m.retired ? <s>{m.label}</s> : m.label}
              </Chip>
            ))}
          </div>
          <div className="settings__add">
            <input
              value={newEmotion}
              placeholder="new emotion"
              onChange={(e) => setNewEmotion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && newEmotion.trim()) {
                  addTaxonomyItem('emotions', newEmotion.trim())
                  setNewEmotion('')
                }
              }}
            />
          </div>
        </section>

        <section>
          <Rule>Saved queries</Rule>
          {db.savedQueries.map((q) => (
            <div className="settings__row" key={q.id}>
              <span>
                {q.name} <code className="faint">{q.query}</code>
              </span>
              <Button variant="quiet" onClick={() => deleteQuery(q.id)}>
                remove
              </Button>
            </div>
          ))}
        </section>

        {/* §8 Deletes are soft for 30 days. */}
        <section>
          <Rule right={<span className="faint">soft for 30 days</span>}>Trash</Rule>
          {deleted.length === 0 ? (
            <span className="faint">Nothing deleted.</span>
          ) : (
            deleted.map((t) => (
              <div className="settings__row" key={t.id}>
                <span className="mono">
                  {formatDate(t.date, false)} · {t.direction} ·{' '}
                  {t.contract === 'OPT' ? `${t.strike} ${t.optionType}` : t.contract}
                </span>
                <Button variant="quiet" onClick={() => restoreTrades([t.id])}>
                  restore
                </Button>
              </div>
            ))
          )}
        </section>

        <section>
          <Rule>Data</Rule>
          <div className="settings__row">
            <span>
              Export the whole journal as JSON
              <span className="faint"> — local-first means it is yours</span>
            </span>
            <Button
              variant="quiet"
              onClick={() => {
                const blob = new Blob([JSON.stringify(db, null, 2)], {
                  type: 'application/json',
                })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `ledger-${today()}.json`
                a.click()
                URL.revokeObjectURL(url)
              }}
            >
              Export
            </Button>
          </div>
          <Divider />
          <div className="settings__row">
            <span>
              Reset to seed data
              <span className="faint"> — this one is not undoable</span>
            </span>
            <Button
              variant="quiet"
              onClick={async () => {
                if (
                  window.confirm(
                    'Discard this journal and reload the seeded demo data?',
                  )
                ) {
                  await clearSnapshot()
                  window.location.reload()
                }
              }}
            >
              Reset
            </Button>
          </div>
        </section>
      </div>
    </div>
  )
}

export { fmtRupees, useSetupLookup }
