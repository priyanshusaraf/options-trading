/* Instrument Notebook — §5.2, `gn`
 *
 * "The living research document. Left: a shallow tree of evergreen docs.
 *  Right: a paper-material editor with a generous 68ch measure."
 *
 * Two structural features make this a notebook rather than a folder of files:
 * promotion (§5.2 ⌘⇧P, the mechanic that makes the notebook fill itself) and
 * the backlinks panel.
 */

import { useEffect, useMemo, useState } from 'react'
import {
  useDB,
  useDocs,
  useInstrument,
  useLevels,
  useRegime,
  useTrades,
} from '../data/hooks'
import { navigate, toast, useUI } from '../app/uiState'
import {
  addLevel,
  createDoc,
  deleteDoc,
  removeLevel,
  restoreDocVersion,
  setRegime,
  tagLevel,
  updateDoc,
} from '../data/actions'
import { BlockEditor } from '../components/editor/BlockEditor'
import { LevelLadder } from '../components/editor/blocks'
import { Button, Chip, Divider, Empty, Rule } from '../components/primitives'
import { MistakeChip } from '../components/domain'
import { fmtRupees } from '../components/data'
import { formatDate, relativeDays } from '../domain/dates'
import { mistakeLedger } from '../domain/metrics'
import { REGIMES } from '../domain/taxonomy'
import './surfaces.css'

export function Notebook() {
  const ui = useUI()
  const db = useDB()
  const inst = useInstrument(ui.route.instrumentId)
  const docs = useDocs(ui.route.instrumentId)
  const levels = useLevels(ui.route.instrumentId)
  const regime = useRegime(ui.route.instrumentId)
  const trades = useTrades(ui.route.instrumentId)
  const [activeId, setActiveId] = useState<string | null>(
    ui.route.objectId ?? docs[0]?.id ?? null,
  )
  const [showVersions, setShowVersions] = useState(false)

  useEffect(() => {
    if (ui.route.objectId) setActiveId(ui.route.objectId)
  }, [ui.route.objectId])

  useEffect(() => {
    if (!activeId || !docs.some((d) => d.id === activeId)) {
      setActiveId(docs[0]?.id ?? null)
    }
  }, [docs, activeId])

  const doc = docs.find((d) => d.id === activeId)

  // §5.2 "Mistakes I keep making" becomes a live index of every trade tagged
  // with those mistakes, with their aggregate cost at the top.
  const mistakes = useMemo(
    () => (inst ? mistakeLedger(trades, inst) : []),
    [trades, inst],
  )

  if (!inst) return null

  return (
    <div className="surface">
      <div className="surface__head">
        <span className="surface__title">Notebook · {inst.name}</span>
        <span className="surface__spacer" />
        {doc && (
          <>
            {/* §5.2 The header shows "last changed 11 days ago", which quietly
                shames stale convictions. */}
            <span className="faint" style={{ fontSize: 'var(--t-11)' }}>
              last changed {relativeDays(doc.updatedAt)}
            </span>
            {doc.versions.length > 0 && (
              <Button variant="quiet" onClick={() => setShowVersions((v) => !v)}>
                {doc.versions.length} versions
              </Button>
            )}
          </>
        )}
        <Button
          variant="quiet"
          onClick={() => {
            const title = window.prompt('Document title')
            if (title) setActiveId(createDoc(inst.id, title))
          }}
        >
          + doc
        </Button>
      </div>

      <div className="surface__body surface__body--flush nb">
        {/* ── Tree ────────────────────────────────────────────────────── */}
        <nav className="nb__tree scroll">
          {docs.map((d) => (
            <button
              key={d.id}
              className={`nb__item ${d.id === activeId ? 'is-active' : ''}`}
              onClick={() => setActiveId(d.id)}
            >
              <span className="nb__itemtitle">{d.title}</span>
              {d.backlinks.length > 0 && (
                <span className="nb__backcount mono">{d.backlinks.length}</span>
              )}
            </button>
          ))}
        </nav>

        {/* ── Editor ──────────────────────────────────────────────────── */}
        <div className="nb__main scroll">
          {!doc ? (
            <Empty>No documents.</Empty>
          ) : (
            <>
              <h2 className="nb__title">{doc.title}</h2>

              {/* Structured docs render their live projection above the prose,
                  because §5.2 says the Cockpit's levels view *is* a projection
                  of this document, not a copy of it. */}
              {doc.title === 'Levels' && (
                <div className="nb__panel">
                  <LevelLadder
                    levels={levels}
                    onTag={(id, o) => {
                      tagLevel(id, o)
                      toast(`Level ${o}`, true)
                    }}
                    onRemove={(id) => {
                      removeLevel(id)
                      toast('Level removed', true)
                    }}
                  />
                  <Button
                    variant="quiet"
                    onClick={() => {
                      const price = window.prompt('Price')
                      if (!price || Number.isNaN(Number(price))) return
                      const type = window.prompt('supply / demand / pivot', 'supply')
                      addLevel(
                        inst.id,
                        Number(price),
                        (type as never) ?? 'supply',
                        window.prompt('Source') ?? '',
                      )
                      toast('Level added', true)
                    }}
                  >
                    + level
                  </Button>
                </div>
              )}

              {doc.title === 'Regime' && (
                <div className="nb__panel">
                  <div className="nb__regimes">
                    {REGIMES.map((r) => (
                      <Chip
                        key={r}
                        tone={regime?.state === r ? 'interactive' : 'neutral'}
                        onClick={() => {
                          const why = window.prompt(`Why is the regime now ${r}?`)
                          if (why != null) {
                            setRegime(inst.id, r, why)
                            toast(`Regime → ${r}`, true)
                          }
                        }}
                      >
                        {r}
                      </Chip>
                    ))}
                  </div>
                  {/* A dated log of every regime change and why. §5.2 */}
                  <div className="nb__log">
                    {db.regimeLog
                      .filter((x) => x.instrumentId === inst.id)
                      .sort((a, b) => b.at - a.at)
                      .map((x) => (
                        <div className="nb__logrow" key={x.id}>
                          <span className="mono faint">
                            {formatDate(
                              new Date(x.at).toISOString().slice(0, 10),
                              false,
                            )}
                          </span>
                          <span className="mono">{x.state}</span>
                          <span className="nb__lognote">{x.note}</span>
                        </div>
                      ))}
                  </div>
                </div>
              )}

              {doc.title === 'Mistakes I keep making' && mistakes.length > 0 && (
                <div className="nb__panel">
                  <div className="nb__mistaketotal">
                    <span className="label">Aggregate cost</span>
                    <span className="num neg">
                      {fmtRupees(
                        -mistakes.reduce((a, m) => a + m.totalRupees, 0),
                      )}
                    </span>
                  </div>
                  <div className="nb__mistakes">
                    {mistakes.map((m) => (
                      <MistakeChip
                        key={m.mistake}
                        mistake={m.mistake}
                        count={m.count}
                        cost={m.totalRupees}
                        onClick={() =>
                          navigate({
                            surface: 'blotter',
                            query: `mistake:${m.mistake}`,
                          })
                        }
                      />
                    ))}
                  </div>
                </div>
              )}

              <BlockEditor
                value={doc.body}
                onChange={(v) => updateDoc(doc.id, v)}
                placeholder="Evergreen. Written once, revised forever."
                minRows={16}
                savedAt={doc.updatedAt}
                className="nb__editor"
              />

              {showVersions && doc.versions.length > 0 && (
                <div className="nb__panel">
                  <Rule>Version history</Rule>
                  {[...doc.versions].reverse().map((v, i) => (
                    <div className="nb__version" key={v.at}>
                      <span className="mono faint">{relativeDays(v.at)}</span>
                      <span className="nb__versionpreview">
                        {v.body.slice(0, 90) || '(empty)'}
                      </span>
                      <Button
                        variant="quiet"
                        onClick={() => {
                          restoreDocVersion(doc.id, doc.versions.length - 1 - i)
                          toast('Version restored', true)
                        }}
                      >
                        restore
                      </Button>
                    </div>
                  ))}
                </div>
              )}

              {!doc.seeded && (
                <>
                  <Divider />
                  <Button
                    variant="quiet"
                    onClick={() => {
                      deleteDoc(doc.id)
                      toast('Document deleted', true)
                    }}
                  >
                    Delete document
                  </Button>
                </>
              )}
            </>
          )}
        </div>

        {/* ── Backlinks ───────────────────────────────────────────────── */}
        {/* §5.2 Any evergreen doc shows every session, trade and review that
            references it. Bidirectional. §1.4 */}
        <aside className="nb__backlinks scroll">
          <div className="label">Backlinks</div>
          {!doc || doc.backlinks.length === 0 ? (
            <div className="faint nb__nobacklinks">
              Nothing references this yet. Promote a session note with{' '}
              <code>⌘⇧P</code> to build the link.
            </div>
          ) : (
            doc.backlinks
              .sort((a, b) => b.at - a.at)
              .map((b) => (
                <button
                  key={`${b.kind}_${b.id}`}
                  className="nb__backlink"
                  onClick={() =>
                    b.kind === 'trade'
                      ? navigate({ surface: 'trade', objectId: b.id })
                      : navigate({
                          surface: 'cockpit',
                          date: b.id.split('|')[1] ?? ui.route.date,
                        })
                  }
                >
                  <span className="label">{b.kind}</span>
                  <span className="nb__backlabel">{b.label}</span>
                </button>
              ))
          )}
        </aside>
      </div>
    </div>
  )
}
