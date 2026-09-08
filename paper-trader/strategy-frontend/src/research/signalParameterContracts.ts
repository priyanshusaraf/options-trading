import { sameJson, type CatalogueHelpParameter, type V2Draft, type V2SemanticReceipt, type VerifiedCatalogue } from '../shell/contracts'
import { labelFor, parameterKey, record, SaveVerificationError } from './builderParameterContracts'

export type SignalParameter = Readonly<{
  key: string; nodeId: string; nodeName: string; name: string; label: string
  definition: CatalogueHelpParameter; explicit: boolean; value: unknown
}>
export type ParameterEdit = Readonly<{ mode: 'set'; raw: string }> | Readonly<{ mode: 'clear' }>
export type ParameterEdits = Readonly<Record<string, ParameterEdit>>
export type ParameterCommand = Readonly<Record<string, unknown>>

export function signalParameters(draft: Pick<V2Draft, 'document'>, catalogue: VerifiedCatalogue): readonly SignalParameter[] {
  const components = new Map(catalogue.groups.flatMap((group) => group.components).map((item) => [`${item.component_id}@${item.component_version}`, item]))
  return draft.document.nodes.flatMap((node, index) => {
    const component = components.get(`${node.component.component_id}@${node.component.component_version}`)
    if (!component) throw new SaveVerificationError('A strategy component is unavailable in the current library. Open Build to review it before editing parameters.')
    const nodeName = `${component.display_name} · ${index + 1}`
    return component.help.customisation.parameters.map((definition) => {
      const explicit = Object.hasOwn(node.parameters, definition.name)
      return { key: parameterKey(node.node_id, definition.name), nodeId: node.node_id, nodeName, name: definition.name,
        label: `${labelFor(definition.name)} (${definition.units})`, definition, explicit,
        value: explicit ? node.parameters[definition.name] : definition.default }
    })
  })
}
export function parameterKind(definition: CatalogueHelpParameter) {
  if (Array.isArray(definition.enum)) return 'enum'
  if (['bool', 'boolean'].includes(definition.type)) return 'boolean'
  if (['int', 'float', 'number'].includes(definition.type)) return 'number'
  return ['str', 'string'].includes(definition.type) ? 'text' : 'json'
}
export function parameterRaw(value: unknown, definition: CatalogueHelpParameter) {
  return parameterKind(definition) === 'text' && typeof value === 'string' ? value : JSON.stringify(value) ?? ''
}
function parseParameterValue(raw: string, definition: CatalogueHelpParameter): unknown {
  if (parameterKind(definition) === 'text') return raw
  let value: unknown
  try { value = JSON.parse(raw) } catch { throw new SaveVerificationError('Enter a valid value before saving.') }
  if (parameterKind(definition) === 'number') validateNumericParameter(value, definition)
  return value
}
function validateNumericParameter(value: unknown, definition: CatalogueHelpParameter) {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new SaveVerificationError('Enter a finite number.')
  if (definition.type === 'int' && !Number.isInteger(value)) throw new SaveVerificationError('Enter a whole number.')
  const domain = record(definition.domain)
  if (typeof domain.minimum === 'number' && value < domain.minimum) throw new SaveVerificationError(`Enter ${domain.minimum} or more.`)
  if (typeof domain.maximum === 'number' && value > domain.maximum) throw new SaveVerificationError(`Enter ${domain.maximum} or less.`)
}
function parameterCommand(row: SignalParameter, edit: ParameterEdit): ParameterCommand | null {
  const identity = { node_id: row.nodeId, parameter_id: row.name }
  if (edit.mode === 'clear') return row.explicit ? { command: 'clear_parameter', ...identity } : null
  const value = parseParameterValue(edit.raw, row.definition)
  return row.explicit && sameJson(value, row.value) ? null : { command: 'set_parameter', ...identity, value }
}
export function prepareParameterEdits(rows: readonly SignalParameter[], edits: ParameterEdits) {
  const commands: ParameterCommand[] = [], errors: Record<string, string> = {}
  for (const [key, edit] of Object.entries(edits)) {
    const row = rows.find((item) => item.key === key)
    if (!row) { errors[key] = 'An edited parameter no longer exists. Discard pending edits and reload the draft.'; continue }
    try { const command = parameterCommand(row, edit); if (command) commands.push(command) }
    catch (error) { errors[key] = error instanceof SaveVerificationError ? error.message : 'Enter a valid parameter value.' }
  }
  return { commands, errors }
}
export function requireParameterValidation(receipt: V2SemanticReceipt, base: V2Draft, commands: readonly ParameterCommand[]) {
  if (receipt.commit_state !== 'DRY_RUN_ROLLED_BACK' || receipt.intent !== 'EDIT' || receipt.base_semantic_revision !== base.semantic_revision
    || !sameJson(receipt.forward_commands, commands)) throw new SaveVerificationError('Parameter validation could not be verified. Reload the draft before trying again.')
}
export function requireParameterReadback(draft: V2Draft, expected: V2Draft, commands: readonly ParameterCommand[]) {
  if (draft.semantic_revision !== expected.semantic_revision || draft.current_version !== expected.current_version
    || draft.content_address !== expected.content_address || draft.graph_address !== expected.graph_address) throw new SaveVerificationError('The draft changed during the save. Reload and review your retained edits.')
  for (const command of commands) requireAppliedParameter(draft, command)
}
function requireAppliedParameter(draft: V2Draft, command: ParameterCommand) {
    const node = draft.document.nodes.find((item) => item.node_id === command.node_id)
    if (!node) throw new SaveVerificationError('A saved parameter node is unavailable. Reload the draft.')
    const name = String(command.parameter_id), explicit = Object.hasOwn(node.parameters, name)
    const matches = command.command === 'clear_parameter' ? !explicit : explicit && sameJson(node.parameters[name], command.value)
    if (!matches) throw new SaveVerificationError('The saved parameters do not match your edits. Reload to review the draft.')
}
