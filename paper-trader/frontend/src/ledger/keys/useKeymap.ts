/* The keymap — §9
 *
 * §0.10 "Keyboard is the primary input device. The mouse is an accessibility
 * affordance and a reading tool, not the way the product is driven."
 *
 * Two rules govern this file:
 *   · Single-letter bindings (T, O, j, k, x…) must never fire while the user
 *     is typing. Every handler checks the edit context first.
 *   · `g` is a prefix, not a chord — it arms and then waits, with a 1.2s
 *     timeout, matching §4.2's "two keystrokes, no hands off home row".
 */

import { useEffect, useMemo, useRef } from 'react'
import { buildCommands, stepDate, type Command } from './commands'
import {
  closeOverlay,
  getUI,
  navigate,
  openOverlay,
  peek,
  setMode,
  setPrefix,
  setSelection,
  setUI,
  toast,
  toggleSplit,
  togglePnl,
  back,
  forward,
} from '../app/uiState'
import { getDB, redo, undo } from '../data/store'
import { deleteTrades, gradeTrades, resolveScenario, sessionKey } from '../data/actions'
import type { Grade } from '../domain/types'
import { updateSettings } from '../data/actions'
import { objectUrl } from '../domain/ids'
import { getListNav } from '../surfaces/listNav'

function isEditing(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  if (!el) return false
  const tag = el.tagName
  return (
    tag === 'INPUT' ||
    tag === 'TEXTAREA' ||
    tag === 'SELECT' ||
    el.isContentEditable
  )
}

export interface ListNav {
  /** j/k movement and the list verbs of §9.4, supplied by the active surface. */
  move?: (delta: number, extend?: boolean) => void
  open?: () => void
  openSplit?: () => void
  peek?: () => void
  select?: () => void
  edit?: () => void
  filter?: () => void
  groupBy?: () => void
  focusQuery?: () => void
  top?: () => void
  bottom?: () => void
  tag?: () => void
  addMistake?: () => void
}

export function useKeymap(listNav?: ListNav) {
  const commands = useMemo(() => buildCommands(), [])
  const navRef = useRef<ListNav | undefined>(listNav)
  navRef.current = listNav

  useEffect(() => {
    let prefixTimer: ReturnType<typeof setTimeout> | null = null

    function armPrefix(p: string) {
      setPrefix(p)
      if (prefixTimer) clearTimeout(prefixTimer)
      prefixTimer = setTimeout(() => setPrefix(null), 1200)
    }

    function clearPrefix() {
      if (prefixTimer) clearTimeout(prefixTimer)
      setPrefix(null)
    }

    function onKey(e: KeyboardEvent) {
      const ui = getUI()
      const db = getDB()
      const editing = isEditing(e.target)
      const mod = e.metaKey || e.ctrlKey
      const key = e.key
      const lower = key.toLowerCase()

      // ── Escape: close the topmost thing. Always available. ────────────
      if (key === 'Escape') {
        if (ui.overlay) {
          closeOverlay()
          return
        }
        if (ui.peekId) {
          peek(null)
          return
        }
        if (ui.drawer) {
          setUI({ drawer: null })
          return
        }
        if (ui.pendingPrefix) {
          clearPrefix()
          return
        }
        if (ui.split) {
          setUI({ split: null, focusedPane: 'primary' })
          return
        }
        return
      }

      // ── Modified chords work even while typing. §9.1 ───────────────────
      if (mod) {
        // ⌘K palette
        if (lower === 'k' && !e.shiftKey) {
          e.preventDefault()
          openOverlay(ui.overlay === 'palette' ? null : 'palette')
          return
        }
        if (lower === 'f' && e.shiftKey) {
          e.preventDefault()
          navigate({ surface: 'search' })
          return
        }
        if (lower === 'i' && e.shiftKey) {
          e.preventDefault()
          openOverlay('palette')
          return
        }
        if (key === ' ' && e.shiftKey) {
          e.preventDefault()
          openOverlay('capture')
          return
        }
        if (lower === 'e') {
          e.preventDefault()
          togglePnl()
          return
        }
        if (lower === 'z') {
          e.preventDefault()
          const label = e.shiftKey ? redo() : undo()
          toast(
            label
              ? `${e.shiftKey ? 'Redid' : 'Undid'} ${label}`
              : `Nothing to ${e.shiftKey ? 'redo' : 'undo'}`,
          )
          return
        }
        if (lower === 'c' && e.shiftKey) {
          e.preventDefault()
          const id = ui.cursorId ?? ui.route.objectId
          if (!id) return toast('Nothing selected')
          navigator.clipboard
            ?.writeText(objectUrl(ui.route.surface, id))
            .then(() => toast('Link copied'))
            .catch(() => toast('Could not copy'))
          return
        }
        if (key === '\\') {
          e.preventDefault()
          if (e.shiftKey) toggleSplit()
          else setUI({ sidebarOpen: !ui.sidebarOpen })
          return
        }
        if (key === '.') {
          e.preventDefault()
          setUI({ inspectorOpen: !ui.inspectorOpen })
          return
        }
        if (key === '[') {
          e.preventDefault()
          back()
          return
        }
        if (key === ']') {
          e.preventDefault()
          forward()
          return
        }
        // ⌘⇧1/2/3 modes · ⌘1–9 instruments · ⌘1–5 grade selection
        if (/^[1-9]$/.test(key)) {
          e.preventDefault()
          if (e.shiftKey) {
            const modes = ['prep', 'live', 'review'] as const
            const m = modes[Number(key) - 1]
            if (m) setMode(m)
            return
          }
          // §5.3 ⌘1–5 grades the selection in bulk — but only when there *is*
          // a selection, otherwise ⌘1–9 means "switch instrument". §9.1
          if (ui.selection.length && Number(key) <= 5) {
            const grade = (['A', 'B', 'C', 'D', 'F'] as Grade[])[Number(key) - 1]
            gradeTrades(ui.selection, grade)
            toast(`Graded ${ui.selection.length} → ${grade}`, true)
            return
          }
          const ordered = [...db.instruments].sort((a, b) => a.order - b.order)
          const inst = ordered[Number(key) - 1]
          if (inst) navigate({ instrumentId: inst.id })
          return
        }
        return
      }

      // ── ⌥ scenario resolution — works in Live without leaving the stream.
      if (e.altKey && /^[1-9]$/.test(key)) {
        e.preventDefault()
        const session = db.sessions.find(
          (s) => s.id === sessionKey(ui.route.instrumentId, ui.route.date),
        )
        const sc = session?.scenarios[Number(key) - 1]
        if (sc) {
          // Cycles pending → playing-out → invalidated, so one key does the
          // whole job during the session. §2.3
          const next =
            sc.status === 'pending'
              ? 'playing-out'
              : sc.status === 'playing-out'
                ? 'invalidated'
                : 'pending'
          resolveScenario(session!.id, sc.id, next)
          toast(`Scenario ${sc.letter} · ${next}`, true)
        }
        return
      }

      // Everything below is a bare key: never fire while typing.
      if (editing) return

      // ── `g` prefix. §4.2 ──────────────────────────────────────────────
      if (ui.pendingPrefix === 'g') {
        e.preventDefault()
        clearPrefix()
        const map: Record<string, () => void> = {
          d: () => navigate({ surface: 'cockpit' }),
          n: () => navigate({ surface: 'notebook' }),
          t: () => navigate({ surface: 'blotter' }),
          p: () => navigate({ surface: 'playbook' }),
          l: () => navigate({ surface: 'timeline' }),
          s: () => navigate({ surface: 'stats' }),
          v: () => navigate({ surface: 'vault' }),
          r: () => navigate({ surface: 'review' }),
          i: () => navigate({ surface: 'inbox' }),
          u: () => navigate({ surface: 'guide' }),
          g: () => navRef.current?.top?.(),
        }
        map[lower]?.()
        return
      }

      // Match on the lowercased key plus the shift flag rather than on the
      // shifted character. Layouts, caps lock and synthetic events do not
      // agree on whether shift+t arrives as "T" or as "t"; the modifier flag
      // is the only thing all of them report consistently.
      if (lower === 'g') {
        e.preventDefault()
        if (e.shiftKey) navRef.current?.bottom?.()
        else armPrefix('g')
        return
      }

      // ── §4.2 temporal navigation ──────────────────────────────────────
      if (key === '[' || key === ']') {
        e.preventDefault()
        const dir = key === '[' ? -1 : 1
        stepDate(dir, e.altKey ? 'week' : e.shiftKey ? 'month' : 'day')
        return
      }

      // ── §9.3 Capture ──────────────────────────────────────────────────
      // Documented as T / O / N. Accepted with or without shift: no lowercase
      // binding competes for these letters, and under time pressure at 09:34
      // insisting on the shift key is friction in exactly the place §1.2 says
      // friction is a bug.
      if (lower === 't') {
        e.preventDefault()
        openOverlay('ticket')
        return
      }
      if (lower === 'o') {
        e.preventDefault()
        setUI({ pendingPrefix: 'observe' })
        return
      }
      if (lower === 'n') {
        e.preventDefault()
        navigate({ surface: 'notebook' })
        return
      }
      if (key === '?') {
        e.preventDefault()
        openOverlay('shortcuts')
        return
      }

      // ── §9.4 Lists ────────────────────────────────────────────────────
      // The active surface publishes its verbs; if none has, bare keys do
      // nothing rather than firing on the wrong surface.
      const nav = getListNav() ?? navRef.current
      if (!nav) return

      // §9.4 j/k move · ⇧j/k extend selection.
      if (lower === 'j' || lower === 'k') {
        e.preventDefault()
        nav.move?.(lower === 'j' ? 1 : -1, e.shiftKey)
        return
      }

      switch (key) {
        case ' ':
          e.preventDefault()
          nav.peek?.()
          return
        case 'Enter':
          e.preventDefault()
          nav.open?.()
          return
        case 'x':
          e.preventDefault()
          nav.select?.()
          return
        case 'e':
          e.preventDefault()
          nav.edit?.()
          return
        case 'f':
          e.preventDefault()
          nav.filter?.()
          return
        case '#':
          e.preventDefault()
          nav.tag?.()
          return
        case 'm':
          e.preventDefault()
          nav.addMistake?.()
          return
        case '/':
          e.preventDefault()
          nav.focusQuery?.()
          return
        case 'Backspace':
        case 'Delete': {
          e.preventDefault()
          const ids = ui.selection.length
            ? ui.selection
            : ui.cursorId
              ? [ui.cursorId]
              : []
          if (!ids.length) return
          // §8 Delete is undoable, so it needs no confirmation.
          deleteTrades(ids)
          setSelection([])
          toast(`Deleted ${ids.length} trade${ids.length > 1 ? 's' : ''}`, true)
          return
        }
      }
    }

    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      if (prefixTimer) clearTimeout(prefixTimer)
    }
  }, [])

  return commands as Command[]
}

/** §5.11 Density and theme are applied to the scope root so tokens cascade.
 *
 *  The source wrote these onto document.documentElement. Inside a host app that
 *  stomps the host's own theming, so they land on `.ledger-root` instead — which
 *  is also what the token selectors now target, since the PostCSS pass rewrites
 *  `:root[data-theme=…]` to `.ledger-root[data-theme=…]`. */
export function useAppearance(settings: {
  theme: string
  density: string
  cvdSafe: boolean
}) {
  useEffect(() => {
    const root = document.querySelector('.ledger-root') as HTMLElement | null
    if (!root) return
    root.dataset.theme = settings.theme
    root.dataset.density = settings.density
    if (settings.cvdSafe) root.dataset.cvd = 'on'
    else delete root.dataset.cvd
  }, [settings.theme, settings.density, settings.cvdSafe])
}

export { updateSettings }
