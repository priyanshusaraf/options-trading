import { ContractError } from '../../shell/contracts'

function record(input: unknown): Record<string, unknown> {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new ContractError()
  return input as Record<string, unknown>
}
function text(input: unknown): string {
  if (typeof input !== 'string' || !input.trim()) throw new ContractError()
  return input
}
function amount(input: unknown): number {
  if (typeof input !== 'number' || !Number.isFinite(input)) throw new ContractError()
  return input
}
function count(input: unknown): number {
  const value = amount(input)
  if (!Number.isSafeInteger(value) || value < 0) throw new ContractError()
  return value
}
function calendarDate(input: unknown): string {
  const value = text(input)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(Date.parse(value)) || new Date(value).toISOString().slice(0, 10) !== value) throw new ContractError()
  return value
}
function updateTime(input: unknown): string {
  const value = text(input)
  if (!/^\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)$/.test(value) || !Number.isFinite(Date.parse(value))) throw new ContractError()
  calendarDate(value.slice(0, 10))
  return value
}
function point(input: unknown) {
  const value = record(input)
  return { timestamp: calendarDate(value.timestamp), realized_pnl: amount(value.realized_pnl) }
}
function strategy(input: unknown) {
  const value = record(input)
  return { strategy_key: value.strategy_key === null ? null : text(value.strategy_key), strategy_version: value.strategy_version === null ? null : text(value.strategy_version),
    display_name: text(value.display_name), realized_pnl: amount(value.realized_pnl), closed_trades: count(value.closed_trades) }
}
function untradedStrategy(input: unknown) {
  const value = record(input)
  return { strategy_key: text(value.strategy_key), strategy_version: value.strategy_version === null ? null : text(value.strategy_version), display_name: text(value.display_name) }
}
function validateRows(strategies: ReturnType<typeof strategy>[], untraded: ReturnType<typeof untradedStrategy>[]) {
  const identities = strategies.map((item) => JSON.stringify([item.strategy_key, item.strategy_version]))
  const keys = untraded.map((item) => item.strategy_key)
  if (new Set(identities).size !== identities.length || new Set(keys).size !== keys.length) throw new ContractError()
  const traded = new Set(strategies.map((item) => item.strategy_key))
  if (keys.some((key) => traded.has(key))) throw new ContractError()
}
function validateTotals(points: ReturnType<typeof point>[], strategies: ReturnType<typeof strategy>[], total: number, trades: number) {
  if ((points.at(-1)?.realized_pnl ?? 0) !== total) throw new ContractError()
  if (strategies.reduce((sum, item) => sum + item.closed_trades, 0) !== trades) throw new ContractError()
  const sum = strategies.reduce((sum, item) => sum + item.realized_pnl, 0)
  // Each strategy and the combined total are rounded separately to cents.
  const roundingTolerance = (strategies.length + 1) * 0.005 + 1e-8
  if (Math.abs(sum - total) > roundingTolerance) throw new ContractError()
}
export function parsePaperPortfolio(input: unknown) {
  const value = record(input)
  if (value.schema !== 'paper-portfolio/1' || value.currency !== 'INR' || !Array.isArray(value.points) || !Array.isArray(value.strategies) || !Array.isArray(value.untraded_strategies)) throw new ContractError()
  const points = value.points.map(point)
  const strategies = value.strategies.map(strategy)
  const untraded_strategies = value.untraded_strategies.map(untradedStrategy)
  validateRows(strategies, untraded_strategies)
  const as_of = updateTime(value.as_of)
  const realized_pnl = amount(value.realized_pnl), closed_trades = count(value.closed_trades)
  if (points.some((item, index) => index > 0 && Date.parse(item.timestamp) <= Date.parse(points[index - 1].timestamp))) throw new ContractError()
  validateTotals(points, strategies, realized_pnl, closed_trades)
  return { currency: 'INR' as const, as_of, points, strategies, untraded_strategies, realized_pnl, closed_trades }
}
export type PaperPortfolio = ReturnType<typeof parsePaperPortfolio>
