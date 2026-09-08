import type { CatalogueComponent, V2Draft, V2PublishReceipt, V2SemanticReceipt } from '../shell/contracts'
import { parseSavedResearchPolicy } from './preparedResearchContracts'

type Command = Readonly<Record<string, unknown>>
export function record(value: unknown): Record<string, unknown> { return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {} }
export function descriptor(component: CatalogueComponent) { return record(component.descriptor) }
export function parameterRows(component: CatalogueComponent | undefined) { return component ? record(descriptor(component).parameters) : {} }
export function labelFor(identifier: string) { return identifier.split('.').at(-1)!.replace(/([a-z0-9])([A-Z])/g, '$1 $2').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase()) }

export class SaveVerificationError extends Error {}

export function stageParameterCommand(commands: Command[], command: Command) {
  const last = commands.at(-1)
  return last?.command === 'set_parameter' && last.node_id === command.node_id && last.parameter_id === command.parameter_id
    ? [...commands.slice(0, -1), command] : [...commands, command]
}
export function parameterKey(nodeId: string, parameterId: string) { return JSON.stringify([nodeId, parameterId]) }
export function requireSemanticCommit(receipt: V2SemanticReceipt, base: V2Draft) {
  if (receipt.commit_state !== 'DRAFT_COMMITTED' || receipt.intent !== 'EDIT' || receipt.base_semantic_revision !== base.semantic_revision
    || receipt.base_content_address !== base.content_address || receipt.base_graph_address !== base.graph_address) throw new SaveVerificationError('The draft save could not be verified.')
}
export function requirePublication(receipt: V2PublishReceipt, saved: V2Draft) {
  if (receipt.graph_version !== (saved.current_version ?? 0) + 1 || receipt.semantic_revision !== saved.semantic_revision || receipt.content_address !== saved.content_address || receipt.graph_address !== saved.graph_address) {
    throw new SaveVerificationError('The saved version does not match your draft. Reload to check it before continuing.')
  }
}
export function publishedAddress(input: unknown, graphId: string, version: number, graphAddress: string) {
  const checked = parseSavedResearchPolicy(input, graphId, version), row = record(input)
  if (row.graph_address !== graphAddress || record(row.document).strategy_version !== version) throw new SaveVerificationError('The saved version could not be verified.')
  return checked.contentAddress
}

export function requirePublishedDraft(current: V2Draft, saved: V2Draft, version: number) {
  if (current.semantic_revision !== saved.semantic_revision || current.current_version !== version || current.published_revision !== saved.semantic_revision
    || current.graph_address !== saved.graph_address || current.document.strategy_version !== version + 1) throw new SaveVerificationError('The draft changed after the version was saved. Reload to review it.')
}
