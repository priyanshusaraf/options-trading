import { describe, expect, it } from 'vitest'
import { explainValue, formatRupees } from './settingFormat'

describe('rupee formatting uses Indian digit grouping', () => {
  it('groups in lakhs, not thousands', () => {
    expect(formatRupees(1234567)).toBe('₹12,34,567')
  })
  it('leaves small numbers alone', () => {
    expect(formatRupees(500)).toBe('₹500')
    expect(formatRupees(7000)).toBe('₹7,000')
  })
  it('handles negatives', () => {
    expect(formatRupees(-2500)).toBe('−₹2,500')
  })
})

describe('explaining a stored value', () => {
  it('shows a stop as a NEGATIVE percent — 0.30 is a 30% loss, not a gain', () => {
    expect(explainValue('stop_loss_pct', 0.3)).toBe('−30%')
    expect(explainValue('intraday_stop_loss_pct', 0.01)).toBe('−1%')
  })

  it('shows other fractions as plain percent', () => {
    expect(explainValue('target_pct', 0.6)).toBe('60%')
    expect(explainValue('daily_profit_giveback_frac', 0.3)).toBe('30%')
  })

  it('reads 0 on a fraction as off, not as 0%', () => {
    expect(explainValue('alert_proximity_pct', 0)).toBe('off')
  })

  it('renders durations', () => {
    expect(explainValue('reentry_cooldown_minutes', 15)).toBe('15 min')
    expect(explainValue('position_loop_seconds', 1)).toBe('1s')
    expect(explainValue('max_holding_days', 5)).toBe('5d')
  })

  it('reads a 0 duration as off', () => {
    expect(explainValue('reentry_cooldown_minutes', 0)).toBe('off')
  })

  it('renders rupee limits with grouping, and 0 as no cap', () => {
    expect(explainValue('max_daily_loss', 5000)).toBe('₹5,000')
    expect(explainValue('bot_capital_cap', 0)).toBe('no cap')
    expect(explainValue('intraday_max_margin', 7000)).toBe('₹7,000')
  })

  it('renders leverage', () => {
    expect(explainValue('intraday_leverage', 5)).toBe('5×')
  })

  it('renders booleans', () => {
    expect(explainValue('trail_enabled', true)).toBe('on')
    expect(explainValue('notify_on_signal', false)).toBe('off')
  })

  it('says nothing when a bare count already reads fine', () => {
    expect(explainValue('max_open_positions', 4)).toBeNull()
    expect(explainValue('max_reinforcements', 3)).toBeNull()
  })
})

describe('units that are NOT fractions — each of these was a real bug', () => {
  it('gap_guard_pct is already a percent: 0.6 is 0.6%, not 60%', () => {
    // config.py:166 defaults it to 0.6 meaning 0.6%, its bound is (0, 10), and
    // runner.py logs `gapped ≥ {value}%`. Multiplying by 100 was a 100x error
    // on a safety knob.
    expect(explainValue('gap_guard_pct', 0.6)).toBe('0.6%')
    expect(explainValue('gap_guard_pct', 1)).toBe('1%')
  })

  it('intraday_profit_lock_threshold is RUPEES despite ending in _threshold', () => {
    expect(explainValue('intraday_profit_lock_threshold', 600)).toBe('₹600')
  })

  it('overtrade thresholds are signal COUNTS, not fractions', () => {
    expect(explainValue('overtrade_today_threshold', 5)).toBeNull()
    expect(explainValue('overtrade_rolling_threshold', 12)).toBeNull()
  })

  it('order_failure_disarm_count is a count', () => {
    expect(explainValue('order_failure_disarm_count', 3)).toBeNull()
  })

  it('genuine fractions still read as percent', () => {
    expect(explainValue('intraday_profit_lock_frac', 0.3)).toBe('30%')
    expect(explainValue('overnight_auto_pct', 0.1)).toBe('10%')
  })
})
