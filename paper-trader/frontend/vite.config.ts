import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The backend runs on :8090 (8000 is left free for the unrelated analyst app).
// Dev server proxies REST + WebSocket so the frontend just calls /api and /ws.
const BACKEND = process.env.VITE_BACKEND ?? 'http://127.0.0.1:8090'

// Bind to the Tailscale interface so phones on the tailnet can reach the cockpit
// WITHOUT exposing it to the local LAN. The backend stays on 127.0.0.1 and is only
// reachable through the proxy below. Override with VITE_HOST=0.0.0.0 to serve the LAN too.
const HOST = process.env.VITE_HOST ?? '100.120.27.71'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    host: HOST,
    port: 5173,
    // MagicDNS hostnames must be allow-listed or Vite blocks the Host header.
    allowedHosts: ['.ts.net'],
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/ws': { target: BACKEND.replace('http', 'ws'), ws: true },
    },
  },
})
