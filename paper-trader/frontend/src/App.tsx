import { useEffect, useState } from 'react'
import { getReleaseProfile, getStatus } from './lib/api'
import type { ReleaseProfileManifest } from './lib/types'
import { LiveProvider } from './state/LiveContext'
import TopBar, { V0TopBar } from './components/TopBar'
import MobileTopBar, { V0MobileTopBar } from './components/MobileTopBar'
import { V0ReleaseBanner } from './components/SessionBanner'
import Watchlist from './views/WatchlistView'
import ActivePositionsView from './views/ActivePositionsView'
import EngineView from './views/EngineView'
import LedgerView from './views/LedgerView'
import OptionsCalcView from './views/OptionsCalcView'
import BacktestsView from './views/BacktestsView'
import PortfolioView from './views/PortfolioView'
import DashboardView from './views/DashboardView'
import TradesView from './views/TradesView'
import CalendarView from './views/CalendarView'
import GraphView from './views/GraphView'
import SettingsView from './views/SettingsView'

const TABS: [string, string][] = [
  ['watchlist', 'Watchlist'],
  ['positions', 'Active Positions'],
  ['journal', 'Journal'],
  ['engine', 'Engine / Logs'],
  ['options', 'Options Calc'],
  ['backtests', 'Backtests'],
  ['portfolio', 'Portfolio'],
  ['trades', 'Trade Log'],
  ['calendar', 'Calendar'],
  ['dashboard', 'Dashboard'],
  ['graph', 'Strategy Graph'],
  ['settings', 'Settings'],
]

const V0_SURFACES = [
  ['strategy_graph', 'graph', 'Strategy Graph'],
  ['backtesting', 'backtests', 'Backtests'],
] as const

export function v0TabsFor(manifest: ReleaseProfileManifest): readonly (readonly [string, string])[] {
  return V0_SURFACES
    .filter(([capability]) => manifest.capabilities[capability]?.ui_navigation === true)
    .map(([, id, label]) => [id, label] as const)
}

// Desktop ≥768px keeps the original layout; below that we render the phone header.
function useIsDesktop() {
  const [isDesktop, setIsDesktop] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(min-width: 768px)').matches,
  )
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 768px)')
    const onChange = () => setIsDesktop(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return isDesktop
}

function Shell() {
  const [tab, setTab] = useState('watchlist')
  const isDesktop = useIsDesktop()
  // The research plane (Portfolio tab) is frozen behind PT_RESEARCH_ENABLED on the
  // backend; /api/status reports the flag so the tab appears only when enabled.
  const [researchEnabled, setResearchEnabled] = useState(false)
  useEffect(() => {
    getStatus().then((s) => setResearchEnabled(!!s.research_enabled)).catch(() => {})
  }, [])
  const tabs = researchEnabled ? TABS : TABS.filter(([key]) => key !== 'portfolio')
  return (
    <div className="min-h-full flex flex-col">
      {isDesktop
        ? <TopBar tab={tab} setTab={setTab} tabs={tabs} />
        : <MobileTopBar tab={tab} setTab={setTab} tabs={tabs} />}
      <main className="flex-1 p-3">
        {tab === 'watchlist' && <Watchlist />}
        {tab === 'positions' && <ActivePositionsView />}
        {tab === 'engine' && <EngineView />}
        {tab === 'options' && <OptionsCalcView />}
        {tab === 'backtests' && (isDesktop
          ? <BacktestsView />
          : <div className="card p-4 text-sm text-muted">Backtests is desktop-only — open this on your Mac.</div>)}
        {tab === 'portfolio' && researchEnabled && <PortfolioView />}
        {tab === 'trades' && <TradesView />}
        {tab === 'calendar' && <CalendarView />}
        {tab === 'dashboard' && <DashboardView />}
        {tab === 'graph' && <GraphView researchEnabled={researchEnabled} />}
        {tab === 'settings' && <SettingsView />}
      </main>
      {/* The journal renders OUTSIDE <main>: it is a full-bleed fixed sub-app
          with its own shell and its own internal scroll panes, so flowing it
          inside the padded main column would fight its layout. Mounting it only
          while its tab is active is also what keeps its global keydown listener
          from swallowing bare letters on every other view. */}
      {tab === 'journal' && <LedgerView onExit={() => setTab('watchlist')} />}
    </div>
  )
}

export function V0Shell({ manifest }: { manifest: ReleaseProfileManifest }) {
  const tabs = v0TabsFor(manifest)
  const [tab, setTab] = useState(() => tabs[0]?.[0] ?? 'unavailable')
  const isDesktop = useIsDesktop()
  return (
    <div className="min-h-full w-full min-w-0 max-w-full overflow-x-hidden flex flex-col">
      {isDesktop
        ? <V0TopBar tab={tab} setTab={setTab} tabs={tabs} />
        : <V0MobileTopBar tab={tab} setTab={setTab} tabs={tabs} />}
      <V0ReleaseBanner />
      <main className="flex-1 w-full min-w-0 max-w-full overflow-x-auto p-3">
        {tab === 'graph' && <GraphView researchEnabled={manifest.research_enabled} />}
        {tab === 'backtests' && <BacktestsView />}
        {tab === 'unavailable' && (
          <div className="card p-4 text-sm text-muted">
            No research surface is enabled by the server release profile.
          </div>
        )}
      </main>
    </div>
  )
}

export function AppForReleaseState({
  manifest,
  profileUnavailable,
}: {
  manifest: ReleaseProfileManifest | null
  profileUnavailable: boolean
}) {
  if (profileUnavailable) {
    return (
      <main className="min-h-full grid place-items-center p-4">
        <div className="card max-w-lg p-4 text-sm text-amber-300" role="alert">
          The server release profile could not be verified. Product surfaces remain unavailable.
        </div>
      </main>
    )
  }
  if (manifest === null) {
    return <main className="min-h-full grid place-items-center text-sm text-muted">Loading release profile…</main>
  }
  if (manifest.release_profile === 'v0_research_signal') {
    return <V0Shell manifest={manifest} />
  }
  return <LiveProvider><Shell /></LiveProvider>
}

export default function App() {
  const [manifest, setManifest] = useState<ReleaseProfileManifest | null>(null)
  const [profileUnavailable, setProfileUnavailable] = useState(false)
  useEffect(() => {
    getReleaseProfile().then(setManifest).catch(() => setProfileUnavailable(true))
  }, [])
  return <AppForReleaseState manifest={manifest} profileUnavailable={profileUnavailable} />
}
