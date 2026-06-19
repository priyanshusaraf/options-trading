import { useState } from 'react'
import { LiveProvider } from './state/LiveContext'
import TopBar from './components/TopBar'
import HomeView from './views/HomeView'
import Monitor from './views/Monitor'
import ActivePositionsView from './views/ActivePositionsView'
import EngineView from './views/EngineView'
import OptionsCalcView from './views/OptionsCalcView'
import BacktestsView from './views/BacktestsView'
import DashboardView from './views/DashboardView'

const TABS: [string, string][] = [
  ['home', 'Home'],
  ['positions', 'Active Positions'],
  ['monitor', 'Monitor'],
  ['engine', 'Engine / Logs'],
  ['options', 'Options Calc'],
  ['backtests', 'Backtests'],
  ['dashboard', 'Dashboard'],
]

function Shell() {
  const [tab, setTab] = useState('home')
  return (
    <div className="min-h-full flex flex-col">
      <TopBar tab={tab} setTab={setTab} tabs={TABS} />
      <main className="flex-1 p-3">
        {tab === 'home' && <HomeView />}
        {tab === 'positions' && <ActivePositionsView />}
        {tab === 'monitor' && <Monitor />}
        {tab === 'engine' && <EngineView />}
        {tab === 'options' && <OptionsCalcView />}
        {tab === 'backtests' && <BacktestsView />}
        {tab === 'dashboard' && <DashboardView />}
      </main>
    </div>
  )
}

export default function App() {
  return <LiveProvider><Shell /></LiveProvider>
}
