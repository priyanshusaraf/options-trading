import { TraderSelect } from '../components/TraderSelect'
import { OptimizationSettingsFields, optimizationInputProblem } from './OptimizationSettingsFields'
import { disabledOptimization } from '../shell/contracts'
import { useEffect, useRef, useState } from 'react'
import { errorMessage, type StrategyApi } from '../shell/api'
import type { ResearchSettingsRevision, ResearchValues } from '../shell/contracts'

type Props = { api: StrategyApi; strategy?: { projectId: string; graphId: string }; currentVersion?: number | null }
type Field = Exclude<keyof ResearchValues, 'risk_policy' | 'optimization'>
const fields: readonly { key: Field; label: string; min: number; max: number; step: string; scale?: number }[] = [
  { key: 'research_capital', label: 'Research capital (INR)', min: .01, max: 1000000000, step: 'any' },
  { key: 'min_trades', label: 'Minimum out-of-sample trades', min: 1, max: 100000, step: '1' },
  { key: 'n_folds', label: 'Walk-forward folds', min: 2, max: 32, step: '1' },
  { key: 'min_positive_fold_frac', label: 'Minimum profitable folds (%)', min: 0, max: 100, step: 'any', scale: 100 },
  { key: 'stop_loss_pct', label: 'Stop loss (%)', min: 0, max: 99.999999, step: 'any', scale: 100 },
  { key: 'take_profit_pct', label: 'Take profit (%)', min: 0, max: 99.999999, step: 'any', scale: 100 },
  { key: 'seed', label: 'Reproducibility seed', min: 0, max: 2147483647, step: '1' },
]
function supportsBands(revision: ResearchSettingsRevision | null) {
  return ['research-settings-revision/2', 'research-settings-revision/3'].includes(revision?.schema ?? '') || Boolean(revision?.supportedValuesSchema)
}
function settingsRequest(previous: { body: string; id: string } | null, body: { expected_revision: number; values: Partial<ResearchValues> }, enabled: boolean) {
  const identity = JSON.stringify({ ...body, enabled })
  return previous?.body === identity ? previous : { body: identity, id: crypto.randomUUID() }
}

function RiskField({ strategy, enabled, disabled, values, displayed, change, inherit }: {
  strategy: boolean; enabled: boolean; disabled: boolean; values: Partial<ResearchValues>; displayed: Partial<ResearchValues>
  change: (key: keyof ResearchValues, value: string) => void; inherit: (key: keyof ResearchValues) => void
}) {
  return <label>Risk policy<TraderSelect label="Risk policy" value={displayed.risk_policy ?? 'none'} onValueChange={(value) => change('risk_policy', value)} disabled={disabled} options={[{ value: 'none', label: 'Signal exits' }, { value: 'pine-v4-ratchet/1', label: 'V4 ratchet stops' }, { value: 'pine-v4-reversal/1', label: 'V4 stops and reversals · 1 unit' }]} /><small>{strategy && enabled && Object.hasOwn(values, "risk_policy") ? "Strategy override" : "Workspace default"}</small>{strategy && Object.hasOwn(values, 'risk_policy') && <button type="button" onClick={() => inherit('risk_policy')}>Use workspace value</button>}</label>
}

function editableValues(document: ResearchSettingsRevision) {
  if (!document.supportedValuesSchema) return document.values
  return { stop_loss_pct: 0, take_profit_pct: 0, ...(document.supportedValuesSchema === 'research-values/3' ? { optimization: disabledOptimization() } : {}), ...document.values }
}
function inheritedValues(result: Awaited<ReturnType<StrategyApi['strategyResearchSettings']>> | ResearchSettingsRevision) {
  if (!('workspace' in result)) return {}
  return { ...(Object.hasOwn(result.values ?? {}, 'stop_loss_pct') ? { stop_loss_pct: 0, take_profit_pct: 0 } : {}), ...(Object.hasOwn(result.values ?? {}, 'optimization') ? { optimization: disabledOptimization() } : {}), ...result.workspace.values }
}
function supportsSearch(revision: ResearchSettingsRevision | null, inherited: Partial<ResearchValues>) {
  return revision?.schema === 'research-settings-revision/3' || revision?.supportedValuesSchema === 'research-values/3' || Object.hasOwn(inherited, 'optimization')
}
function settingsProvenance(strategy: boolean, revision: ResearchSettingsRevision | null) {
  const number = revision?.revision ?? '…'
  return strategy ? `Strategy settings revision ${number}. Fields without an override use workspace defaults.` : `Workspace defaults revision ${number}. These defaults apply to new runs.`
}
export function ResearchSettings({ api, strategy, currentVersion }: Props) {
  const [revision, setRevision] = useState<ResearchSettingsRevision | null>(null)
  const [inherited, setInherited] = useState<Partial<ResearchValues>>({})
  const [values, setValues] = useState<Partial<ResearchValues>>({})
  const [enabled, setEnabled] = useState(false)
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState('')
  const [attempt, setAttempt] = useState(0)
  const request = useRef<AbortController | null>(null)
  const retry = useRef<{ body: string; id: string } | null>(null)
  const projectId = strategy?.projectId, graphId = strategy?.graphId
  useEffect(() => {
    const controller = new AbortController(); request.current = controller
    setPending(true)
    const read = projectId && graphId ? api.strategyResearchSettings(projectId, graphId, controller.signal) : api.workspaceResearchSettings(controller.signal)
    void read.then((result) => {
      if (controller.signal.aborted) return
      const document = 'workspace' in result ? result.strategy : result
      setRevision(document); setValues(editableValues(document)); setEnabled(document.enabled && (!graphId || document.revision > 0))
      setInherited(inheritedValues(result))
      setMessage('')
    }).catch((error) => { if (!controller.signal.aborted) setMessage(errorMessage(error)) })
      .finally(() => { if (!controller.signal.aborted) setPending(false) })
    return () => controller.abort()
  }, [api, projectId, graphId, attempt])
  useEffect(() => () => request.current?.abort(), [])
  const busy = pending || !revision
  const controlsDisabled = busy || Boolean(strategy && !enabled)
  const displayed = strategy && !enabled ? inherited : { ...inherited, ...values }
  const change = (key: keyof ResearchValues, value: number | string) => setValues((current) => ({ ...current, [key]: value }))
  const inherit = (key: keyof ResearchValues) => setValues((current) => Object.fromEntries(Object.entries(current).filter(([name]) => name !== key)))
  async function save(event: React.FormEvent) {
    event.preventDefault()
    if (!revision || pending) return
    const optimizationError = values.optimization ? optimizationInputProblem(values.optimization) : null
    if (optimizationError) { setMessage(optimizationError); return }
    const body = { expected_revision: revision.revision, values }
    retry.current = settingsRequest(retry.current, body, enabled)
    request.current?.abort(); const controller = new AbortController(); request.current = controller
    setPending(true); setMessage('')
    try {
      const saved = await api.saveResearchSettings({ ...body, request_id: retry.current.id }, controller.signal, strategy ? { ...strategy, enabled } : undefined)
      if (controller.signal.aborted) return
      setRevision(saved); retry.current = null
      setMessage('Settings saved. Queued and completed runs keep their original settings.')
    } catch (error) { if (!controller.signal.aborted) setMessage(errorMessage(error)) }
    finally { if (!controller.signal.aborted) setPending(false) }
  }
  return <form className="research-settings-form" onSubmit={(event) => void save(event)}>
    {strategy && <label className="research-settings-enable"><input type="checkbox" checked={enabled} disabled={busy} onChange={(event) => setEnabled(event.target.checked)} />Use strategy overrides</label>}
    <p className="settings-provenance">{settingsProvenance(Boolean(strategy), revision)}</p>
    <fieldset disabled={controlsDisabled}>
      {fields.filter((field) => !["stop_loss_pct", "take_profit_pct"].includes(field.key) || supportsBands(revision) || Object.hasOwn(inherited, field.key)).map((field) => { const current = displayed[field.key] ?? (["stop_loss_pct", "take_profit_pct"].includes(field.key) ? 0 : undefined); return <label key={field.key}>{field.label}<input aria-label={field.label} type="number" required min={field.min} max={field.max} step={field.step} value={typeof current === 'number' ? current * (field.scale ?? 1) : ''} onChange={(event) => change(field.key, event.target.value === '' ? '' : Number(event.target.value) / (field.scale ?? 1))} /><small>{strategy && enabled && Object.hasOwn(values, field.key) ? "Strategy override" : "Workspace default"}</small>{strategy && Object.hasOwn(values, field.key) && <button type="button" onClick={() => inherit(field.key)}>Use workspace value</button>}</label> })}
      <RiskField strategy={Boolean(strategy)} enabled={enabled} disabled={controlsDisabled} values={values} displayed={displayed} change={change} inherit={inherit} />
    </fieldset>
    {supportsSearch(revision, inherited) && <>
      <OptimizationSettingsFields api={api} strategy={strategy} currentVersion={currentVersion} value={displayed.optimization ?? disabledOptimization()} disabled={controlsDisabled}
        onChange={(update) => setValues((current) => ({ ...current, optimization: update(current.optimization ?? inherited.optimization ?? disabledOptimization()) }))} />
      {strategy && Object.hasOwn(values, 'optimization') && <button type="button" disabled={pending || !enabled} onClick={() => inherit('optimization')}>Use workspace search setting</button>}
    </>}
    {(supportsBands(revision) || Object.hasOwn(inherited, "stop_loss_pct")) && <p>Stop loss and take profit: 0 disables the percentage band. A completed close confirms the threshold from the actual entry price; exit fills at the next open with slippage. Gaps can exceed the threshold. This is not an intrabar stop order.</p>}
    <div className="research-settings-actions"><button type="submit" disabled={busy}>{pending ? 'Working…' : 'Save settings'}</button><button type="button" disabled={pending} onClick={() => setAttempt((value) => value + 1)}>Reload settings</button></div>
    {message && <p role="status">{message}</p>}
  </form>
}
