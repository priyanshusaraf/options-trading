// Liquidity-priority order (mirrors backend core/instruments.py)
export const PRIORITY = [
  'NIFTY', 'GOLDM', 'SILVERM', 'CRUDEOIL', 'BANKNIFTY', 'NATURALGAS',
  'SENSEX', 'COPPERM', 'ZINC', 'LEAD', 'DHANIYA',
]

export const prio = (k: string): number => {
  const i = PRIORITY.indexOf(k)
  return i < 0 ? 99 : i
}

// stable per-instrument colours for equity curves
export const COLORS: Record<string, string> = {
  NIFTY: '#3b82f6', GOLDM: '#e0b341', SILVERM: '#c0c4cc', CRUDEOIL: '#ef4444',
  BANKNIFTY: '#8b5cf6', NATURALGAS: '#06b6d4', SENSEX: '#22c55e', COPPERM: '#f97316',
  ZINC: '#14b8a6', LEAD: '#a3a3a3', DHANIYA: '#ec4899',
}
export const colorFor = (k: string) => COLORS[k] || '#3b82f6'
