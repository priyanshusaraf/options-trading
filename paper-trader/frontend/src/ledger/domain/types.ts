/* Entity model — §3.1, §3.2
 *
 * The organising idea of this file is §3.2: three data layers kept
 * structurally distinct, because conflating them is how journals lie.
 *
 *   BELIEF     locked at commit, append-only after
 *   FACT       immutable, ideally broker-sourced
 *   JUDGEMENT  freely editable forever
 *
 * Each field group below is annotated with its layer. The UI reads these
 * annotations through the material system: belief and judgement render on
 * paper, fact renders on glass.
 */

export type ID = string
/** ISO date, no time: `2026-07-29`. The day is the atomic unit. §0.7 */
export type DateStr = string
/** Epoch milliseconds. */
export type Timestamp = number

// ── Instrument ────────────────────────────────────────────────────────────
// §0.3 The instrument is a workspace, not a filter.
// §1.4 In the real workstation these objects come from the shared instrument
// registry. The journal never maintains its own list — here we seed a local
// registry that a host shell would replace.

export type InstrumentKind = 'index-fno' | 'commodity' | 'equity' | 'fx'

export interface SessionHours {
  /** IST, 24h `HH:MM`. §2.1 the mode engine is per-instrument. */
  open: string
  close: string
}

export interface Instrument {
  id: ID
  /** Ticker abbreviation shown in the 48px rail. §4.1 */
  code: string
  name: string
  kind: InstrumentKind
  lotSize: number
  tick: number
  hours: SessionHours
  /** Rail order is yours and persists. §4.1 */
  order: number
  /** §11.2 — R is defined once, per instrument, and never mixed. */
  rBasis: RBasis
  /** Rupee risk per trade when rBasis is 'fixed-rupee'. */
  fixedRisk?: number
  /** Account equity used when rBasis is 'account-pct'. */
  accountEquity?: number
  accountRiskPct?: number
}

/** §11.2 R definition. One thing, chosen per instrument, versioned by settings. */
export type RBasis = 'initial-stop' | 'fixed-rupee' | 'account-pct'

// ── Regime ────────────────────────────────────────────────────────────────
// §3.3 A small state machine you set manually. Every trade inherits the
// regime active at its timestamp, which makes "my ORB setup only works in
// expansion" a query rather than a hunch.

export type RegimeState =
  | 'trending'
  | 'range'
  | 'expansion'
  | 'compression'
  | 'event-driven'

export interface RegimeChange {
  id: ID
  instrumentId: ID
  state: RegimeState
  at: Timestamp
  /** Why. A dated log, not just a current value. §5.2 */
  note: string
}

// ── Levels ────────────────────────────────────────────────────────────────
// §2.2.3 Levels persist across sessions and accumulate a respect counter.

export type LevelType = 'supply' | 'demand' | 'pivot' | 'vwap' | 'gap'

export interface Level {
  id: ID
  instrumentId: ID
  price: number
  type: LevelType
  /** Where it came from — "prev day high", "weekly VAH". */
  source: string
  createdAt: Timestamp
  /** More decision-relevant than the price alone. §5.1 */
  held: number
  broken: number
  lastTouchedAt?: Timestamp
  brokenAt?: Timestamp
  active: boolean
}

// ── Playbook ──────────────────────────────────────────────────────────────
// §0.4 Setups are hypotheses with sample sizes.
// §5.6 A setup you cannot define in two sentences is not a setup, it is a mood.

export interface PlaybookEntry {
  id: ID
  /** Single-keystroke shortlist position 1–9; 0 is reserved for off-book. §2.3 */
  shortcut: number
  /** Shortcode used by the ticket grammar. §9.6 */
  code: string
  name: string
  instrumentIds: ID[]
  definition: string
  entryTrigger: string
  invalidation: string
  typicalR: number
  /** The market regime it needs. §3.3 */
  regimes: RegimeState[]
  createdAt: Timestamp
  /** So you can see when you changed the rules and whether it helped. §5.6 */
  revisions: PlaybookRevision[]
  archived: boolean
}

export interface PlaybookRevision {
  at: Timestamp
  field: string
  from: string
  to: string
  why: string
}

// ── Session ───────────────────────────────────────────────────────────────
// §3.1 One per date. Everything hangs off it, which is why the timeline is
// free — it is the primary key rendered.

export type Mode = 'prep' | 'live' | 'review'

export interface Session {
  id: ID
  instrumentId: ID
  date: DateStr
  /** BELIEF — markdown, becomes read-only at lock. */
  thesis: string
  /** BELIEF — locked at commit, append-only after. */
  scenarios: Scenario[]
  /** BELIEF — the commitment device. §2.2.4 */
  risk: RiskEnvelope
  /** The lock stamp. Null until committed. §2.2.5 */
  lockedAt: Timestamp | null
  /** Appends after the lock. Never revisions. §0.1 */
  appends: Append[]
  /** JUDGEMENT — filled during Session Review. §2.4 */
  review: SessionReview | null
  createdAt: Timestamp
  updatedAt: Timestamp
}

export interface Append {
  id: ID
  at: Timestamp
  text: string
}

export type ScenarioStatus =
  | 'pending'
  | 'playing-out'
  | 'invalidated'
  | 'hit'
  | 'missed'

export interface Scenario {
  id: ID
  /** A · B · C — the letter shown in the stream header and bound to ⌥1/2/3. */
  letter: string
  name: string
  trigger: string
  /** Required to lock. "Can't lock — scenario B has no invalidation." §8 */
  invalidation: string
  target: string
  probability: number
  status: ScenarioStatus
  resolvedAt?: Timestamp
  /** §2.4.1 did the hit actually pay? Reading right and earning are different. */
  paid?: boolean
}

export interface RiskEnvelope {
  maxTrades: number
  maxLossR: number
  maxConcurrent: number
}

// ── Stream ────────────────────────────────────────────────────────────────
// §2.3 A single reverse-chronological column. The day's black box recorder.
// Append-only event log. §3.4

export type StreamEventKind =
  | 'session-open'
  | 'observation'
  | 'trade'
  | 'fill'
  | 'screenshot'
  | 'scenario'
  | 'limit-breach'
  | 'thesis-lock'
  | 'note'
  | 'question'
  | 'mistake-note'
  | 'regime-change'

export interface StreamEvent {
  id: ID
  sessionId: ID
  instrumentId: ID
  at: Timestamp
  kind: StreamEventKind
  text: string
  /** Set for trade/fill events. */
  tradeId?: ID
  artifactId?: ID
  scenarioId?: ID
  tags: string[]
  /** §1.4 stamped with the module you were looking at when captured. */
  capturedFrom?: string
  /** Quick-captured items land in the Inbox until triaged. §4.4 */
  inbox?: boolean
}

// ── Trade ─────────────────────────────────────────────────────────────────

export type Direction = 'long' | 'short'
export type OptionType = 'CE' | 'PE'
export type ContractKind = 'FUT' | 'EQ' | 'OPT'

/** §11.4 Spreads are a single trade object with legs, not linked trades. */
export interface Leg {
  id: ID
  at: Timestamp
  side: 'entry' | 'exit'
  price: number
  qty: number
  fees: number
}

export type Grade = 'A' | 'B' | 'C' | 'D' | 'F'

export interface Trade {
  id: ID
  instrumentId: ID
  sessionId: ID
  date: DateStr

  // ── FACT — immutable, ideally broker-sourced. §3.2
  direction: Direction
  contract: ContractKind
  strike?: number
  optionType?: OptionType
  expiry?: DateStr
  qty: number
  legs: Leg[]
  openedAt: Timestamp
  closedAt: Timestamp | null

  // ── BELIEF — locked at entry. §3.2
  /** Written at entry, frozen. Renders with a hairline left rule + stamp. */
  entryNote: string
  entryNoteLockedAt: Timestamp | null
  /** 1–5, locked after commit. §6.4 ConfidenceMeter */
  confidence: number
  /** The stop that defines R when rBasis is 'initial-stop'. §11.2 */
  plannedStop?: number
  plannedTarget?: number
  /** Recorded pre-trade where possible — one keystroke in the ticket. §3.3 */
  emotionAtEntry?: string
  /** Attribution is mandatory: a playbook entry, or explicitly off-book. §0.4 */
  setupId: ID | null
  /** "off-book" is itself a tracked behaviour. §0.4 */
  offBook: boolean
  /** Inherited from the regime active at the trade's timestamp. §3.3 */
  regime: RegimeState | null

  // ── JUDGEMENT — freely editable forever. §3.2
  grade: Grade | null
  /** The truest process metric in the system. §2.4.2 */
  takeAgain: boolean | null
  executionScore: number | null
  exitNote: string
  lesson: string
  mistakes: string[]
  emotions: string[]
  emotionAtExit?: string

  /** FACT if broker-sourced, JUDGEMENT if hand-entered. §11.1 */
  mfeR: number | null
  maeR: number | null
  mfeSource: 'manual' | 'market-data'

  tags: string[]
  artifactIds: ID[]
  /** Auto-applied when the risk envelope was already breached. §2.2.4 */
  autoTags: string[]
  createdAt: Timestamp
  updatedAt: Timestamp
  deletedAt: Timestamp | null
}

// ── Notebook ──────────────────────────────────────────────────────────────
// §5.2 The living research document.

export interface NotebookDoc {
  id: ID
  instrumentId: ID
  title: string
  /** Shallow tree. */
  parentId: ID | null
  order: number
  body: string
  /** Quietly shames stale convictions. §5.2 */
  updatedAt: Timestamp
  createdAt: Timestamp
  /** Version history you can scrub. §5.2 */
  versions: DocVersion[]
  /** Backlinks are bidirectional. §1.4, §5.2 */
  backlinks: Backlink[]
  /** Seeded docs cannot be deleted, only emptied. */
  seeded: boolean
}

export interface DocVersion {
  at: Timestamp
  body: string
}

export interface Backlink {
  kind: 'session' | 'trade' | 'review' | 'doc'
  id: ID
  label: string
  at: Timestamp
}

// ── Review ────────────────────────────────────────────────────────────────
// §2.4 Linear, one question at a time. P&L hidden until step 4.

export interface SessionReview {
  /** Step 1 — produces the market read score, independent of money. */
  reconciled: boolean
  /** Step 5 — the one required field in the whole review. §2.4.5 */
  oneLineForTomorrow: string
  /** Free prose, paper material. */
  notes: string
  completedAt: Timestamp | null
  /** Which step the user is on, so review resumes where it left off. */
  step: number
}

export interface PeriodReview {
  id: ID
  kind: 'weekly' | 'monthly'
  /** ISO week start or month start. */
  periodStart: DateStr
  instrumentId: ID | null
  /** You write the prose; the system supplies the evidence. §2.5 */
  body: string
  createdAt: Timestamp
  updatedAt: Timestamp
}

// ── Artifacts ─────────────────────────────────────────────────────────────
// §5.9 Vault. A screenshot with no context is a note you failed to finish.

export interface Artifact {
  id: ID
  instrumentId: ID
  sessionId: ID | null
  tradeId: ID | null
  kind: 'screenshot' | 'file'
  name: string
  /** Data URL. Local-first: the image lives in the same store as the note. */
  data: string
  /** OCR'd in the background so it's searchable. §2.3 */
  ocrText: string
  tags: string[]
  at: Timestamp
}

// ── Macro events ──────────────────────────────────────────────────────────
// §1.4 The workstation's macro calendar, filtered to this instrument.

export interface MacroEvent {
  id: ID
  date: DateStr
  /** `HH:MM` IST. */
  time: string
  title: string
  instrumentIds: ID[]
  importance: 'high' | 'medium' | 'low'
}

// ── Saved queries ─────────────────────────────────────────────────────────
// §4.1 Pinned saved queries live below the fixed sidebar sections.

export interface SavedQuery {
  id: ID
  name: string
  query: string
  pinned: boolean
  createdAt: Timestamp
}

// ── Taxonomy + settings ───────────────────────────────────────────────────
// §3.3 user-editable, schema-versioned. §5.11 Schema edits are versioned so
// historical data is never silently re-interpreted.

export interface TaxonomyItem {
  id: ID
  label: string
  /** Removed items stay resolvable for historical rows. */
  retired: boolean
}

export interface Settings {
  schemaVersion: number
  density: 'compact' | 'comfortable'
  theme: 'dark' | 'light'
  cvdSafe: boolean
  sound: boolean
  /** §5.7 Below this, a metric renders with no number at all. */
  evidenceThreshold: number
  /** Default risk envelope for new sessions. §2.2.4 */
  defaultRisk: RiskEnvelope
  mistakes: TaxonomyItem[]
  emotions: TaxonomyItem[]
  /** P&L reveal state — §2.1 Live mode collapses it to a glyph. */
  pnlVisible: boolean
}

// ── The database shape ────────────────────────────────────────────────────

export interface DB {
  instruments: Instrument[]
  sessions: Session[]
  trades: Trade[]
  events: StreamEvent[]
  levels: Level[]
  playbook: PlaybookEntry[]
  docs: NotebookDoc[]
  artifacts: Artifact[]
  macroEvents: MacroEvent[]
  regimeLog: RegimeChange[]
  savedQueries: SavedQuery[]
  periodReviews: PeriodReview[]
  settings: Settings
}
