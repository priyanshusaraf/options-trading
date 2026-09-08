import { ContractError } from '../../shell/contracts'

function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new ContractError()
  return value as Record<string, unknown>
}
function keys(value: Record<string, unknown>, required: string[], optional: string[] = []) {
  if (!required.every((key) => Object.hasOwn(value, key)) || Object.keys(value).some((key) => ![...required, ...optional].includes(key))) throw new ContractError()
}
function text(value: unknown, limit: number) {
  if (typeof value !== 'string' || !value.length || value.length > limit) throw new ContractError()
  return value
}
function integer(value: unknown, minimum: number) {
  if (!Number.isSafeInteger(value) || Number(value) < minimum) throw new ContractError()
  return Number(value)
}
function provenance(input: unknown) {
  const value = record(input)
  keys(value, ['semantic_version', 'source', 'source_sha256'], ['scope'])
  if (!/^[a-f0-9]{64}$/.test(text(value.source_sha256, 64))) throw new ContractError()
  return Object.freeze({ semantic_version: integer(value.semantic_version, 1), source: text(value.source, 512),
    source_sha256: value.source_sha256 as string, scope: value.scope === undefined ? undefined : text(value.scope, 1000) })
}
function preset(input: unknown) {
  const value = record(input)
  keys(value, ['preset_id', 'name', 'description', 'parameters', 'provenance', 'available'])
  const parameters = record(value.parameters)
  if (Object.values(parameters).some((item) => typeof item !== 'boolean' && (typeof item !== 'number' || !Number.isFinite(item)))) throw new ContractError()
  if (typeof value.available !== 'boolean') throw new ContractError()
  return Object.freeze({ preset_id: text(value.preset_id, 128), name: text(value.name, 128), description: text(value.description, 4000),
    parameters: Object.freeze(parameters), provenance: provenance(value.provenance), available: value.available })
}
export type StrategyPreset = ReturnType<typeof preset>
export function parsePresets(input: unknown): readonly StrategyPreset[] {
  const value = record(input); keys(value, ['presets'])
  if (!Array.isArray(value.presets) || value.presets.length > 100) throw new ContractError()
  const presets = value.presets.map(preset)
  if (new Set(presets.map((item) => item.preset_id)).size !== presets.length) throw new ContractError()
  return Object.freeze(presets)
}
export function parsePresetCopy(input: unknown, projectId: string, identifier: string) {
  const value = record(input)
  keys(value, ['project_id', 'identifier', 'display_name', 'revision', 'current_version', 'graph'])
  if (value.project_id !== projectId || value.identifier !== identifier) throw new ContractError()
  const graph = record(value.graph)
  if (graph.format_version !== 2 || graph.strategy_id !== identifier || graph.strategy_version !== 1) throw new ContractError()
  if (value.revision !== 0 || value.current_version !== null) throw new ContractError()
  return Object.freeze({ project_id: projectId, identifier, display_name: text(value.display_name, 128) })
}
