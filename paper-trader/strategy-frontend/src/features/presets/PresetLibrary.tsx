import { useEffect, useState } from 'react'
import { ArrowUpRight } from 'lucide-react'
import { errorMessage, type StrategyApi } from '../../shell/api'
import { CreateDraft } from './CreateDraft'
import { StrategyDialog } from './NewStrategy'
import { StrategyComponents } from './StrategyComponents'
import type { StrategyPreset } from './presetContracts'

function PresetCard({ preset, onUse }: { preset: StrategyPreset; onUse: () => void }) {
  return <article className="slate-preset-card">
    <h2>{preset.name}</h2>
    <details><summary>How it works</summary><p>{preset.description}</p></details>
    <details><summary>Default settings</summary><dl>{Object.entries(preset.parameters).map(([name, value]) => <div key={name}><dt>{name.replaceAll('_', ' ')}</dt><dd>{String(value)}</dd></div>)}</dl></details>
    <p className="slate-preset-inclusion">Included with your plan</p>
    <button className="slate-primary-action" disabled={!preset.available} onClick={onUse}>{preset.available ? 'Use this preset' : 'Not available'}<ArrowUpRight size={16} aria-hidden="true" /></button>
  </article>
}

export function PresetLibrary({ api, projectId, onCreated }: {
  api: StrategyApi; projectId?: string; onCreated: (projectId: string, identifier: string) => void
}) {
  const [section, setSection] = useState<'strategies' | 'components'>('strategies')
  const [presets, setPresets] = useState<readonly StrategyPreset[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [selected, setSelected] = useState<StrategyPreset | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    void api.presets(controller.signal).then((rows) => {
      if (!controller.signal.aborted) { setPresets(rows); setLoading(false) }
    }).catch((caught: unknown) => {
      if (!controller.signal.aborted) { setError(errorMessage(caught)); setLoading(false) }
    })
    return () => controller.abort()
  }, [api, attempt])
  return <>
    <div className="slate-heading"><h1>Presets</h1></div>
    <nav className="slate-preset-sections" aria-label="Preset sections">
      <button aria-pressed={section === 'strategies'} onClick={() => setSection('strategies')}>Strategies</button>
      <button aria-pressed={section === 'components'} onClick={() => setSection('components')}>Strategy components</button>
    </nav>
    {section === 'components' ? <StrategyComponents /> : <section aria-label="Strategies">
    <p className="slate-preset-note">Choose a starting strategy, make it yours, and backtest it with your data.</p>
    {loading ? <p role="status">Loading presets…</p> : error ? <section className="slate-state"><p role="alert">{error}</p><button onClick={() => { setError(''); setLoading(true); setAttempt((value) => value + 1) }}>Try again</button></section>
      : presets.length ? <div className="slate-preset-grid">{presets.map((preset) => <PresetCard key={preset.preset_id} preset={preset} onUse={() => setSelected(preset)} />)}</div>
        : <section className="slate-state"><h2>No presets yet</h2><p>You can start with an empty strategy in Strategies.</p></section>}
    </section>}
    {selected && <StrategyDialog title="Make this strategy yours" onClose={() => setSelected(null)}>
      <CreateDraft key={`${projectId ?? ''}:${selected.preset_id}`} api={api} projectId={projectId} preset={selected}
        onCreated={(project, identifier) => { setSelected(null); onCreated(project, identifier) }} onCancel={() => setSelected(null)} />
    </StrategyDialog>}
  </>
}
