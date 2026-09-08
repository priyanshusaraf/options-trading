import { TraderSelect } from '../components/TraderSelect'
import { useEffect, useState } from 'react'
import { errorMessage, type StrategyApi } from '../shell/api'
import { compareOptimizationAxes, disabledOptimization, parseOptimizationSettings, v2Document,
  type CanonicalOptimizationSettings, type OptimizationAxis } from '../shell/contracts'
import { record, SaveVerificationError } from './builderParameterContracts'
import { parseSavedResearchPolicy } from './preparedResearchContracts'
import { signalParameters, type SignalParameter } from './signalParameterContracts'

type ChoiceState = { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; rows: readonly SignalParameter[]; version: number | null }
function compareDecimals(left: string, right: string) {
  const places = (value: string) => value.includes('.') ? value.length - value.indexOf('.') - 1 : 0
  const scale = Math.max(places(left), places(right))
  const a = BigInt(left.replace('.', '')) * 10n ** BigInt(scale - places(left))
  const b = BigInt(right.replace('.', '')) * 10n ** BigInt(scale - places(right))
  return a < b ? -1 : a > b ? 1 : 0
}
export function optimizationInputProblem(input: CanonicalOptimizationSettings): string | null {
  try { parseOptimizationSettings(input) } catch { return 'Choose 1–4 parameters and use plain decimals such as 1 or 0.5, without trailing zeros or exponents.' }
  if (input.axes.some((axis) => compareDecimals(axis.step, '0') <= 0)) return 'Each search step must be greater than zero.'
  if (input.axes.some((axis) => compareDecimals(axis.minimum, axis.maximum) > 0)) return 'Each minimum must be no greater than its maximum.'
  return null
}
async function loadChoices(api: StrategyApi, projectId: string, graphId: string, currentVersion: number | null | undefined, signal: AbortSignal): Promise<ChoiceState> {
  const version = currentVersion === undefined ? (await api.v2Draft(projectId, graphId, signal)).current_version : currentVersion
  if (version === null) return { kind: 'ready', rows: [], version }
  const [saved, catalogue] = await Promise.all([api.v2Version(projectId, graphId, version, signal), api.catalogue(signal)])
  parseSavedResearchPolicy(saved, graphId, version)
  const document = v2Document(record(saved).document, graphId)
  if (document.strategy_version !== version) throw new SaveVerificationError('The saved strategy version could not be verified.')
  const rows = signalParameters({ document }, catalogue).filter((row) => row.explicit && ['int', 'float'].includes(row.definition.type)
    && row.definition.enum === null && typeof row.value === 'number' && Number.isFinite(row.value))
  return { kind: 'ready', rows, version }
}
function axisIdentity(axis: Pick<OptimizationAxis, 'node_id' | 'parameter_id'>) { return JSON.stringify([axis.node_id, axis.parameter_id]) }

export function OptimizationSettingsFields({ api, strategy, currentVersion, value, disabled, onChange }: {
  api: StrategyApi; strategy?: { projectId: string; graphId: string }; currentVersion?: number | null
  value: CanonicalOptimizationSettings; disabled: boolean
  onChange: (update: (previous: CanonicalOptimizationSettings) => CanonicalOptimizationSettings) => void
}) {
  const [result, setResult] = useState<{ api: StrategyApi; scope: string; state: ChoiceState } | null>(null)
  const [attempt, setAttempt] = useState(0)
  const scope = JSON.stringify([strategy?.projectId, strategy?.graphId, currentVersion])
  const state: ChoiceState = result?.api === api && result.scope === scope ? result.state : { kind: 'loading' }
  useEffect(() => {
    if (!strategy) return
    const controller = new AbortController()
    setResult({ api, scope, state: { kind: 'loading' } })
    void loadChoices(api, strategy.projectId, strategy.graphId, currentVersion, controller.signal)
      .then((next) => { if (!controller.signal.aborted) setResult({ api, scope, state: next }) })
      .catch((error) => { if (!controller.signal.aborted) setResult({ api, scope, state: { kind: 'error', message: error instanceof SaveVerificationError ? error.message : errorMessage(error) } }) })
    return () => controller.abort()
  }, [api, strategy?.projectId, strategy?.graphId, currentVersion, attempt, scope])
  if (!strategy) return <div className="optimization-settings"><h3>Development search</h3><p>Search is off in workspace defaults. Configure graph-specific numeric parameters in each strategy’s Settings.</p></div>
  const rows = state.kind === 'ready' ? state.rows : []
  const available = rows.filter((row) => !value.axes.some((axis) => axisIdentity(axis) === row.key))
  const problem = optimizationInputProblem(value)
  function add(key: string) {
    const row = rows.find((item) => item.key === key)
    if (!row) return
    onChange((current) => current.axes.length >= 4 || current.axes.some((axis) => axisIdentity(axis) === key) ? current
      : { ...current, axes: [...current.axes, { node_id: row.nodeId, parameter_id: row.name, step: '', minimum: '', maximum: '' }].sort(compareOptimizationAxes) })
  }
  function change(axis: OptimizationAxis, field: 'step' | 'minimum' | 'maximum', raw: string) {
    onChange((current) => ({ ...current, axes: current.axes.map((item) => axisIdentity(item) === axisIdentity(axis) ? { ...item, [field]: raw } : item) }))
  }
  return <div className="optimization-settings"><h3>Development search</h3>
    <p>Test the saved baseline and one step either side of each parameter, within your bounds: up to 81 combinations across four parameters. Selection uses development data; the selected candidate is then evaluated on the later locked window.</p>
    <label><input type="checkbox" checked={value.enabled} disabled={disabled || (!value.enabled && rows.length === 0)} onChange={(event) => { const enabled = event.target.checked; onChange(() => enabled ? { ...disabledOptimization(), enabled: true } : disabledOptimization()) }} />Enable bounded development search</label>
    <p>Turning this off removes its search axes. It does not change signal values or publish a selected candidate.</p>
    {state.kind === 'loading' && <p role="status">Loading saved numeric parameters…</p>}
    {state.kind === 'error' && <p role="alert">{state.message}</p>}
    {state.kind === 'ready' && rows.length === 0 && <p>Save a version with explicitly set, non-enum numeric parameters first.</p>}
    {value.enabled && <>
      <label>Add optimization parameter<TraderSelect label="Add optimization parameter" value="" disabled={disabled || available.length === 0 || value.axes.length >= 4} onValueChange={add} options={[{ value: '', label: 'Choose a saved parameter' }, ...available.map((row) => ({ value: row.key, label: `${row.nodeName}: ${row.label} · baseline ${String(row.value)}` }))]} /></label>
      {value.axes.map((axis, index) => {
        const row = rows.find((item) => item.key === axisIdentity(axis))
        const label = row ? `${row.nodeName}: ${row.label}` : `Unavailable saved parameter ${index + 1}`
        return <div className="optimization-axis" key={axisIdentity(axis)}><strong>{label}</strong>
          {row && <p>Baseline in version {state.kind === 'ready' ? state.version : ''}: {String(row.value)}</p>}
          {!row && state.kind === 'ready' && <p role="alert">Remove this axis or save a version that contains its explicit numeric parameter.</p>}
          {(['step', 'minimum', 'maximum'] as const).map((field) => <label key={field}>{field === 'step' ? 'Step' : field === 'minimum' ? 'Minimum' : 'Maximum'}<input aria-label={`${label} ${field}`} inputMode="decimal" maxLength={128} required value={axis[field]} disabled={disabled} onChange={(event) => change(axis, field, event.target.value)} /></label>)}
          <button type="button" disabled={disabled} onClick={() => onChange((current) => ({ ...current, axes: current.axes.filter((item) => axisIdentity(item) !== axisIdentity(axis)) }))}>Remove search parameter {index + 1}</button>
        </div>
      })}
      <p>The saved baseline, integer types and component bounds are checked before queueing. The worker checks the replay budget before search starts.</p>
      {problem && <p role="alert">{problem}</p>}
    </>}
    <button type="button" disabled={disabled || state.kind === 'loading'} onClick={() => setAttempt((current) => current + 1)}>Reload saved search parameters</button>
  </div>
}
