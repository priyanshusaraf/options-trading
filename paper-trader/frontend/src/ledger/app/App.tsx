/* App root — wires the shell, the router, the keymap and the overlays. */

import { useEffect, useMemo } from 'react'
import { Shell } from './shell/Shell'
import {
  closeOverlay,
  getUI,
  navigate,
  peek,
  setMode,
  useUI,
  type Route,
} from './uiState'
import { boot, wasFirstRun } from '../data/store'
import { useDB, useInstrument, useStore, useTrades } from '../data/hooks'
import { useAppearance, useKeymap } from '../keys/useKeymap'
import { suggestedMode } from '../domain/dates'

import { Cockpit } from '../surfaces/Cockpit'
import { Notebook } from '../surfaces/Notebook'
import { Blotter } from '../surfaces/Blotter'
import { TradeDetail, TradeInspector } from '../surfaces/TradeDetail'
import { Timeline } from '../surfaces/Timeline'
import { Playbook } from '../surfaces/Playbook'
import { Stats } from '../surfaces/Stats'
import { Review } from '../surfaces/Review'
import { Vault, ArtifactInspector } from '../surfaces/Vault'
import { Search } from '../surfaces/Search'
import { Inbox, PeriodReview, Settings } from '../surfaces/Misc'
import { Guide } from '../surfaces/Guide'

import {
  CommandPalette,
  Drawer,
  QuickCapture,
  ShortcutSheet,
  Toasts,
} from '../components/overlays'
import { Peek } from '../components/data'
import { ProgressLine } from '../components/primitives'

function SurfaceFor({ route }: { route: Route }) {
  switch (route.surface) {
    case 'cockpit': return <Cockpit />
    case 'notebook': return <Notebook />
    case 'blotter': return <Blotter />
    case 'trade': return <TradeDetail />
    case 'timeline': return <Timeline />
    case 'playbook': return <Playbook />
    case 'stats': return <Stats />
    case 'review': return <Review />
    case 'vault': return <Vault />
    case 'search': return <Search />
    case 'inbox': return <Inbox />
    case 'weekly': return <PeriodReview />
    case 'settings': return <Settings />
    case 'guide': return <Guide />
    default: return null
  }
}

/* The workspace proper. Mounted only once the gate is passed, so the global
 * keymap is never listening behind the sign-in screen. */
function Workspace() {
  const store = useStore()
  const ui = useUI()
  const db = useDB()
  const commands = useKeymap()
  const inst = useInstrument(ui.route.instrumentId)
  const trades = useTrades(ui.route.instrumentId)

  useAppearance(db.settings)

  // §2.1 The mode is auto-suggested by the instrument's session clock, and is
  // per-instrument — but a manual choice always wins until the user changes
  // instrument.
  useEffect(() => {
    if (!inst || ui.modeManual) return
    setMode(suggestedMode(inst), false)
  }, [inst?.id, ui.modeManual])

  // §8 Peek dismisses on any nav.
  useEffect(() => {
    peek(null)
  }, [ui.route.surface, ui.route.objectId, ui.route.date, ui.route.instrumentId])

  // Deep links: ledger://surface/id, and plain #hash routing so the browser
  // back button is not a trap.
  useEffect(() => {
    const apply = () => {
      const hash = window.location.hash.slice(1)
      if (!hash) return
      const [surface, objectId] = hash.split('/')
      if (surface) navigate({ surface: surface as Route['surface'], objectId })
    }
    window.addEventListener('hashchange', apply)
    return () => window.removeEventListener('hashchange', apply)
  }, [])

  const peeked = useMemo(
    () =>
      ui.peekId
        ? (db.trades.find((t) => t.id === ui.peekId) ?? null)
        : null,
    [ui.peekId, db.trades],
  )

  // §4.1 The status bar shows the sample size of the *current view*.
  const sampleSize =
    ui.route.surface === 'blotter' || ui.route.surface === 'stats'
      ? trades.length
      : ui.route.surface === 'trade'
        ? 1
        : trades.length

  const inspector = useMemo(() => {
    if (ui.route.surface === 'vault' && ui.cursorId) {
      return <ArtifactInspector id={ui.cursorId} />
    }
    const id = ui.cursorId ?? ui.route.objectId
    const trade = db.trades.find((t) => t.id === id)
    return trade ? <TradeInspector trade={trade} /> : null
  }, [ui.cursorId, ui.route.objectId, ui.route.surface, db.trades])

  if (!store.ready) {
    return (
      <div className="boot">
        <ProgressLine active />
      </div>
    )
  }

  return (
    <>
      <Shell
        sampleSize={sampleSize}
        inspector={inspector}
        onPalette={() => {
          const cur = getUI()
          if (cur.overlay === 'palette') closeOverlay()
          else navigate({}, { replace: true })
        }}
        split={ui.split ? <SurfaceFor route={ui.split} /> : undefined}
      >
        <SurfaceFor route={ui.route} />
      </Shell>

      {/* ── Overlays — §6.5 ─────────────────────────────────────────── */}
      {ui.overlay === 'palette' && <CommandPalette commands={commands} />}
      {ui.overlay === 'capture' && <QuickCapture />}
      {ui.overlay === 'shortcuts' && (
        <ShortcutSheet commands={commands} onClose={closeOverlay} />
      )}
      {ui.drawer?.kind === 'screenshot' && (
        <Drawer title="Attach screenshot">
          <p className="faint" style={{ fontSize: 'var(--t-12)', lineHeight: 1.5 }}>
            In the workstation, <code>⌘⇧4</code> region-captures the screen and
            drops the image straight into the stream at the current timestamp.
            In the browser, add the file from the Vault — it lands in the same
            place and auto-associates with an open trade.
          </p>
        </Drawer>
      )}

      {/* §6.5 Peek — space-triggered, dismisses on any nav. */}
      {peeked && (
        <Peek>
          <TradeInspector trade={peeked} />
        </Peek>
      )}

      <Toasts />
    </>
  )
}

export function App() {
  // The source shipped a client-side sign-in gate here. It is deleted, not
  // ported: it compared credentials in the browser, printed them on screen, and
  // protected nothing. paper-trader already gates every /api/* call behind
  // Bearer PT_API_TOKEN, which is real.
  useEffect(() => {
    void boot().then(() => {
      // A device with no journal lands on the Guide rather than on a Cockpit
      // whose every element is unexplained. This is a landing choice made once
      // — not a tour: the Guide is the same permanent surface either way, and
      // nothing about it is dismissed or hidden afterwards.
      if (wasFirstRun()) navigate({ surface: 'guide' }, { replace: true })
    })
  }, [])

  return <Workspace />
}
