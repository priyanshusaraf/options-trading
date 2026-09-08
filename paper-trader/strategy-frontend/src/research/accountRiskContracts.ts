import { ContractError, type BrowserIdentity } from '../shell/contracts'

export const accountRiskFields = [
  { key: 'max_daily_loss', label: 'Daily net realized loss limit (INR)', help: 'Halts new entries when today’s realized loss, including recorded charges, reaches this amount.' },
  { key: 'max_open_drawdown', label: 'Daily realized and open loss limit (INR)', help: 'Halts new entries when net realized P&L plus gross open-position marks reaches this loss.' },
  { key: 'max_daily_profit', label: 'Daily net realized profit limit (INR)', help: 'Halts new entries when today’s realized profit, after recorded charges, reaches this amount.' },
] as const
export type AccountRiskKey = typeof accountRiskFields[number]['key']
export type AccountRiskSetting = Readonly<{ key: AccountRiskKey; value: number; default: number; overridden: boolean }>

export function canEditAccountRisk(identity: BrowserIdentity | null) {
  const membership = identity?.memberships.find((item) => item.organization_id === identity.organization_id)
  return membership?.role === 'owner' || membership?.role === 'admin'
}
function object(input: unknown): Record<string, unknown> {
  if (input === null || typeof input !== 'object' || Array.isArray(input)) throw new ContractError()
  return input as Record<string, unknown>
}
function amount(input: unknown): number {
  if (typeof input !== 'number' || !Number.isFinite(input) || input < 0 || input > 100_000_000) throw new ContractError()
  return input
}
export function validateAccountRiskUpdate(key: AccountRiskKey, value: number) {
  if (!accountRiskFields.some((field) => field.key === key)) throw new ContractError()
  return { key, value: amount(value) }
}
function setting(input: unknown, key: AccountRiskKey): AccountRiskSetting {
  const row = object(input)
  if (row.type !== 'float' || typeof row.overridden !== 'boolean') throw new ContractError()
  return Object.freeze({ key, value: amount(row.value), default: amount(row.default), overridden: row.overridden })
}
export function parseAccountRiskSettings(input: unknown): readonly AccountRiskSetting[] {
  const rows = object(input).params
  if (!Array.isArray(rows) || rows.length > 300) throw new ContractError()
  return Object.freeze(accountRiskFields.map(({ key }) => {
    const matching = rows.filter((row) => object(row).key === key)
    if (matching.length !== 1) throw new ContractError()
    return setting(matching[0], key)
  }))
}
export function parseAccountRiskSave(input: unknown, key: AccountRiskKey, value: number) {
  const row = object(input)
  if (Object.keys(row).length !== 2 || row.key !== key || typeof row.value !== 'string' || row.value.trim() === '') throw new ContractError()
  if (amount(Number(row.value)) !== value) throw new ContractError()
  return value
}
