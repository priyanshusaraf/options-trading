/* Trade Detail — §5.4
 *
 * "Three columns. The split is philosophical: fact | narrative | judgement."
 *
 * The FACT column is glass, the NARRATIVE and JUDGEMENT columns are paper, so
 * you can see at a glance which parts of the record were written before the
 * market answered. §3.2
 */

import { useMemo, useState } from 'react'
import { useDB, useInstrument, useSetupLookup, useTrades } from '../data/hooks'
import { navigate, toast, useUI } from '../app/uiState'
import {
  closeTrade,
  tagTrades,
  untagTrade,
  updateTradeJudgement,
} from '../data/actions'
import {
  captureRatio,
  entryPrice,
  exitPrice,
  exitQuality,
  fees,
  grossPnl,
  holdMs,
  ledger,
  netPnl,
  realisedR,
} from '../domain/metrics'
import { formatDate, formatDuration, formatTime } from '../domain/dates'
import { Button, Chip, Divider, Empty, Kbd, Rule, Tag } from '../components/primitives'
import { ConfidenceMeter, DirGlyph, GradePill, MistakeChip, RMeter } from '../components/domain'
import { BlockEditor } from '../components/editor/BlockEditor'
import { fmtPct, fmtR, fmtRupees, signClass } from '../components/data'
import type { Grade, Trade } from '../domain/types'
import './surfaces.css'

export function TradeDetail() {
  const ui = useUI()
  const db = useDB()
  const trade = db.trades.find((t) => t.id === ui.route.objectId)
  const inst = useInstrument(trade?.instrumentId ?? ui.route.instrumentId)
  const setups = useSetupLookup()
  const all = useTrades(trade?.instrumentId)

  // §5.4 "The context strip at the bottom silently places this trade in its
  // own reference class."
  const reference = useMemo(() => {
    if (!trade || !inst) return null
    const sameSetup = all.filter(
      (t) =>
        t.setupId === trade.setupId &&
        t.id !== trade.id &&
        t.date.slice(0, 7) === trade.date.slice(0, 7),
    )
    return { trades: sameSetup, ledger: ledger(sameSetup, inst, db.settings.evidenceThreshold) }
  }, [trade, inst, all, db.settings.evidenceThreshold])

  if (!trade || !inst) {
    return <Empty kbd="gt">No trade selected.</Empty>
  }

  const entry = entryPrice(trade)
  const exit = exitPrice(trade)
  const r = realisedR(trade, inst)
  const capture = captureRatio(trade, inst)
  const hold = holdMs(trade)
  const setup = setups.get(trade.setupId)
  const nextTrade = all[all.findIndex((t) => t.id === trade.id) + 1]

  return (
    <div className="surface">
      <div className="surface__head">
        <DirGlyph direction={trade.direction} />
        <span className="surface__title mono">
          {inst.code}{' '}
          {trade.contract === 'OPT'
            ? `${trade.strike} ${trade.optionType}`
            : trade.contract}
        </span>
        <span className="faint">
          {trade.direction === 'long' ? 'Long' : 'Short'} ·{' '}
          {formatDate(trade.date, false)} {formatTime(trade.openedAt, false)}
          {trade.closedAt && ` → ${formatTime(trade.closedAt, false)}`}
        </span>
        {trade.closedAt == null && <Chip tone="interactive">open</Chip>}
        <span className="surface__spacer" />
        {trade.closedAt == null && (
          <Button
            variant="quiet"
            onClick={() => {
              const p = window.prompt('Exit price?')
              if (p && !Number.isNaN(Number(p))) {
                closeTrade(trade.id, Number(p))
                toast('Trade closed', true)
              }
            }}
          >
            Close position
          </Button>
        )}
        {nextTrade && (
          <Button
            variant="quiet"
            onClick={() => navigate({ surface: 'trade', objectId: nextTrade.id })}
            kbd="⌘⏎"
          >
            next trade
          </Button>
        )}
      </div>

      <div className="surface__body td">
        <div className="td__cols">
          {/* ── FACT (glass) — immutable, ideally broker-sourced ─────── */}
          <section className="td__fact glass">
            <div className="label td__colhead">Fact</div>
            <FactRow label="entry" value={entry?.toFixed(2) ?? '—'} />
            <FactRow label="exit" value={exit?.toFixed(2) ?? 'open'} />
            <FactRow label="qty" value={String(trade.qty)} />
            <FactRow
              label="gross"
              value={fmtRupees(grossPnl(trade))}
              tone={signClass(grossPnl(trade))}
            />
            <FactRow label="fees" value={fmtRupees(-fees(trade))} tone="faint" />
            <FactRow
              label="net"
              value={fmtRupees(netPnl(trade))}
              tone={signClass(netPnl(trade))}
            />
            <FactRow label="R" value={fmtR(r)} tone={signClass(r)} />
            <FactRow label="hold" value={hold ? formatDuration(hold) : '—'} />
            <Divider />
            <FactRow label="MFE" value={fmtR(trade.mfeR)} tone="pos" />
            <FactRow label="MAE" value={fmtR(trade.maeR)} tone="neg" />
            {/* §5.4 capture % — "the most under-used metric in discretionary
                trading", which is why it sits in the fact column by default. */}
            <FactRow
              label="capture"
              value={capture == null ? '—' : fmtPct(capture)}
              tone={capture != null && capture < 0.5 ? 'attn' : undefined}
            />
            <div className="td__rmeter">
              <RMeter mae={trade.maeR} mfe={trade.mfeR} realised={r} width={180} />
            </div>
            {/* §11.1 MFE/MAE are manual here — the honest label matters,
                because a hand-typed fact is weaker evidence than a fill. */}
            <div className="td__mfe">
              <label>
                MFE (R)
                <input
                  type="number" step="0.1"
                  value={trade.mfeR ?? ''}
                  onChange={(e) =>
                    updateTradeJudgement(trade.id, {
                      mfeR: e.target.value === '' ? null : Number(e.target.value),
                    })
                  }
                />
              </label>
              <label>
                MAE (R)
                <input
                  type="number" step="0.1"
                  value={trade.maeR ?? ''}
                  onChange={(e) =>
                    updateTradeJudgement(trade.id, {
                      maeR: e.target.value === '' ? null : Number(e.target.value),
                    })
                  }
                />
              </label>
              <span className="faint td__source">
                source: {trade.mfeSource}
              </span>
            </div>
            <Divider />
            <div className="label td__colhead">Fills</div>
            {trade.legs.map((l) => (
              <FactRow
                key={l.id}
                label={`${l.side} ${formatTime(l.at, false)}`}
                value={`${l.qty} @ ${l.price.toFixed(2)}`}
              />
            ))}
          </section>

          {/* ── NARRATIVE (paper) — belief, locked at entry ───────────── */}
          <section className="td__narrative paper">
            <div className="label td__colhead">Narrative</div>
            {trade.entryNoteLockedAt && (
              <div className="lock-stamp">
                ── locked {formatTime(trade.entryNoteLockedAt)} ──
              </div>
            )}
            <div className="locked-block">
              <div className="prose">
                {trade.entryNote || (
                  <span className="faint">
                    No pre-trade note. This trade is tagged{' '}
                    <code>no-thesis</code>.
                  </span>
                )}
              </div>
              <div className="td__conf">
                Conf{' '}
                <ConfidenceMeter value={trade.confidence} locked />{' '}
                <span className="faint">{trade.confidence}/5</span>
              </div>
            </div>

            {trade.closedAt && (
              <>
                <div className="lock-stamp" style={{ marginTop: 16 }}>
                  ── appended {formatTime(trade.closedAt)} ──
                </div>
                <BlockEditor
                  value={trade.exitNote}
                  onChange={(v) => updateTradeJudgement(trade.id, { exitNote: v })}
                  placeholder="What actually happened on the way out?"
                  minRows={4}
                  savedAt={trade.updatedAt}
                />
              </>
            )}

            {trade.artifactIds.length > 0 && (
              <div className="td__shots">
                {trade.artifactIds.map((id) => {
                  const a = db.artifacts.find((x) => x.id === id)
                  return (
                    <Chip key={id} onClick={() => navigate({ surface: 'vault' })}>
                      ▣ {a?.name ?? id}
                    </Chip>
                  )
                })}
              </div>
            )}
          </section>

          {/* ── JUDGEMENT (paper) — freely editable forever ───────────── */}
          <section className="td__judgement paper">
            <div className="label td__colhead">Judgement</div>

            <JRow label="Setup">
              {trade.offBook ? (
                <Chip tone="attention">off-book</Chip>
              ) : (
                <span
                  className="td__link"
                  onClick={() =>
                    navigate({ surface: 'playbook', objectId: trade.setupId ?? undefined })
                  }
                >
                  {setup?.name ?? '—'}
                </span>
              )}
            </JRow>
            <JRow label="Regime">
              <span className="mono">{trade.regime ?? 'unset'}</span>
            </JRow>
            <JRow label="Decision">
              <GradePill
                grade={trade.grade}
                onChange={(g: Grade) => {
                  updateTradeJudgement(trade.id, { grade: g })
                  toast(`Graded ${g}`, true)
                }}
              />
            </JRow>

            {/* §2.4.2 "the important one" — the truest process metric in the
                system. */}
            <JRow label="Again?">
              <span className="td__again">
                <button
                  className={`thesisdiff__btn ${trade.takeAgain === true ? 'is-on' : ''}`}
                  onClick={() => updateTradeJudgement(trade.id, { takeAgain: true })}
                >
                  yes
                </button>
                <button
                  className={`thesisdiff__btn ${trade.takeAgain === false ? 'is-on' : ''}`}
                  onClick={() => updateTradeJudgement(trade.id, { takeAgain: false })}
                >
                  no
                </button>
                <span className="faint td__hint">
                  given only what you knew at entry
                </span>
              </span>
            </JRow>

            <JRow label="Exec">
              <input
                className="td__num"
                type="number" min={0} max={10}
                value={trade.executionScore ?? ''}
                placeholder="—"
                onChange={(e) =>
                  updateTradeJudgement(trade.id, {
                    executionScore:
                      e.target.value === '' ? null : Number(e.target.value),
                  })
                }
              />
              <span className="faint">/10</span>
            </JRow>

            <JRow label="Mistakes">
              <span className="td__tags">
                {trade.autoTags.map((m) => (
                  <MistakeChip key={m} mistake={m} auto />
                ))}
                {trade.mistakes.map((m) => (
                  <MistakeChip
                    key={m}
                    mistake={m}
                    onRemove={() => untagTrade(trade.id, m, 'mistake')}
                    onClick={() =>
                      navigate({ surface: 'blotter', query: `mistake:${m}` })
                    }
                  />
                ))}
                <select
                  className="td__add"
                  value=""
                  onChange={(e) => {
                    if (e.target.value) {
                      tagTrades([trade.id], e.target.value, 'mistake')
                      toast('Mistake tagged', true)
                    }
                  }}
                >
                  <option value="">+ mistake</option>
                  {db.settings.mistakes
                    .filter((m) => !m.retired && !trade.mistakes.includes(m.label))
                    .map((m) => (
                      <option key={m.id} value={m.label}>
                        {m.label}
                      </option>
                    ))}
                </select>
              </span>
            </JRow>

            <JRow label="Emotion">
              <span className="td__tags">
                <span className="mono faint">
                  {trade.emotionAtEntry ?? '—'} → {trade.emotionAtExit ?? '—'}
                </span>
                <select
                  className="td__add"
                  value=""
                  onChange={(e) =>
                    e.target.value &&
                    updateTradeJudgement(trade.id, { emotionAtExit: e.target.value })
                  }
                >
                  <option value="">set exit</option>
                  {db.settings.emotions
                    .filter((x) => !x.retired)
                    .map((x) => (
                      <option key={x.id} value={x.label}>
                        {x.label}
                      </option>
                    ))}
                </select>
              </span>
            </JRow>

            <JRow label="Tags">
              <span className="td__tags">
                {trade.tags.map((t) => (
                  <Tag key={t} onRemove={() => untagTrade(trade.id, t, 'tag')}>
                    {t}
                  </Tag>
                ))}
                <button
                  className="td__add"
                  onClick={() => {
                    const t = window.prompt('Tag (use / for hierarchy)')
                    if (t) tagTrades([trade.id], t, 'tag')
                  }}
                >
                  + tag
                </button>
              </span>
            </JRow>

            <Rule>Lesson</Rule>
            <BlockEditor
              value={trade.lesson}
              onChange={(v) => updateTradeJudgement(trade.id, { lesson: v })}
              placeholder="What does this trade teach that the last one didn’t?"
              minRows={4}
            />
          </section>
        </div>

        {/* ── Context strip ──────────────────────────────────────────── */}
        <div className="td__context">
          <span className="label">Context</span>
          <button
            className="td__link"
            onClick={() =>
              navigate({
                surface: 'cockpit',
                date: trade.date,
                instrumentId: trade.instrumentId,
              })
            }
          >
            session thesis
          </button>
          {reference && reference.trades.length > 0 && (
            <>
              <span className="faint">·</span>
              <button
                className="td__link"
                onClick={() =>
                  navigate({
                    surface: 'blotter',
                    query: `setup:${setups.code(trade.setupId)} date:${trade.date.slice(0, 7)}`,
                  })
                }
              >
                {reference.trades.length} other{' '}
                {setups.code(trade.setupId)} trades this month
              </button>
              <span className="faint mono">
                (exp{' '}
                {reference.ledger.expectancy.state === 'insufficient'
                  ? '░░░'
                  : fmtR(reference.ledger.expectancy.value, 1)}
                , n={reference.ledger.count})
              </span>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function FactRow({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone?: string
}) {
  return (
    <div className="td__factrow">
      <span className="td__factlabel">{label}</span>
      <span className={`num ${tone ?? ''}`}>{value}</span>
    </div>
  )
}

function JRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="td__jrow">
      <span className="td__jlabel">{label}</span>
      <span className="td__jvalue">{children}</span>
    </div>
  )
}

/** Inspector rendering of a trade — §4.1 "Selecting a blotter row shows the
 *  full trade in the inspector; ⏎ promotes it to the full page. This is the
 *  primary reason the blotter never needs a modal." */
export function TradeInspector({ trade }: { trade: Trade }) {
  const inst = useInstrument(trade.instrumentId)
  const setups = useSetupLookup()
  const [note, setNote] = useState(trade.lesson)
  if (!inst) return null
  const r = realisedR(trade, inst)
  const q = exitQuality([trade], inst, 1)

  return (
    <div className="insp">
      <div className="insp__head">
        <DirGlyph direction={trade.direction} />
        <span className="mono">
          {inst.code}{' '}
          {trade.contract === 'OPT'
            ? `${trade.strike} ${trade.optionType}`
            : trade.contract}
        </span>
        <span className="faint mono">{formatDate(trade.date, false)}</span>
      </div>
      <div className="insp__r">
        <span className={`num ${signClass(r)}`}>{fmtR(r)}</span>
        <RMeter mae={trade.maeR} mfe={trade.mfeR} realised={r} width={120} />
      </div>
      <Divider />
      <div className="insp__grid">
        <span className="label">setup</span>
        <span>{trade.offBook ? 'off-book' : setups.name(trade.setupId)}</span>
        <span className="label">grade</span>
        <span><GradePill grade={trade.grade} /></span>
        <span className="label">again</span>
        <span>{trade.takeAgain == null ? '—' : trade.takeAgain ? 'yes' : 'no'}</span>
        <span className="label">capture</span>
        <span className="mono">
          {q.capture.n ? fmtPct(q.capture.value) : '—'}
        </span>
        <span className="label">regime</span>
        <span className="mono">{trade.regime ?? 'unset'}</span>
      </div>
      {(trade.mistakes.length > 0 || trade.autoTags.length > 0) && (
        <>
          <Divider />
          <div className="insp__tags">
            {trade.autoTags.map((m) => (
              <MistakeChip key={m} mistake={m} auto />
            ))}
            {trade.mistakes.map((m) => (
              <MistakeChip key={m} mistake={m} />
            ))}
          </div>
        </>
      )}
      <Divider />
      <div className="label">Entry note · locked</div>
      <div className="locked-block prose insp__prose">
        {trade.entryNote || <span className="faint">none</span>}
      </div>
      <div className="label" style={{ marginTop: 12 }}>Lesson</div>
      <textarea
        className="insp__textarea"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        onBlur={() => updateTradeJudgement(trade.id, { lesson: note })}
        placeholder="Editable forever."
      />
      <div className="insp__foot faint">
        <Kbd>⏎</Kbd> open full <Kbd>⌘⇧C</Kbd> copy link
      </div>
    </div>
  )
}
