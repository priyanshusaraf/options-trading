/* React bindings over the store, plus the derived selectors surfaces need. */

import { useSyncExternalStore, useMemo } from 'react'
import { getSnapshot, subscribe } from './store'
import type {
  DB, ID, Instrument, Session, Trade,
} from '../domain/types'
import { sessionKey } from './actions'
import { realisedR } from '../domain/metrics'

export function useStore() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot)
}

export function useDB(): DB {
  return useStore().db
}

export function useSettings() {
  return useDB().settings
}

export function useInstruments(): Instrument[] {
  const db = useDB()
  return useMemo(
    () => [...db.instruments].sort((a, b) => a.order - b.order),
    [db.instruments],
  )
}

export function useInstrument(id: ID): Instrument | undefined {
  return useDB().instruments.find((i) => i.id === id)
}

export function useSession(instrumentId: ID, date: string): Session | undefined {
  const db = useDB()
  return db.sessions.find((s) => s.id === sessionKey(instrumentId, date))
}

/** Live trades for an instrument, newest first. Soft-deleted rows are excluded
 *  everywhere except the Settings trash view. */
export function useTrades(instrumentId?: ID): Trade[] {
  const db = useDB()
  return useMemo(() => {
    let list = db.trades.filter((t) => !t.deletedAt)
    if (instrumentId) list = list.filter((t) => t.instrumentId === instrumentId)
    return list.sort((a, b) => b.openedAt - a.openedAt)
  }, [db.trades, instrumentId])
}

export function useSessionTrades(sessionId: ID): Trade[] {
  const db = useDB()
  return useMemo(
    () =>
      db.trades
        .filter((t) => t.sessionId === sessionId && !t.deletedAt)
        .sort((a, b) => a.openedAt - b.openedAt),
    [db.trades, sessionId],
  )
}

export function useStream(sessionId: ID) {
  const db = useDB()
  return useMemo(
    () =>
      db.events
        .filter((e) => e.sessionId === sessionId && !e.inbox)
        .sort((a, b) => b.at - a.at),
    [db.events, sessionId],
  )
}

/** §4.4 The Inbox count in the sidebar; Prep's first block is "triage inbox". */
export function useInbox(instrumentId?: ID) {
  const db = useDB()
  return useMemo(
    () =>
      db.events
        .filter((e) => e.inbox && (!instrumentId || e.instrumentId === instrumentId))
        .sort((a, b) => b.at - a.at),
    [db.events, instrumentId],
  )
}

export function useLevels(instrumentId: ID) {
  const db = useDB()
  return useMemo(
    () =>
      db.levels
        .filter((l) => l.instrumentId === instrumentId && l.active)
        .sort((a, b) => b.price - a.price),
    [db.levels, instrumentId],
  )
}

export function usePlaybook(instrumentId?: ID) {
  const db = useDB()
  return useMemo(() => {
    let list = db.playbook.filter((p) => !p.archived)
    if (instrumentId) {
      list = list.filter(
        (p) => !p.instrumentIds.length || p.instrumentIds.includes(instrumentId),
      )
    }
    return list.sort((a, b) => a.shortcut - b.shortcut)
  }, [db.playbook, instrumentId])
}

export function useDocs(instrumentId: ID) {
  const db = useDB()
  return useMemo(
    () =>
      db.docs
        .filter((d) => d.instrumentId === instrumentId)
        .sort((a, b) => a.order - b.order),
    [db.docs, instrumentId],
  )
}

export function useMacroEvents(instrumentId: ID, date: string) {
  const db = useDB()
  return useMemo(
    () =>
      db.macroEvents
        .filter((e) => e.date === date && e.instrumentIds.includes(instrumentId))
        .sort((a, b) => a.time.localeCompare(b.time)),
    [db.macroEvents, instrumentId, date],
  )
}

export function useRegime(instrumentId: ID) {
  const db = useDB()
  return useMemo(() => {
    const log = db.regimeLog
      .filter((r) => r.instrumentId === instrumentId)
      .sort((a, b) => b.at - a.at)
    return log[0] ?? null
  }, [db.regimeLog, instrumentId])
}

export function useArtifacts(instrumentId?: ID) {
  const db = useDB()
  return useMemo(() => {
    let list = db.artifacts
    if (instrumentId) list = list.filter((a) => a.instrumentId === instrumentId)
    return [...list].sort((a, b) => b.at - a.at)
  }, [db.artifacts, instrumentId])
}

/** §4.1 The rail's 3px state bar: grey flat, tinted position open, amber for
 *  limit breached or unreviewed session. */
export type RailState = 'flat' | 'position' | 'attention'

export function useRailStates(): Record<ID, RailState> {
  const db = useDB()
  return useMemo(() => {
    const out: Record<ID, RailState> = {}
    for (const inst of db.instruments) {
      const open = db.trades.some(
        (t) => t.instrumentId === inst.id && !t.deletedAt && t.closedAt == null,
      )
      const unreviewed = db.sessions.some(
        (s) =>
          s.instrumentId === inst.id &&
          s.lockedAt != null &&
          !s.review?.completedAt &&
          db.trades.some((t) => t.sessionId === s.id && !t.deletedAt),
      )
      out[inst.id] = unreviewed ? 'attention' : open ? 'position' : 'flat'
    }
    return out
  }, [db.instruments, db.trades, db.sessions])
}

/** §5.1 The "UNRESOLVED" nag row — sessions with trades but no review.
 *  It disappears when empty; that is the only place the app nags. */
export function useUnresolved(instrumentId: ID) {
  const db = useDB()
  return useMemo(
    () =>
      db.sessions
        .filter(
          (s) =>
            s.instrumentId === instrumentId &&
            !s.review?.completedAt &&
            db.trades.some((t) => t.sessionId === s.id && !t.deletedAt),
        )
        .sort((a, b) => b.date.localeCompare(a.date)),
    [db.sessions, db.trades, instrumentId],
  )
}

/** Ordered session dates for an instrument — powers `[` / `]`. §4.2 */
export function useSessionDates(instrumentId: ID): string[] {
  const db = useDB()
  return useMemo(() => {
    const dates = new Set<string>()
    for (const s of db.sessions) {
      if (s.instrumentId === instrumentId) dates.add(s.date)
    }
    for (const t of db.trades) {
      if (t.instrumentId === instrumentId && !t.deletedAt) dates.add(t.date)
    }
    return [...dates].sort()
  }, [db.sessions, db.trades, instrumentId])
}

export function useOpenPositions(instrumentId: ID) {
  const db = useDB()
  return useMemo(
    () =>
      db.trades.filter(
        (t) => t.instrumentId === instrumentId && !t.deletedAt && t.closedAt == null,
      ),
    [db.trades, instrumentId],
  )
}

/** Today's used risk in R, shown in the status bar. §4.1 */
export function useDayRisk(instrumentId: ID, date: string): number {
  const db = useDB()
  return useMemo(() => {
    const inst = db.instruments.find((i) => i.id === instrumentId)
    if (!inst) return 0
    return db.trades
      .filter((t) => t.instrumentId === instrumentId && t.date === date && !t.deletedAt)
      .reduce((a, t) => a + (realisedR(t, inst) ?? 0), 0)
  }, [db.trades, db.instruments, instrumentId, date])
}

export function useSetupLookup() {
  const db = useDB()
  return useMemo(() => {
    const byId = new Map(db.playbook.map((p) => [p.id, p]))
    return {
      code: (id: ID | null) => (id ? (byId.get(id)?.code ?? '—') : 'off-book'),
      name: (id: ID | null) => (id ? (byId.get(id)?.name ?? '—') : 'Off-book'),
      get: (id: ID | null) => (id ? byId.get(id) : undefined),
    }
  }, [db.playbook])
}
