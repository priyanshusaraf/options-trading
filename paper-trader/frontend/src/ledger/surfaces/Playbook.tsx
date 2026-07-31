/* Playbook — §5.6, `gp`
 *
 * "The playbook is where the product's opinion is strongest: a setup you
 *  cannot define in two sentences is not a setup, it is a mood."
 *
 * Expanded, a setup shows its definition, invalidation, R distribution,
 * performance split by regime and weekday, its worst five trades, and an edit
 * history so you can see when you changed the rules and whether it helped.
 */

import { useMemo, useState } from 'react'
import { useDB, useInstrument, usePlaybook, useTrades } from '../data/hooks'
import { navigate, toast, useUI } from '../app/uiState'
import { archivePlaybook, upsertPlaybook } from '../data/actions'
import { PlaybookRow } from '../components/domain'
import { Distribution, StatCell, fmtR, signClass } from '../components/data'
import { Button, Chip, Divider, Empty, Rule } from '../components/primitives'
import {
  byBucket,
  ledger,
  proportion,
  realisedR,
  rHistogram,
  stat,
} from '../domain/metrics'
import { formatDate, weekday } from '../domain/dates'
import { REGIMES } from '../domain/taxonomy'
import type { PlaybookEntry, Trade } from '../domain/types'
import './surfaces.css'

export function Playbook() {
  const ui = useUI()
  const db = useDB()
  const inst = useInstrument(ui.route.instrumentId)
  const entries = usePlaybook(ui.route.instrumentId)
  const trades = useTrades(ui.route.instrumentId)
  const [expanded, setExpanded] = useState<string | null>(ui.route.objectId ?? null)

  const offBook = useMemo(() => trades.filter((t) => t.offBook), [trades])

  if (!inst) return null

  return (
    <div className="surface">
      <div className="surface__head">
        <span className="surface__title">Playbook · {inst.name}</span>
        <span className="surface__spacer" />
        <Button
          variant="quiet"
          onClick={() => {
            const id = upsertPlaybook({
              name: 'New setup',
              code: 'new',
              instrumentIds: [inst.id],
              shortcut: entries.length + 1,
            })
            setExpanded(id)
          }}
        >
          + setup
        </Button>
      </div>

      <div className="surface__body surface__body--flush">
        {entries.length === 0 ? (
          <Empty>
            Your setups live here. What is the trade you take most often?
          </Empty>
        ) : (
          entries.map((entry) => (
            <PlaybookEntryRow
              key={entry.id}
              entry={entry}
              trades={trades.filter((t) => t.setupId === entry.id)}
              inst={inst}
              threshold={db.settings.evidenceThreshold}
              expanded={expanded === entry.id}
              onToggle={() =>
                setExpanded((v) => (v === entry.id ? null : entry.id))
              }
            />
          ))
        )}

        {/* §0.4 "off-book" is itself a tracked behaviour, so it gets a row. */}
        <div className="pb-offbook">
          <Rule right={<span className="faint">not a setup — a behaviour</span>}>
            Off-book
          </Rule>
          <div className="pb-offbook__body">
            <StatCell
              label="Expectancy of off-book trades"
              stat={stat(
                offBook
                  .map((t) => realisedR(t, inst))
                  .filter((r): r is number => r != null),
                'R',
                db.settings.evidenceThreshold,
              )}
              hint="Compare against your in-playbook expectancy. If off-book is better, the playbook is the problem — not your discipline."
            />
            <Button
              variant="quiet"
              onClick={() => navigate({ surface: 'blotter', query: 'offbook:yes' })}
            >
              {offBook.length} trades →
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

function PlaybookEntryRow({
  entry,
  trades,
  inst,
  threshold,
  expanded,
  onToggle,
}: {
  entry: PlaybookEntry
  trades: Trade[]
  inst: NonNullable<ReturnType<typeof useInstrument>>
  threshold: number
  expanded: boolean
  onToggle: () => void
}) {
  const [editing, setEditing] = useState(false)
  const l = useMemo(() => ledger(trades, inst, threshold), [trades, inst, threshold])

  const rs = useMemo(
    () =>
      trades
        .map((t) => realisedR(t, inst))
        .filter((r): r is number => r != null),
    [trades, inst],
  )

  // Rolling cumulative R, sampled to ~5 points for the block sparkline.
  const spark = useMemo(() => {
    if (rs.length < 5) return []
    const chunk = Math.ceil(rs.length / 5)
    const out: number[] = []
    for (let i = 0; i < rs.length; i += chunk) {
      const slice = rs.slice(i, i + chunk)
      out.push(slice.reduce((a, b) => a + b, 0) / slice.length)
    }
    return out
  }, [rs])

  const byRegime = useMemo(
    () => byBucket(trades, inst, (t) => t.regime ?? 'unset', threshold),
    [trades, inst, threshold],
  )
  const byWeekday = useMemo(
    () => byBucket(trades, inst, (t) => weekday(t.date), threshold),
    [trades, inst, threshold],
  )
  const worst = useMemo(
    () =>
      [...trades]
        .filter((t) => realisedR(t, inst) != null)
        .sort((a, b) => (realisedR(a, inst) ?? 0) - (realisedR(b, inst) ?? 0))
        .slice(0, 5),
    [trades, inst],
  )

  return (
    <PlaybookRow
      entry={entry}
      expectancy={l.expectancy}
      winRate={l.winRate}
      adherence={proportion(
        trades.filter((t) => t.grade === 'A' || t.grade === 'B').length,
        trades.filter((t) => t.grade != null).length,
        threshold,
      )}
      spark={spark}
      expanded={expanded}
      onToggle={onToggle}
    >
      <div className="pb-detail">
        <div className="pb-detail__defs">
          {editing ? (
            <PlaybookEditor entry={entry} onDone={() => setEditing(false)} />
          ) : (
            <>
              <DefRow label="Definition" value={entry.definition} />
              <DefRow label="Entry trigger" value={entry.entryTrigger} />
              <DefRow label="Invalidation" value={entry.invalidation} />
              <div className="pb-detail__meta">
                <span className="mono faint">typical {entry.typicalR}R</span>
                {entry.regimes.map((r) => (
                  <Chip key={r}>{r}</Chip>
                ))}
                <span className="surface__spacer" />
                <Button variant="quiet" onClick={() => setEditing(true)}>
                  Edit
                </Button>
                <Button
                  variant="quiet"
                  onClick={() => {
                    archivePlaybook(entry.id)
                    toast('Setup archived', true)
                  }}
                >
                  Archive
                </Button>
                <Button
                  variant="quiet"
                  onClick={() =>
                    navigate({ surface: 'blotter', query: `setup:${entry.code}` })
                  }
                >
                  {trades.length} trades →
                </Button>
              </div>
            </>
          )}
        </div>

        <div className="pb-detail__stats">
          <div>
            <Rule>R distribution</Rule>
            {rs.length ? (
              <Distribution bins={rHistogram(rs)} height={80} />
            ) : (
              <span className="faint">No closed trades.</span>
            )}
          </div>

          <div>
            <Rule>By regime</Rule>
            {byRegime.length ? (
              byRegime
                .sort((a, b) => REGIMES.indexOf(a.key as never) - REGIMES.indexOf(b.key as never))
                .map((b) => (
                  <div className="pb-split" key={b.key}>
                    <span className="pb-split__key">{b.key}</span>
                    <StatCell stat={b.stat} compact />
                  </div>
                ))
            ) : (
              <span className="faint">—</span>
            )}
          </div>

          <div>
            <Rule>By weekday</Rule>
            {byWeekday.map((b) => (
              <div className="pb-split" key={b.key}>
                <span className="pb-split__key">{b.key}</span>
                <StatCell stat={b.stat} compact />
              </div>
            ))}
          </div>
        </div>

        {worst.length > 0 && (
          <div>
            <Rule>Worst five</Rule>
            {worst.map((t) => (
              <button
                key={t.id}
                className="pb-worst"
                onClick={() => navigate({ surface: 'trade', objectId: t.id })}
              >
                <span className="mono faint">{formatDate(t.date, false)}</span>
                <span className={`num ${signClass(realisedR(t, inst))}`}>
                  {fmtR(realisedR(t, inst))}
                </span>
                <span className="pb-worst__note">
                  {t.lesson || t.exitNote || t.mistakes.join(', ') || '—'}
                </span>
              </button>
            ))}
          </div>
        )}

        {/* §5.6 an edit history so you can see when you changed the rules and
            whether it helped. */}
        {entry.revisions.length > 0 && (
          <div>
            <Rule>Rule changes</Rule>
            {entry.revisions.map((rev, i) => (
              <div className="pb-rev" key={i}>
                <span className="mono faint">{formatDate(new Date(rev.at).toISOString().slice(0, 10))}</span>
                <span className="pb-rev__field label">{rev.field}</span>
                <div className="pb-rev__body">
                  <div className="pb-rev__from">{rev.from}</div>
                  <div className="pb-rev__to">{rev.to}</div>
                  {rev.why && <div className="pb-rev__why faint">{rev.why}</div>}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </PlaybookRow>
  )
}

function DefRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="pb-def">
      <span className="label pb-def__label">{label}</span>
      <span className="pb-def__value">
        {value || <span className="faint">Not defined — this is a mood, not a setup.</span>}
      </span>
    </div>
  )
}

function PlaybookEditor({
  entry,
  onDone,
}: {
  entry: PlaybookEntry
  onDone: () => void
}) {
  const [draft, setDraft] = useState(entry)
  return (
    <div className="pb-edit">
      <label>
        Name
        <input
          value={draft.name}
          onChange={(e) => setDraft({ ...draft, name: e.target.value })}
        />
      </label>
      <label>
        Shortcode
        <input
          value={draft.code}
          onChange={(e) => setDraft({ ...draft, code: e.target.value })}
        />
      </label>
      <label>
        Definition
        <textarea
          rows={2}
          value={draft.definition}
          onChange={(e) => setDraft({ ...draft, definition: e.target.value })}
        />
      </label>
      <label>
        Entry trigger
        <textarea
          rows={2}
          value={draft.entryTrigger}
          onChange={(e) => setDraft({ ...draft, entryTrigger: e.target.value })}
        />
      </label>
      <label>
        Invalidation
        <textarea
          rows={2}
          value={draft.invalidation}
          onChange={(e) => setDraft({ ...draft, invalidation: e.target.value })}
        />
      </label>
      <label>
        Typical R
        <input
          type="number" step="0.1"
          value={draft.typicalR}
          onChange={(e) => setDraft({ ...draft, typicalR: Number(e.target.value) })}
        />
      </label>
      <div className="pb-edit__regimes">
        {REGIMES.map((r) => (
          <Chip
            key={r}
            tone={draft.regimes.includes(r) ? 'interactive' : 'neutral'}
            onClick={() =>
              setDraft({
                ...draft,
                regimes: draft.regimes.includes(r)
                  ? draft.regimes.filter((x) => x !== r)
                  : [...draft.regimes, r],
              })
            }
          >
            {r}
          </Chip>
        ))}
      </div>
      <Divider />
      <div className="pb-edit__actions">
        <Button variant="quiet" onClick={onDone}>
          Cancel
        </Button>
        <Button
          variant="primary"
          onClick={() => {
            upsertPlaybook(draft)
            toast('Setup updated', true)
            onDone()
          }}
        >
          Save
        </Button>
      </div>
    </div>
  )
}
