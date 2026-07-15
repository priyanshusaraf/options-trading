import { useEffect, useState } from 'react'
import { getStatus } from './lib/api'
import { LiveProvider } from './state/LiveContext'
import TopBar from './components/TopBar'
import MobileTopBar from './components/MobileTopBar'
import Watchlist from './views/WatchlistView'
import ActivePositionsView from './views/ActivePositionsView'
import EngineView from './views/EngineView'
import OptionsCalcView from './views/OptionsCalcView'
import BacktestsView from './views/BacktestsView'
import PortfolioView from './views/PortfolioView'
import DashboardView from './views/DashboardView'
import TradesView from './views/TradesView'
import CalendarView from './views/CalendarView'
import SettingsView from './views/SettingsView'

const TABS: [string, string][] = [
  ['watchlist', 'Watchlist'],
  ['positions', 'Active Positions'],
  ['engine', 'Engine / Logs'],
  ['options', 'Options Calc'],
  ['backtests', 'Backtests'],
  ['portfolio', 'Portfolio'],
  ['trades', 'Trade Log'],
  ['calendar', 'Calendar'],
  ['dashboard', 'Dashboard'],
  ['settings', 'Settings'],
]

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
        {tab === 'settings' && <SettingsView />}
      </main>
    </div>
  )
}

export default function App() {
  return <LiveProvider><Shell /></LiveProvider>
}
