import { useEffect, useMemo, useState } from 'react'
import {
  getJournalInstruments, getJournalOpenTradesMtm, getJournalTrades,
  addJournalTrade, closeJournalTrade, addJournalMissed, getJournalMissed,
  getJournalStats,
} from '../lib/api'
import type {
  JournalInstrumentDTO, JournalTradeDTO, JournalMissedDTO, JournalStatsDTO,
} from '../lib/types'
import { Badge, badgeVariants } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

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
    <Card className="p-3 flex flex-col gap-2">
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
        <Input className="h-auto bg-panel2 border-edge px-2 py-1.5 text-sm"
          placeholder="lots" inputMode="numeric" value={lots}
          onChange={(e) => setLots(e.target.value)} />
        <Input className="h-auto bg-panel2 border-edge px-2 py-1.5 text-sm"
          placeholder="entry price" inputMode="decimal" value={price}
          onChange={(e) => setPrice(e.target.value)} />
        <Input className="col-span-2 h-auto bg-panel2 border-edge px-2 py-1.5 text-sm"
          placeholder="setup tag (optional)" value={tag}
          onChange={(e) => setTag(e.target.value)} />
      </div>
      <Button onClick={submit} disabled={busy || !symbol || !price}
        variant="toolbar" size="toolbar"
        className="py-1.5 font-semibold bg-emerald-500/20 text-emerald-300 border-emerald-500/40 hover:bg-emerald-500/30 hover:border-emerald-500/60 disabled:opacity-40">
        {busy ? 'Adding…' : 'Log trade'}
      </Button>
    </Card>
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
    return <Card className="p-3 text-xs text-muted">No open journal trades.</Card>
  }
  return (
    <Card className="p-3 flex flex-col gap-2">
      <div className="text-xs font-semibold text-muted">Open ({trades.length})</div>
      {trades.map((t) => (
        <div key={t.id} className="flex items-center gap-2 text-sm border-b border-edge/60 pb-2 last:border-0 last:pb-0">
          <Badge variant="chip" className="bg-panel2 text-muted">{t.instrument_symbol}</Badge>
          <span className={`text-xs font-semibold ${t.direction === 'LONG' ? 'text-emerald-400' : 'text-down'}`}>
            {t.direction}
          </span>
          <span className="text-xs text-muted">{t.lots} lot @ {n(t.entry_price)}</span>
          <span className={`ml-auto text-xs font-semibold ${pnlClass(t.unrealized)}`}>
            {t.unrealized == null ? 'MTM —' : `₹${n(t.unrealized)}`}
          </span>
          {closingId === t.id ? (
            <div className="flex gap-1">
              <Input className="w-20 h-auto bg-panel2 border-edge px-1.5 py-1 text-xs"
                placeholder="exit" inputMode="decimal" value={exitPrice}
                onChange={(e) => setExitPrice(e.target.value)} />
              <Button onClick={() => submitClose(t.id)}
                variant="toolbar" size="toolbar"
                className="bg-emerald-500/20 text-emerald-300 border-emerald-500/40 hover:bg-emerald-500/30">
                ✓
              </Button>
            </div>
          ) : (
            <Button onClick={() => setClosingId(t.id)}
              variant="toolbar" size="toolbar" className="text-muted hover:text-zinc-200">
              Close
            </Button>
          )}
        </div>
      ))}
    </Card>
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
    <Card className="p-3 flex flex-col gap-2">
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
        <Input className="col-span-2 h-auto bg-panel2 border-edge px-2 py-1.5 text-sm"
          placeholder="why skipped?" value={reason} onChange={(e) => setReason(e.target.value)} />
      </div>
      <Button onClick={submit} disabled={busy || !symbol || !reason}
        variant="toolbar" size="toolbar"
        className="py-1.5 font-semibold bg-amber-500/20 text-amber-300 border-amber-500/40 hover:bg-amber-500/30 hover:border-amber-500/60 disabled:opacity-40">
        {busy ? 'Adding…' : 'Log missed setup'}
      </Button>
    </Card>
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
        <Card className="p-3 flex flex-col gap-2">
          <div className="text-xs font-semibold text-muted">By tag</div>
          {tagRows.length === 0 && <div className="text-xs text-muted">No closed trades yet.</div>}
          {tagRows.map(([tag, row]) => (
            <div key={tag} className="flex items-center gap-2 text-sm">
              <Badge variant="chip" className="bg-panel2 text-muted">{tag}</Badge>
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
        </Card>
      )}

      <Card className="p-3 flex flex-col gap-2">
        <div className="text-xs font-semibold text-muted">Closed ({closedTrades.length})</div>
        {closedTrades.slice(0, 30).map((t) => (
          <div key={t.id} className="flex items-center gap-2 text-sm border-b border-edge/60 pb-1.5 last:border-0">
            <Badge variant="chip" className="bg-panel2 text-muted">{t.instrument_symbol}</Badge>
            <span className={`text-xs font-semibold ${t.direction === 'LONG' ? 'text-emerald-400' : 'text-down'}`}>
              {t.direction}
            </span>
            <span className="text-xs text-muted">{n(t.entry_price)} → {n(t.exit_price)}</span>
            {t.setup_tag && <Badge variant="chip" className="bg-panel2 text-muted">{t.setup_tag}</Badge>}
          </div>
        ))}
      </Card>

      {missed.length > 0 && (
        <Card className="p-3 flex flex-col gap-2">
          <div className="text-xs font-semibold text-muted">Missed setups ({missed.length})</div>
          {missed.slice(0, 20).map((m) => (
            <div key={m.id} className="flex items-center gap-2 text-sm border-b border-edge/60 pb-1.5 last:border-0">
              <Badge variant="chip" className="bg-panel2 text-muted">{m.instrument_symbol}</Badge>
              <span className={`text-xs font-semibold ${m.direction === 'LONG' ? 'text-emerald-400' : 'text-down'}`}>
                {m.direction}
              </span>
              <span className="text-xs text-muted flex-1">{m.skip_reason}</span>
            </div>
          ))}
        </Card>
      )}
    </div>
  )
}
