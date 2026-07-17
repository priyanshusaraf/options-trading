import { useEffect, useMemo, useRef, useState } from 'react'
import {
  getJournalFeed, getJournalInstruments, upsertJournalDay,
  addJournalNote, deleteJournalNote, putJournalBias, addJournalTrade,
} from '../lib/api'
import type {
  JournalFeedDTO, JournalFeedDayDTO, JournalBiasDTO, JournalInstrumentDTO,
} from '../lib/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'

const n = (v: number | null | undefined) => (v == null ? '—' : v.toFixed(2))
const pnlClass = (v: number | null | undefined) =>
  v == null ? 'text-muted' : v >= 0 ? 'text-emerald-400' : 'text-down'
const todayISO = () => new Date().toLocaleDateString('en-CA') // YYYY-MM-DD, local
const fmtDay = (iso: string) =>
  new Date(iso + 'T00:00:00').toLocaleDateString('en-IN',
    { weekday: 'short', day: '2-digit', month: 'short' })
const fmtTime = (iso: string) =>
  new Date(iso).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })

// Textarea that autosaves on blur only when its value actually changed.
function AutoText({ value, placeholder, onSave, rows = 3 }: {
  value: string | null; placeholder: string; onSave: (v: string) => void; rows?: number
}) {
  const [v, setV] = useState(value ?? '')
  const initial = useRef(value ?? '')
  useEffect(() => { setV(value ?? ''); initial.current = value ?? '' }, [value])
  return (
    <textarea
      className="w-full resize-y bg-panel2 border border-edge rounded px-2 py-1.5 text-sm text-zinc-200 placeholder:text-muted focus:outline-none focus:border-zinc-500"
      rows={rows} placeholder={placeholder} value={v}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => { if (v !== initial.current) { initial.current = v; onSave(v) } }}
    />
  )
}

function BiasChip({ bias, onSave }: { bias: JournalBiasDTO; onSave: (stance: string, note: string) => void }) {
  const [editing, setEditing] = useState(false)
  const [stance, setStance] = useState(bias.stance ?? '')
  const [note, setNote] = useState(bias.note ?? '')
  useEffect(() => { setStance(bias.stance ?? ''); setNote(bias.note ?? '') }, [bias])
  if (editing) {
    return (
      <div className="flex items-center gap-1">
        <span className="text-xs font-semibold text-muted">{bias.horizon}</span>
        <Input className="w-24 h-auto bg-panel2 border-edge px-1.5 py-1 text-xs"
          placeholder="stance" value={stance} onChange={(e) => setStance(e.target.value)} />
        <Input className="w-40 h-auto bg-panel2 border-edge px-1.5 py-1 text-xs"
          placeholder="note" value={note} onChange={(e) => setNote(e.target.value)} />
        <Button variant="toolbar" size="toolbar"
          className="bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
          onClick={() => { onSave(stance, note); setEditing(false) }}>✓</Button>
      </div>
    )
  }
  return (
    <button onClick={() => setEditing(true)}
      className="flex items-baseline gap-1.5 rounded border border-edge bg-panel2 px-2 py-1 hover:border-zinc-500">
      <span className="text-xs font-semibold text-muted">{bias.horizon}</span>
      <span className="text-sm font-semibold text-zinc-200">{bias.stance || '—'}</span>
      {bias.note && <span className="text-xs text-muted">· {bias.note}</span>}
    </button>
  )
}

function NoteComposer({ instruments, onAdd }: {
  instruments: JournalInstrumentDTO[]; onAdd: (body: string, sym?: string) => void
}) {
  const [body, setBody] = useState('')
  const [sym, setSym] = useState('')
  const submit = () => { if (body.trim()) { onAdd(body.trim(), sym || undefined); setBody(''); setSym('') } }
  return (
    <div className="flex gap-1">
      <Input className="flex-1 h-auto bg-panel2 border-edge px-2 py-1.5 text-sm"
        placeholder="drop a note…" value={body}
        onChange={(e) => setBody(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') submit() }} />
      <select className="bg-panel2 border border-edge rounded px-1.5 py-1 text-xs text-muted"
        value={sym} onChange={(e) => setSym(e.target.value)}>
        <option value="">—</option>
        {instruments.map((i) => <option key={i.symbol} value={i.symbol}>{i.symbol}</option>)}
      </select>
      <Button variant="toolbar" size="toolbar" onClick={submit}
        className="text-muted hover:text-zinc-200">＋</Button>
    </div>
  )
}

function TradeComposer({ instruments, onAdd }: {
  instruments: JournalInstrumentDTO[]; onAdd: () => void
}) {
  const [open, setOpen] = useState(false)
  const [symbol, setSymbol] = useState(instruments[0]?.symbol ?? '')
  const [direction, setDirection] = useState<'LONG' | 'SHORT'>('LONG')
  const [lots, setLots] = useState('1')
  const [price, setPrice] = useState('')
  const [tag, setTag] = useState('')
  useEffect(() => { if (!symbol && instruments[0]) setSymbol(instruments[0].symbol) }, [instruments, symbol])
  const submit = async () => {
    if (!symbol || !price) return
    await addJournalTrade({ symbol, direction, lots: parseInt(lots, 10) || 1,
      entry_price: parseFloat(price), setup_tag: tag || undefined })
    setPrice(''); setTag(''); setOpen(false); onAdd()
  }
  if (!open) {
    return <Button variant="toolbar" size="toolbar" onClick={() => setOpen(true)}
      className="text-muted hover:text-zinc-200 self-start">＋ trade</Button>
  }
  return (
    <div className="grid grid-cols-2 gap-1.5">
      <select className="bg-panel2 border border-edge rounded px-2 py-1 text-sm"
        value={symbol} onChange={(e) => setSymbol(e.target.value)}>
        {instruments.map((i) => <option key={i.symbol} value={i.symbol}>{i.symbol}</option>)}
      </select>
      <div className="flex gap-1">
        {(['LONG', 'SHORT'] as const).map((d) => (
          <button key={d} onClick={() => setDirection(d)}
            className={`flex-1 rounded px-2 py-1 text-xs font-semibold border ${direction === d
              ? (d === 'LONG' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                              : 'bg-down/20 text-down border-down/40')
              : 'bg-panel2 text-muted border-edge'}`}>{d}</button>
        ))}
      </div>
      <Input className="h-auto bg-panel2 border-edge px-2 py-1 text-sm" placeholder="lots"
        inputMode="numeric" value={lots} onChange={(e) => setLots(e.target.value)} />
      <Input className="h-auto bg-panel2 border-edge px-2 py-1 text-sm" placeholder="entry price"
        inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} />
      <Input className="col-span-2 h-auto bg-panel2 border-edge px-2 py-1 text-sm"
        placeholder="setup tag (optional)" value={tag} onChange={(e) => setTag(e.target.value)} />
      <Button variant="toolbar" size="toolbar" onClick={submit} disabled={!symbol || !price}
        className="bg-emerald-500/20 text-emerald-300 border-emerald-500/40 disabled:opacity-40">
        Log trade
      </Button>
      <Button variant="toolbar" size="toolbar" onClick={() => setOpen(false)}
        className="text-muted">Cancel</Button>
    </div>
  )
}

function DayCard({ day, instruments, isToday, reload }: {
  day: JournalFeedDayDTO; instruments: JournalInstrumentDTO[]; isToday: boolean; reload: () => void
}) {
  return (
    <Card className="p-3 flex flex-col gap-2.5">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-zinc-200">{fmtDay(day.date)}</span>
        {isToday && <Badge variant="chip" className="bg-emerald-500/15 text-emerald-300">today</Badge>}
        {(day.trades.length > 0) && (
          <span className={`ml-auto text-xs font-semibold ${pnlClass(day.net_pnl)}`}>₹{n(day.net_pnl)}</span>
        )}
      </div>

      <AutoText value={day.market_view} placeholder="what am I feeling about the market today…"
        rows={3} onSave={(v) => upsertJournalDay({ entry_date: day.date, market_view: v }).then(reload)} />

      {day.notes.length > 0 && (
        <div className="flex flex-col gap-1">
          {day.notes.map((nt) => (
            <div key={nt.id} className="group flex items-start gap-2 text-sm">
              <span className="text-[11px] text-muted tabular-nums pt-0.5">{fmtTime(nt.noted_at)}</span>
              {nt.instrument_symbol && <Badge variant="chip" className="bg-panel2 text-muted">{nt.instrument_symbol}</Badge>}
              <span className="flex-1 text-zinc-300">{nt.body}</span>
              <button onClick={() => deleteJournalNote(nt.id).then(reload)}
                className="opacity-0 group-hover:opacity-100 text-muted hover:text-down text-xs">✕</button>
            </div>
          ))}
        </div>
      )}
      {isToday && <NoteComposer instruments={instruments}
        onAdd={(body, sym) => addJournalNote({ body, instrument_symbol: sym }).then(reload)} />}

      {day.trades.length > 0 && (
        <div className="flex flex-col gap-1 border-t border-edge/60 pt-2">
          <div className="text-[11px] uppercase tracking-wide text-muted">Trades taken</div>
          {day.trades.map((t) => (
            <div key={t.id} className="flex items-center gap-2 text-sm">
              <Badge variant="chip" className="bg-panel2 text-muted">{t.instrument_symbol}</Badge>
              <span className={`text-xs font-semibold ${t.direction === 'LONG' ? 'text-emerald-400' : 'text-down'}`}>{t.direction}</span>
              <span className="text-xs text-muted">{t.lots} lot @ {n(t.entry_price)}{t.exit_price != null ? ` → ${n(t.exit_price)}` : ''}</span>
              {t.setup_tag && <Badge variant="chip" className="bg-panel2 text-muted">{t.setup_tag}</Badge>}
              {t.net_pnl != null && <span className={`ml-auto text-xs font-semibold ${pnlClass(t.net_pnl)}`}>₹{n(t.net_pnl)}</span>}
            </div>
          ))}
        </div>
      )}
      {isToday && <TradeComposer instruments={instruments} onAdd={reload} />}

      {day.missed.length > 0 && (
        <div className="flex flex-col gap-1 border-t border-edge/60 pt-2">
          <div className="text-[11px] uppercase tracking-wide text-muted">Missed</div>
          {day.missed.map((m) => (
            <div key={m.id} className="flex items-center gap-2 text-sm">
              <Badge variant="chip" className="bg-amber-500/15 text-amber-300">{m.instrument_symbol}</Badge>
              <span className="text-xs text-muted flex-1">{m.skip_reason}</span>
            </div>
          ))}
        </div>
      )}

      <div className="border-t border-edge/60 pt-2">
        <div className="text-[11px] uppercase tracking-wide text-muted mb-1">Result</div>
        <AutoText value={day.result} placeholder="how did it go…" rows={2}
          onSave={(v) => upsertJournalDay({ entry_date: day.date, result: v }).then(reload)} />
      </div>
    </Card>
  )
}

export default function JournalView() {
  const [feed, setFeed] = useState<JournalFeedDTO | null>(null)
  const [instruments, setInstruments] = useState<JournalInstrumentDTO[]>([])

  const reload = () => {
    getJournalFeed().then(setFeed).catch(() => {})
    getJournalInstruments().then((d) => setInstruments(d.instruments || [])).catch(() => {})
  }
  useEffect(() => { reload(); const t = setInterval(reload, 15000); return () => clearInterval(t) }, [])

  // Pin "today" at the top, creating a synthetic empty day if none exists yet.
  const days = useMemo(() => {
    const list = feed?.days ?? []
    const today = todayISO()
    if (list.some((d) => d.date === today)) return list
    return [{ date: today, market_view: null, result: null, net_pnl: 0, notes: [], trades: [], missed: [] }, ...list]
  }, [feed])

  const stats = feed?.stats
  return (
    <div className="flex flex-col gap-3">
      <Card className="p-3 flex flex-wrap items-center gap-3">
        {(feed?.bias ?? []).map((b) => (
          <BiasChip key={b.horizon} bias={b}
            onSave={(stance, note) => putJournalBias(b.horizon, { stance, note }).then(reload)} />
        ))}
        {stats && (
          <div className="ml-auto flex items-center gap-4 text-xs">
            <span className="text-muted">net <span className={`font-semibold ${pnlClass(stats.net_pnl)}`}>₹{n(stats.net_pnl)}</span></span>
            <span className="text-muted">win {stats.win_rate == null ? '—' : `${Math.round(stats.win_rate * 100)}%`}</span>
            <span className="text-muted">{stats.days_journaled} days</span>
          </div>
        )}
      </Card>

      {days.map((d) => (
        <DayCard key={d.date} day={d} instruments={instruments} isToday={d.date === todayISO()} reload={reload} />
      ))}
    </div>
  )
}
