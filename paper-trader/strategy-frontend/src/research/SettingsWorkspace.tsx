import { SignalParameterSettings } from './SignalParameterSettings'
import type { PublishedGraph } from '../shell/contracts'
import { AccountRiskSettings } from './AccountRiskSettings'
import type { StrategyApi } from '../shell/api'
import { ResearchSettings } from './ResearchSettings'
import './settings-workspace.css'

export function SettingsWorkspace({ api, strategy, onEditSignals, onBacktest, onPublished, currentVersion }: {
  api: StrategyApi; strategy?: { projectId: string; graphId: string }
  onEditSignals?: () => void; onBacktest?: () => void
  onPublished?: (version: PublishedGraph) => void; currentVersion?: number | null
}) {
  return <section className="settings-workspace" aria-labelledby="settings-title">
    <header><h1 id="settings-title">{strategy ? 'Strategy settings' : 'Settings'}</h1>
      <p>{strategy ? 'Review research assumptions for this strategy. Clear an override to inherit your workspace value.' : 'Set workspace defaults for new research runs. Each strategy can keep its own overrides.'}</p></header>
    {strategy && <SignalParameterSettings key={strategy.graphId} api={api} projectId={strategy.projectId} graphId={strategy.graphId} currentVersion={currentVersion} onPublished={onPublished} onOpenBuilder={onEditSignals} />}
    <section><h2>{strategy ? 'Research assumptions' : 'Research defaults'}</h2><ResearchSettings key={strategy?.graphId ?? 'workspace'} api={api} strategy={strategy} currentVersion={currentVersion} /></section>
    {!strategy && <AccountRiskSettings api={api} />}
    <section><h2>Simulation timing</h2><p>Signals use completed bars and fill at the next bar open with the run’s recorded slippage and charges. V4 risk policies require compatible V4 strategy outputs.</p>
      <p>Saved and queued runs retain their original settings. Changing these defaults does not change an existing result.</p>
      {onBacktest && <button onClick={onBacktest}>Review settings and backtest</button>}</section>
  </section>
}
