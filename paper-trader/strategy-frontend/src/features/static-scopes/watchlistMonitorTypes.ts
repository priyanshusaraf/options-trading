import type { ScopeMember } from './staticScopeContracts'

export type WatchlistMonitorContext = Readonly<{
  projectId: string; scopeId: string; scopeRevision: number; scopeAddress: string; membershipAddress: string
}>
export type WatchlistStrategySelection = Readonly<{ graphId: string; graphVersion: number; timeframe: string }>
export type WatchlistMonitorRow = Readonly<{
  memberKey: string; configurationRevision: number; pinned: boolean
  graph: Readonly<{ graphId: string; graphVersion: number; graphVersionAddress: string; label: string }> | null
  timeframe: string | null
  supportedTimeframes: readonly Readonly<{ value: string; label: string }>[]
  assignmentId: string | null
  monitoring: 'OFF' | 'ON' | 'STARTING' | 'PAUSED' | 'BLOCKED'
  canConfigure: boolean; canPin: boolean; canSetMonitoring: boolean; reason: string | null
  result: Readonly<{
    kind: 'NOT_EVALUATED' | 'HOLD' | 'SIGNAL' | 'WARMUP' | 'STALE' | 'ERROR'
    label: string; evaluatedAt: string | null; assignmentId: string | null; graphVersionAddress: string | null
    reason: string | null; warmup: Readonly<{ available: number; required: number }> | null
  }>
}>
export type WatchlistMonitorSnapshot = Readonly<{ context: WatchlistMonitorContext; rows: readonly WatchlistMonitorRow[] }>
export interface WatchlistMonitorClient {
  list(context: WatchlistMonitorContext, signal: AbortSignal): Promise<WatchlistMonitorSnapshot>
  configure(context: WatchlistMonitorContext, member: ScopeMember, expectedRevision: number,
    selection: WatchlistStrategySelection, signal: AbortSignal): Promise<WatchlistMonitorRow>
  pin(context: WatchlistMonitorContext, member: ScopeMember, expectedRevision: number,
    pinned: boolean, signal: AbortSignal): Promise<WatchlistMonitorRow>
  setMonitoring(context: WatchlistMonitorContext, member: ScopeMember, expectedRevision: number,
    enabled: boolean, signal: AbortSignal): Promise<WatchlistMonitorRow>
}
