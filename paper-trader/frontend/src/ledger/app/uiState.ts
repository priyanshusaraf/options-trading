/* Ephemeral UI state: route, selection, overlays, mode.
 *
 * Kept out of the record store on purpose — none of this is journal data, and
 * ⌘Z must never undo a panel toggle. §8 "Undo is total" applies to the record,
 * not to the viewport.
 */

import { useSyncExternalStore } from 'react'
import type { ID, Mode } from '../domain/types'
import { today } from '../domain/dates'
import { getDB } from '../data/store'
import { reorderInstruments } from '../data/actions'

export type Surface =
  | 'cockpit'
  | 'notebook'
  | 'blotter'
  | 'trade'
  | 'timeline'
  | 'playbook'
  | 'stats'
  | 'review'
  | 'vault'
  | 'search'
  | 'settings'
  | 'inbox'
  | 'weekly'
  | 'guide'

export interface Route {
  surface: Surface
  instrumentId: ID
  date: string
  /** Selected object for detail surfaces. */
  objectId?: ID
  /** Blotter/search query text. */
  query?: string
  /** Timeline zoom. §5.5 */
  zoom?: 'year' | 'month' | 'day'
}

export type OverlayKind =
  | null
  | 'palette'
  | 'capture'
  | 'shortcuts'
  | 'confirm-lock'
  | 'instrument-switcher'
  | 'peek'
  | 'ticket'
  | 'drawer'
  | 'walkthrough'

export interface Toast {
  id: number
  text: string
  /** §8 Toast is always undoable. */
  undoable: boolean
  at: number
}

export interface UIState {
  route: Route
  /** Split pane — the two comparisons that actually matter. §4.1 */
  split: Route | null
  focusedPane: 'primary' | 'split'
  history: Route[]
  future: Route[]
  mode: Mode
  /** User override of the session-clock suggestion. §2.1 */
  modeManual: boolean
  sidebarOpen: boolean
  inspectorOpen: boolean
  /** Blotter selection, used by bulk grade/tag. §5.3 */
  selection: ID[]
  cursorId: ID | null
  overlay: OverlayKind
  overlayArg?: unknown
  peekId: ID | null
  toasts: Toast[]
  /** `g`-prefix pending. §4.2 */
  pendingPrefix: string | null
  /** §2.1 P&L reveal, ⌘E. Live mode collapses it by default. */
  pnlRevealed: boolean
  drawer: { kind: string; arg?: unknown } | null
}

const initial: UIState = {
  route: { surface: 'cockpit', instrumentId: 'bnf', date: today(), zoom: 'month' },
  split: null,
  focusedPane: 'primary',
  history: [],
  future: [],
  mode: 'prep',
  modeManual: false,
  sidebarOpen: true,
  inspectorOpen: false,
  selection: [],
  cursorId: null,
  overlay: null,
  peekId: null,
  toasts: [],
  pendingPrefix: null,
  pnlRevealed: true,
  drawer: null,
}

let state: UIState = initial
const listeners = new Set<() => void>()

function emit() {
  state = { ...state }
  for (const fn of listeners) fn()
}

export function subscribeUI(fn: () => void) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function getUI(): UIState {
  return state
}

export function useUI(): UIState {
  return useSyncExternalStore(subscribeUI, getUI, getUI)
}

export function setUI(patch: Partial<UIState>) {
  state = { ...state, ...patch }
  emit()
}

// ── Navigation ────────────────────────────────────────────────────────────
// §4.2 Back/forward traverse full navigation history.

export function navigate(patch: Partial<Route>, opts: { replace?: boolean } = {}) {
  const next = { ...state.route, ...patch }
  if (opts.replace) {
    state = { ...state, route: next }
  } else {
    state = {
      ...state,
      route: next,
      history: [...state.history, state.route].slice(-100),
      future: [],
      // Selection is per-surface; carrying it across is always wrong.
      selection: patch.surface && patch.surface !== state.route.surface ? [] : state.selection,
    }
  }
  emit()
}

/** §4.3 ⌘⏎ on any result opens it in the split pane instead of the current one. */
export function navigateSplit(patch: Partial<Route>) {
  const base = state.split ?? state.route
  state = { ...state, split: { ...base, ...patch }, focusedPane: 'split' }
  emit()
}

export function closeSplit() {
  state = { ...state, split: null, focusedPane: 'primary' }
  emit()
}

export function toggleSplit() {
  if (state.split) return closeSplit()
  // §4.1 The default split is the comparison that matters on this surface.
  const r = state.route
  const companion: Route =
    r.surface === 'cockpit'
      ? { ...r, surface: 'review' }
      : r.surface === 'trade'
        ? { ...r, surface: 'cockpit' }
        : { ...r }
  state = { ...state, split: companion, focusedPane: 'split' }
  emit()
}

export function back() {
  const prev = state.history[state.history.length - 1]
  if (!prev) return
  state = {
    ...state,
    route: prev,
    history: state.history.slice(0, -1),
    future: [state.route, ...state.future].slice(0, 100),
  }
  emit()
}

export function forward() {
  const next = state.future[0]
  if (!next) return
  state = {
    ...state,
    route: next,
    history: [...state.history, state.route],
    future: state.future.slice(1),
  }
  emit()
}

// ── Overlays ──────────────────────────────────────────────────────────────

export function openOverlay(kind: OverlayKind, arg?: unknown) {
  state = { ...state, overlay: kind, overlayArg: arg }
  emit()
}

export function closeOverlay() {
  state = { ...state, overlay: null, overlayArg: undefined }
  emit()
}

export function openDrawer(kind: string, arg?: unknown) {
  state = { ...state, drawer: { kind, arg } }
  emit()
}

export function closeDrawer() {
  state = { ...state, drawer: null }
  emit()
}

/** §8 space peeks; peek dismisses on any nav. */
export function peek(id: ID | null) {
  state = { ...state, peekId: id }
  emit()
}

// ── Toasts ────────────────────────────────────────────────────────────────
// §6.5 bottom-left, 4s, always undoable.

let toastSeq = 0

export function toast(text: string, undoable = false) {
  const t: Toast = { id: ++toastSeq, text, undoable, at: Date.now() }
  state = { ...state, toasts: [...state.toasts, t] }
  emit()
  setTimeout(() => dismissToast(t.id), 4000)
}

export function dismissToast(id: number) {
  state = { ...state, toasts: state.toasts.filter((t) => t.id !== id) }
  emit()
}

// ── Selection ─────────────────────────────────────────────────────────────

export function setSelection(ids: ID[]) {
  state = { ...state, selection: ids }
  emit()
}

export function toggleSelected(id: ID) {
  const has = state.selection.includes(id)
  state = {
    ...state,
    selection: has
      ? state.selection.filter((x) => x !== id)
      : [...state.selection, id],
  }
  emit()
}

export function setCursor(id: ID | null) {
  state = { ...state, cursorId: id }
  emit()
}

// ── Mode ──────────────────────────────────────────────────────────────────

export function setMode(mode: Mode, manual = true) {
  state = {
    ...state,
    mode,
    modeManual: manual,
    // §2.1 Live mode collapses P&L to a single glyph unless expanded.
    pnlRevealed: mode === 'live' ? false : state.pnlRevealed,
  }
  emit()
}

export function togglePnl() {
  state = { ...state, pnlRevealed: !state.pnlRevealed }
  emit()
}

export function setPrefix(prefix: string | null) {
  state = { ...state, pendingPrefix: prefix }
  emit()
}

/** §4.1 Rail reordering is drag; the order is yours and persists — so it
 *  writes through to the record store rather than living in UI state. */
export function reorderRail(draggedId: ID, targetId: ID) {
  const db = getDB()
  const ordered = [...db.instruments].sort((a, b) => a.order - b.order).map((i) => i.id)
  const from = ordered.indexOf(draggedId)
  const to = ordered.indexOf(targetId)
  if (from < 0 || to < 0) return
  ordered.splice(from, 1)
  ordered.splice(to, 0, draggedId)
  reorderInstruments(ordered)
}
