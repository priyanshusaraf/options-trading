import { useState } from 'react'
import { LiveProvider } from './state/LiveContext'
import TopBar from './components/TopBar'
import Watchlist from './views/WatchlistView'
import ActivePositionsView from './views/ActivePositionsView'
import EngineView from './views/EngineView'
import OptionsCalcView from './views/OptionsCalcView'
import BacktestsView from './views/BacktestsView'
import DashboardView from './views/DashboardView'
import TradesView from './views/TradesView'
import SettingsView from './views/SettingsView'

const TABS: [string, string][] = [
  ['watchlist', 'Watchlist'],
  ['positions', 'Active Positions'],
  ['engine', 'Engine / Logs'],
  ['options', 'Options Calc'],
  ['backtests', 'Backtests'],
  ['trades', 'Trade Log'],
  ['dashboard', 'Dashboard'],
  ['settings', 'Settings'],
]

function Shell() {
  const [tab, setTab] = useState('watchlist')
  return (
    <div className="min-h-full flex flex-col">
      <TopBar tab={tab} setTab={setTab} tabs={TABS} />
      <main className="flex-1 p-3">
        {tab === 'watchlist' && <Watchlist />}
        {tab === 'positions' && <ActivePositionsView />}
        {tab === 'engine' && <EngineView />}
        {tab === 'options' && <OptionsCalcView />}
        {tab === 'backtests' && <BacktestsView />}
        {tab === 'trades' && <TradesView />}
        {tab === 'dashboard' && <DashboardView />}
        {tab === 'settings' && <SettingsView />}
      </main>
    </div>
  )
}

export default function App() {
  return <LiveProvider><Shell /></LiveProvider>
}
