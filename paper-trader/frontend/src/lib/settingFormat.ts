/* How a stored setting value should READ to a human.
 *
 * The stored value never changes — this is presentation only. `stop_loss_pct`
 * is 0.30 in the DB and in the input box; it just also says "−30%" beside it,
 * because "0.30" does not tell you it is a thirty-percent stop, and getting
 * that wrong on a live account is expensive.
 */

/** Indian digit grouping: 12,34,567 rather than 1,234,567. */
export function formatRupees(n: number): string {
  if (!isFinite(n)) return String(n)
  const neg = n < 0
  const s = Math.abs(Math.round(n)).toString()
  let out: string
  if (s.length <= 3) {
    out = s
  } else {
    const last3 = s.slice(-3)
    const rest = s.slice(0, -3)
    out = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + ',' + last3
  }
  return `${neg ? '−' : ''}₹${out}`
}

/**
 * A short human gloss for a setting value, or null when the raw number already
 * reads fine (counts, plain integers).
 *
 * `key` decides the unit — the backend only tells us int/float/bool, which is
 * not enough to know that `_pct` is a fraction and `_minutes` is a duration.
 */
export function explainValue(key: string, value: unknown): string | null {
  if (typeof value === 'boolean') return value ? 'on' : 'off'
  if (typeof value !== 'number' || !isFinite(value)) return null

  // Values that are ALREADY a percentage, not a fraction. Multiplying these
  // by 100 is a 100× error, and on gap_guard_pct it is a 100× error on a
  // safety knob: config.py:166 defaults it to 0.6 meaning 0.6%, its bound is
  // (0, 10), and the engine logs it as `gapped ≥ {value}%`.
  if (ALREADY_PERCENT.has(key)) return value === 0 ? 'off' : `${round(value)}%`

  // Rupee amounts that happen to end in a fraction-ish suffix.
  if (RUPEE_KEYS.has(key)) return value === 0 ? 'no cap' : formatRupees(value)

  // Plain counts. `_threshold` is NOT a reliable fraction marker — the
  // overtrade thresholds are signal counts.
  if (COUNT_KEYS.has(key)) return null

  // A stop is a loss, so show its sign — 0.30 is −30%, not +30%.
  if (key.includes('stop_loss_pct')) return `−${round(value * 100)}%`
  if (key.endsWith('_pct') || key.endsWith('_frac')) {
    if (value === 0) return 'off'
    return `${round(value * 100)}%`
  }
  if (key.endsWith('_minutes')) return value === 0 ? 'off' : `${round(value)} min`
  if (key.endsWith('_seconds')) return `${round(value)}s`
  if (key.endsWith('_days')) return `${round(value)}d`
  if (RUPEE_KEYS.has(key)) return value === 0 ? 'no cap' : formatRupees(value)
  if (key.endsWith('_leverage')) return `${round(value)}×`
  return null
}

/** Values stored as a PERCENT already, so they must not be multiplied by 100.
 *  Verified against app/core/config.py and the engine's own log strings. */
const ALREADY_PERCENT = new Set(['gap_guard_pct'])

/** Bare counts. Listed because `_threshold` is not a reliable fraction marker. */
const COUNT_KEYS = new Set([
  'overtrade_today_threshold', 'overtrade_rolling_threshold',
  'order_failure_disarm_count', 'max_round_trips_per_day',
])

/** Keys whose numbers are rupees. Named explicitly rather than guessed, because
 *  a wrong guess here misreads a capital limit. */
const RUPEE_KEYS = new Set([
  'max_daily_loss', 'max_open_drawdown', 'bot_capital_cap', 'capital_reserve',
  'max_capital_per_trade', 'intraday_min_margin', 'intraday_max_margin',
  'intraday_purple_margin',
  // Rupees despite the name: config.py defaults it to 600.0, i.e. ₹600 of
  // profit, not a fraction.
  'intraday_profit_lock_threshold',
])

function round(n: number): string {
  const r = Math.round(n * 100) / 100
  return String(r)
}

/**
 * Settings that can halt trading, move real money, or disable a safety net.
 * These are separated in the UI so they are never skimmed past among tuning
 * knobs. Membership is deliberately explicit — a pattern match would quietly
 * mis-tier a new key.
 */
export const DANGER_KEYS = new Set([
  'max_daily_loss',
  'max_open_drawdown',
  'bot_capital_cap',
  'capital_reserve',
  'gtt_stop_enabled',
  'intraday_enabled',
  'order_failure_disarm_count',
  'gap_guard_enabled',
  'gap_guard_pct',
  'gap_guard_index',
  'gap_guard_resume',
  'daily_profit_lock_pct',
  'daily_profit_giveback_frac',
  'max_round_trips_per_day',
  'max_stale_seconds',
])
