/* Search results — §5.10, ⌘⇧F
 *
 * "Full-surface search with the query bar on top, facet rail on the left, and
 *  grouped results. Matches show a two-line snippet with the term highlighted.
 *  Results are ranked by recency-weighted relevance, but the facet counts are
 *  always exact — you should be able to trust '14 trades tagged early-exit in
 *  Q2' as a number, not an estimate."
 */

import { useMemo, useState } from 'react'
import { useDB, useSetupLookup } from '../data/hooks'
import { navigate, useUI } from '../app/uiState'
import { Chip, Empty, Rule } from '../components/primitives'
import { fmtR, signClass } from '../components/data'
import { realisedR } from '../domain/metrics'
import { runQuery, withTerm } from '../domain/query'
import { formatDate } from '../domain/dates'
import './surfaces.css'

type Hit = {
  id: string
  kind: 'trade' | 'session' | 'note' | 'observation' | 'setup'
  title: string
  snippet: string
  at: number
  score: number
  open: () => void
}

export function Search() {
  const ui = useUI()
  const db = useDB()
  const setups = useSetupLookup()
  const [q, setQ] = useState(ui.route.query ?? '')

  const term = q
    .split(/\s+/)
    .filter((t) => !t.includes(':'))
    .join(' ')
    .trim()
    .toLowerCase()

  // Structured terms filter; free text ranks. Both use the same parser as the
  // blotter, so the query language is one language. §6.4
  const trades = useMemo(
    () =>
      runQuery(q, db.trades.filter((t) => !t.deletedAt), {
        instruments: db.instruments,
        setupCode: setups.code,
        haystack: (t) =>
          `${t.entryNote} ${t.exitNote} ${t.lesson} ${t.tags.join(' ')}`,
      }),
    [q, db.trades, db.instruments, setups],
  )

  const hits = useMemo<Hit[]>(() => {
    const now = Date.now()
    const out: Hit[] = []
    const rank = (at: number, base: number) => {
      // Recency-weighted: half-life of ~90 days.
      const days = (now - at) / 86_400_000
      return base * Math.pow(0.5, days / 90)
    }
    const contains = (s: string) => !term || s.toLowerCase().includes(term)

    for (const t of trades) {
      const text = `${t.entryNote} ${t.exitNote} ${t.lesson}`
      if (!contains(text) && !contains(t.tags.join(' '))) continue
      const inst = db.instruments.find((i) => i.id === t.instrumentId)
      out.push({
        id: t.id, kind: 'trade', at: t.openedAt, score: rank(t.openedAt, 1),
        title: `${inst?.code} ${
          t.contract === 'OPT' ? `${t.strike} ${t.optionType}` : t.contract
        } · ${t.direction} · ${formatDate(t.date, false)}`,
        snippet: text.trim() || t.tags.join(' ') || '—',
        open: () => navigate({ surface: 'trade', objectId: t.id, instrumentId: t.instrumentId }),
      })
    }

    if (term) {
      for (const s of db.sessions) {
        if (!contains(s.thesis) && !contains(s.review?.oneLineForTomorrow ?? '')) continue
        const inst = db.instruments.find((i) => i.id === s.instrumentId)
        out.push({
          id: s.id, kind: 'session', at: s.updatedAt, score: rank(s.updatedAt, 0.9),
          title: `${inst?.code} · ${formatDate(s.date)}`,
          snippet: s.thesis || s.review?.oneLineForTomorrow || '—',
          open: () =>
            navigate({ surface: 'cockpit', date: s.date, instrumentId: s.instrumentId }),
        })
      }
      for (const d of db.docs) {
        if (!contains(d.body) && !contains(d.title)) continue
        out.push({
          id: d.id, kind: 'note', at: d.updatedAt, score: rank(d.updatedAt, 0.8),
          title: d.title,
          snippet: d.body || '—',
          open: () =>
            navigate({ surface: 'notebook', objectId: d.id, instrumentId: d.instrumentId }),
        })
      }
      for (const e of db.events) {
        if (!contains(e.text)) continue
        out.push({
          id: e.id, kind: 'observation', at: e.at, score: rank(e.at, 0.7),
          title: `${e.kind} · ${formatDate(e.sessionId.split('|')[1] ?? '', false)}`,
          snippet: e.text,
          open: () =>
            navigate({
              surface: 'cockpit',
              date: e.sessionId.split('|')[1] ?? ui.route.date,
              instrumentId: e.instrumentId,
            }),
        })
      }
      for (const p of db.playbook) {
        if (!contains(`${p.name} ${p.definition} ${p.entryTrigger}`)) continue
        out.push({
          id: p.id, kind: 'setup', at: p.createdAt, score: rank(p.createdAt, 0.85),
          title: p.name,
          snippet: p.definition,
          open: () => navigate({ surface: 'playbook', objectId: p.id }),
        })
      }
    }
    return out.sort((a, b) => b.score - a.score).slice(0, 300)
  }, [trades, term, db, ui.route.date])

  // Facet counts are exact, computed over the *filtered* trade set. §5.10
  const facets = useMemo(() => {
    const count = (fn: (t: (typeof trades)[number]) => string[]) => {
      const m = new Map<string, number>()
      for (const t of trades) {
        for (const k of fn(t)) m.set(k, (m.get(k) ?? 0) + 1)
      }
      return [...m.entries()].sort((a, b) => b[1] - a[1])
    }
    return {
      instrument: count((t) => [
        db.instruments.find((i) => i.id === t.instrumentId)?.code ?? '',
      ]),
      setup: count((t) => [t.offBook ? 'off-book' : setups.code(t.setupId)]),
      mistake: count((t) => [...t.mistakes, ...t.autoTags]),
      emotion: count((t) => (t.emotionAtEntry ? [t.emotionAtEntry] : [])),
      grade: count((t) => (t.grade ? [t.grade] : [])),
      regime: count((t) => (t.regime ? [t.regime] : [])),
    }
  }, [trades, db.instruments, setups])

  const grouped = useMemo(() => {
    const m = new Map<string, Hit[]>()
    for (const h of hits) m.set(h.kind, [...(m.get(h.kind) ?? []), h])
    return [...m.entries()]
  }, [hits])

  return (
    <div className="surface">
      <div className="surface__head">
        <span className="mono faint">⌘⇧F</span>
        <input
          className="blotter__query mono"
          autoFocus
          value={q}
          placeholder="free text and field:value together — early-exit setup:orb date:2026-q3"
          onChange={(e) => setQ(e.target.value)}
        />
        <span className="mono faint">{hits.length} results</span>
      </div>

      <div className="surface__body surface__body--flush search">
        {/* Facet rail. Every click writes into the query bar, so the UI
            teaches the language. §6.4 */}
        <aside className="search__facets scroll">
          {Object.entries(facets).map(([field, entries]) =>
            entries.length ? (
              <div className="search__facetgroup" key={field}>
                <div className="label">{field}</div>
                {entries.slice(0, 10).map(([value, n]) => (
                  <button
                    key={value}
                    className="search__facet"
                    onClick={() => setQ(withTerm(q, field, value))}
                  >
                    <span className="search__facetname">{value || '—'}</span>
                    <span className="mono faint">{n}</span>
                  </button>
                ))}
              </div>
            ) : null,
          )}
        </aside>

        <div className="search__results scroll">
          {!hits.length ? (
            <Empty>
              {q.trim() ? 'Nothing matches.' : 'Search notes, trades, sessions and setups.'}
            </Empty>
          ) : (
            grouped.map(([kind, list]) => (
              <div key={kind}>
                <Rule right={<span className="mono">{list.length}</span>}>{kind}</Rule>
                {list.slice(0, 40).map((h) => (
                  <button key={h.id} className="search__hit" onClick={h.open}>
                    <div className="search__hittitle">
                      {h.title}
                      {h.kind === 'trade' && (
                        <TradeR id={h.id} />
                      )}
                    </div>
                    <div className="search__snippet">
                      {highlight(h.snippet, term)}
                    </div>
                  </button>
                ))}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

function TradeR({ id }: { id: string }) {
  const db = useDB()
  const t = db.trades.find((x) => x.id === id)
  const inst = db.instruments.find((i) => i.id === t?.instrumentId)
  if (!t || !inst) return null
  const r = realisedR(t, inst)
  return <span className={`num ${signClass(r)}`}>{fmtR(r)}</span>
}

/** Two-line snippet with the term highlighted. §5.10 */
function highlight(text: string, term: string) {
  const clean = text.replace(/\s+/g, ' ').trim()
  if (!term) return clean.slice(0, 180)
  const i = clean.toLowerCase().indexOf(term)
  if (i < 0) return clean.slice(0, 180)
  const from = Math.max(0, i - 60)
  const snippet = clean.slice(from, from + 180)
  const j = snippet.toLowerCase().indexOf(term)
  return (
    <>
      {from > 0 && '…'}
      {snippet.slice(0, j)}
      <mark className="search__mark">{snippet.slice(j, j + term.length)}</mark>
      {snippet.slice(j + term.length)}
    </>
  )
}

export { Chip }
