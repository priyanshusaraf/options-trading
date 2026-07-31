import { useEffect, useState } from 'react'

import {
  claimManualFill, contractFromSymbol, instrumentForSymbol, listManualFills,
  optionTypeFromSymbol, type ManualFill,
} from '../../data/manualFills'
import { addTrade } from '../../data/actions'
import { useDB } from '../../data/hooks'
import { today } from '../../domain/dates'

/**
 * Trades the owner placed by hand on the Kite account, waiting for a reason.
 *
 * The split is the point. Everything above the divider is FACT — broker-sourced
 * price, quantity, side and time — and is rendered cold and unelectable. The
 * owner never types a number. Below it is the one thing only they can supply:
 * why.
 *
 * Materialising goes through addTrade(), never by writing a Trade directly, so
 * every rule still fires — off-book attribution, no-thesis auto-tagging, regime
 * inheritance, risk-envelope breach. Bypassing it would produce records the
 * rest of the journal cannot reason about.
 */
export function PendingReasons({ compact = false }: { compact?: boolean }) {
  const db = useDB()
  const [fills, setFills] = useState<ManualFill[]>([])
  const [busy, setBusy] = useState<string | null>(null)

  const reload = () => { void listManualFills().then(setFills) }

  useEffect(() => {
    reload()
    const t = setInterval(reload, 60_000)
    return () => clearInterval(t)
  }, [])

  if (!fills.length) return null

  return (
    <section className={`pending ${compact ? 'is-compact' : ''}`}>
      <div className="pending__head">
        <span className="label">Trades awaiting a reason</span>
        <span className="mono faint">{fills.length}</span>
      </div>
      {fills.map((f) => (
        <FillCard
          key={f.order_id}
          fill={f}
          instruments={db.instruments}
          playbook={db.playbook.filter((p) => !p.archived)}
          busy={busy === f.order_id}
          onDone={() => { setBusy(null); reload() }}
          onBusy={() => setBusy(f.order_id)}
        />
      ))}
    </section>
  )
}

function FillCard({
  fill, instruments, playbook, busy, onBusy, onDone,
}: {
  fill: ManualFill
  instruments: { id: string; code: string }[]
  playbook: { id: string; name: string }[]
  busy: boolean
  onBusy: () => void
  onDone: () => void
}) {
  const guessed = instrumentForSymbol(fill.tradingsymbol, instruments)
  const [instrumentId, setInstrumentId] = useState(guessed ?? '')
  const [why, setWhy] = useState('')
  const [setupId, setSetupId] = useState<string>('')
  const [confidence, setConfidence] = useState(3)
  const [error, setError] = useState<string | null>(null)

  const dir = fill.side === 'BUY' ? 'long' : 'short'
  const glyph = fill.side === 'BUY' ? '▲' : '▼'

  async function save() {
    if (!instrumentId) { setError('Which instrument is this?'); return }
    if (!why.trim()) { setError('A reason is the only thing this asks of you.'); return }
    setError(null)
    onBusy()
    try {
      const tradeId = addTrade({
        instrumentId,
        date: today(),
        direction: dir,
        contract: contractFromSymbol(fill.tradingsymbol),
        optionType: optionTypeFromSymbol(fill.tradingsymbol),
        qty: fill.qty,
        price: fill.avg_price ?? 0,
        setupId: setupId || null,
        // Setup attribution is mandatory: no setup means off-book, which the
        // Playbook tracks as its own population with its own expectancy.
        offBook: !setupId,
        confidence,
        entryNote: why.trim(),
      })
      await claimManualFill(fill.order_id, tradeId)
      onDone()
    } catch (e) {
      setError(String(e))
      onDone()
    }
  }

  async function dismiss() {
    onBusy()
    try {
      await claimManualFill(fill.order_id, 'not-mine')
    } finally {
      onDone()
    }
  }

  return (
    <article className={`pfill ${fill.verdict === 'NEEDS_REVIEW' ? 'is-review' : ''}`}>
      {/* ── FACT: broker-sourced, never editable ─────────────────────── */}
      <div className="pfill__fact glass">
        <span className={`pfill__dir ${dir === 'long' ? 'pos' : 'neg'}`}>{glyph}</span>
        <span className="mono pfill__sym">{fill.tradingsymbol}</span>
        <span className="mono num">{fill.qty}</span>
        <span className="mono num">@{fill.avg_price ?? '—'}</span>
        <span className="mono faint">
          {fill.order_ts ? new Date(fill.order_ts).toLocaleTimeString() : ''}
        </span>
      </div>

      {fill.verdict === 'NEEDS_REVIEW' && (
        <p className="pfill__warn attn">
          This might be one of the bot's exchange stops rather than yours — it
          arrived untagged on a symbol the bot also traded today. Confirm before
          filing it.
        </p>
      )}

      {/* ── BELIEF / JUDGEMENT: the only part you supply ──────────────── */}
      <div className="pfill__ask paper">
        {!guessed && (
          <label className="pfill__row">
            <span className="label">Instrument</span>
            <select value={instrumentId} onChange={(e) => setInstrumentId(e.target.value)}>
              <option value="">choose…</option>
              {instruments.map((i) => (
                <option key={i.id} value={i.id}>{i.code}</option>
              ))}
            </select>
          </label>
        )}

        <textarea
          className="pfill__why"
          rows={2}
          placeholder="Why did you take this?"
          value={why}
          onChange={(e) => setWhy(e.target.value)}
        />

        <div className="pfill__row">
          <select value={setupId} onChange={(e) => setSetupId(e.target.value)}>
            <option value="">off-book</option>
            {playbook.map((p) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <label className="pfill__conf">
            <span className="label">conf</span>
            <input
              type="range" min={1} max={5} value={confidence}
              onChange={(e) => setConfidence(Number(e.target.value))}
            />
            <span className="mono num">{confidence}</span>
          </label>
        </div>

        {error && <p className="pfill__err neg">{error}</p>}

        <div className="pfill__actions">
          <button className="pfill__save" disabled={busy} onClick={() => void save()}>
            {busy ? 'saving…' : 'Save reason'}
          </button>
          <button className="pfill__dismiss" disabled={busy} onClick={() => void dismiss()}>
            Not mine
          </button>
        </div>
      </div>
    </article>
  )
}
