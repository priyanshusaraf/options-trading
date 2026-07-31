/* Trade Blotter — §5.3, `gt`
 *
 * "A real data grid. Keyboard-navigable, virtualised, column-configurable, and
 *  honest about density."
 *
 * §5.3 R is the primary column, not P&L — "you can toggle, but the default
 * teaches the right instinct."
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { useDB, useInstrument, useSetupLookup, useTrades } from '../data/hooks'
import { navigate, navigateSplit, peek, setCursor, setSelection, toast, useUI } from '../app/uiState'
import { DataGrid, type Column, type GroupedRows } from '../components/data/DataGrid'
import { NumericCell, StatCell, fmtR, fmtRupees, signClass } from '../components/data'
import { BlotterSummary, DirGlyph, GradePill, MistakeDots } from '../components/domain'
import { Button, Chip, Empty, Kbd } from '../components/primitives'
import { runQuery, sortTrades, suggestQuery, withTerm, QUERY_FIELDS } from '../domain/query'
import { ledger, netPnl, realisedR } from '../domain/metrics'
import { formatDate, formatTime, weekday } from '../domain/dates'
import { saveQuery } from '../data/actions'
import type { Trade } from '../domain/types'
import { registerListNav } from './listNav'
import './surfaces.css'

type GroupKey = 'none' | 'setup' | 'weekday' | 'regime' | 'emotion' | 'mistake'

export function Blotter() {
  const ui = useUI()
  const db = useDB()
  const inst = useInstrument(ui.route.instrumentId)
  const setups = useSetupLookup()
  const all = useTrades()
  const [query, setQuery] = useState(ui.route.query ?? '')
  const [sort, setSort] = useState<{ key: string; dir: 'asc' | 'desc' }>({
    key: 'date',
    dir: 'desc',
  })
  const [unit, setUnit] = useState<'R' | '₹'>('R')
  const [group, setGroup] = useState<GroupKey>('none')
  const [suggestions, setSuggestions] = useState<string[]>([])
  const queryRef = useRef<HTMLInputElement>(null)

  useEffect(() => setQuery(ui.route.query ?? ''), [ui.route.query])

  const vocab = useMemo(
    () => ({
      instrument: db.instruments.map((i) => i.code),
      setup: db.playbook.map((p) => p.code),
      mistake: db.settings.mistakes.map((m) => m.label),
      emotion: db.settings.emotions.map((e) => e.label),
      grade: ['A', 'B', 'C', 'D', 'F'],
      regime: ['trending', 'range', 'expansion', 'compression', 'event-driven'],
      dir: ['long', 'short'],
      again: ['yes', 'no'],
      offbook: ['yes', 'no'],
      open: ['yes', 'no'],
      weekday: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'],
    }),
    [db.instruments, db.playbook, db.settings],
  )

  const filtered = useMemo(() => {
    const base = runQuery(query, all, {
      instruments: db.instruments,
      setupCode: setups.code,
      haystack: (t) =>
        `${t.entryNote} ${t.exitNote} ${t.lesson} ${t.tags.join(' ')} ${t.date}`,
    })
    return sortTrades(base, sort.key, sort.dir, (id) =>
      db.instruments.find((i) => i.id === id),
    )
  }, [query, all, db.instruments, setups, sort])

  // §5.3 The summary row recomputes for the current filter and always shows
  // sample size and interval.
  const summary = useMemo(
    () => (inst ? ledger(filtered, inst, db.settings.evidenceThreshold) : null),
    [filtered, inst, db.settings.evidenceThreshold],
  )

  const groups = useMemo<GroupedRows<Trade>[] | null>(() => {
    if (group === 'none') return null
    const keyOf = (t: Trade): string => {
      switch (group) {
        case 'setup': return setups.code(t.setupId)
        case 'weekday': return weekday(t.date)
        case 'regime': return t.regime ?? 'unset'
        case 'emotion': return t.emotionAtEntry ?? 'unrecorded'
        case 'mistake': return t.mistakes[0] ?? t.autoTags[0] ?? 'clean'
        default: return ''
      }
    }
    const map = new Map<string, Trade[]>()
    for (const t of filtered) {
      const k = keyOf(t)
      map.set(k, [...(map.get(k) ?? []), t])
    }
    return [...map.entries()]
      .map(([key, rows]) => {
        const l = inst ? ledger(rows, inst, db.settings.evidenceThreshold) : null
        return {
          key,
          label: key,
          rows,
          summary: l ? (
            <>
              n={l.count} · exp{' '}
              {l.expectancy.state === 'insufficient'
                ? '░░░'
                : fmtR(l.expectancy.value, 2)}
            </>
          ) : null,
        }
      })
      .sort((a, b) => b.rows.length - a.rows.length)
  }, [group, filtered, setups, inst, db.settings.evidenceThreshold])

  // §9.4 j/k move · space peek · ⏎ open · x select · ⇧j/k extend · / query
  const cursorIndex = filtered.findIndex((t) => t.id === ui.cursorId)
  useEffect(
    () =>
      registerListNav({
        move: (delta, extend) => {
          const next = Math.max(
            0,
            Math.min(filtered.length - 1, (cursorIndex < 0 ? 0 : cursorIndex) + delta),
          )
          const t = filtered[next]
          if (!t) return
          setCursor(t.id)
          if (extend) {
            const from = Math.min(cursorIndex < 0 ? 0 : cursorIndex, next)
            const to = Math.max(cursorIndex < 0 ? 0 : cursorIndex, next)
            setSelection(filtered.slice(from, to + 1).map((x) => x.id))
          }
        },
        open: () => {
          if (ui.cursorId) navigate({ surface: 'trade', objectId: ui.cursorId })
        },
        openSplit: () => {
          if (ui.cursorId) navigateSplit({ surface: 'trade', objectId: ui.cursorId })
        },
        peek: () => peek(ui.cursorId),
        select: () => {
          if (!ui.cursorId) return
          setSelection(
            ui.selection.includes(ui.cursorId)
              ? ui.selection.filter((x) => x !== ui.cursorId)
              : [...ui.selection, ui.cursorId],
          )
        },
        focusQuery: () => queryRef.current?.focus(),
        filter: () => queryRef.current?.focus(),
        top: () => filtered[0] && setCursor(filtered[0].id),
        bottom: () =>
          filtered.length && setCursor(filtered[filtered.length - 1].id),
        groupBy: () => setGroup((g) => (g === 'none' ? 'setup' : 'none')),
      }),
    [filtered, cursorIndex, ui.cursorId, ui.selection],
  )

  const columns = useMemo<Column<Trade>[]>(
    () => [
      {
        key: 'date', label: 'Date', width: 74, sortable: true,
        render: (t) => formatDate(t.date, false),
      },
      {
        key: 'time', label: 'Time', width: 52,
        render: (t) => (
          <span className="mono faint">{formatTime(t.openedAt, false)}</span>
        ),
      },
      {
        key: 'dir', label: 'Dir', width: 34, type: 'glyph',
        render: (t) => <DirGlyph direction={t.direction} />,
      },
      {
        key: 'instr', label: 'Instr', width: 58,
        render: (t) => (
          <span className="mono">
            {db.instruments.find((i) => i.id === t.instrumentId)?.code}
          </span>
        ),
      },
      {
        key: 'contract', label: 'Strike', width: 82,
        render: (t) => (
          <span className="mono">
            {t.contract === 'OPT' ? `${t.strike} ${t.optionType}` : t.contract}
          </span>
        ),
      },
      {
        key: 'setup', label: 'Setup', width: 78, sortable: true,
        render: (t) =>
          t.offBook ? (
            <span className="faint">off-book</span>
          ) : (
            setups.code(t.setupId)
          ),
      },
      {
        key: 'qty', label: 'Qty', width: 52, type: 'num', sortable: true,
        render: (t) => <span className="mono">{t.qty}</span>,
      },
      // §5.3 R is the primary column, not P&L.
      {
        key: 'r', label: unit === 'R' ? 'R' : '₹', width: 66, type: 'num', sortable: true,
        render: (t) => {
          const i = db.instruments.find((x) => x.id === t.instrumentId)
          if (!i) return '—'
          const r = realisedR(t, i)
          if (t.closedAt == null) return <span className="faint mono">open</span>
          const net = netPnl(t)
          return unit === 'R' ? (
            <NumericCell value={r} unit="R" />
          ) : (
            <span className={`mono ${signClass(net)}`}>{fmtRupees(net)}</span>
          )
        },
      },
      {
        key: 'grade', label: 'Grade', width: 52, sortable: true, align: 'center',
        render: (t) => <GradePill grade={t.grade} />,
      },
      // §5.3 M is a mistake density glyph column: zero to three dots.
      {
        key: 'm', label: 'M', width: 34, type: 'glyph',
        render: (t) => (
          <MistakeDots count={t.mistakes.length + t.autoTags.length} />
        ),
      },
      {
        key: 'conf', label: 'Conf', width: 44, type: 'num', sortable: true,
        render: (t) => <span className="mono faint">{t.confidence}</span>,
      },
      {
        key: 'again', label: 'Again', width: 50, align: 'center',
        render: (t) =>
          t.takeAgain == null ? (
            <span className="faint">—</span>
          ) : (
            <span className={t.takeAgain ? '' : 'attn'}>
              {t.takeAgain ? 'yes' : 'no'}
            </span>
          ),
      },
    ],
    [db.instruments, setups, unit],
  )

  if (!inst) return null

  return (
    <div className="surface">
      <div className="surface__head blotter__head">
        {/* §6.4 QueryBar — every facet click writes into it, so the UI teaches
            the language. */}
        <span className="mono faint">?</span>
        <input
          ref={queryRef}
          className="blotter__query mono"
          value={query}
          placeholder="instrument:bnf setup:orb r:>0 date:2026-q2"
          onChange={(e) => {
            setQuery(e.target.value)
            setSuggestions(suggestQuery(e.target.value, vocab))
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              e.currentTarget.blur()
              setSuggestions([])
            }
            if (e.key === 'Enter') {
              navigate({ query }, { replace: true })
              setSuggestions([])
              e.currentTarget.blur()
            }
            if (e.key === 'Tab' && suggestions.length) {
              e.preventDefault()
              const tokens = query.split(/\s+/)
              tokens[tokens.length - 1] = suggestions[0]
              setQuery(tokens.join(' ') + ' ')
              setSuggestions([])
            }
          }}
          onBlur={() => setTimeout(() => setSuggestions([]), 120)}
        />
        <span className="blotter__count mono">{filtered.length} trades</span>
        <span className="surface__spacer" />
        <Button
          variant="quiet"
          onClick={() => setUnit((u) => (u === 'R' ? '₹' : 'R'))}
          title="R is the default because it teaches the right instinct"
        >
          {unit}
        </Button>
        <select
          className="blotter__group"
          value={group}
          onChange={(e) => setGroup(e.target.value as GroupKey)}
          title="Group by · ⌘G"
        >
          <option value="none">no grouping</option>
          <option value="setup">by setup</option>
          <option value="weekday">by weekday</option>
          <option value="regime">by regime</option>
          <option value="emotion">by emotion</option>
          <option value="mistake">by mistake</option>
        </select>
        {query.trim() && (
          <Button
            variant="quiet"
            onClick={() => {
              const name = window.prompt('Name this query', query.slice(0, 40))
              if (name) {
                saveQuery(name, query)
                toast('Query pinned', true)
              }
            }}
          >
            Pin
          </Button>
        )}
      </div>

      {suggestions.length > 0 && (
        <div className="blotter__suggest">
          {suggestions.map((s) => (
            <Chip
              key={s}
              onClick={() => {
                const tokens = query.split(/\s+/)
                tokens[tokens.length - 1] = s
                setQuery(tokens.join(' ') + ' ')
                queryRef.current?.focus()
              }}
            >
              {s}
            </Chip>
          ))}
        </div>
      )}

      {ui.selection.length > 0 && (
        <div className="blotter__bulk">
          <span className="label">{ui.selection.length} selected</span>
          <span className="faint">
            <Kbd>⌘1</Kbd>–<Kbd>⌘5</Kbd> grade A–F · <Kbd>⌫</Kbd> delete
          </span>
          <Button variant="quiet" onClick={() => setSelection([])}>
            Clear
          </Button>
        </div>
      )}

      <div className="surface__body surface__body--flush">
        <DataGrid
          rows={filtered}
          groups={groups}
          columns={columns}
          rowKey={(t) => t.id}
          rowHeight={db.settings.density === 'compact' ? 28 : 34}
          selection={ui.selection}
          cursorKey={ui.cursorId}
          sort={sort}
          onSort={(key) =>
            setSort((s) =>
              s.key === key
                ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' }
                : { key, dir: 'desc' },
            )
          }
          onCursor={setCursor}
          onOpen={(t) => navigate({ surface: 'trade', objectId: t.id })}
          onPeek={(t) => peek(t.id)}
          onToggleSelect={(key) =>
            setSelection(
              ui.selection.includes(key)
                ? ui.selection.filter((x) => x !== key)
                : [...ui.selection, key],
            )
          }
          empty={
            <Empty kbd="T">
              {query.trim()
                ? 'No trades match this query.'
                : 'No trades yet.'}
            </Empty>
          }
          summary={
            summary && (
              <BlotterSummary
                count={summary.count}
                expectancy={summary.expectancy}
                adherence={summary.adherence}
                goodGrades={summary.goodGradeRate}
              />
            )
          }
        />
      </div>
    </div>
  )
}

/** Facet click helper shared with the Search surface. §6.4 */
export function addFacet(query: string, field: string, value: string): string {
  if (!QUERY_FIELDS.includes(field as never)) return query
  return withTerm(query, field, value)
}

export { StatCell }
