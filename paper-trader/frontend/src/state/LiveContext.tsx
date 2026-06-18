import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import type { LiveState, LogEntry } from '../lib/types'

interface Ctx { state: LiveState | null; logs: LogEntry[]; connected: boolean }
const LiveCtx = createContext<Ctx>({ state: null, logs: [], connected: false })
export const useLive = () => useContext(LiveCtx)

export function LiveProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<LiveState | null>(null)
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    let stop = false
    const connect = () => {
      const ws = new WebSocket(`ws://${location.host}/ws`)
      wsRef.current = ws
      ws.onopen = () => setConnected(true)
      ws.onclose = () => { setConnected(false); if (!stop) setTimeout(connect, 1500) }
      ws.onmessage = (e) => {
        const m = JSON.parse(e.data)
        if (m.type === 'state') setState(m.data)
        else if (m.type === 'log') setLogs((p) => [...p.slice(-500), m.data])
        else if (m.type === 'logs') setLogs(m.data)
      }
    }
    connect()
    return () => { stop = true; wsRef.current?.close() }
  }, [])

  return <LiveCtx.Provider value={{ state, logs, connected }}>{children}</LiveCtx.Provider>
}
