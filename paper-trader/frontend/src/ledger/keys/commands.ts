/* The command registry — one definition per verb, consumed by both the
 * keymap (§9) and the command palette (§4.3). Defining them once is what makes
 * §1.3's claim true: "the command palette and ? are the documentation."
 */

import {
  back,
  closeSplit,
  forward,
  navigate,
  openOverlay,
  peek,
  setMode,
  setUI,
  toast,
  toggleSplit,
  togglePnl,
  getUI,
} from '../app/uiState'
import { getDB, redo, undo } from '../data/store'
import { addDays, addMonths, today } from '../domain/dates'
import { updateSettings } from '../data/actions'
import { objectUrl } from '../domain/ids'
import type { Surface } from '../app/uiState'

export interface Command {
  id: string
  title: string
  section: string
  kbd?: string
  run: () => void
  /** Availability predicate; also filters the palette. */
  when?: () => boolean
  paletteHidden?: boolean
}

const go = (surface: Surface) => () => navigate({ surface })

/** §4.2 Temporal navigation: `[` and `]` move one session back/forward *in the
 *  current view*. Holding ⌥ steps by week, ⇧ by month. */
export function stepDate(dir: -1 | 1, unit: 'day' | 'week' | 'month') {
  const ui = getUI()
  const db = getDB()
  const cur = ui.route.date

  if (unit === 'month') return navigate({ date: addMonths(cur, dir) })
  if (unit === 'week') return navigate({ date: addDays(cur, dir * 7) })

  // By day, `[`/`]` step through *sessions that exist*, not raw calendar days
  // — stepping into four empty weekend days to reach Friday is not "one
  // session back".
  const dates = [
    ...new Set(
      db.sessions
        .filter((s) => s.instrumentId === ui.route.instrumentId)
        .map((s) => s.date),
    ),
  ].sort()
  const idx = dates.indexOf(cur)
  if (idx === -1) {
    const fallback =
      dir < 0
        ? [...dates].reverse().find((d) => d < cur)
        : dates.find((d) => d > cur)
    return navigate({ date: fallback ?? addDays(cur, dir) })
  }
  const next = dates[idx + dir]
  navigate({ date: next ?? addDays(cur, dir) })
}

export function buildCommands(): Command[] {
  return [
    // ── §9.1 Global ──────────────────────────────────────────────────────
    { id: 'palette', title: 'Command palette', section: 'Global', kbd: '⌘K', run: () => openOverlay('palette') },
    { id: 'capture', title: 'Quick capture', section: 'Global', kbd: '⌘⇧Space', run: () => openOverlay('capture') },
    { id: 'search', title: 'Full search', section: 'Global', kbd: '⌘⇧F', run: go('search') },
    { id: 'instrument-switcher', title: 'Instrument switcher', section: 'Global', kbd: '⌘⇧I', run: () => openOverlay('palette') },
    {
      id: 'toggle-sidebar', title: 'Toggle sidebar', section: 'Global', kbd: '⌘\\',
      run: () => setUI({ sidebarOpen: !getUI().sidebarOpen }),
    },
    {
      id: 'toggle-inspector', title: 'Toggle inspector', section: 'Global', kbd: '⌘.',
      run: () => setUI({ inspectorOpen: !getUI().inspectorOpen }),
    },
    { id: 'split', title: 'Split pane', section: 'Global', kbd: '⌘⇧\\', run: toggleSplit },
    { id: 'close-split', title: 'Close split pane', section: 'Global', run: closeSplit, when: () => Boolean(getUI().split) },
    { id: 'back', title: 'Back', section: 'Global', kbd: '⌘[', run: back },
    { id: 'forward', title: 'Forward', section: 'Global', kbd: '⌘]', run: forward },
    { id: 'prev-session', title: 'Previous session', section: 'Global', kbd: '[', run: () => stepDate(-1, 'day') },
    { id: 'next-session', title: 'Next session', section: 'Global', kbd: ']', run: () => stepDate(1, 'day') },
    { id: 'shortcuts', title: 'Keyboard shortcuts', section: 'Global', kbd: '?', run: () => openOverlay('shortcuts') },
    {
      id: 'undo', title: 'Undo', section: 'Global', kbd: '⌘Z',
      run: () => {
        const label = undo()
        // §8 A toast confirming what was undone.
        toast(label ? `Undid ${label}` : 'Nothing to undo')
      },
    },
    {
      id: 'redo', title: 'Redo', section: 'Global', kbd: '⌘⇧Z',
      run: () => {
        const label = redo()
        toast(label ? `Redid ${label}` : 'Nothing to redo')
      },
    },

    // §2.1 Modes, not screens.
    { id: 'mode-prep', title: 'Prep mode', section: 'Modes', kbd: '⌘⇧1', run: () => setMode('prep') },
    { id: 'mode-live', title: 'Live mode', section: 'Modes', kbd: '⌘⇧2', run: () => setMode('live') },
    { id: 'mode-review', title: 'Review mode', section: 'Modes', kbd: '⌘⇧3', run: () => setMode('review') },
    {
      id: 'toggle-pnl', title: 'Reveal / hide P&L', section: 'Modes', kbd: '⌘E',
      run: togglePnl,
    },

    // ── §9.2 Navigation (g prefix) ───────────────────────────────────────
    { id: 'go-today', title: 'Go to today’s Cockpit', section: 'Navigation', kbd: 'g d', run: () => navigate({ surface: 'cockpit', date: today() }) },
    { id: 'go-notebook', title: 'Go to Notebook', section: 'Navigation', kbd: 'g n', run: go('notebook') },
    { id: 'go-trades', title: 'Go to Trades', section: 'Navigation', kbd: 'g t', run: go('blotter') },
    { id: 'go-playbook', title: 'Go to Playbook', section: 'Navigation', kbd: 'g p', run: go('playbook') },
    { id: 'go-timeline', title: 'Go to Timeline', section: 'Navigation', kbd: 'g l', run: go('timeline') },
    { id: 'go-stats', title: 'Go to Research Bench', section: 'Navigation', kbd: 'g s', run: go('stats') },
    { id: 'go-vault', title: 'Go to Vault', section: 'Navigation', kbd: 'g v', run: go('vault') },
    { id: 'go-review', title: 'Go to Session Review', section: 'Navigation', kbd: 'g r', run: go('review') },
    { id: 'go-inbox', title: 'Go to Inbox', section: 'Navigation', kbd: 'g i', run: go('inbox') },
    { id: 'go-weekly', title: 'Go to Weekly review', section: 'Navigation', run: go('weekly') },
    { id: 'go-settings', title: 'Settings & schema', section: 'Navigation', run: go('settings') },
    { id: 'go-guide', title: 'Guide — how this works', section: 'Navigation', kbd: 'g u', run: go('guide') },

    // ── §9.3 Capture ─────────────────────────────────────────────────────
    { id: 'new-trade', title: 'New trade ticket', section: 'Capture', kbd: 'T', run: () => openOverlay('ticket') },
    { id: 'new-observation', title: 'New observation', section: 'Capture', kbd: 'O', run: () => setUI({ overlay: null, pendingPrefix: 'observe' }) },
    { id: 'screenshot', title: 'Attach screenshot', section: 'Capture', kbd: '⌘⇧4', run: () => openDrawerScreenshot() },

    // ── Object verbs — §8 "Objects, not pages" ───────────────────────────
    {
      id: 'copy-link', title: 'Copy link to selection', section: 'Object', kbd: '⌘⇧C',
      run: () => {
        const ui = getUI()
        const id = ui.cursorId ?? ui.route.objectId
        if (!id) return toast('Nothing selected')
        navigator.clipboard
          ?.writeText(objectUrl(ui.route.surface, id))
          .then(() => toast('Link copied'))
          .catch(() => toast('Could not copy'))
      },
    },
    { id: 'dismiss-peek', title: 'Dismiss peek', section: 'Object', run: () => peek(null), paletteHidden: true },

    // ── Appearance ───────────────────────────────────────────────────────
    {
      id: 'toggle-theme', title: 'Toggle light / dark', section: 'Appearance',
      run: () => {
        const s = getDB().settings
        updateSettings({ theme: s.theme === 'dark' ? 'light' : 'dark' })
      },
    },
    {
      id: 'toggle-density', title: 'Toggle compact / comfortable', section: 'Appearance',
      run: () => {
        const s = getDB().settings
        updateSettings({
          density: s.density === 'compact' ? 'comfortable' : 'compact',
        })
      },
    },
    {
      id: 'toggle-cvd', title: 'Toggle colourblind-safe palette', section: 'Appearance',
      run: () => updateSettings({ cvdSafe: !getDB().settings.cvdSafe }),
    },

  ]
}

function openDrawerScreenshot() {
  // The real product region-captures via the OS. In the browser the honest
  // equivalent is a file picker, surfaced through the same drawer.
  openOverlay('drawer', 'screenshot')
  setUI({ drawer: { kind: 'screenshot' } })
}
