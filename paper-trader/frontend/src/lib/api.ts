const j = (u: string) => fetch(u).then((r) => r.json())

export const getStatus = () => j('/api/status')
export const getInstruments = () => j('/api/instruments')
export const getCandles = (key: string) => j(`/api/candles/${key}`)
export const getOptionCandles = (key: string) => j(`/api/option-candles/${key}`)
export const getOptionsCalc = (key: string) => j(`/api/options-calc/${key}`)
export const getDashboard = () => j('/api/dashboard')
export const getLogs = (n = 300) => j(`/api/logs?limit=${n}`)

export const toggleInstrument = (key: string, enabled: boolean) =>
  fetch(`/api/instruments/${key}/toggle`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  }).then((r) => r.json())
