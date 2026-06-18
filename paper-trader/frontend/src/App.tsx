import { useState } from 'react'
import { LiveProvider } from './state/LiveContext'
import TopBar from './components/TopBar'
import Monitor from './views/Monitor'
import EngineView from './views/EngineView'
import OptionsCalcView from './views/OptionsCalcView'
import DashboardView from './views/DashboardView'

const TABS: [string, string][] = [
  ['monitor', 'Monitor'],
  ['engine', 'Engine / Logs'],
  ['options', 'Options Calc'],
  ['dashboard', 'Dashboard'],
]

function Shell() {
  const [tab, setTab] = useState('monitor')
  return (
    <div className="min-h-full flex flex-col">
      <TopBar tab={tab} setTab={setTab} tabs={TABS} />
      <main className="flex-1 p-3">
        {tab === 'monitor' && <Monitor />}
        {tab === 'engine' && <EngineView />}
        {tab === 'options' && <OptionsCalcView />}
        {tab === 'dashboard' && <DashboardView />}
      </main>
    </div>
  )
}

export default function App() {
  return <LiveProvider><Shell /></LiveProvider>
}
