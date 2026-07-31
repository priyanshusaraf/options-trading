/* CommandPalette — §4.3
 *
 * "Not a search box with commands bolted on — a typed interpreter."
 *
 *   bare text → fuzzy across commands, instruments, sessions, trades, notes,
 *               setups, tags. Results grouped, best group first, ⇥ cycles.
 *   >  commands only
 *   @  jump to instrument
 *   #  tag
 *   /  date (/yesterday, /last thu, /2026-06, /june)
 *   $  trade by ID or fuzzy description
 *   ?  structured query, hands off to the query bar
 *
 * Actions are contextual; ⌘⏎ on any result opens it in the split pane.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { useDB } from '../../data/hooks'
import { closeOverlay, navigate, navigateSplit, useUI } from '../../app/uiState'
import { formatDate, parseDateExpression, weekday } from '../../domain/dates'
import { Kbd } from '../primitives'
import type { Command } from '../../keys/commands'
import './overlays.css'

export interface PaletteResult {
  id: string
  group: string
  label: string
  hint?: string
  kbd?: string
  score?: number
  run: (opts: { split: boolean }) => void
}

/** Tie-break only. §4.3 puts the *best* group first, so this ordering applies
 *  when two groups match equally well. */
const GROUP_ORDER = [
  'Commands', 'Instruments', 'Sessions', 'Trades', 'Setups', 'Notes', 'Tags', 'Dates',
]

/** How well a candidate matches: a prefix beats a substring beats a
 *  subsequence. Without this, "orb" ranks "G-o-to R-esearch B-ench" — a
 *  subsequence hit — above the ORB setup the user is plainly looking for. */
function score(hay: string, needle: string): number {
  if (!needle) return 1
  const h = hay.toLowerCase()
  const n = needle.toLowerCase()
  if (h === n) return 100
  if (h.startsWith(n)) return 60
  const words = h.split(/[\s·/-]+/)
  if (words.some((w) => w.startsWith(n))) return 45
  if (h.includes(n)) return 30
  return fuzzy(h, n) ? 5 : 0
}

export function CommandPalette({ commands }: { commands: Command[] }) {
  const db = useDB()
  const ui = useUI()
  const [q, setQ] = useState('')
  const [index, setIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => inputRef.current?.focus(), [])
  useEffect(() => setIndex(0), [q])

  const results = useMemo<PaletteResult[]>(() => {
    // Only the documented prefixes are sigils. Treating any first character as
    // one silently switches the interpreter into a mode the user did not ask
    // for, and bare text stops reaching trades, sessions, notes and setups.
    const SIGILS = '>@#/$?'
    const sigil = q.length && SIGILS.includes(q[0]) ? q[0] : ''
    const rest = q.slice(1).trim()
    const term = q.trim().toLowerCase()
    const out: PaletteResult[] = []

    const needle = (sigil ? rest : term).toLowerCase()
    // Returns 0 for "no match", so it doubles as the guard and the rank.
    const match = (hay: string) => score(hay, needle)

    // `>` commands only
    if (sigil !== '@' && sigil !== '#' && sigil !== '/' && sigil !== '$') {
      for (const c of commands) {
        if (c.paletteHidden) continue
        if (!c.when?.() && c.when) continue
        const s0 = match(`${c.title} ${c.kbd ?? ''}`)
        if (needle && !s0) continue
        out.push({
          id: `cmd_${c.id}`,
          group: 'Commands',
          label: c.title,
          hint: c.section,
          kbd: c.kbd,
          score: s0,
          run: () => c.run(),
        })
      }
    }

    // `@` instruments
    if (sigil !== '>' && sigil !== '#' && sigil !== '/' && sigil !== '$') {
      for (const inst of db.instruments) {
        const s0 = Math.max(match(inst.code), match(inst.name))
        if (needle && !s0) continue
        out.push({
          id: `inst_${inst.id}`,
          group: 'Instruments',
          label: inst.name,
          hint: inst.code,
          score: s0,
          run: ({ split }) =>
            (split ? navigateSplit : navigate)({
              instrumentId: inst.id,
              surface: 'cockpit',
            }),
        })
      }
    }

    // `/` dates — /yesterday, /last thu, /2026-06, /june
    if (sigil === '/' || !sigil) {
      const parsed = parseDateExpression(sigil === '/' ? rest : term)
      if (parsed) {
        out.push({
          id: `date_${parsed}`,
          group: 'Dates',
          label: `${formatDate(parsed)} · ${weekday(parsed)}`,
          hint: 'open session',
          score: 70,
          run: ({ split }) =>
            (split ? navigateSplit : navigate)({ date: parsed, surface: 'cockpit' }),
        })
      }
    }

    // `#` tags
    if (sigil === '#' || !sigil) {
      const tags = new Set<string>()
      for (const t of db.trades) t.tags.forEach((x) => tags.add(x))
      for (const e of db.events) e.tags.forEach((x) => tags.add(x))
      for (const m of db.settings.mistakes) tags.add(m.label)
      for (const tag of tags) {
        const s0 = match(tag)
        if (needle && !s0) continue
        out.push({
          id: `tag_${tag}`,
          group: 'Tags',
          label: `#${tag}`,
          hint: 'filter blotter',
          score: s0,
          run: ({ split }) =>
            (split ? navigateSplit : navigate)({
              surface: 'blotter',
              query: `tag:${tag} or mistake:${tag}`,
            }),
        })
      }
    }

    // `$` trades by id or fuzzy description
    if (sigil === '$' || (!sigil && term.length > 2)) {
      for (const t of db.trades.filter((x) => !x.deletedAt).slice(0, 400)) {
        const inst = db.instruments.find((i) => i.id === t.instrumentId)
        const setup = db.playbook.find((p) => p.id === t.setupId)
        const desc = `${inst?.code ?? ''} ${t.strike ?? ''} ${t.optionType ?? t.contract} ${
          t.direction
        } ${setup?.code ?? 'off-book'} ${t.date} ${t.id}`
        const s0 = match(desc)
        if (!needle || !s0) continue
        out.push({
          id: `tr_${t.id}`,
          group: 'Trades',
          label: `${inst?.code} ${
            t.contract === 'OPT' ? `${t.strike} ${t.optionType}` : t.contract
          } · ${t.direction}`,
          hint: `${formatDate(t.date, false)} · ${setup?.code ?? 'off-book'}`,
          score: s0,
          run: ({ split }) =>
            (split ? navigateSplit : navigate)({
              surface: 'trade',
              objectId: t.id,
              instrumentId: t.instrumentId,
            }),
        })
      }
    }

    // Sessions, setups and notes on bare text.
    if (!sigil || sigil === '>') {
      if (term) {
        for (const s of db.sessions.slice(0, 400)) {
          const s0 = Math.max(match(s.date), match(s.thesis))
          if (!s0) continue
          const inst = db.instruments.find((i) => i.id === s.instrumentId)
          out.push({
            id: `se_${s.id}`,
            group: 'Sessions',
            label: `${inst?.code} · ${formatDate(s.date)}`,
            hint: s.thesis.slice(0, 60),
            score: s0,
            run: ({ split }) =>
              (split ? navigateSplit : navigate)({
                surface: 'cockpit',
                instrumentId: s.instrumentId,
                date: s.date,
              }),
          })
        }
        for (const p of db.playbook) {
          const s0 = Math.max(match(p.name), match(p.code))
          if (!s0) continue
          out.push({
            id: `pb_${p.id}`,
            group: 'Setups',
            label: p.name,
            hint: p.code,
            score: s0,
            run: ({ split }) =>
              (split ? navigateSplit : navigate)({
                surface: 'playbook',
                objectId: p.id,
              }),
          })
        }
        for (const d of db.docs) {
          const s0 = Math.max(match(d.title), match(d.body) ? 20 : 0)
          if (!s0) continue
          const inst = db.instruments.find((i) => i.id === d.instrumentId)
          out.push({
            id: `doc_${d.id}`,
            group: 'Notes',
            label: d.title,
            hint: inst?.code,
            score: s0,
            run: ({ split }) =>
              (split ? navigateSplit : navigate)({
                surface: 'notebook',
                instrumentId: d.instrumentId,
                objectId: d.id,
              }),
          })
        }
      }
    }

    // `?` hands off to the query bar. §4.3
    if (sigil === '?') {
      out.length = 0
      out.push({
        id: 'query',
        group: 'Commands',
        label: `Run query: ${rest || '…'}`,
        hint: 'opens the blotter with this filter',
        run: ({ split }) =>
          (split ? navigateSplit : navigate)({ surface: 'blotter', query: rest }),
      })
    }

    // §4.3 Results grouped, best group first — "best" meaning the group
    // holding the strongest match, not a fixed precedence list.
    const best = new Map<string, number>()
    for (const r of out) {
      best.set(r.group, Math.max(best.get(r.group) ?? 0, r.score ?? 0))
    }
    const groups = [...best.keys()].sort(
      (a, b) =>
        (best.get(b) ?? 0) - (best.get(a) ?? 0) ||
        GROUP_ORDER.indexOf(a) - GROUP_ORDER.indexOf(b),
    )
    return groups.flatMap((g) =>
      out
        .filter((r) => r.group === g)
        .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
        .slice(0, 8),
    )
  }, [q, db, commands])

  const groups = [...new Set(results.map((r) => r.group))]

  function commit(split: boolean) {
    const r = results[index]
    if (!r) return
    closeOverlay()
    r.run({ split })
  }

  return (
    <div className="overlay" onMouseDown={closeOverlay}>
      <div
        className="palette"
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Command palette"
      >
        <input
          ref={inputRef}
          className="palette__input"
          value={q}
          placeholder="Type to search — > commands  @ instrument  # tag  / date  $ trade  ? query"
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'ArrowDown') {
              e.preventDefault()
              setIndex((i) => Math.min(results.length - 1, i + 1))
            } else if (e.key === 'ArrowUp') {
              e.preventDefault()
              setIndex((i) => Math.max(0, i - 1))
            } else if (e.key === 'Tab') {
              // ⇥ cycles groups. §4.3
              e.preventDefault()
              const cur = results[index]?.group
              const gi = groups.indexOf(cur)
              const next = groups[(gi + 1) % groups.length]
              const target = results.findIndex((r) => r.group === next)
              if (target >= 0) setIndex(target)
            } else if (e.key === 'Enter') {
              e.preventDefault()
              commit(e.metaKey || e.ctrlKey)
            } else if (e.key === 'Escape') {
              e.preventDefault()
              closeOverlay()
            }
          }}
        />
        <div className="palette__results scroll">
          {groups.map((g) => (
            <div key={g}>
              <div className="palette__group label">{g}</div>
              {results
                .map((r, i) => ({ r, i }))
                .filter(({ r }) => r.group === g)
                .map(({ r, i }) => (
                  <button
                    key={r.id}
                    className={`palette__item ${i === index ? 'is-active' : ''}`}
                    onMouseEnter={() => setIndex(i)}
                    onClick={(e) => {
                      closeOverlay()
                      r.run({ split: e.metaKey || e.ctrlKey })
                    }}
                  >
                    <span className="palette__label">{r.label}</span>
                    {r.hint && <span className="palette__hint">{r.hint}</span>}
                    {r.kbd && <Kbd>{r.kbd}</Kbd>}
                  </button>
                ))}
            </div>
          ))}
          {!results.length && (
            <div className="palette__none faint">No matches.</div>
          )}
        </div>
        <div className="palette__foot">
          <span className="faint">
            {ui.route.surface} · {db.instruments.find((i) => i.id === ui.route.instrumentId)?.code}
          </span>
          <span className="palette__footkeys">
            <Kbd>⏎</Kbd> open <Kbd>⌘⏎</Kbd> split <Kbd>⇥</Kbd> group
          </span>
        </div>
      </div>
    </div>
  )
}

/** Subsequence fuzzy match — cheap, and good enough at these list sizes. */
export function fuzzy(hay: string, needle: string): boolean {
  if (!needle) return true
  let i = 0
  for (const ch of hay) {
    if (ch === needle[i]) i++
    if (i === needle.length) return true
  }
  return false
}
