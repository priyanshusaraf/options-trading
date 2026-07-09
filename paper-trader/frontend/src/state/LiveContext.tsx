import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import type { LiveState, LiveTick, LogEntry, PositionTick, ProviderHealth } from '../lib/types'

interface Ctx {
  state: LiveState | null; logs: LogEntry[]; connected: boolean
  liveTicks: Record<string, LiveTick>
  positionTicks: Record<string, PositionTick>
  health: ProviderHealth | null
}
const LiveCtx = createContext<Ctx>({
  state: null, logs: [], connected: false, liveTicks: {}, positionTicks: {}, health: null,
})
export const useLive = () => useContext(LiveCtx)

export function LiveProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<LiveState | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [liveTicks, setLiveTicks] = useState<Record<string, LiveTick>>({})
  const [positionTicks, setPositionTicks] = useState<Record<string, PositionTick>>({})
  const [health, setHealth] = useState<ProviderHealth | null>(null)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    let stop = false
    const TOKEN = import.meta.env.VITE_PT_TOKEN as string | undefined
    const connect = () => {
      const ws = new WebSocket(
        `ws://${location.host}/ws${TOKEN ? `?token=${encodeURIComponent(TOKEN)}` : ''}`,
      )
      wsRef.current = ws
      ws.onopen = () => setConnected(true)
      ws.onclose = () => { setConnected(false); if (!stop) setTimeout(connect, 1500) }
      ws.onmessage = (e) => {
        const m = JSON.parse(e.data)
        if (m.type === 'state') {
          setState(m.data)
          if (m.data?.health) setHealth(m.data.health)
          if (m.data?.position_ticks) setPositionTicks(m.data.position_ticks)
        }
        else if (m.type === 'position_ticks') setPositionTicks(m.data || {})
        // keep a generous buffer (1000) so routine DISARMED_SKIP/COOLDOWN_SKIP
        // chatter doesn't evict ERROR/TRADE lines during an outage (C9)
        else if (m.type === 'log') setLogs((p) => [...p.slice(-1000), m.data])
        else if (m.type === 'logs') setLogs(m.data)
        else if (m.type === 'live_ticks') setLiveTicks(m.data || {})
      }
    }
    connect()
    return () => { stop = true; wsRef.current?.close() }
  }, [])

  return (
    <LiveCtx.Provider value={{ state, logs, connected, liveTicks, positionTicks, health }}>
      {children}
    </LiveCtx.Provider>
  )
}
