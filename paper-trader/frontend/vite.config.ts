import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The backend runs on :8090 (8000 is left free for the unrelated analyst app).
// Dev server proxies REST + WebSocket so the frontend just calls /api and /ws.
const BACKEND = process.env.VITE_BACKEND ?? 'http://127.0.0.1:8090'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/ws': { target: BACKEND.replace('http', 'ws'), ws: true },
    },
  },
})
