import { useEffect, useState, type FormEvent } from 'react'
import type { IrEditableNode, IrEditableParameter } from '../lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card'
import type { GraphEditorState } from './graphEditorState'

const buttonClass = 'rounded border border-edge px-3 py-1.5 text-xs font-medium text-zinc-200 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400'
const inputClass = 'rounded border border-edge bg-bg px-2 py-1.5 text-sm text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400'

const fieldToken = (value: string): string => value.replace(/[^a-zA-Z0-9_-]/g, '_')

function ParameterControl({
  node,
  parameter,
  disabled,
  errorId,
  onSet,
  onClear,
}: {
  node: IrEditableNode
  parameter: IrEditableParameter
  disabled: boolean
  errorId?: string
  onSet: (source: string) => void
  onClear: () => void
}) {
  const inputId = `override-${fieldToken(node.instance_id)}-${fieldToken(parameter.identifier)}`
  const [source, setSource] = useState(() => JSON.stringify(parameter.value))
  useEffect(() => {
    setSource(JSON.stringify(parameter.value))
  }, [parameter.value])

  const submit = (event: FormEvent) => {
    event.preventDefault()
    onSet(source)
  }

  return (
    <form className="space-y-2 rounded border border-edge/70 p-3" onSubmit={submit}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <label htmlFor={inputId} className="text-xs font-medium text-zinc-200">
          {parameter.identifier}
        </label>
        <span className="text-[11px] text-muted">
          {parameter.overridden ? 'Explicit override' : 'Inherited/default'} · {parameter.kind}
        </span>
      </div>
      <p className="text-[11px] text-muted">
        Default: <code>{JSON.stringify(parameter.default)}</code>
      </p>
      <div className="flex flex-wrap gap-2">
        <input
          id={inputId}
          name={`${node.instance_id}.${parameter.identifier}`}
          className={`${inputClass} min-w-48 flex-1 font-mono`}
          value={source}
          onChange={(event) => setSource(event.target.value)}
          aria-describedby={errorId}
          disabled={disabled}
        />
        <button
          type="submit"
          className={buttonClass}
          aria-label={`Set ${node.instance_id} ${parameter.identifier} override`}
          disabled={disabled}
        >
          Set
        </button>
        {parameter.overridden && (
          <button
            type="button"
            className={buttonClass}
            aria-label={`Clear ${node.instance_id} ${parameter.identifier} override`}
            disabled={disabled}
            onClick={onClear}
          >
            Clear
          </button>
        )}
      </div>
    </form>
  )
}

export function GraphEditControls({
  state,
  onDisplayName,
  onSetOverride,
  onClearOverride,
  onUndo,
  onRedo,
  onReload,
}: {
  state: GraphEditorState
  onDisplayName: (displayName: string) => void
  onSetOverride: (instanceId: string, parameter: string, source: string) => void
  onClearOverride: (instanceId: string, parameter: string) => void
  onUndo: () => void
  onRedo: () => void
  onReload: () => void
}) {
  const document = state.accepted
  const [displayName, setDisplayName] = useState(document?.display_name ?? '')
  useEffect(() => {
    if (document) setDisplayName(document.display_name)
  }, [document?.version, document?.display_name])

  if (!document) return null
  const pending = state.phase === 'saving' || state.phase === 'reloading'
  const blocked = pending || state.phase === 'conflicted'
  const fieldErrorId = state.draft?.instanceId && state.draft.parameter
    ? `override-error-${fieldToken(state.draft.instanceId)}-${fieldToken(state.draft.parameter)}`
    : undefined
  const errors = state.failure?.envelope?.errors ?? []

  return (
    <section aria-labelledby="graph-edit-heading" className="mb-4 space-y-3">
      <Card>
        <CardHeader className="p-4 pb-2">
          <CardTitle id="graph-edit-heading" className="text-sm">Graph editing</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 p-4 pt-2">
          <form
            className="flex flex-wrap items-end gap-2"
            onSubmit={(event) => {
              event.preventDefault()
              onDisplayName(displayName)
            }}
          >
            <div className="min-w-64 flex-1 space-y-1">
              <label htmlFor="graph-display-name" className="text-xs font-medium text-zinc-200">
                Graph display name
              </label>
              <input
                id="graph-display-name"
                name="graph-display-name"
                className={`${inputClass} w-full`}
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                disabled={blocked}
              />
            </div>
            <button type="submit" className={buttonClass} disabled={blocked}>
              Update display name
            </button>
          </form>

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={buttonClass}
              disabled={blocked || state.undo.length === 0}
              onClick={onUndo}
            >Undo</button>
            <button
              type="button"
              className={buttonClass}
              disabled={blocked || state.redo.length === 0}
              onClick={onRedo}
            >Redo</button>
            <button
              type="button"
              className={buttonClass}
              disabled={state.phase === 'reloading'}
              onClick={onReload}
            >Reload server</button>
          </div>
        </CardContent>
      </Card>

      {document.editable_nodes.map((node) => (
        <Card key={node.instance_id}>
          <CardHeader className="p-4 pb-2">
            <CardTitle className="text-sm">{node.instance_id}</CardTitle>
            <p className="text-[11px] text-muted">
              {node.component_identifier} v{node.component_version}
            </p>
          </CardHeader>
          <CardContent className="grid gap-2 p-4 pt-2 lg:grid-cols-2">
            {node.parameters.map((parameter) => {
              const affected = state.draft?.instanceId === node.instance_id
                && state.draft.parameter === parameter.identifier
              return (
                <div key={parameter.identifier}>
                  <ParameterControl
                    node={node}
                    parameter={parameter}
                    disabled={blocked}
                    errorId={affected ? fieldErrorId : undefined}
                    onSet={(source) => onSetOverride(
                      node.instance_id, parameter.identifier, source,
                    )}
                    onClear={() => onClearOverride(
                      node.instance_id, parameter.identifier,
                    )}
                  />
                  {affected && state.failure && (
                    <p id={fieldErrorId} className="mt-1 text-xs text-amber-300">
                      {errors.length > 0
                        ? errors.map((error) => [
                            error.clause,
                            error.path.join('.'),
                            error.message,
                          ].filter(Boolean).join(' · ')).join('; ')
                        : state.failure.message}
                    </p>
                  )}
                </div>
              )
            })}
          </CardContent>
        </Card>
      ))}

      {pending && (
        <p role="status" aria-live="polite" className="text-xs text-muted">
          {state.phase === 'reloading'
            ? 'Reloading accepted editor state'
            : 'Publishing editor changes'}
        </p>
      )}
      {state.failure && (
        <div role="alert" className="rounded border border-amber-500/60 p-3 text-xs">
          <p className="font-medium text-amber-200">{state.failure.message}</p>
          {errors.map((error, index) => (
            <p key={`${error.operation_index}:${index}`} className="mt-1 text-muted">
              {[error.clause, error.path.join('.'), error.message]
                .filter(Boolean).join(' · ')}
            </p>
          ))}
        </div>
      )}
    </section>
  )
}
