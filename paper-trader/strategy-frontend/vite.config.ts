import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { readFileSync } from 'node:fs'

const localCertificate = process.env.STRATEGY_OS_DEV_TLS_CERT
const localKey = process.env.STRATEGY_OS_DEV_TLS_KEY

export default defineConfig(({ command }) => ({
  plugins: [react(), tailwindcss()],
  server: {
    https: command === 'serve' && localCertificate && localKey ? {
      cert: readFileSync(localCertificate), key: readFileSync(localKey),
    } : undefined,
    proxy: { '/api': { target: 'http://127.0.0.1:8090', xfwd: true } },
  },
  test: {
    environment: 'jsdom',
    globals: false,
    setupFiles: ['./src/test/setup.ts'],
  },
}))
