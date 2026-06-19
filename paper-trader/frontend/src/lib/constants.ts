// Liquidity-priority order (mirrors backend core/instruments.py seed)
export const PRIORITY = [
  'NIFTY', 'GOLDM', 'SILVERM', 'CRUDEOIL', 'BANKNIFTY', 'NATURALGAS',
  'SENSEX', 'COPPERM',
]

export const prio = (k: string): number => {
  const i = PRIORITY.indexOf(k)
  return i < 0 ? 99 : i
}

// stable per-instrument colours for equity curves
export const COLORS: Record<string, string> = {
  NIFTY: '#3b82f6', GOLDM: '#e0b341', SILVERM: '#c0c4cc', CRUDEOIL: '#ef4444',
  BANKNIFTY: '#8b5cf6', NATURALGAS: '#06b6d4', SENSEX: '#22c55e', COPPERM: '#f97316',
}

const PALETTE = ['#3b82f6', '#e0b341', '#ef4444', '#8b5cf6', '#06b6d4', '#22c55e',
  '#f97316', '#ec4899', '#14b8a6', '#a3a3a3', '#eab308', '#60a5fa']

// stable colour for any instrument key (seed names fixed; others hashed)
export const colorFor = (k: string): string => {
  if (COLORS[k]) return COLORS[k]
  let h = 0
  for (let i = 0; i < k.length; i++) h = (h * 31 + k.charCodeAt(i)) >>> 0
  return PALETTE[h % PALETTE.length]
}
