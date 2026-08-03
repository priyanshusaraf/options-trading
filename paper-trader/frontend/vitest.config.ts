import path from 'path'
import { defineConfig } from 'vitest/config'

// Keep discovery on the three directories that own frontend behavior tests.
// Component render tests use .test.ts with React.createElement because this
// suite deliberately runs in Node rather than carrying a browser DOM shim.
export default defineConfig({
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  test: {
    include: ['src/ledger/**/*.test.ts', 'src/lib/**/*.test.ts', 'src/views/**/*.test.ts'],
    environment: 'node',
  },
})
