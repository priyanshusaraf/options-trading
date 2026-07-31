/* Research Bench — §5.7, `gs`
 *
 * "Not a dashboard. A workbench of ~10 fixed analyses, each with a filter bar,
 *  each stating its own sample size and interval, each with a plain-language
 *  'what this would change' line underneath."
 *
 * Every analysis here is also expressible as a query, so any interesting cell
 * drills straight into a filtered blotter. That is what the `→` buttons do.
 */

import { Fragment, useMemo, useState } from 'react'
import { useDB, useInstrument, useSetupLookup, useTrades } from '../data/hooks'
import { navigate, useUI } from '../app/uiState'
import {
  Distribution,
  EquityTrack,
  Heatmap,
  ReliabilityCurve,
  StatCell,
  fmtPct,
  fmtR,
  fmtRupees,
  signClass,
  type HeatCell,
} from '../components/data'
import { Button, Empty, Rule } from '../components/primitives'
import {
  adherenceSplit,
  behaviouralSequences,
  byBucket,
  calibration,
  decisionOutcome,
  equityCurve,
  exitQuality,
  expectancyGrid,
  ledger,
  mistakeLedger,
  realisedR,
  rHistogram,
  stat,
} from '../domain/metrics'
import { runQuery } from '../domain/query'
import { weekday } from '../domain/dates'
import { REGIMES } from '../domain/taxonomy'
import './surfaces.css'

export function Stats() {
  const ui = useUI()
  const db = useDB()
  const inst = useInstrument(ui.route.instrumentId)
  const setups = useSetupLookup()
  const [filter, setFilter] = useState('')
  const [scope, setScope] = useState<'instrument' | 'all'>('instrument')

  const base = useTrades(scope === 'instrument' ? ui.route.instrumentId : undefined)
  const threshold = db.settings.evidenceThreshold

  const trades = useMemo(
    () =>
      runQuery(filter, base, {
        instruments: db.instruments,
        setupCode: setups.code,
        haystack: (t) => `${t.entryNote} ${t.lesson} ${t.tags.join(' ')}`,
      }),
    [filter, base, db.instruments, setups],
  )

  const rs = useMemo(
    () =>
      inst
        ? trades
            .map((t) => realisedR(t, inst))
            .filter((r): r is number => r != null)
        : [],
    [trades, inst],
  )

  if (!inst) return null

  const l = ledger(trades, inst, threshold)
  const curve = equityCurve(trades, inst)
  const last20 = rs.slice(-20)
  const bins = rHistogram(rs)
  const highlightBins = rHistogram(rs).map((b) => ({
    ...b,
    count: last20.filter((r) => r >= b.from && r < b.to).length,
  }))

  return (
    <div className="surface">
      <div className="surface__head">
        <span className="surface__title">Research bench</span>
        <input
          className="blotter__query mono"
          value={filter}
          placeholder="filter every analysis — setup:orb regime:expansion date:2026-q3"
          onChange={(e) => setFilter(e.target.value)}
        />
        <Button
          variant="quiet"
          onClick={() => setScope((s) => (s === 'all' ? 'instrument' : 'all'))}
        >
          {scope === 'all' ? 'all instruments' : inst.code}
        </Button>
        <span className="mono faint">n={trades.length}</span>
      </div>

      <div className="surface__body stats">
        {/* ── Money ledger and process ledger, side by side, never averaged
            together. §0.2 ─────────────────────────────────────────────── */}
        <Panel
          title="Two ledgers"
          hint="A trader improves by watching these decouple. They are never averaged together."
        >
          <div className="stats__ledgers">
            <div className="stats__ledger">
              <div className="label">Money</div>
              <StatCell label="Expectancy" stat={l.expectancy} format="R" />
              <StatCell label="Win rate" stat={l.winRate} format="%" />
              <div className="stats__line">
                <span className="label">Total</span>
                <span className={`num ${signClass(l.totalR)}`}>{fmtR(l.totalR)}</span>
                <span className={`num ${signClass(l.netRupees)}`}>
                  {fmtRupees(l.netRupees)}
                </span>
              </div>
              <div className="stats__line">
                <span className="label">Max drawdown</span>
                <span className="num neg">{fmtR(l.maxDrawdownR)}</span>
              </div>
            </div>
            <div className="stats__ledger">
              <div className="label">Process</div>
              <StatCell label="Would take again" stat={l.takeAgainRate} format="%" />
              <StatCell label="A/B decisions" stat={l.goodGradeRate} format="%" />
              <StatCell label="Adherence" stat={l.adherence} format="%" />
              <StatCell label="Capture" stat={l.captureRate} format="%" />
            </div>
          </div>
          <EquityTrack values={curve} height={100} />
        </Panel>

        {/* 1 ── R distribution ──────────────────────────────────────────── */}
        <Panel
          title="R distribution"
          hint="Changes position sizing and stop placement. Highlighted bars are your last 20 trades."
          onDrill={() => navigate({ surface: 'blotter', query: filter })}
        >
          {rs.length ? (
            <Distribution bins={bins} highlight={highlightBins} height={130} />
          ) : (
            <Empty>No closed trades in this filter.</Empty>
          )}
        </Panel>

        {/* 2 ── Expectancy grid ─────────────────────────────────────────── */}
        <Panel
          title="Expectancy grid · setup × regime"
          hint="Which setups to stop taking. Hatched cells are below the evidence threshold and carry no number."
        >
          <ExpectancyGrid
            trades={trades}
            inst={inst}
            threshold={threshold}
            setupCode={setups.code}
            onDrill={(setup, regime) =>
              navigate({
                surface: 'blotter',
                query: `setup:${setup} regime:${regime}`,
              })
            }
          />
        </Panel>

        {/* 3 ── Calibration ─────────────────────────────────────────────── */}
        <Panel
          title="Calibration"
          hint="Whether your conviction means anything. Points on the diagonal mean your stated confidence predicts outcomes; below it means you are overconfident."
        >
          <div className="stats__calib">
            <ReliabilityCurve
              points={calibration(trades, inst, threshold).map((p) => ({
                stated: (p.confidence - 0.5) / 5,
                realised: p.winRate.value,
                n: p.winRate.n,
              }))}
              width={240}
              height={180}
            />
            <div className="stats__caliblist">
              {calibration(trades, inst, threshold).map((p) => (
                <div className="stats__line" key={p.confidence}>
                  <span className="label">conf {p.confidence}</span>
                  <StatCell stat={p.avgR} format="R" compact />
                </div>
              ))}
            </div>
          </div>
        </Panel>

        {/* 4 ── Decision × outcome 2×2 ──────────────────────────────────── */}
        <Panel
          title="Decision × outcome"
          hint="Separates skill from luck. The off-diagonal cells teach more than the others: a good decision that lost, and a bad decision that won."
        >
          <Quadrants trades={trades} inst={inst} />
        </Panel>

        {/* 5 ── Thesis accuracy ─────────────────────────────────────────── */}
        <Panel
          title="Thesis accuracy"
          hint="Whether you read the market or just the tape. A scenario that hit but did not pay is a read you failed to trade."
        >
          <ThesisAccuracy />
        </Panel>

        {/* 6 ── Exit quality ────────────────────────────────────────────── */}
        <Panel
          title="Exit quality"
          hint="The single biggest leak for most discretionary traders. Capture below ~60% means you are exiting winners on feel rather than plan."
        >
          <ExitQualityPanel trades={trades} inst={inst} threshold={threshold} />
        </Panel>

        {/* 7 ── Mistake ledger ──────────────────────────────────────────── */}
        <Panel
          title="Mistake ledger"
          hint="What to work on this month, in rupees. Ranked by attributable cost, not by frequency."
        >
          <MistakeTable trades={trades} inst={inst} />
        </Panel>

        {/* 8 ── Adherence ───────────────────────────────────────────────── */}
        <Panel
          title="Adherence"
          hint="Whether your discipline is actually costing you. If off-book beats in-playbook over a real sample, the playbook is what needs revising."
        >
          <AdherencePanel trades={trades} inst={inst} threshold={threshold} />
        </Panel>

        {/* 9 ── Behavioural sequences ───────────────────────────────────── */}
        <Panel
          title="Behavioural sequences"
          hint="Revenge and overtrading, made visible. Compare the expectancy of your first three trades of a day against everything after."
        >
          <SequencePanel trades={trades} inst={inst} threshold={threshold} />
        </Panel>

        {/* 10 ── Instrument comparison ──────────────────────────────────── */}
        <Panel
          title="Instrument comparison"
          hint="Where to concentrate. Expectancy and adherence per instrument, over the same window."
          onDrill={() => setScope('all')}
        >
          <InstrumentTable threshold={threshold} />
        </Panel>

        {/* 11 ── Weekday / time of day ──────────────────────────────────── */}
        <Panel
          title="Weekday and time of day"
          hint="When to be flat. Treat any single cell below the threshold as noise, however tempting."
        >
          <div className="stats__buckets">
            <div>
              <Rule>By weekday</Rule>
              {byBucket(trades, inst, (t) => weekday(t.date), threshold).map((b) => (
                <div className="stats__line" key={b.key}>
                  <button
                    className="stats__key"
                    onClick={() =>
                      navigate({ surface: 'blotter', query: `weekday:${b.key}` })
                    }
                  >
                    {b.key}
                  </button>
                  <StatCell stat={b.stat} format="R" compact />
                </div>
              ))}
            </div>
            <div>
              <Rule>By session hour</Rule>
              {byBucket(
                trades,
                inst,
                (t) => `${String(new Date(t.openedAt).getHours()).padStart(2, '0')}:00`,
                threshold,
              )
                .sort((a, b) => a.key.localeCompare(b.key))
                .map((b) => (
                  <div className="stats__line" key={b.key}>
                    <span className="stats__key mono">{b.key}</span>
                    <StatCell stat={b.stat} format="R" compact />
                  </div>
                ))}
            </div>
          </div>
        </Panel>
      </div>
    </div>
  )
}

// ── Panel shell ───────────────────────────────────────────────────────────

function Panel({
  title,
  hint,
  children,
  onDrill,
}: {
  title: string
  hint: string
  children: React.ReactNode
  onDrill?: () => void
}) {
  return (
    <section className="panel">
      <header className="panel__head">
        <span className="panel__title">{title}</span>
        {onDrill && (
          <Button variant="quiet" onClick={onDrill}>
            →
          </Button>
        )}
      </header>
      <div className="panel__body">{children}</div>
      {/* §5.7 each with a plain-language "what this would change" line. */}
      <footer className="panel__hint">{hint}</footer>
    </section>
  )
}

// ── Individual analyses ───────────────────────────────────────────────────

function ExpectancyGrid({
  trades,
  inst,
  threshold,
  setupCode,
  onDrill,
}: {
  trades: ReturnType<typeof useTrades>
  inst: NonNullable<ReturnType<typeof useInstrument>>
  threshold: number
  setupCode: (id: string | null) => string
  onDrill: (setup: string, regime: string) => void
}) {
  const cells = useMemo(
    () =>
      expectancyGrid(
        trades,
        inst,
        (t) => setupCode(t.setupId),
        (t) => t.regime ?? 'unset',
        threshold,
      ),
    [trades, inst, setupCode, threshold],
  )
  const setupKeys = [...new Set(cells.map((c) => c.rowKey))]
  if (!setupKeys.length) return <Empty>Nothing to grid yet.</Empty>

  const cols = REGIMES as readonly string[]
  return (
    <div className="grid2">
      <div className="grid2__corner" />
      {cols.map((c) => (
        <div className="grid2__colhead label" key={c}>
          {c.slice(0, 6)}
        </div>
      ))}
      {setupKeys.map((rk) => (
        // A keyed Fragment, not a bare <> — inside a map, an unkeyed fragment
        // makes React reconcile siblings positionally and silently drop rows.
        <Fragment key={rk}>
          <div className="grid2__rowhead">{rk}</div>
          {cols.map((ck) => {
            const cell = cells.find((c) => c.rowKey === rk && c.colKey === ck)
            const insufficient = !cell || cell.stat.state === 'insufficient'
            return (
              <button
                key={`${rk}_${ck}`}
                className={`grid2__cell ${insufficient ? 'is-insufficient' : ''}`}
                onClick={() => onDrill(rk, ck)}
                title={cell ? `n=${cell.stat.n}` : 'no trades'}
              >
                {!cell ? (
                  <span className="faint">·</span>
                ) : insufficient ? (
                  <span className="faint mono">░ {cell.stat.n}</span>
                ) : (
                  <span className={`mono ${signClass(cell.stat.value)}`}>
                    {fmtR(cell.stat.value, 1)}
                  </span>
                )}
              </button>
            )
          })}
        </Fragment>
      ))}
    </div>
  )
}

function Quadrants({
  trades,
  inst,
}: {
  trades: ReturnType<typeof useTrades>
  inst: NonNullable<ReturnType<typeof useInstrument>>
}) {
  const q = decisionOutcome(trades, inst)
  const cell = (label: string, list: typeof q.goodWin, emphasis?: boolean) => {
    const rupees = list.reduce((a, t) => {
      const r = realisedR(t, inst)
      return a + (r ?? 0)
    }, 0)
    return (
      <button
        className={`quad ${emphasis ? 'is-emphasis' : ''}`}
        onClick={() =>
          navigate({
            surface: 'blotter',
            query:
              label.includes('Good')
                ? `grade:A or grade:B ${label.includes('win') ? 'r:>0' : 'r:<0'}`
                : `${label.includes('win') ? 'r:>0' : 'r:<0'} -grade:A -grade:B`,
          })
        }
      >
        <span className="label">{label}</span>
        <span className="quad__n mono">{list.length}</span>
        <span className={`quad__r num ${signClass(rupees)}`}>{fmtR(rupees)}</span>
      </button>
    )
  }
  return (
    <div className="quads">
      {cell('Good decision · win', q.goodWin)}
      {/* The two that teach. §2.5 */}
      {cell('Good decision · loss', q.goodLoss, true)}
      {cell('Bad decision · win', q.badWin, true)}
      {cell('Bad decision · loss', q.badLoss)}
      {q.ungraded.length > 0 && (
        <div className="quads__ungraded faint">
          {q.ungraded.length} trades ungraded — this 2×2 cannot see them.
        </div>
      )}
    </div>
  )
}

function ThesisAccuracy() {
  const ui = useUI()
  const db = useDB()
  const sessions = db.sessions.filter(
    (s) => s.instrumentId === ui.route.instrumentId && s.lockedAt,
  )
  const all = sessions.flatMap((s) => s.scenarios)
  const resolved = all.filter((s) => s.status !== 'pending')
  const hit = resolved.filter((s) => s.status === 'hit')
  const paid = hit.filter((s) => s.paid)

  if (!resolved.length) return <Empty>No resolved scenarios yet.</Empty>

  return (
    <div className="stats__thesis">
      <div className="stats__line">
        <span className="label">Scenarios resolved</span>
        <span className="mono">
          {resolved.length} of {all.length}
        </span>
      </div>
      <div className="stats__line">
        <span className="label">Hit rate</span>
        <span className="mono">
          {fmtPct(hit.length / resolved.length)}{' '}
          <span className="faint">n={resolved.length}</span>
        </span>
      </div>
      <div className="stats__line">
        <span className="label">Hits that paid</span>
        <span className={`mono ${hit.length && paid.length / hit.length < 0.5 ? 'attn' : ''}`}>
          {hit.length ? fmtPct(paid.length / hit.length) : '—'}{' '}
          <span className="faint">n={hit.length}</span>
        </span>
      </div>
      <div className="stats__note faint">
        Reading the market right and making money from it are separate claims.
        A high hit rate with a low paid rate means the read is fine and the
        execution is not.
      </div>
    </div>
  )
}

function ExitQualityPanel({
  trades,
  inst,
  threshold,
}: {
  trades: ReturnType<typeof useTrades>
  inst: NonNullable<ReturnType<typeof useInstrument>>
  threshold: number
}) {
  const q = exitQuality(trades, inst, threshold)

  return (
    <div className="stats__exit">
      <StatCell
        label="Capture, on winners"
        stat={q.capture}
        format="%"
        hint="Realised R ÷ MFE R. Measured on winners, because a loser whose MFE was +0.05R produces a capture of −20 and would swamp the average."
      />
      <StatCell label="R left on the table" stat={q.leftOnTable} format="R" />
      <StatCell
        label="R given back, all trades"
        stat={q.gaveBack}
        format="R"
        hint="Includes losers that went green first — the trades capture % cannot see."
      />
      <StatCell label="Heat before winners (MAE)" stat={q.maeBeforeWinners} format="R" />
      {q.captureSamples.length > 0 && (
        <Distribution bins={rHistogram(q.captureSamples, 0.2)} height={80} />
      )}
    </div>
  )
}

function MistakeTable({
  trades,
  inst,
}: {
  trades: ReturnType<typeof useTrades>
  inst: NonNullable<ReturnType<typeof useInstrument>>
}) {
  const rows = mistakeLedger(trades, inst)
  if (!rows.length) return <Empty>No mistakes tagged in this filter.</Empty>
  const max = Math.max(...rows.map((r) => r.totalRupees), 1)
  return (
    <div className="mtable">
      {rows.map((m) => (
        <button
          key={m.mistake}
          className="mtable__row"
          onClick={() => navigate({ surface: 'blotter', query: `mistake:${m.mistake}` })}
        >
          <span className="mtable__name">{m.mistake}</span>
          <span className="mtable__bar">
            <span
              className="mtable__fill"
              style={{ width: `${(m.totalRupees / max) * 100}%` }}
            />
          </span>
          <span className="mtable__count mono faint">×{m.count}</span>
          <span className="mtable__cost num neg">{fmtRupees(-m.totalRupees)}</span>
          <span
            className={`mtable__trend mono ${m.trend === 'rising' ? 'attn' : 'faint'}`}
            title={`${m.trend} over the window`}
          >
            {m.trend === 'rising' ? '↑' : m.trend === 'falling' ? '↓' : '·'}
          </span>
        </button>
      ))}
    </div>
  )
}

function AdherencePanel({
  trades,
  inst,
  threshold,
}: {
  trades: ReturnType<typeof useTrades>
  inst: NonNullable<ReturnType<typeof useInstrument>>
  threshold: number
}) {
  const a = adherenceSplit(trades, inst, threshold)
  return (
    <div className="stats__adherence">
      <StatCell label="In playbook" stat={a.inBook} format="R" />
      <StatCell label="Off book" stat={a.offBook} format="R" />
      <StatCell label="Adherence rate" stat={a.rate} format="%" />
    </div>
  )
}

function SequencePanel({
  trades,
  inst,
  threshold,
}: {
  trades: ReturnType<typeof useTrades>
  inst: NonNullable<ReturnType<typeof useInstrument>>
  threshold: number
}) {
  const s = behaviouralSequences(trades, inst, threshold)
  return (
    <div className="stats__seq">
      <StatCell label="Size after a loss" stat={s.sizeAfterLoss} format="x" />
      <StatCell label="Minutes to next trade after a loss" stat={s.minutesAfterLoss} format="raw" />
      <StatCell label="Trades 1–3 of a day" stat={s.earlyTradeExpectancy} format="R" />
      <StatCell label="Trade 4 and beyond" stat={s.lateTradeExpectancy} format="R" />
    </div>
  )
}

function InstrumentTable({ threshold }: { threshold: number }) {
  const db = useDB()
  const rows = db.instruments.map((inst) => {
    const ts = db.trades.filter((t) => t.instrumentId === inst.id && !t.deletedAt)
    return { inst, ledger: ledger(ts, inst, threshold) }
  })
  return (
    <div className="itable">
      {rows.map(({ inst, ledger: l }) => (
        <button
          key={inst.id}
          className="itable__row"
          onClick={() => navigate({ instrumentId: inst.id, surface: 'stats' })}
        >
          <span className="itable__code mono">{inst.code}</span>
          <span className="itable__name">{inst.name}</span>
          <StatCell stat={l.expectancy} format="R" compact />
          <span className="mono faint">
            adh {l.adherence.n ? fmtPct(l.adherence.value) : '—'}
          </span>
        </button>
      ))}
    </div>
  )
}

export { stat, Heatmap }
export type { HeatCell }
