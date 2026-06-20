import { useEffect, useState } from 'react'
import { getSettings, setSetting, resetSetting } from '../lib/api'
import type { SettingRow } from '../lib/types'

// Human label + one-line doc for each runtime-overridable knob. Anything not
// listed still renders with its raw key.
const META: Record<string, { label: string; help: string }> = {
  reinforce_enabled: { label: 'Reinforcement enabled', help: 'Same-direction signal on a held winner strengthens management (no added qty).' },
  reinforce_min_profit_pct: { label: 'Min profit to reinforce', help: 'Position must be at least this far in profit before a reinforcement counts. Recommended 0.10.' },
  reinforce_lock_pct: { label: 'SL lock per reinforcement', help: 'Each reinforcement locks the stop to entry×(1+count×this). 0.05 ⇒ entry 300→SL 315.' },
  reinforce_extend_tp: { label: 'Extend target on reinforce', help: 'Push the take-profit out as confirmations stack (safe: stop is already locked in profit).' },
  reinforce_tp_extend_pct: { label: 'TP extension per reinforce', help: 'Fraction of entry added to the target each reinforcement. Recommended 0.20.' },
  reinforce_tp_max_pct: { label: 'TP extension cap', help: 'Target never extends beyond entry×(1+this). Recommended 1.50 (theta limits the upside of waiting).' },
  reinforce_cooldown_minutes: { label: 'Reinforcement cooldown (min)', help: 'Minimum gap between counted reinforcements. Recommended 15.' },
  max_reinforcements: { label: 'Max reinforcements', help: 'Cap on confirmations per trade. Recommended 3.' },
  overnight_enabled: { label: 'Overnight holding enabled', help: 'Allow eligible positions to carry past session close.' },
  overnight_auto_pct: { label: 'Auto-overnight ≤ % capital', help: 'Positions this small auto-hold overnight. Recommended 0.10.' },
  overnight_max_pct: { label: 'Never overnight > % capital', help: 'Hard cap — bigger positions never carry, even reinforced. Recommended 0.25.' },
  overnight_min_reinforcements: { label: 'Reinforcements for mid-size', help: 'Positions between the two thresholds need this many reinforcements to carry. Recommended 1.' },
  overnight_min_days_to_expiry: { label: 'Min days to expiry', help: 'Force square-off if expiry is closer than this — avoids the theta cliff. Recommended 2.' },
  block_overnight_into_weekend: { label: 'Block weekend carry', help: 'Square off on Fridays (3 days of theta over a weekend). Default off.' },
  max_holding_days: { label: 'Max holding period (days)', help: 'Hard cap — long options bleed; close dead-money trades. Recommended 5.' },
  square_off_buffer_minutes: { label: 'Square-off buffer (min)', help: 'Decide hold-vs-close this long before session close. Recommended 15.' },
  trail_enabled: { label: 'Trailing stop enabled', help: 'Continuously ratchet the stop up as profit thresholds are crossed.' },
  trail_trigger_pct: { label: 'Trail trigger step', help: 'Profit per ratchet step (fraction of entry).' },
  trail_lock_pct: { label: 'Trail lock per step', help: 'Stop raised by this fraction of entry per step crossed.' },
  trail_target_pct: { label: 'Trail target cap', help: 'Stop ratcheting once profit reaches this.' },
  option_cache_enabled: { label: 'Option-data cache', help: 'Persist every downloaded chain into a growing local research dataset.' },
  option_cache_snapshot_minutes: { label: 'Cache snapshot cadence (min)', help: 'At most one chain snapshot per instrument per this many minutes.' },
  stop_loss_pct: { label: 'Initial stop (−%)', help: 'Initial premium stop below entry.' },
  target_pct: { label: 'Initial target (+%)', help: 'Initial premium target above entry.' },
  max_stale_seconds: { label: 'Max stale (sec)', help: 'A mark older than this is stale — no SL/TP fires on it.' },
  position_loop_seconds: { label: 'Risk loop cadence (sec)', help: 'Fast lane: mark + trail + SL/TP.' },
  signal_loop_seconds: { label: 'Signal loop cadence (sec)', help: 'Slow lane: scan candles + entries.' },
  notify_enabled: { label: 'Notifications enabled', help: 'Master switch for Telegram alerts. No-op unless TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID are set in .env.' },
  notify_on_signal: { label: 'Alert on every signal', help: 'Also ping on each fresh entry signal — can be noisy. Default off.' },
  alert_proximity_pct: { label: 'Near-SL/TP alert threshold', help: 'Warn when the premium comes within this fraction of the stop or target level. Recommended 0.10 (10%).' },
  exec_market_max_spread_pct: { label: 'Market-order max spread', help: 'Send a MARKET order only when the bid-ask spread is at/under this fraction; wider routes a capped limit instead. Recommended 0.01 (1%).' },
  exec_limit_max_spread_pct: { label: 'Skip-entry spread', help: 'Above this spread an entry is SKIPPED — too illiquid to enter safely (e.g. some commodity options). Recommended 0.05 (5%).' },
  exec_max_slippage_pct: { label: 'Limit slippage cap', help: 'A marketable-limit order is capped this far off the mid price. Recommended 0.01 (1%).' },
  exec_min_top_qty_lots: { label: 'Min top-of-book (lots)', help: 'Require this many lots on the touch to send a MARKET order; a thinner book routes a capped limit. Recommended 1.' },
  max_daily_loss: { label: 'Daily loss halt (₹)', help: 'Stop opening new trades for the rest of the day once realized net loss reaches this. 0 = off. Recommended 5000.' },
  bot_capital_cap: { label: 'Bot capital cap (₹)', help: 'Hard ceiling on what the bot may ever deploy. 0 = no extra cap. Protects your capital even if Kite briefly mis-reports margin.' },
  capital_reserve: { label: 'Capital reserve (₹)', help: 'Live: account margin kept free for your own trades — the bot never dips into it.' },
  gtt_stop_enabled: { label: 'Exchange-side GTT stop', help: 'Live only: also place a Good-Till-Triggered stop on Zerodha so the position is protected even if the bot/laptop/internet goes down. Trails with the bot stop; cancelled when the bot exits.' },
}

const GROUPS: [string, (k: string) => boolean][] = [
  ['Reinforcement', (k) => k.startsWith('reinforce_') || k === 'max_reinforcements'],
  ['Overnight holding', (k) => k.startsWith('overnight_') || k === 'max_holding_days' || k === 'square_off_buffer_minutes' || k === 'block_overnight_into_weekend'],
  ['Trailing stop', (k) => k.startsWith('trail_')],
  ['Option-data cache', (k) => k.startsWith('option_cache_')],
  ['Risk & cadence', (k) => ['stop_loss_pct', 'target_pct', 'max_stale_seconds', 'position_loop_seconds', 'signal_loop_seconds'].includes(k)],
  ['Notifications', (k) => k.startsWith('notify_') || k === 'alert_proximity_pct'],
  ['Execution & risk limits', (k) => k.startsWith('exec_') || k === 'max_daily_loss' || k === 'bot_capital_cap' || k === 'capital_reserve' || k === 'gtt_stop_enabled'],
]

function Row({ r, onSaved }: { r: SettingRow; onSaved: () => void }) {
  const [v, setV] = useState(r.value)
  useEffect(() => setV(r.value), [r.value])
  const m = META[r.key] || { label: r.key, help: '' }
  const changed = String(v) !== String(r.default)
  const save = (val: any) =>
    setSetting(r.key, val).then((res: any) => {
      if (res && res.error) {
        setV(r.value) // reject out-of-bounds: revert to last good value
        window.alert(res.error)
      } else {
        onSaved()
      }
    })

  return (
    <div className="flex items-start gap-3 py-2 border-t border-edge/50">
      <div className="flex-1 min-w-0">
        <div className="text-sm text-zinc-200">{m.label}
          {changed && <span className="badge bg-blue-500/15 text-blue-300 ml-2">overridden</span>}</div>
        <div className="text-[11px] text-muted">{m.help}</div>
      </div>
      <div className="flex items-center gap-2">
        {r.type === 'bool' ? (
          <button onClick={() => { setV(!v); save(!v) }}
            className={`badge ${v ? 'bg-up/20 text-up' : 'bg-zinc-700/40 text-muted'}`}>{v ? 'on' : 'off'}</button>
        ) : (
          <input type="number" value={v} step={r.type === 'int' ? 1 : 'any'}
            onChange={(e) => setV(r.type === 'int' ? parseInt(e.target.value) : parseFloat(e.target.value))}
            onBlur={() => save(v)} onKeyDown={(e) => e.key === 'Enter' && save(v)}
            className="w-24 bg-panel2 border border-edge rounded px-2 py-1 text-xs tabular-nums" />
        )}
        <span className="text-[10px] text-muted w-20 text-right">default {String(r.default)}</span>
        <button disabled={!changed} onClick={() => resetSetting(r.key).then(onSaved)}
          className={`badge ${changed ? 'bg-zinc-700/40 text-muted hover:text-zinc-200' : 'opacity-30'}`}>reset</button>
      </div>
    </div>
  )
}

export default function SettingsView() {
  const [rows, setRows] = useState<SettingRow[]>([])
  const load = () => getSettings().then((d) => setRows(d.params || []))
  useEffect(() => { load() }, [])

  return (
    <div className="flex flex-col gap-3">
      <div className="card p-3">
        <div className="stat-label">Manual override — every value applies live, no code changes or restart</div>
        <div className="text-[11px] text-muted">Defaults shown are my recommended values; override any of them and the engine picks it up on the next loop.</div>
      </div>
      {GROUPS.map(([title, match]) => {
        const group = rows.filter((r) => match(r.key))
        if (!group.length) return null
        return (
          <div key={title} className="card p-3">
            <div className="text-sm font-semibold text-zinc-100 mb-1">{title}</div>
            {group.map((r) => <Row key={r.key} r={r} onSaved={load} />)}
          </div>
        )
      })}
    </div>
  )
}
