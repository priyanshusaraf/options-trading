/* Actions — the only way the UI mutates anything.
 *
 * Business rules that the design document treats as structural live here, not
 * in components, so they cannot be bypassed by a new surface:
 *   · the thesis lock and its append-only consequence  (§0.1, §2.2.5)
 *   · risk-envelope breach and auto-tagging            (§2.2.4)
 *   · regime inheritance at trade timestamp            (§3.3)
 *   · mandatory setup attribution / off-book tracking  (§0.4)
 *   · no-thesis tagging                                (§1.2)
 */

import { deleteArtifactBytes } from './idb'
import { getDB, mutate } from './store'
import { uid } from '../domain/ids'
import { AUTO_MISTAKES } from '../domain/taxonomy'
import { realisedR } from '../domain/metrics'
import { today } from '../domain/dates'
import type {
  Append,
  Artifact,
  DateStr,
  Direction,
  Grade,
  ID,
  Level,
  NotebookDoc,
  PlaybookEntry,
  RegimeState,
  Scenario,
  ScenarioStatus,
  Session,
  Settings,
  StreamEvent,
  StreamEventKind,
  Trade,
} from '../domain/types'

export const sessionKey = (instrumentId: ID, date: DateStr) =>
  `${instrumentId}|${date}`

// ── Sessions ──────────────────────────────────────────────────────────────

export function ensureSession(instrumentId: ID, date: DateStr): Session {
  const db = getDB()
  const id = sessionKey(instrumentId, date)
  const found = db.sessions.find((s) => s.id === id)
  if (found) return found

  const now = Date.now()
  const fresh: Session = {
    id,
    instrumentId,
    date,
    thesis: '',
    scenarios: [],
    risk: { ...db.settings.defaultRisk },
    lockedAt: null,
    appends: [],
    review: null,
    createdAt: now,
    updatedAt: now,
  }
  mutate('create session', (d) => {
    if (!d.sessions.some((s) => s.id === id)) d.sessions.push(fresh)
  })
  return fresh
}

/** Pre-lock only. After the lock, the thesis is read-only and `appendToSession`
 *  is the only way to add to it. §0.1 */
export function setThesis(sessionId: ID, thesis: string): void {
  mutate('edit thesis', (d) => {
    const s = d.sessions.find((x) => x.id === sessionId)
    if (!s || s.lockedAt) return
    s.thesis = thesis
    s.updatedAt = Date.now()
  })
}

export function setRisk(sessionId: ID, risk: Session['risk']): void {
  mutate('set risk envelope', (d) => {
    const s = d.sessions.find((x) => x.id === sessionId)
    if (!s || s.lockedAt) return
    s.risk = risk
    s.updatedAt = Date.now()
  })
}

export function upsertScenario(sessionId: ID, scenario: Partial<Scenario> & { id?: ID }): void {
  mutate('edit scenario', (d) => {
    const s = d.sessions.find((x) => x.id === sessionId)
    if (!s || s.lockedAt) return
    if (scenario.id) {
      const existing = s.scenarios.find((x) => x.id === scenario.id)
      if (existing) Object.assign(existing, scenario)
      return
    }
    const letter = String.fromCharCode(65 + s.scenarios.length)
    s.scenarios.push({
      id: uid('sc'),
      letter,
      name: scenario.name ?? '',
      trigger: scenario.trigger ?? '',
      invalidation: scenario.invalidation ?? '',
      target: scenario.target ?? '',
      probability: scenario.probability ?? 0,
      status: 'pending',
    })
    s.updatedAt = Date.now()
  })
}

export function removeScenario(sessionId: ID, scenarioId: ID): void {
  mutate('remove scenario', (d) => {
    const s = d.sessions.find((x) => x.id === sessionId)
    if (!s || s.lockedAt) return
    s.scenarios = s.scenarios.filter((x) => x.id !== scenarioId)
    s.scenarios.forEach((sc, i) => (sc.letter = String.fromCharCode(65 + i)))
  })
}

/** §8 "Errors are directions." Returns the reason a lock cannot proceed,
 *  plus the field to jump the cursor to — never a bare validation failure. */
export interface LockBlocker {
  message: string
  scenarioId?: ID
  field?: string
}

export function lockBlockers(session: Session): LockBlocker[] {
  const out: LockBlocker[] = []
  if (!session.thesis.trim()) {
    out.push({ message: 'Can’t lock — the thesis is empty.', field: 'thesis' })
  }
  // §2.2.2 "You are gently required to enter at least two scenarios."
  if (session.scenarios.length < 2) {
    out.push({
      message: 'Can’t lock — a thesis needs at least two scenarios.',
      field: 'scenarios',
    })
  }
  for (const sc of session.scenarios) {
    if (!sc.name.trim()) {
      out.push({
        message: `Can’t lock — scenario ${sc.letter} has no name.`,
        scenarioId: sc.id, field: 'name',
      })
    }
    // The named example from §8, implemented literally.
    if (!sc.invalidation.trim() && sc.name.toLowerCase() !== 'chop, no trade') {
      out.push({
        message: `Can’t lock — scenario ${sc.letter} has no invalidation level.`,
        scenarioId: sc.id, field: 'invalidation',
      })
    }
  }
  return out
}

/** §2.2.5 The only confirmation dialog in the product. */
export function lockThesis(sessionId: ID): LockBlocker[] {
  const db = getDB()
  const session = db.sessions.find((s) => s.id === sessionId)
  if (!session) return [{ message: 'Session not found.' }]
  if (session.lockedAt) return []
  const blockers = lockBlockers(session)
  if (blockers.length) return blockers

  const now = Date.now()
  mutate('lock thesis', (d) => {
    const s = d.sessions.find((x) => x.id === sessionId)!
    s.lockedAt = now
    s.updatedAt = now
    d.events.push({
      id: uid('ev'),
      sessionId,
      instrumentId: s.instrumentId,
      at: now,
      kind: 'thesis-lock',
      text: 'thesis locked',
      tags: [],
    })
  })
  return []
}

/** §0.1 "You can append, never revise." */
export function appendToSession(sessionId: ID, text: string): void {
  if (!text.trim()) return
  const entry: Append = { id: uid('ap'), at: Date.now(), text: text.trim() }
  mutate('append to thesis', (d) => {
    const s = d.sessions.find((x) => x.id === sessionId)
    if (!s) return
    s.appends.push(entry)
    s.updatedAt = entry.at
  })
}

/** §2.3 Doing this live is far more honest than doing it at 16:00. */
export function resolveScenario(
  sessionId: ID,
  scenarioId: ID,
  status: ScenarioStatus,
): void {
  mutate('resolve scenario', (d) => {
    const s = d.sessions.find((x) => x.id === sessionId)
    const sc = s?.scenarios.find((x) => x.id === scenarioId)
    if (!s || !sc) return
    sc.status = status
    sc.resolvedAt = Date.now()
    d.events.push({
      id: uid('ev'),
      sessionId,
      instrumentId: s.instrumentId,
      at: Date.now(),
      kind: 'scenario',
      text: `scenario ${sc.letter} · ${status}`,
      scenarioId,
      tags: [],
    })
  })
}

/** §2.4.1 Did the scenario that hit actually pay? Reading the market right
 *  and making money are different claims. */
export function setScenarioPaid(sessionId: ID, scenarioId: ID, paid: boolean) {
  mutate('mark scenario paid', (d) => {
    const sc = d.sessions
      .find((x) => x.id === sessionId)
      ?.scenarios.find((x) => x.id === scenarioId)
    if (sc) sc.paid = paid
  })
}

// ── Review ────────────────────────────────────────────────────────────────

export function updateReview(
  sessionId: ID,
  patch: Partial<NonNullable<Session['review']>>,
): void {
  mutate('update review', (d) => {
    const s = d.sessions.find((x) => x.id === sessionId)
    if (!s) return
    s.review = {
      reconciled: false,
      oneLineForTomorrow: '',
      notes: '',
      completedAt: null,
      step: 1,
      ...s.review,
      ...patch,
    }
    s.updatedAt = Date.now()
  })
}

/** §2.4.5 "Nothing else about the review is required; this is." */
export function completeReview(sessionId: ID): string | null {
  const db = getDB()
  const s = db.sessions.find((x) => x.id === sessionId)
  if (!s) return 'Session not found.'
  if (!s.review?.oneLineForTomorrow.trim()) {
    return 'One line for tomorrow is required to close the review.'
  }
  mutate('complete review', (d) => {
    const target = d.sessions.find((x) => x.id === sessionId)!
    target.review!.completedAt = Date.now()
    target.review!.step = 5
  })
  return null
}

// ── Trades ────────────────────────────────────────────────────────────────

export interface NewTradeInput {
  instrumentId: ID
  date: DateStr
  direction: Direction
  contract: Trade['contract']
  strike?: number
  optionType?: Trade['optionType']
  qty: number
  price: number
  stop?: number
  target?: number
  setupId: ID | null
  offBook: boolean
  confidence: number
  emotionAtEntry?: string
  entryNote?: string
}

/** §2.2.4 The envelope is a commitment device: when breached, the Cockpit
 *  turns amber and every new trade gets auto-tagged `over-limit`. */
export interface RiskStatus {
  tradesUsed: number
  rUsed: number
  openCount: number
  breached: boolean
  reasons: string[]
}

export function riskStatus(sessionId: ID): RiskStatus {
  const db = getDB()
  const session = db.sessions.find((s) => s.id === sessionId)
  const inst = db.instruments.find((i) => i.id === session?.instrumentId)
  const trades = db.trades.filter((t) => t.sessionId === sessionId && !t.deletedAt)
  const rUsed = inst
    ? trades.reduce((a, t) => a + (realisedR(t, inst) ?? 0), 0)
    : 0
  const openCount = trades.filter((t) => t.closedAt == null).length
  const reasons: string[] = []
  if (session) {
    if (trades.length >= session.risk.maxTrades) reasons.push('max trades reached')
    if (rUsed <= session.risk.maxLossR) reasons.push('max loss reached')
    if (openCount >= session.risk.maxConcurrent) reasons.push('max concurrent positions')
  }
  return {
    tradesUsed: trades.length,
    rUsed,
    openCount,
    breached: reasons.length > 0,
    reasons,
  }
}

export function addTrade(input: NewTradeInput): ID {
  const db = getDB()
  const sessionId = sessionKey(input.instrumentId, input.date)
  ensureSession(input.instrumentId, input.date)
  const session = getDB().sessions.find((s) => s.id === sessionId)!
  const now = Date.now()
  const id = uid('tr')

  // §3.3 The trade inherits the regime active at its timestamp.
  const log = db.regimeLog
    .filter((r) => r.instrumentId === input.instrumentId)
    .sort((a, b) => a.at - b.at)
  let regime: RegimeState | null = null
  for (const entry of log) if (entry.at <= now) regime = entry.state

  const autoTags: string[] = []
  // §1.2 A trade with no pre-commitment is not an error — it is logged and
  // tagged, which is a statistic you will eventually want to see.
  if (!session.lockedAt) autoTags.push(AUTO_MISTAKES.noThesis)
  if (input.offBook) autoTags.push(AUTO_MISTAKES.offBook)
  const risk = riskStatus(sessionId)
  if (risk.breached) autoTags.push(AUTO_MISTAKES.overLimit)

  const trade: Trade = {
    id,
    instrumentId: input.instrumentId,
    sessionId,
    date: input.date,
    direction: input.direction,
    contract: input.contract,
    strike: input.strike,
    optionType: input.optionType,
    qty: input.qty,
    legs: [
      { id: uid('lg'), at: now, side: 'entry', price: input.price, qty: input.qty, fees: 0 },
    ],
    openedAt: now,
    closedAt: null,
    entryNote: input.entryNote ?? '',
    // BELIEF locks at entry. There is no grace window. §11.5
    entryNoteLockedAt: now,
    confidence: input.confidence,
    plannedStop: input.stop,
    plannedTarget: input.target,
    emotionAtEntry: input.emotionAtEntry,
    setupId: input.setupId,
    offBook: input.offBook,
    regime,
    grade: null,
    takeAgain: null,
    executionScore: null,
    exitNote: '',
    lesson: '',
    mistakes: [],
    emotions: input.emotionAtEntry ? [input.emotionAtEntry] : [],
    mfeR: null,
    maeR: null,
    mfeSource: 'manual',
    tags: [],
    artifactIds: [],
    autoTags,
    createdAt: now,
    updatedAt: now,
    deletedAt: null,
  }

  mutate('log trade', (d) => {
    d.trades.push(trade)
    d.events.push({
      id: uid('ev'),
      sessionId,
      instrumentId: input.instrumentId,
      at: now,
      kind: 'trade',
      text: `${input.direction === 'long' ? '▲' : '▼'} ${input.qty} @ ${input.price}`,
      tradeId: id,
      tags: [],
    })
    if (risk.breached) {
      d.events.push({
        id: uid('ev'),
        sessionId,
        instrumentId: input.instrumentId,
        at: now,
        kind: 'limit-breach',
        text: `risk envelope breached — ${risk.reasons.join(', ')}`,
        tags: [],
      })
    }
  })
  return id
}

export function closeTrade(tradeId: ID, price: number, fees = 0): void {
  const now = Date.now()
  mutate('close trade', (d) => {
    const t = d.trades.find((x) => x.id === tradeId)
    if (!t || t.closedAt) return
    t.legs.push({ id: uid('lg'), at: now, side: 'exit', price, qty: t.qty, fees })
    t.closedAt = now
    t.updatedAt = now
    d.events.push({
      id: uid('ev'),
      sessionId: t.sessionId,
      instrumentId: t.instrumentId,
      at: now,
      kind: 'fill',
      text: `exit ${t.qty} @ ${price}`,
      tradeId,
      tags: [],
    })
  })
}

/** JUDGEMENT layer — freely editable forever. §3.2 */
export function updateTradeJudgement(
  tradeId: ID,
  patch: Partial<
    Pick<
      Trade,
      | 'grade' | 'takeAgain' | 'executionScore' | 'exitNote' | 'lesson'
      | 'mistakes' | 'emotions' | 'emotionAtExit' | 'mfeR' | 'maeR' | 'tags'
    >
  >,
): void {
  mutate('edit trade', (d) => {
    const t = d.trades.find((x) => x.id === tradeId)
    if (!t) return
    Object.assign(t, patch)
    t.updatedAt = Date.now()
  })
}

/** §5.3 ⌘1–5 grades the current selection in bulk. */
export function gradeTrades(ids: ID[], grade: Grade): void {
  mutate(`grade ${ids.length} trade${ids.length > 1 ? 's' : ''}`, (d) => {
    for (const t of d.trades) {
      if (ids.includes(t.id)) {
        t.grade = grade
        t.updatedAt = Date.now()
      }
    }
  })
}

export function tagTrades(ids: ID[], tag: string, kind: 'tag' | 'mistake' | 'emotion') {
  mutate(`add ${kind}`, (d) => {
    for (const t of d.trades) {
      if (!ids.includes(t.id)) continue
      const list = kind === 'tag' ? t.tags : kind === 'mistake' ? t.mistakes : t.emotions
      if (!list.includes(tag)) list.push(tag)
      t.updatedAt = Date.now()
    }
  })
}

export function untagTrade(id: ID, tag: string, kind: 'tag' | 'mistake' | 'emotion') {
  mutate(`remove ${kind}`, (d) => {
    const t = d.trades.find((x) => x.id === id)
    if (!t) return
    if (kind === 'tag') t.tags = t.tags.filter((x) => x !== tag)
    if (kind === 'mistake') t.mistakes = t.mistakes.filter((x) => x !== tag)
    if (kind === 'emotion') t.emotions = t.emotions.filter((x) => x !== tag)
    t.updatedAt = Date.now()
  })
}

/** §8 Deletes are soft for 30 days. */
export function deleteTrades(ids: ID[]): void {
  mutate(`delete ${ids.length} trade${ids.length > 1 ? 's' : ''}`, (d) => {
    for (const t of d.trades) {
      if (ids.includes(t.id)) t.deletedAt = Date.now()
    }
  })
}

export function restoreTrades(ids: ID[]): void {
  mutate('restore trade', (d) => {
    for (const t of d.trades) if (ids.includes(t.id)) t.deletedAt = null
  })
}

// ── Stream ────────────────────────────────────────────────────────────────

export function addStreamEvent(
  input: Omit<StreamEvent, 'id' | 'at'> & { at?: number },
): ID {
  const id = uid('ev')
  const event: StreamEvent = { ...input, id, at: input.at ?? Date.now() }
  mutate(input.inbox ? 'quick capture' : `add ${input.kind}`, (d) => {
    d.events.push(event)
  })
  return id
}

export function observe(
  sessionId: ID,
  instrumentId: ID,
  text: string,
  kind: StreamEventKind = 'observation',
): ID | null {
  if (!text.trim()) return null
  return addStreamEvent({
    sessionId, instrumentId, kind, text: text.trim(), tags: [],
  })
}

/** §4.4 Triage moves an inbox item into the day proper. */
export function triageEvent(eventId: ID, keep: boolean): void {
  mutate(keep ? 'triage to session' : 'dismiss capture', (d) => {
    const e = d.events.find((x) => x.id === eventId)
    if (!e) return
    if (keep) e.inbox = false
    else d.events = d.events.filter((x) => x.id !== eventId)
  })
}

export function reparentEvent(eventId: ID, tradeId: ID | null): void {
  mutate('re-parent to trade', (d) => {
    const e = d.events.find((x) => x.id === eventId)
    if (e) e.tradeId = tradeId ?? undefined
  })
}

export function deleteEvent(eventId: ID): void {
  mutate('delete stream event', (d) => {
    d.events = d.events.filter((x) => x.id !== eventId)
  })
}

// ── Levels ────────────────────────────────────────────────────────────────

export function addLevel(
  instrumentId: ID,
  price: number,
  type: Level['type'],
  source: string,
): void {
  mutate('add level', (d) => {
    d.levels.push({
      id: uid('lv'), instrumentId, price, type, source,
      createdAt: Date.now(), held: 0, broken: 0, active: true,
    })
  })
}

/** §2.2.3 Levels accumulate a "times respected / times broken" counter
 *  automatically as you tag them. */
export function tagLevel(levelId: ID, outcome: 'held' | 'broken'): void {
  mutate(`level ${outcome}`, (d) => {
    const lv = d.levels.find((x) => x.id === levelId)
    if (!lv) return
    if (outcome === 'held') {
      lv.held++
      lv.lastTouchedAt = Date.now()
    } else {
      lv.broken++
      lv.brokenAt = Date.now()
      lv.lastTouchedAt = Date.now()
    }
  })
}

export function removeLevel(levelId: ID): void {
  mutate('remove level', (d) => {
    d.levels = d.levels.filter((x) => x.id !== levelId)
  })
}

// ── Playbook ──────────────────────────────────────────────────────────────

export function upsertPlaybook(entry: Partial<PlaybookEntry> & { id?: ID }): ID {
  const id = entry.id ?? uid('pb')
  mutate(entry.id ? 'edit setup' : 'add setup', (d) => {
    const existing = d.playbook.find((p) => p.id === id)
    if (existing) {
      // §5.6 An edit history, so you can see when you changed the rules and
      // whether it helped.
      for (const field of ['definition', 'entryTrigger', 'invalidation'] as const) {
        const next = entry[field]
        if (typeof next === 'string' && next !== existing[field]) {
          existing.revisions.push({
            at: Date.now(), field, from: existing[field], to: next, why: '',
          })
        }
      }
      Object.assign(existing, entry)
      return
    }
    d.playbook.push({
      id,
      shortcut: entry.shortcut ?? d.playbook.length + 1,
      code: entry.code ?? 'new',
      name: entry.name ?? 'New setup',
      instrumentIds: entry.instrumentIds ?? [],
      definition: entry.definition ?? '',
      entryTrigger: entry.entryTrigger ?? '',
      invalidation: entry.invalidation ?? '',
      typicalR: entry.typicalR ?? 1,
      regimes: entry.regimes ?? [],
      createdAt: Date.now(),
      revisions: [],
      archived: false,
    })
  })
  return id
}

export function archivePlaybook(id: ID, archived = true): void {
  mutate(archived ? 'archive setup' : 'restore setup', (d) => {
    const p = d.playbook.find((x) => x.id === id)
    if (p) p.archived = archived
  })
}

// ── Notebook ──────────────────────────────────────────────────────────────

export function updateDoc(docId: ID, body: string): void {
  mutate('edit note', (d) => {
    const doc = d.docs.find((x) => x.id === docId)
    if (!doc) return
    // §5.2 Version history you can scrub. Only snapshot on meaningful change,
    // otherwise every keystroke becomes a version.
    const last = doc.versions[doc.versions.length - 1]
    if (!last || Math.abs(last.body.length - doc.body.length) > 40) {
      doc.versions.push({ at: doc.updatedAt, body: doc.body })
      if (doc.versions.length > 50) doc.versions.shift()
    }
    doc.body = body
    doc.updatedAt = Date.now()
  })
}

export function createDoc(instrumentId: ID, title: string, parentId: ID | null = null): ID {
  const id = uid('doc')
  mutate('create note', (d) => {
    const doc: NotebookDoc = {
      id, instrumentId, title, parentId,
      order: d.docs.filter((x) => x.instrumentId === instrumentId).length,
      body: '', updatedAt: Date.now(), createdAt: Date.now(),
      versions: [], backlinks: [], seeded: false,
    }
    d.docs.push(doc)
  })
  return id
}

export function deleteDoc(docId: ID): void {
  mutate('delete note', (d) => {
    const doc = d.docs.find((x) => x.id === docId)
    if (!doc || doc.seeded) return
    d.docs = d.docs.filter((x) => x.id !== docId)
  })
}

/** §5.2 ⌘⇧P promotes a block from a session note into an evergreen doc,
 *  carrying a backlink to the session it came from. This is the mechanic that
 *  makes the notebook fill itself. */
export function promoteToDoc(
  docId: ID,
  text: string,
  origin: { kind: 'session' | 'trade'; id: ID; label: string },
): void {
  mutate('promote to notebook', (d) => {
    const doc = d.docs.find((x) => x.id === docId)
    if (!doc) return
    doc.versions.push({ at: doc.updatedAt, body: doc.body })
    doc.body = `${doc.body.trimEnd()}\n\n${text.trim()}\n`
    doc.updatedAt = Date.now()
    if (!doc.backlinks.some((b) => b.id === origin.id)) {
      doc.backlinks.push({ ...origin, at: Date.now() })
    }
  })
}

export function restoreDocVersion(docId: ID, index: number): void {
  mutate('restore note version', (d) => {
    const doc = d.docs.find((x) => x.id === docId)
    const v = doc?.versions[index]
    if (!doc || !v) return
    doc.versions.push({ at: doc.updatedAt, body: doc.body })
    doc.body = v.body
    doc.updatedAt = Date.now()
  })
}

// ── Regime ────────────────────────────────────────────────────────────────

export function setRegime(instrumentId: ID, state: RegimeState, note: string): void {
  mutate('change regime', (d) => {
    d.regimeLog.push({ id: uid('rg'), instrumentId, state, at: Date.now(), note })
    const sessionId = sessionKey(instrumentId, today())
    if (d.sessions.some((s) => s.id === sessionId)) {
      d.events.push({
        id: uid('ev'), sessionId, instrumentId, at: Date.now(),
        kind: 'regime-change', text: `regime → ${state}`, tags: [],
      })
    }
  })
}

// ── Artifacts ─────────────────────────────────────────────────────────────

export function addArtifact(
  // `id` is optional so the caller can mint it FIRST, upload the bytes under
  // it, and only then record the artifact — see Vault.onFiles. The bytes live
  // in their own table rather than inside the snapshot blob (design spec §3.2).
  a: Omit<Artifact, 'id' | 'at'> & { at?: number; id?: ID },
): ID {
  const id = a.id ?? uid('af')
  const at = a.at ?? Date.now()
  mutate('add screenshot', (d) => {
    d.artifacts.push({ ...a, id, at })
    if (a.sessionId) {
      d.events.push({
        id: uid('ev'), sessionId: a.sessionId, instrumentId: a.instrumentId,
        at, kind: 'screenshot', text: a.name, artifactId: id,
        tradeId: a.tradeId ?? undefined, tags: [],
      })
    }
    // §2.3 If a trade is open, it auto-associates with that trade.
    if (a.tradeId) {
      const t = d.trades.find((x) => x.id === a.tradeId)
      if (t && !t.artifactIds.includes(id)) t.artifactIds.push(id)
    }
  })
  return id
}

/** §2.3 …and can be re-parented later by drag. */
export function reparentArtifact(artifactId: ID, tradeId: ID | null): void {
  mutate('re-parent screenshot', (d) => {
    const a = d.artifacts.find((x) => x.id === artifactId)
    if (!a) return
    for (const t of d.trades) {
      t.artifactIds = t.artifactIds.filter((x) => x !== artifactId)
    }
    a.tradeId = tradeId
    if (tradeId) {
      const t = d.trades.find((x) => x.id === tradeId)
      if (t) t.artifactIds.push(artifactId)
    }
  })
}

export function tagArtifact(artifactId: ID, tag: string): void {
  mutate('tag screenshot', (d) => {
    const a = d.artifacts.find((x) => x.id === artifactId)
    if (a && !a.tags.includes(tag)) a.tags.push(tag)
  })
}

export function deleteArtifact(artifactId: ID): void {
  mutate('delete screenshot', (d) => {
    d.artifacts = d.artifacts.filter((x) => x.id !== artifactId)
    d.events = d.events.filter((e) => e.artifactId !== artifactId)
    for (const t of d.trades) {
      t.artifactIds = t.artifactIds.filter((x) => x !== artifactId)
    }
  })
  // Fire-and-forget, deliberately NOT awaited and NOT inside the mutate
  // closure: mutate() is synchronous and the record change must stay undoable.
  // ⌘Z restores the record; if the bytes were already deleted the thumbnail
  // will not resolve. An orphaned blob is cheap and its id is never reused, so
  // leaving them is the lesser failure.
  void deleteArtifactBytes(artifactId)
}

// ── Saved queries ─────────────────────────────────────────────────────────

export function saveQuery(name: string, query: string, pinned = true): void {
  mutate('save query', (d) => {
    d.savedQueries.push({ id: uid('sq'), name, query, pinned, createdAt: Date.now() })
  })
}

export function deleteQuery(id: ID): void {
  mutate('delete saved query', (d) => {
    d.savedQueries = d.savedQueries.filter((q) => q.id !== id)
  })
}

// ── Period reviews ────────────────────────────────────────────────────────

export function upsertPeriodReview(
  kind: 'weekly' | 'monthly',
  periodStart: DateStr,
  instrumentId: ID | null,
  body: string,
): void {
  mutate('edit review', (d) => {
    const found = d.periodReviews.find(
      (r) => r.kind === kind && r.periodStart === periodStart && r.instrumentId === instrumentId,
    )
    if (found) {
      found.body = body
      found.updatedAt = Date.now()
      return
    }
    d.periodReviews.push({
      id: uid('pr'), kind, periodStart, instrumentId, body,
      createdAt: Date.now(), updatedAt: Date.now(),
    })
  })
}

// ── Settings ──────────────────────────────────────────────────────────────

export function updateSettings(patch: Partial<Settings>): void {
  mutate('change settings', (d) => {
    Object.assign(d.settings, patch)
  })
}

export function updateInstrument(id: ID, patch: Partial<Session['instrumentId']> | Record<string, unknown>): void {
  mutate('edit instrument', (d) => {
    const inst = d.instruments.find((i) => i.id === id)
    if (inst) Object.assign(inst, patch)
  })
}

export function reorderInstruments(orderedIds: ID[]): void {
  mutate('reorder instruments', (d) => {
    orderedIds.forEach((id, i) => {
      const inst = d.instruments.find((x) => x.id === id)
      if (inst) inst.order = i
    })
  })
}

export function addTaxonomyItem(kind: 'mistakes' | 'emotions', label: string): void {
  mutate('add taxonomy item', (d) => {
    const list = d.settings[kind]
    if (list.some((x) => x.label === label)) return
    list.push({ id: label, label, retired: false })
  })
}

/** Retire rather than delete: historical rows must stay resolvable. §5.11 */
export function retireTaxonomyItem(kind: 'mistakes' | 'emotions', id: ID): void {
  mutate('retire taxonomy item', (d) => {
    const item = d.settings[kind].find((x) => x.id === id)
    if (item) item.retired = !item.retired
  })
}
