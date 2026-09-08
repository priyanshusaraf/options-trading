import { useEffect, useState } from 'react'
import { errorMessage, type StrategyApi } from '../../shell/api'
import type { ResearchDataset } from '../../shell/contracts'
import { parseScopeMemberContext, verifyScopeMember, type StaticScope, type StaticScopeMemberContext } from './staticScopeContracts'

type MemberState = { kind: 'none' } | { kind: 'loading' } | { kind: 'error'; message: string } | { kind: 'ready'; scope: StaticScope; dataset: ResearchDataset }
export function useScopeMember(api: StrategyApi, context: StaticScopeMemberContext | undefined, datasets: readonly ResearchDataset[] | undefined, graphVersion: number | null, projectId: string, graphId: string) {
  const [stored, setStored] = useState<{ api: StrategyApi; context: StaticScopeMemberContext | undefined; datasets: readonly ResearchDataset[] | undefined; state: MemberState }>({ api, context, datasets, state: { kind: 'loading' } })
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    if (!context || !datasets) return
    const controller = new AbortController(); setStored({ api, context, datasets, state: { kind: 'loading' } })
    async function load() {
      const selected = parseScopeMemberContext(context, projectId, graphId)
      const scope = await api.staticScope(selected.project_id, selected.scope_id, selected.revision, controller.signal)
      const dataset = verifyScopeMember(selected, scope, datasets!, graphVersion)
      if (!controller.signal.aborted) setStored({ api, context, datasets, state: { kind: 'ready', scope, dataset } })
    }
    void load().catch((error) => { if (!controller.signal.aborted) setStored({ api, context, datasets, state: { kind: 'error', message: `${errorMessage(error)} The selected watchlist revision, member or history could not be verified.` } }) })
    return () => controller.abort()
  }, [api, context, datasets, graphVersion, projectId, graphId, attempt])
  const state: MemberState = !context ? { kind: 'none' } : !datasets || stored.api !== api || stored.context !== context || stored.datasets !== datasets ? { kind: 'loading' } : stored.state
  return { state, retry: () => setAttempt((value) => value + 1) }
}
export function scopeMemberKey(context: StaticScopeMemberContext | undefined) {
  return context ? `${context.address}/${context.dataset_manifest_address}` : null
}
export function scopeMemberReady(context: StaticScopeMemberContext | undefined, state: MemberState, applied: boolean, retainedRequest: boolean) {
  return !context || retainedRequest || (state.kind === 'ready' && applied)
}
export function ScopeMemberStatus({ state, applied, canApply, onApply, retry }: { state: MemberState; applied: boolean; canApply: boolean; onApply: () => void; retry: () => void }) {
  if (state.kind === 'none') return null
  if (state.kind === 'loading') return <p role="status">Checking the selected watchlist member…</p>
  if (state.kind === 'error') return <div><p role="alert">{state.message}</p><button onClick={retry}>Retry watchlist selection</button></div>
  return <div className="scope-member-context"><p>Opened from {state.scope.name}, revision {state.scope.snapshot.revision}. This is a single-member selection; research inputs remain editable.</p>
    {!applied && <><p>The current research setup has not been changed.</p><button disabled={!canApply} onClick={onApply}>Use member for next run</button></>}
  </div>
}
