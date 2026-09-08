import { sameJson, v2Document, type OptimizationSelection, type PublishedGraph, type V2Draft, type V2Document } from '../shell/contracts'
import { parameterKey, record, SaveVerificationError } from './builderParameterContracts'
import { parseSavedResearchPolicy } from './preparedResearchContracts'
import { prepareParameterEdits, type ParameterEdit, type ParameterEdits, type SignalParameter } from './signalParameterContracts'

export type ParameterProposal = Readonly<{ runId: number; baseline: PublishedGraph; selection: OptimizationSelection }>

function proposalBaseline(proposal: ParameterProposal, draft: V2Draft, saved: unknown) {
  const { baseline } = proposal
  const policy = parseSavedResearchPolicy(saved, baseline.identifier, baseline.version)
  const document = v2Document(record(saved).document, baseline.identifier)
  if (draft.project_id !== baseline.project_id || draft.graph_identifier !== baseline.identifier
    || draft.current_version !== baseline.version || draft.published_revision !== draft.semantic_revision
    || policy.contentAddress !== baseline.content_address || draft.graph_address !== record(saved).graph_address) {
    throw new SaveVerificationError('This strategy changed since the optimization run. Run the latest saved version before applying its suggestion.')
  }
  if (document.strategy_version !== baseline.version || !sameJson({ ...draft.document, strategy_version: baseline.version }, document)) {
    throw new SaveVerificationError('The current draft does not match the optimization baseline. Reload and compare the saved versions.')
  }
  return document
}

function proposedDocument(document: V2Document, proposal: ParameterProposal, rows: readonly SignalParameter[]) {
  const nodes = document.nodes.map((node) => ({ ...node, parameters: { ...node.parameters } }))
  const edits: Record<string, ParameterEdit> = {}
  for (const parameter of proposal.selection.parameters) {
    const key = parameterKey(parameter.node_id, parameter.parameter_id)
    const row = rows.find((item) => item.key === key)
    const node = nodes.find((item) => item.node_id === parameter.node_id)
    if (!row?.explicit || !node || Object.hasOwn(edits, key)) throw new SaveVerificationError('A suggested parameter no longer matches this strategy.')
    node.parameters[parameter.parameter_id] = parameter.value
    edits[key] = { mode: 'set', raw: JSON.stringify(parameter.value) }
  }
  return { document: { ...document, nodes }, edits }
}

export function proposalParameterEdits(proposal: ParameterProposal, draft: V2Draft, saved: unknown, rows: readonly SignalParameter[]): ParameterEdits {
  const baseline = proposalBaseline(proposal, draft, saved)
  const proposed = proposedDocument(baseline, proposal, rows)
  if (!sameJson(proposed.document, proposal.selection.canonical_document)) {
    throw new SaveVerificationError('The suggested strategy contains changes beyond the displayed parameters. It cannot be applied here.')
  }
  if (Object.keys(prepareParameterEdits(rows, proposed.edits).errors).length) throw new SaveVerificationError('A suggested value is outside the current component limits.')
  return proposed.edits
}
