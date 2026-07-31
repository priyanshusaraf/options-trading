/* The store — optimistic, offline, totally undoable. §8
 *
 *   "Every write lands in the UI immediately and queues. The network is never
 *    a reason you cannot log a trade at 09:34."
 *
 *   "⌘Z undoes deletes, grades, tag changes, and edits, with a toast
 *    confirming what was undone. Deletes are soft for 30 days. Consequently,
 *    confirmations are unnecessary."
 *
 * That last sentence is why undo here is *total* rather than per-feature:
 * the absence of confirmation dialogs everywhere in the product is only
 * defensible if every single mutation is reversible. So every mutation goes
 * through `mutate()`, which snapshots first.
 */

import { loadSnapshot, saveSnapshot, SnapshotConflictError } from './idb'
import type { DB } from '../domain/types'
import { buildSeed } from './seed'

export type SyncState = 'synced' | 'saving' | 'offline' | 'error' | 'stale'

interface UndoEntry {
  label: string
  before: DB
}

let db: DB = buildSeed()
let ready = false
let sync: SyncState = 'saving'
const undoStack: UndoEntry[] = []
const redoStack: UndoEntry[] = []
const MAX_UNDO = 60

type Listener = () => void
const listeners = new Set<Listener>()

interface StoreSnapshot {
  version: number
  db: DB
  ready: boolean
  sync: SyncState
}

let version = 0
let snapshotCache: StoreSnapshot = { version: -1, db, ready, sync }

export function subscribe(fn: Listener): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

function emit() {
  version += 1
  for (const fn of listeners) fn()
}

/** useSyncExternalStore requires a stable snapshot identity between changes. */
export function getSnapshot(): StoreSnapshot {
  if (snapshotCache.version !== version) {
    snapshotCache = { version, db, ready, sync }
  }
  return snapshotCache
}

export function getDB(): DB {
  return db
}

// ── Persistence ───────────────────────────────────────────────────────────

let saveTimer: ReturnType<typeof setTimeout> | null = null

// 250ms was right for IndexedDB. Over HTTP it would fire a request per keystroke
// in the notebook editor, so this is the one number the move to a server changes.
const PERSIST_DEBOUNCE_MS = 1_500

function schedulePersist() {
  sync = 'saving'
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    try {
      await saveSnapshot(db)
      sync = navigator.onLine ? 'synced' : 'offline'
    } catch (err) {
      // A conflict means another device moved first. Reloading is the honest
      // response: this client's base version is stale and pushing again would
      // clobber. Anything else is a plain write failure.
      sync = err instanceof SnapshotConflictError ? 'stale' : 'error'
    }
    emit()
  }, PERSIST_DEBOUNCE_MS)
}

/** True when boot found no snapshot on this device — i.e. this is the first
 *  run here. Read by App to decide where to land. It is a landing choice, not
 *  a tour: the Guide is a permanent surface either way. */
let firstRun = false

export function wasFirstRun(): boolean {
  return firstRun
}

export async function boot(): Promise<void> {
  const stored = await loadSnapshot<DB>()
  if (stored && stored.instruments?.length) {
    db = migrate(stored)
    firstRun = false
  } else {
    db = buildSeed()
    firstRun = true
    schedulePersist()
  }
  ready = true
  sync = navigator.onLine ? 'synced' : 'offline'
  purgeExpiredDeletes()
  emit()
}

/** §5.11 Schema edits are versioned so historical data is never silently
 *  re-interpreted. New fields are added with defaults; nothing is rewritten. */
function migrate(stored: DB): DB {
  const seed = buildSeed()
  return {
    ...seed,
    ...stored,
    settings: { ...seed.settings, ...stored.settings },
  }
}

// ── Mutation + undo ───────────────────────────────────────────────────────

function clone(value: DB): DB {
  return typeof structuredClone === 'function'
    ? structuredClone(value)
    : (JSON.parse(JSON.stringify(value)) as DB)
}

/** The single write path. `label` is what the undo toast will say. */
export function mutate(label: string, fn: (draft: DB) => void): void {
  const before = clone(db)
  const draft = clone(db)
  fn(draft)
  db = draft
  undoStack.push({ label, before })
  if (undoStack.length > MAX_UNDO) undoStack.shift()
  redoStack.length = 0
  schedulePersist()
  emit()
}

/** A write that must not be undoable — used only for settings that describe
 *  the viewport rather than the record (theme, density, sidebar state). */
export function mutateQuiet(fn: (draft: DB) => void): void {
  const draft = clone(db)
  fn(draft)
  db = draft
  schedulePersist()
  emit()
}

export function canUndo(): boolean {
  return undoStack.length > 0
}

export function undo(): string | null {
  const entry = undoStack.pop()
  if (!entry) return null
  redoStack.push({ label: entry.label, before: clone(db) })
  db = entry.before
  schedulePersist()
  emit()
  return entry.label
}

export function redo(): string | null {
  const entry = redoStack.pop()
  if (!entry) return null
  undoStack.push({ label: entry.label, before: clone(db) })
  db = entry.before
  schedulePersist()
  emit()
  return entry.label
}

export function peekUndoLabel(): string | null {
  return undoStack.length ? undoStack[undoStack.length - 1].label : null
}

// ── Soft delete ───────────────────────────────────────────────────────────
// §8 Deletes are soft for 30 days.

const THIRTY_DAYS = 30 * 86_400_000

function purgeExpiredDeletes() {
  const cutoff = Date.now() - THIRTY_DAYS
  const expired = db.trades.filter(
    (t) => t.deletedAt != null && t.deletedAt < cutoff,
  )
  if (!expired.length) return
  const ids = new Set(expired.map((t) => t.id))
  db = {
    ...db,
    trades: db.trades.filter((t) => !ids.has(t.id)),
    events: db.events.filter((e) => !e.tradeId || !ids.has(e.tradeId)),
  }
  schedulePersist()
}

export function setSyncState(s: SyncState) {
  sync = s
  emit()
}

if (typeof window !== 'undefined') {
  window.addEventListener('online', () => setSyncState('synced'))
  window.addEventListener('offline', () => setSyncState('offline'))
}
