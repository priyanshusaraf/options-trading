import { useEffect, useMemo, useState } from 'react'
import { getSettings, setSetting, resetSetting } from '../lib/api'
import type { SettingRow } from '../lib/types'
import { DANGER_KEYS, explainValue } from '../lib/settingFormat'
import { Badge, badgeVariants } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { META } from './settingsMeta'

// Groups are matched in order and a key joins the FIRST that claims it. The
// last entry claims everything left over, which is the whole point: before
// this, twelve live knobs — the gap guard, the order-failure disarm, the daily
// profit lock — matched no group and rendered NOWHERE while still governing a
// bot trading real money.
const GROUPS: [string, (k: string) => boolean][] = [
  ['Capital & halts', (k) => DANGER_KEYS.has(k)],
  ['Reinforcement', (k) => k.startsWith('reinforce_') || k === 'max_reinforcements'],
  ['Overnight holding', (k) => k.startsWith('overnight_') || k === 'max_holding_days' || k === 'square_off_buffer_minutes' || k === 'block_overnight_into_weekend'],
  ['Trailing stop', (k) => k.startsWith('trail_')],
  ['Option-data cache', (k) => k.startsWith('option_cache_')],
  ['Entry rules', (k) => k.startsWith('entry_') || k.startsWith('expiry_') || k === 'max_signal_age_minutes'],
  ['Risk & cadence', (k) => ['stop_loss_pct', 'target_pct', 'position_loop_seconds', 'signal_loop_seconds'].includes(k)],
  ['Position & trade limits', (k) => ['max_open_positions', 'reentry_cooldown_minutes', 'max_capital_per_trade'].includes(k)],
  ['Intraday equity (MIS)', (k) => k.startsWith('intraday_')],
  ['Overtrading guard', (k) => k.startsWith('overtrade_')],
  ['Notifications', (k) => k.startsWith('notify_') || k === 'alert_proximity_pct'],
  ['Execution', (k) => k.startsWith('exec_')],
  ['Journal', (k) => k.startsWith('manual_detect_')],
  ['Event risk', (k) => k.startsWith('event_risk_')],
  ['Ledger accuracy', (k) => k.startsWith('ledger_')],
  ['Storage & retention', (k) => k.startsWith('retention_')],
  // Catch-all. Never remove it — an unclaimed key is an invisible key.
  ['Other', () => true],
]

function Row({ r, onSaved }: { r: SettingRow; onSaved: () => void }) {
  const [v, setV] = useState(r.value)
  const [err, setErr] = useState<string | null>(null)
  const [showDetail, setShowDetail] = useState(false)
  useEffect(() => { setV(r.value); setErr(null) }, [r.value])

  const m = META[r.key]
  const label = m?.label ?? r.key
  const help = m?.help
  const gloss = explainValue(r.key, v)
  const defaultGloss = explainValue(r.key, r.default)
  const danger = DANGER_KEYS.has(r.key)
  // A stored override whose value differs from the shipped default. Not merely
  // "customised" — it means any newer default for this knob is having no effect.
  const diverged = r.overridden && String(r.value) !== String(r.default)

  const save = (val: any) =>
    setSetting(r.key, val).then((res: any) => {
      if (res && res.error) {
        setV(r.value)           // reject out-of-bounds: revert to last good
        setErr(String(res.error))
      } else {
        setErr(null)
        onSaved()
      }
    })

  return (
    // Mobile-first: one column that stacks under 640px, two columns from `sm` up.
    // The old row was a single flex line with four fixed-width columns (w-24 + w-16 +
    // w-24 + a button) alongside the label — at 390px that overflowed the viewport and
    // pushed the value out of reach, which is precisely the width this is operated at.
    <div className={cn('flex flex-col sm:flex-row sm:items-start gap-2 sm:gap-3 py-2.5',
                       'border-t border-edge/50',
                       danger && 'border-l-2 border-l-down/40 pl-2')}>
      <div className="flex-1 min-w-0">
        <div className="text-sm text-zinc-200">
          {label}
          {!m && (
            <Badge variant="chip" className="bg-amber-500/15 text-amber-300 ml-2"
                   title="This knob is live but has no description yet.">
              undocumented
            </Badge>
          )}
          {r.overridden && !diverged && (
            <Badge variant="chip" className="bg-blue-500/15 text-blue-300 ml-2"
                   title="A stored override is shadowing the code default. Reset to follow the default again.">
              overridden
            </Badge>
          )}
          {/* An override whose VALUE differs from the shipped default is the trap that
              has cost this project repeatedly: a new default is deployed, the stored
              override keeps shadowing it, and the change silently does nothing. The
              two shipped exit defaults are inert in production for exactly this
              reason. Show it louder than a plain "overridden". */}
          {diverged && (
            <Badge variant="chip" className="bg-amber-500/15 text-amber-300 ml-2"
                   title={`Your stored value (${String(v)}) is shadowing a DIFFERENT shipped default (${String(r.default)}). `
                     + `If the default changed in a recent update, that update is having no effect here until you reset this.`}>
              shadowing default {defaultGloss ?? String(r.default)}
            </Badge>
          )}
        </div>
        {help
          ? <div className="text-[11px] text-muted leading-relaxed">{help}</div>
          : <div className="text-[11px] text-muted italic">
              No description yet — key <span className="font-mono">{r.key}</span>.
            </div>}
        {/* What actually happens if you change it. Collapsed by default so the list
            stays scannable, because the consequence is usually longer than the
            definition — and a knob you cannot reason about is one you will not touch. */}
        {m?.detail && (
          <button onClick={() => setShowDetail((s) => !s)}
                  className="text-[11px] text-blue-300/80 hover:text-blue-300 mt-0.5">
            {showDetail ? 'less' : 'what changes if I move this?'}
          </button>
        )}
        {showDetail && m?.detail && (
          <div className="text-[11px] text-zinc-400 leading-relaxed mt-1 pl-2
                          border-l border-blue-400/30">
            {m.detail}
          </div>
        )}
        <div className="text-[10px] text-muted/70 font-mono mt-0.5">{r.key}</div>
        {err && <div className="text-[11px] text-down mt-1">{err}</div>}
      </div>

      {/* Controls: wrap freely on a phone, stay on one line from `sm` up. */}
      <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap sm:shrink-0">
        {r.choices?.length ? (
          <select value={String(v ?? '')}
            onChange={(e) => {
              const next = e.target.value
              setV(next)
              save(next)
            }}
            className="flex-1 min-w-[8rem] sm:flex-none sm:w-40 bg-panel2 border border-edge
                       rounded px-2 py-2 sm:py-1 text-sm sm:text-xs">
            {r.choices.map((choice) => (
              <option key={choice} value={choice}>{choice}</option>
            ))}
          </select>
        ) : r.type === 'bool' ? (
          <button onClick={() => { setV(!v); save(!v) }}
            className={cn(badgeVariants({ variant: 'chip' }),
                          v ? 'bg-up/20 text-up' : 'bg-zinc-700/40 text-muted')}>
            {v ? 'on' : 'off'}
          </button>
        ) : r.type === 'str' ? (
          <input type="text" value={v ?? ''}
            onChange={(e) => setV(e.target.value)}
            onBlur={() => save(v)}
            onKeyDown={(e) => e.key === 'Enter' && save(v)}
            className="flex-1 min-w-[8rem] sm:flex-none sm:w-40 bg-panel2 border border-edge
                       rounded px-2 py-2 sm:py-1 text-sm sm:text-xs" />
        ) : (
          <input type="number" value={v} step={r.type === 'int' ? 1 : 'any'}
            onChange={(e) => setV(r.type === 'int' ? parseInt(e.target.value) : parseFloat(e.target.value))}
            onBlur={() => save(v)}
            onKeyDown={(e) => e.key === 'Enter' && save(v)}
            className="flex-1 min-w-[6rem] sm:flex-none sm:w-24 bg-panel2 border border-edge
                       rounded px-2 py-2 sm:py-1 text-sm sm:text-xs tabular-nums" />
        )}

        {/* The unit gloss: 0.30 does not tell you it is a 30% stop. */}
        <span className="text-[11px] text-zinc-400 sm:w-16 sm:text-right tabular-nums">
          {gloss ?? ''}
        </span>

        <span className="text-[10px] text-muted sm:w-24 sm:text-right">
          default {defaultGloss ?? String(r.default)}
        </span>

        <button disabled={!r.overridden} onClick={() => resetSetting(r.key).then(onSaved)}
          className={cn(badgeVariants({ variant: 'chip' }),
                        r.overridden ? 'bg-zinc-700/40 text-muted hover:text-zinc-200' : 'opacity-30')}>
          reset
        </button>
      </div>
    </div>
  )
}

function Group({ title, rows, onSaved, openByDefault }: {
  title: string; rows: SettingRow[]; onSaved: () => void; openByDefault: boolean
}) {
  const [open, setOpen] = useState(openByDefault)
  const overrides = rows.filter((r) => r.overridden).length
  const undocumented = rows.filter((r) => !META[r.key]).length

  return (
    <Card className="p-3">
      <button className="w-full flex items-center gap-2 text-left"
              onClick={() => setOpen((o) => !o)}>
        <span className="text-muted text-xs w-3">{open ? '▾' : '▸'}</span>
        <span className="text-sm font-semibold text-zinc-100">{title}</span>
        <span className="text-[11px] text-muted">{rows.length}</span>
        {/* Visible without opening the group, so drift cannot hide. */}
        {overrides > 0 && (
          <Badge variant="chip" className="bg-blue-500/15 text-blue-300">
            {overrides} overridden
          </Badge>
        )}
        {undocumented > 0 && (
          <Badge variant="chip" className="bg-amber-500/15 text-amber-300">
            {undocumented} undocumented
          </Badge>
        )}
      </button>
      {open && rows.map((r) => <Row key={r.key} r={r} onSaved={onSaved} />)}
    </Card>
  )
}

export default function SettingsView() {
  const [rows, setRows] = useState<SettingRow[]>([])
  const [q, setQ] = useState('')
  const load = () => getSettings().then((d) => setRows(d.params || []))
  useEffect(() => { load() }, [])

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    if (!needle) return rows
    return rows.filter((r) => {
      const m = META[r.key]
      return r.key.toLowerCase().includes(needle)
        || (m?.label ?? '').toLowerCase().includes(needle)
        || (m?.help ?? '').toLowerCase().includes(needle)
    })
  }, [rows, q])

  // First matching group wins, so a key lands in exactly one place.
  const grouped = useMemo(() => {
    const out: [string, SettingRow[]][] = GROUPS.map(([t]) => [t, []])
    for (const r of filtered) {
      const idx = GROUPS.findIndex(([, match]) => match(r.key))
      out[idx][1].push(r)
    }
    return out.filter(([, rs]) => rs.length)
  }, [filtered])

  const totalOverrides = rows.filter((r) => r.overridden).length

  return (
    <div className="flex flex-col gap-3">
      <Card className="p-3 flex flex-col gap-2">
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className="stat-label">Engine settings</span>
          <span className="text-[11px] text-muted">
            Every value applies live — no restart, no code change.
          </span>
          {totalOverrides > 0 && (
            <Badge variant="chip" className="bg-blue-500/15 text-blue-300">
              {totalOverrides} overridden
            </Badge>
          )}
        </div>
        <Input value={q} onChange={(e) => setQ(e.target.value)}
               placeholder="Search settings — name, key or description" />
        <div className="text-[11px] text-muted">
          <span className="text-blue-300">Overridden</span> means a stored value
          is shadowing the code default. That is true even when the two look
          identical, which is why it is shown rather than guessed from the number.
        </div>
      </Card>

      {grouped.map(([title, rs], i) => (
        <Group key={title} title={title} rows={rs} onSaved={load}
               // Danger tier and search results open; tuning groups stay shut.
               openByDefault={i === 0 || q.trim().length > 0} />
      ))}

      {!grouped.length && (
        <Card className="p-4 text-sm text-muted">Nothing matches “{q}”.</Card>
      )}
    </div>
  )
}
