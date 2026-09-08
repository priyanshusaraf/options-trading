import { useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, errorMessage, type StrategyApi } from '../shell/api'
import { TraderSelect } from '../components/TraderSelect'
import { sameJson, type PublishedGraph, type V2Draft, type VerifiedCatalogue } from '../shell/contracts'
import { publishedAddress, record, requirePublication, requirePublishedDraft, requireSemanticCommit, SaveVerificationError } from './builderParameterContracts'
import { parameterKind, parameterRaw, prepareParameterEdits, requireParameterReadback, requireParameterValidation,
  signalParameters, type ParameterCommand, type ParameterEdit, type ParameterEdits, type SignalParameter } from './signalParameterContracts'
import { proposalParameterEdits, type ParameterProposal } from './optimizationProposal'

type Props = { api: StrategyApi; projectId: string; graphId: string; currentVersion?: number | null
  onPublished?: (version: PublishedGraph) => void; onOpenBuilder?: () => void; proposal?: ParameterProposal }
type Loaded = { draft: V2Draft; catalogue: VerifiedCatalogue; rows: readonly SignalParameter[] }

function parameterError(error: unknown) {
  if (error instanceof SaveVerificationError) return error.message
  if (error instanceof ApiError && error.envelope?.code === 'STRATEGY_LIBRARY_CHANGED') return 'Components changed. Your entered values are retained. Open Build to review the component update before saving a version.'
  if (error instanceof ApiError && error.envelope?.code === 'SEMANTIC_REVISION_CONFLICT') return 'Another edit changed the strategy. Reload the latest draft and review your retained values before saving.'
  return errorMessage(error)
}
function ParameterInput({ row, edit, disabled, invalid, onChange }: { row: SignalParameter; edit?: ParameterEdit; disabled: boolean; invalid: boolean; onChange: (raw: string) => void }) {
  const kind = parameterKind(row.definition)
  const value = edit?.mode === 'clear' ? parameterRaw(row.definition.default, row.definition)
    : edit?.mode === 'set' ? edit.raw : parameterRaw(row.value, row.definition)
  const props = { id: row.key, 'aria-label': `${row.nodeName}: ${row.label}`, 'aria-invalid': invalid, 'aria-describedby': `${row.key}-help${invalid ? ` ${row.key}-error` : ''}`, required: row.definition.required, value, disabled }
  if (kind === 'enum' || kind === 'boolean') {
    const choices = kind === 'boolean' ? [false, true] : row.definition.enum as unknown[]
    return <TraderSelect id={row.key} label={props['aria-label']} describedBy={props['aria-describedby']} invalid={invalid}
      value={value} disabled={disabled} required={row.definition.required} onValueChange={onChange}
      options={choices.map((choice) => ({ value: JSON.stringify(choice), label: kind === 'boolean' ? choice ? 'Yes' : 'No' : String(choice) }))} />
  }
  if (kind === 'json') return <textarea {...props} rows={3} onChange={(event) => onChange(event.target.value)} />
  const domain = record(row.definition.domain)
  return <input {...props} type={kind === 'number' ? 'number' : 'text'} step={row.definition.type === 'int' ? '1' : 'any'}
    min={typeof domain.minimum === 'number' ? domain.minimum : undefined} max={typeof domain.maximum === 'number' ? domain.maximum : undefined}
    onChange={(event) => onChange(event.target.value)} />
}
function ParameterField({ row, edit, disabled, error, staged, onEdit, onClear }: {
  row: SignalParameter; edit?: ParameterEdit; disabled: boolean; error?: string; staged: boolean
  onEdit: (raw: string) => void; onClear: () => void
}) {
  return <div className="signal-parameter-field"><label htmlFor={row.key}>{row.label}</label>
    <ParameterInput row={row} edit={edit} disabled={disabled} invalid={Boolean(error)} onChange={onEdit} />
    <small id={`${row.key}-help`}>Saved: {parameterRaw(row.value, row.definition)} · {row.explicit ? 'Strategy value' : 'Component default'}{staged ? ' · Pending edit' : ''}</small>
    {error && <p id={`${row.key}-error`} role="alert">{error}</p>}
    {(row.explicit || edit) && <button type="button" disabled={disabled} onClick={onClear}>Use component default for {row.label}</button>}
  </div>
}

function SignalParameterSettingsBody({ api, projectId, graphId, currentVersion, onPublished, onOpenBuilder, proposal }: Props) {
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [edits, setEdits] = useState<ParameterEdits>({})
  const [pending, setPending] = useState(true), [blocked, setBlocked] = useState(false)
  const [message, setMessage] = useState(''), [attempt, setAttempt] = useState(0)
  const request = useRef<AbortController | null>(null)
  const editsRef = useRef(edits); editsRef.current = edits
  const publishCallback = useRef(onPublished); publishCallback.current = onPublished
  const observedVersion = useRef(currentVersion)
  const acknowledgedVersion = useRef<number | null>(null)
  const proposalLoaded = useRef(false)
  const prepared = useMemo(() => prepareParameterEdits(loaded?.rows ?? [], edits), [loaded, edits])
  useEffect(() => {
    const controller = new AbortController(); request.current = controller; setPending(true)
    async function load() {
      try {
        const [draft, catalogue] = await Promise.all([api.v2Draft(projectId, graphId, controller.signal), api.catalogue(controller.signal)])
        const rows = signalParameters(draft, catalogue)
        await stageProposal(draft, rows, controller.signal)
        if (Object.keys(editsRef.current).some((key) => !rows.some((row) => row.key === key))) throw new SaveVerificationError('An edited parameter was removed. Discard pending edits before reloading this strategy.')
        if (controller.signal.aborted) return
        await noticePublishedVersion(draft, controller.signal)
        if (controller.signal.aborted) return
        setLoaded({ draft, catalogue, rows }); setBlocked(false); setMessage('Latest draft loaded. Review any pending edits before saving.')
      } catch (error) { if (!controller.signal.aborted) { setBlocked(true); setMessage(parameterError(error)) } }
      finally { if (!controller.signal.aborted) { setPending(false); request.current = null } }
    }
    void load()
    return () => controller.abort()
  // Publication callbacks are kept in a ref so a parent record refresh does not discard edits.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, projectId, graphId, attempt])
  useEffect(function cancelOldContext() {
    return function cancelSave() { request.current?.abort() }
  }, [api])
  async function stageProposal(draft: V2Draft, rows: readonly SignalParameter[], signal: AbortSignal) {
    if (!proposal) return
    const saved = await api.v2Version(projectId, graphId, proposal.baseline.version, signal)
    const suggested = proposalParameterEdits(proposal, draft, saved, rows)
    if (signal.aborted || proposalLoaded.current) return
    setEdits(suggested); proposalLoaded.current = true
  }
  async function noticePublishedVersion(draft: V2Draft, signal: AbortSignal) {
    const version = draft.current_version
    if (version !== null && observedVersion.current !== undefined && version !== observedVersion.current && draft.published_revision === draft.semantic_revision) {
      const saved = await api.v2Version(projectId, graphId, version, signal)
      const address = publishedAddress(saved, graphId, version, draft.graph_address)
      if (!signal.aborted) publishCallback.current?.({ project_id: projectId, identifier: graphId, version, content_address: address })
    }
    observedVersion.current = version
  }
  function acceptDraft(draft: V2Draft, catalogue: VerifiedCatalogue) {
    setLoaded({ draft, catalogue, rows: signalParameters(draft, catalogue) })
  }
  async function applyParameters(base: V2Draft, commands: readonly ParameterCommand[], signal: AbortSignal) {
    if (!commands.length) return base
    const validation = await api.validateV2(projectId, graphId, base.semantic_revision, commands, signal)
    signal.throwIfAborted()
    requireParameterValidation(validation, base, commands)
    const receipt = await api.mutateV2(projectId, graphId, base.semantic_revision, commands, 'EDIT', null, signal)
    signal.throwIfAborted()
    requireSemanticCommit(receipt, base)
    if (!sameJson(receipt.forward_commands, commands)) throw new SaveVerificationError('The saved parameter commands do not match your edits. Reload the draft.')
    const saved = await api.v2Draft(projectId, graphId, signal)
    signal.throwIfAborted()
    requireParameterReadback(saved, { ...base, semantic_revision: receipt.result_semantic_revision, content_address: receipt.result_content_address, graph_address: receipt.result_graph_address }, commands)
    return saved
  }
  async function publishParameters(saved: V2Draft, signal: AbortSignal) {
    const receipt = await api.publishV2(projectId, graphId, saved.semantic_revision, saved.current_version, signal)
    signal.throwIfAborted()
    requirePublication(receipt, saved)
    const version = await api.v2Version(projectId, graphId, receipt.graph_version, signal)
    signal.throwIfAborted()
    const address = publishedAddress(version, graphId, receipt.graph_version, saved.graph_address)
    if (address !== receipt.content_address || !sameJson(record(version).document, saved.document)) throw new SaveVerificationError('The saved version could not be matched to your parameters. Reload to check it.')
    acknowledgedVersion.current = receipt.graph_version; observedVersion.current = receipt.graph_version
    publishCallback.current?.({ project_id: projectId, identifier: graphId, version: receipt.graph_version, content_address: receipt.content_address })
    signal.throwIfAborted()
    const current = await api.v2Draft(projectId, graphId, signal)
    signal.throwIfAborted()
    requirePublishedDraft(current, saved, receipt.graph_version)
    return { current, receipt }
  }
  async function save() {
    if (request.current || !loaded || writesBlocked) return
    const controller = new AbortController(); request.current = controller; setPending(true); setMessage('')
    let draftSaved = false; acknowledgedVersion.current = null
    try {
      const saved = await applyParameters(loaded.draft, prepared.commands, controller.signal)
      if (controller.signal.aborted) return
      acceptDraft(saved, loaded.catalogue); setEdits({}); draftSaved = true
      const { current, receipt } = await publishParameters(saved, controller.signal)
      if (controller.signal.aborted) return
      acceptDraft(current, loaded.catalogue)
      setMessage(`Saved strategy version ${receipt.graph_version}. New backtests can use these parameters; earlier results keep their original version.`)
    } catch (error) {
      if (!controller.signal.aborted) {
        failSave(error, draftSaved)
      }
    } finally { if (!controller.signal.aborted) { setPending(false); request.current = null } }
  }
  function failSave(error: unknown, draftSaved: boolean) {
    if (acknowledgedVersion.current !== null) { setBlocked(true); setMessage(`Saved strategy version ${acknowledgedVersion.current}. Reload the latest draft before editing again. ${parameterError(error)}`); return }
    setBlocked(!(error instanceof ApiError && error.kind === 'input'))
    setMessage(`${draftSaved ? 'Parameters are saved in the draft; the new version is not yet verified.' : 'Your parameter edits are retained.'} ${parameterError(error)}`)
  }
  function clear(row: SignalParameter) {
    setEdits((current) => row.explicit ? { ...current, [row.key]: { mode: 'clear' } }
      : Object.fromEntries(Object.entries(current).filter(([key]) => key !== row.key)))
  }
  const writesBlocked = pending || blocked || Object.keys(prepared.errors).length > 0
  const unpublished = loaded !== null && loaded.draft.published_revision !== loaded.draft.semantic_revision
  return <section aria-labelledby="signal-parameters-title"><h2 id="signal-parameters-title">Signal parameters</h2>
    {proposal && <p>Review the parameters suggested by run {proposal.runId}, based on version {proposal.baseline.version}. The saved values below are your baseline; nothing changes until you save.</p>}
    <p>Change the values used by this strategy’s nodes. Saving validates the draft and publishes a new version for the next backtest.</p>
    {loaded && <p>Draft based on saved version: {loaded.draft.current_version ?? 'None yet'} · {prepared.commands.length} pending parameter changes{unpublished ? ' · Draft has unpublished changes' : ''}</p>}
    {unpublished && <p>A new version includes all current draft changes. Open Build to review node and connection changes.</p>}
    {loaded?.rows.length === 0 && <p>No editable parameters in this draft. Add a parameterized node in Build.</p>}
    {loaded?.draft.document.nodes.map((node) => {
      const rows = loaded.rows.filter((row) => row.nodeId === node.node_id)
      return rows.length > 0 && <fieldset key={node.node_id} disabled={pending}><legend>{rows[0].nodeName}</legend>{rows.map((row) => <ParameterField key={row.key} row={row} edit={edits[row.key]} disabled={pending} error={prepared.errors[row.key]}
        staged={prepared.commands.some((command) => command.node_id === row.nodeId && command.parameter_id === row.name)}
        onEdit={(raw) => setEdits((current) => ({ ...current, [row.key]: { mode: 'set', raw } }))} onClear={() => clear(row)} />)}</fieldset>
    })}
    <div className="research-settings-actions"><button disabled={writesBlocked || !loaded || (!prepared.commands.length && !unpublished)} onClick={() => void save()}>{pending ? 'Working…' : prepared.commands.length ? 'Save parameters and version' : 'Save new version'}</button>
      <button disabled={pending} onClick={() => setAttempt((value) => value + 1)}>Reload latest draft</button>
      {Object.keys(edits).length > 0 && <button disabled={pending} onClick={() => { setEdits({}); setAttempt((value) => value + 1) }}>Discard pending edits and reload</button>}
      {onOpenBuilder && <button disabled={pending} onClick={onOpenBuilder}>Open full builder</button>}</div>
    {message && <p role="status">{message}</p>}
  </section>
}

export function SignalParameterSettings(props: Props) {
  const [scope, setScope] = useState({ api: props.api, generation: 0 })
  if (scope.api !== props.api) { setScope({ api: props.api, generation: scope.generation + 1 }); return null }
  return <SignalParameterSettingsBody key={`${scope.generation}:${props.projectId}:${props.graphId}:${props.proposal?.runId ?? 'manual'}`} {...props} />
}
