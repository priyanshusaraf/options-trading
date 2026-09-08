import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ApiError, errorMessage, type StrategyApi } from '../../shell/api'
import type { StrategyPreset } from './presetContracts'

function copyError(error: unknown) {
  if (error instanceof ApiError) {
    const reasons: Record<string, string> = {
      GRAPH_ALREADY_EXISTS: 'This draft reference is already used. Close this window and start again to create a separate strategy.',
      PROJECT_NOT_FOUND: 'This project is no longer available. Return to Strategies and choose another project.',
      PRESET_NOT_FOUND: 'This preset is no longer available. Return to the library and choose another preset.',
      PRESET_COPY_REJECTED: 'The preset could not be copied. Your name is saved here; try again.',
    }
    const reason = reasons[error.envelope?.code ?? '']
    if (reason) return reason
  }
  return errorMessage(error)
}

export function CreateDraft({ api, projectId, preset, onCreated, onCancel }: {
  api: StrategyApi; projectId?: string; preset?: StrategyPreset
  onCreated: (projectId: string, identifier: string) => void; onCancel: () => void
}) {
  const [identifier] = useState(() => crypto.randomUUID())
  const [name, setName] = useState(preset?.name ?? '')
  const [description, setDescription] = useState('')
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const request = useRef<AbortController | null>(null)
  const destination = useRef(projectId)
  useEffect(() => {
    destination.current = projectId; request.current = null; setPending(false); setMessage(null)
    return () => request.current?.abort()
  }, [api, projectId])

  async function create(signal: AbortSignal) {
    if (!destination.current) {
      const project = await api.createProject('My research', '', signal)
      if (signal.aborted) return
      destination.current = project.project_id
    }
    if (preset) {
      return { projectId: destination.current, identifier: (await api.copyPreset(destination.current, preset.preset_id, identifier, name.trim(), signal)).identifier }
    }
    const draft = await api.createV2Graph(destination.current, identifier, name.trim(), description, signal)
    return { projectId: destination.current, identifier: draft.graph_identifier }
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (request.current || !name.trim()) return
    const controller = new AbortController(); request.current = controller
    setMessage(null); setPending(true)
    try {
      const created = await create(controller.signal)
      if (!controller.signal.aborted && created) onCreated(created.projectId, created.identifier)
    } catch (error) {
      if (!controller.signal.aborted) setMessage(copyError(error))
    } finally {
      if (!controller.signal.aborted) { request.current = null; setPending(false) }
    }
  }
  return <form className="research-form slate-create-form" onSubmit={(event) => void submit(event)}>
    {preset && <p className="slate-form-intro">Start with {preset.name}. You can edit its rules and settings after creating your draft.</p>}
    <label>Strategy name<input autoFocus required disabled={pending} maxLength={128} value={name} placeholder="Give your strategy a name" onChange={(event) => setName(event.target.value)} /></label>
    {!preset && <label>Description <span className="slate-optional">Optional</span><textarea disabled={pending} maxLength={4000} value={description} placeholder="What would you like to explore?" onChange={(event) => setDescription(event.target.value)} /></label>}
    {!projectId && <p className="slate-form-help">We’ll save this strategy in a private “My research” project.</p>}
    {message && <p role="alert">{message}</p>}
    <div className="slate-dialog-actions"><button className="slate-primary-action" disabled={pending}>{pending ? 'Creating…' : 'Create strategy'}</button><button type="button" onClick={() => { request.current?.abort(); onCancel() }}>Cancel</button></div>
  </form>
}
