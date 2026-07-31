/* The frame — §4.1
 *
 *   ┌──┬───────────────┬──────────────────────────┬─────────────┐
 *   │ I│  CONTEXT      │   breadcrumb        ⌘K   │  INSPECTOR  │
 *   │ N│  SIDEBAR      │                          │   (⌘.)      │
 *   │ S│               │      CONTENT PANE        │             │
 *   │ T│  ── pinned ── │                          │             │
 *   │ R│  Queries      ├──────────────────────────┤             │
 *   │  │  Levels       │ ● synced  PREP  n=142 …  │             │
 *   └──┴───────────────┴──────────────────────────┴─────────────┘
 *     48px    216px            flexible               380px
 *
 * All widths fixed — §7.4 "resizable panels are a fidget toy that costs
 * layout consistency."
 */

import { type ReactNode } from 'react'
import {
  navigate,
  reorderRail,
  setUI,
  useUI,
} from '../uiState'
import {
  useDayRisk,
  useInbox,
  useInstruments,
  useLevels,
  useRailStates,
  useSessionDates,
  useStore,
  useUnresolved,
  useDB,
} from '../../data/hooks'
import { formatDate, weekday } from '../../domain/dates'
import { Kbd } from '../../components/primitives'
import { LevelLadder } from '../../components/editor/blocks'
import { fmtR, signClass } from '../../components/data'
import './shell.css'

// ── Instrument rail ───────────────────────────────────────────────────────
// §4.1 48px, always visible. One tile per instrument: ticker abbreviation in
// mono, plus a 3px state bar. ⌘1–9 jumps. Reordering is drag; the order is
// yours and persists.

function InstrumentRail() {
  const instruments = useInstruments()
  const states = useRailStates()
  const ui = useUI()

  return (
    <nav className="rail" aria-label="Instruments">
      {instruments.map((inst, i) => (
        <button
          key={inst.id}
          className={`rail__tile ${
            ui.route.instrumentId === inst.id ? 'is-active' : ''
          }`}
          onClick={() => navigate({ instrumentId: inst.id })}
          title={`${inst.name}${i < 9 ? ` · ⌘${i + 1}` : ''}`}
          draggable
          onDragStart={(e) => e.dataTransfer.setData('text/plain', inst.id)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault()
            const dragged = e.dataTransfer.getData('text/plain')
            if (dragged && dragged !== inst.id) reorderRail(dragged, inst.id)
          }}
        >
          <span className="rail__code mono">{inst.code}</span>
          <span className={`rail__state rail__state--${states[inst.id]}`} />
        </button>
      ))}
    </nav>
  )
}

// ── Context sidebar ───────────────────────────────────────────────────────
// §4.1 216px, ⌘\ to collapse. Sections for the *current instrument*. Never
// changes shape between instruments, so muscle memory holds.
// §7.5 Icons never appear next to text labels in the sidebar — the labels are
// enough and icons there are noise.

const SECTIONS: { surface: Parameters<typeof navigate>[0]['surface']; label: string; kbd: string }[] = [
  { surface: 'cockpit', label: 'Today', kbd: 'gd' },
  { surface: 'notebook', label: 'Notebook', kbd: 'gn' },
  { surface: 'blotter', label: 'Trades', kbd: 'gt' },
  { surface: 'playbook', label: 'Playbook', kbd: 'gp' },
  { surface: 'timeline', label: 'Timeline', kbd: 'gl' },
  { surface: 'stats', label: 'Stats', kbd: 'gs' },
  { surface: 'vault', label: 'Vault', kbd: 'gv' },
]

function Sidebar() {
  const ui = useUI()
  const db = useDB()
  const levels = useLevels(ui.route.instrumentId)
  const inbox = useInbox(ui.route.instrumentId)
  const pinned = db.savedQueries.filter((q) => q.pinned)

  return (
    <aside className="sidebar" aria-label="Context">
      <div className="sidebar__sections">
        {SECTIONS.map((s) => (
          <button
            key={s.surface}
            className={`sidebar__item ${
              ui.route.surface === s.surface ? 'is-active' : ''
            }`}
            onClick={() => navigate({ surface: s.surface })}
          >
            <span>{s.label}</span>
            <span className="sidebar__kbd mono">{s.kbd}</span>
          </button>
        ))}
        <button
          className={`sidebar__item ${ui.route.surface === 'inbox' ? 'is-active' : ''}`}
          onClick={() => navigate({ surface: 'inbox' })}
        >
          <span>Inbox</span>
          {inbox.length > 0 ? (
            <span className="sidebar__count">{inbox.length}</span>
          ) : (
            <span className="sidebar__kbd mono">gi</span>
          )}
        </button>
        {/* The Guide is a permanent destination, not a tour that fires once. */}
        <button
          className={`sidebar__item ${ui.route.surface === 'guide' ? 'is-active' : ''}`}
          onClick={() => navigate({ surface: 'guide' })}
        >
          <span>Guide</span>
          <span className="sidebar__kbd mono">gu</span>
        </button>
      </div>

      {/* §4.1 Below the fixed sections: pinned saved queries and the level
          ladder in miniature. */}
      <div className="sidebar__pinned scroll">
        <div className="label sidebar__grouphead">Queries</div>
        {pinned.map((q) => (
          <button
            key={q.id}
            className="sidebar__query"
            onClick={() => navigate({ surface: 'blotter', query: q.query })}
            title={q.query}
          >
            {q.name}
          </button>
        ))}

        <div className="label sidebar__grouphead">Levels</div>
        <div className="sidebar__levels">
          <LevelLadder levels={levels.slice(0, 8)} compact />
        </div>
      </div>
    </aside>
  )
}

// ── Breadcrumb ────────────────────────────────────────────────────────────

function Breadcrumb({ onPalette }: { onPalette: () => void }) {
  const ui = useUI()
  const db = useDB()
  const inst = db.instruments.find((i) => i.id === ui.route.instrumentId)
  const dates = useSessionDates(ui.route.instrumentId)

  const surfaceName: Record<string, string> = {
    cockpit: 'Session', notebook: 'Notebook', blotter: 'Trades', trade: 'Trade',
    timeline: 'Timeline', playbook: 'Playbook', stats: 'Stats',
    review: 'Review', vault: 'Vault', search: 'Search', settings: 'Settings',
    inbox: 'Inbox', weekly: 'Weekly',
  }

  return (
    <header className="crumb">
      <span className="crumb__inst">{inst?.name}</span>
      <span className="crumb__sep">›</span>
      <span className="crumb__part">{surfaceName[ui.route.surface]}</span>
      <span className="crumb__sep">›</span>
      {/* §4.2 The date scrubber in the breadcrumb is the mouse equivalent of
          [ and ]. */}
      <input
        className="crumb__date mono"
        type="range"
        min={0}
        max={Math.max(0, dates.length - 1)}
        value={Math.max(0, dates.indexOf(ui.route.date))}
        onChange={(e) => {
          const d = dates[Number(e.target.value)]
          if (d) navigate({ date: d })
        }}
        disabled={dates.length < 2}
        title="Scrub sessions"
      />
      <span className="crumb__part mono">
        {formatDate(ui.route.date)} · {weekday(ui.route.date)}
      </span>
      <button className="crumb__palette" onClick={onPalette}>
        <Kbd>⌘K</Kbd>
      </button>
    </header>
  )
}

// ── Status bar ────────────────────────────────────────────────────────────
// §4.1 Sync dot, current mode, sample size of the current view, and today's
// risk used in R. Four things. Nothing blinks.

function StatusBar({ sampleSize }: { sampleSize: number }) {
  const ui = useUI()
  const store = useStore()
  const risk = useDayRisk(ui.route.instrumentId, ui.route.date)
  const unresolved = useUnresolved(ui.route.instrumentId)

  return (
    <footer className="status">
      <span className={`status__dot status__dot--${store.sync}`} title={store.sync} />
      <span className="status__mode label">{ui.mode}</span>
      <span className="status__n mono">n={sampleSize}</span>
      <span className="status__risk mono">
        <span className="faint">⌥R risk </span>
        <span className={signClass(risk)}>{fmtR(risk)}</span>
      </span>
      {unresolved.length > 0 && (
        <button
          className="status__nag attn"
          onClick={() =>
            navigate({ surface: 'review', date: unresolved[0].date })
          }
        >
          {unresolved.length} unreviewed
        </button>
      )}
    </footer>
  )
}

// ── Inspector ─────────────────────────────────────────────────────────────
// §4.1 380px, ⌘. — details of whatever is selected without leaving the list.
// "This is the primary reason the blotter never needs a modal."

function Inspector({ children }: { children: ReactNode }) {
  return (
    <aside className="inspector" aria-label="Inspector">
      <div className="inspector__body scroll">{children}</div>
    </aside>
  )
}

// ── Shell ─────────────────────────────────────────────────────────────────

export function Shell({
  children,
  split,
  inspector,
  sampleSize,
  onPalette,
}: {
  children: ReactNode
  split?: ReactNode
  inspector?: ReactNode
  sampleSize: number
  onPalette: () => void
}) {
  const ui = useUI()
  return (
    <div
      className={`shell ${ui.sidebarOpen ? '' : 'shell--nosidebar'} ${
        ui.inspectorOpen && inspector ? 'shell--inspector' : ''
      }`}
    >
      <InstrumentRail />
      {ui.sidebarOpen && <Sidebar />}
      <main className="main">
        <Breadcrumb onPalette={onPalette} />
        <div className={`panes ${split ? 'panes--split' : ''}`}>
          <section
            className={`pane ${ui.focusedPane === 'primary' ? 'is-focused' : ''}`}
            onMouseDown={() => ui.split && setUI({ focusedPane: 'primary' })}
          >
            {children}
          </section>
          {split && (
            <section
              className={`pane pane--split ${
                ui.focusedPane === 'split' ? 'is-focused' : ''
              }`}
              onMouseDown={() => setUI({ focusedPane: 'split' })}
            >
              {split}
            </section>
          )}
        </div>
        <StatusBar sampleSize={sampleSize} />
      </main>
      {ui.inspectorOpen && inspector && <Inspector>{inspector}</Inspector>}
    </div>
  )
}
