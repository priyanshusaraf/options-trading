import { useEffect, useMemo, useState } from 'react'
import {
  getJournalInstruments, getJournalOpenTradesMtm, getJournalTrades,
  addJournalTrade, closeJournalTrade, addJournalMissed, getJournalMissed,
  getJournalStats,
} from '../lib/api'
import type {
  JournalInstrumentDTO, JournalTradeDTO, JournalMissedDTO, JournalStatsDTO,
} from '../lib/types'

const n = (v: number | null | undefined) => (v == null ? '—' : v.toFixed(2))
const pnlClass = (v: number | null | undefined) =>
  v == null ? 'text-muted' : v >= 0 ? 'text-emerald-400' : 'text-down'

function QuickAdd({ instruments, onAdded }: {
  instruments: JournalInstrumentDTO[]
  onAdded: () => void
}) {
  const [symbol, setSymbol] = useState(instruments[0]?.symbol ?? '')
  const [direction, setDirection] = useState<'LONG' | 'SHORT'>('LONG')
  const [lots, setLots] = useState('1')
  const [price, setPrice] = useState('')
  const [tag, setTag] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!symbol && instruments[0]) setSymbol(instruments[0].symbol)
  }, [instruments, symbol])

  const submit = async () => {
    if (!symbol || !price) return
    setBusy(true)
    try {
      await addJournalTrade({
        symbol, direction, lots: parseInt(lots, 10) || 1,
        entry_price: parseFloat(price), setup_tag: tag || undefined,
      })
      setPrice(''); setTag('')
      onAdded()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card p-3 flex flex-col gap-2">
      <div className="text-xs font-semibold text-muted">Quick add</div>
      <div className="grid grid-cols-2 gap-2">
        <select className="bg-panel2 border border-edge rounded px-2 py-1.5 text-sm"
          value={symbol} onChange={(e) => setSymbol(e.target.value)}>
          {instruments.map((i) => <option key={i.symbol} value={i.symbol}>{i.symbol}</option>)}
        </select>
        <div className="flex gap-1">
          {(['LONG', 'SHORT'] as const).map((d) => (
            <button key={d} onClick={() => setDirection(d)}
              className={`flex-1 rounded px-2 py-1.5 text-xs font-semibold border ${direction === d
                ? (d === 'LONG' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                                  : 'bg-down/20 text-down border-down/40')
                : 'bg-panel2 text-muted border-edge'}`}>{d}</button>
          ))}
        </div>
        <input className="bg-panel2 border border-edge rounded px-2 py-1.5 text-sm"
          placeholder="lots" inputMode="numeric" value={lots}
          onChange={(e) => setLots(e.target.value)} />
        <input className="bg-panel2 border border-edge rounded px-2 py-1.5 text-sm"
          placeholder="entry price" inputMode="decimal" value={price}
          onChange={(e) => setPrice(e.target.value)} />
        <input className="col-span-2 bg-panel2 border border-edge rounded px-2 py-1.5 text-sm"
          placeholder="setup tag (optional)" value={tag}
          onChange={(e) => setTag(e.target.value)} />
      </div>
      <button onClick={submit} disabled={busy || !symbol || !price}
        className="rounded px-3 py-1.5 text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 disabled:opacity-40">
        {busy ? 'Adding…' : 'Log trade'}
      </button>
    </div>
  )
}

function OpenTrades({ trades, onClosed }: {
  trades: JournalTradeDTO[]
  onClosed: () => void
}) {
  const [closingId, setClosingId] = useState<number | null>(null)
  const [exitPrice, setExitPrice] = useState('')

  const submitClose = async (id: number) => {
    if (!exitPrice) return
    await closeJournalTrade(id, { exit_price: parseFloat(exitPrice) })
    setClosingId(null); setExitPrice('')
    onClosed()
  }

  if (!trades.length) {
    return <div className="card p-3 text-xs text-muted">No open journal trades.</div>
  }
  return (
    <div className="card p-3 flex flex-col gap-2">
      <div className="text-xs font-semibold text-muted">Open ({trades.length})</div>
      {trades.map((t) => (
        <div key={t.id} className="flex items-center gap-2 text-sm border-b border-edge/60 pb-2 last:border-0 last:pb-0">
          <span className="badge bg-panel2 text-muted">{t.instrument_symbol}</span>
          <span className={`text-xs font-semibold ${t.direction === 'LONG' ? 'text-emerald-400' : 'text-down'}`}>
            {t.direction}
          </span>
          <span className="text-xs text-muted">{t.lots} lot @ {n(t.entry_price)}</span>
          <span className={`ml-auto text-xs font-semibold ${pnlClass(t.unrealized)}`}>
            {t.unrealized == null ? 'MTM —' : `₹${n(t.unrealized)}`}
          </span>
          {closingId === t.id ? (
            <div className="flex gap-1">
              <input className="w-20 bg-panel2 border border-edge rounded px-1.5 py-1 text-xs"
                placeholder="exit" inputMode="decimal" value={exitPrice}
                onChange={(e) => setExitPrice(e.target.value)} />
              <button onClick={() => submitClose(t.id)}
                className="text-xs px-2 py-1 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                ✓
              </button>
            </div>
          ) : (
            <button onClick={() => setClosingId(t.id)}
              className="text-xs px-2 py-1 rounded bg-panel2 text-muted border border-edge hover:text-zinc-200">
              Close
            </button>
          )}
        </div>
      ))}
    </div>
  )
}

function MissedQuickAdd({ instruments, onAdded }: {
  instruments: JournalInstrumentDTO[]
  onAdded: () => void
}) {
  const [symbol, setSymbol] = useState('')
  const [direction, setDirection] = useState<'LONG' | 'SHORT'>('LONG')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    if (!symbol || !reason) return
    setBusy(true)
    try {
      await addJournalMissed({ symbol, direction, skip_reason: reason })
      setReason('')
      onAdded()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card p-3 flex flex-col gap-2">
      <div className="text-xs font-semibold text-muted">Log a missed setup</div>
      <div className="grid grid-cols-2 gap-2">
        <select className="bg-panel2 border border-edge rounded px-2 py-1.5 text-sm"
          value={symbol} onChange={(e) => setSymbol(e.target.value)}>
          <option value="">instrument…</option>
          {instruments.map((i) => <option key={i.symbol} value={i.symbol}>{i.symbol}</option>)}
        </select>
        <div className="flex gap-1">
          {(['LONG', 'SHORT'] as const).map((d) => (
            <button key={d} onClick={() => setDirection(d)}
              className={`flex-1 rounded px-2 py-1.5 text-xs font-semibold border ${direction === d
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                : 'bg-panel2 text-muted border-edge'}`}>{d}</button>
          ))}
        </div>
        <input className="col-span-2 bg-panel2 border border-edge rounded px-2 py-1.5 text-sm"
          placeholder="why skipped?" value={reason} onChange={(e) => setReason(e.target.value)} />
      </div>
      <button onClick={submit} disabled={busy || !symbol || !reason}
        className="rounded px-3 py-1.5 text-xs font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/40 disabled:opacity-40">
        {busy ? 'Adding…' : 'Log missed setup'}
      </button>
    </div>
  )
}

export default function JournalView() {
  const [instruments, setInstruments] = useState<JournalInstrumentDTO[]>([])
  const [openTrades, setOpenTrades] = useState<JournalTradeDTO[]>([])
  const [closedTrades, setClosedTrades] = useState<JournalTradeDTO[]>([])
  const [missed, setMissed] = useState<JournalMissedDTO[]>([])
  const [stats, setStats] = useState<JournalStatsDTO | null>(null)

  const reload = () => {
    getJournalInstruments().then((d) => setInstruments(d.instruments || [])).catch(() => {})
    getJournalOpenTradesMtm().then((d) => setOpenTrades(d.trades || [])).catch(() => {})
    getJournalTrades().then((d) =>
      setClosedTrades((d.trades || []).filter((t: JournalTradeDTO) => t.exit_price != null))
    ).catch(() => {})
    getJournalMissed().then((d) => setMissed(d.missed || [])).catch(() => {})
    getJournalStats().then(setStats).catch(() => {})
  }

  useEffect(() => {
    reload()
    const t = setInterval(reload, 15000)
    return () => clearInterval(t)
  }, [])

  const tagRows = useMemo(() => Object.entries(stats?.by_tag ?? {}), [stats])

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <QuickAdd instruments={instruments} onAdded={reload} />
        <MissedQuickAdd instruments={instruments} onAdded={reload} />
      </div>

      <OpenTrades trades={openTrades} onClosed={reload} />

      {stats && (
        <div className="card p-3 flex flex-col gap-2">
          <div className="text-xs font-semibold text-muted">By tag</div>
          {tagRows.length === 0 && <div className="text-xs text-muted">No closed trades yet.</div>}
          {tagRows.map(([tag, row]) => (
            <div key={tag} className="flex items-center gap-2 text-sm">
              <span className="badge bg-panel2 text-muted">{tag}</span>
              <span className="text-xs text-muted">{row.trades} trades, {row.wins} wins</span>
              <span className={`ml-auto text-xs font-semibold ${pnlClass(row.net_pnl)}`}>
                ₹{n(row.net_pnl)}
              </span>
            </div>
          ))}
          <div className="border-t border-edge/60 pt-2 text-xs text-muted">
            Missed setups: {stats.missed_summary.count}
            {stats.missed_summary.count > 0 && (
              <> — hypothetical net{' '}
                <span className={pnlClass(stats.missed_summary.hypothetical_net_pnl)}>
                  ₹{n(stats.missed_summary.hypothetical_net_pnl)}
                </span>
              </>
            )}
          </div>
        </div>
      )}

      <div className="card p-3 flex flex-col gap-2">
        <div className="text-xs font-semibold text-muted">Closed ({closedTrades.length})</div>
        {closedTrades.slice(0, 30).map((t) => (
          <div key={t.id} className="flex items-center gap-2 text-sm border-b border-edge/60 pb-1.5 last:border-0">
            <span className="badge bg-panel2 text-muted">{t.instrument_symbol}</span>
            <span className={`text-xs font-semibold ${t.direction === 'LONG' ? 'text-emerald-400' : 'text-down'}`}>
              {t.direction}
            </span>
            <span className="text-xs text-muted">{n(t.entry_price)} → {n(t.exit_price)}</span>
            {t.setup_tag && <span className="badge bg-panel2 text-muted">{t.setup_tag}</span>}
          </div>
        ))}
      </div>

      {missed.length > 0 && (
        <div className="card p-3 flex flex-col gap-2">
          <div className="text-xs font-semibold text-muted">Missed setups ({missed.length})</div>
          {missed.slice(0, 20).map((m) => (
            <div key={m.id} className="flex items-center gap-2 text-sm border-b border-edge/60 pb-1.5 last:border-0">
              <span className="badge bg-panel2 text-muted">{m.instrument_symbol}</span>
              <span className={`text-xs font-semibold ${m.direction === 'LONG' ? 'text-emerald-400' : 'text-down'}`}>
                {m.direction}
              </span>
              <span className="text-xs text-muted flex-1">{m.skip_reason}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
