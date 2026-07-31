import { defineConfig } from 'vitest/config'

// Scoped deliberately: the journal is the only part of this frontend with
// tests, and widening the glob would silently claim to cover views that have
// none.
export default defineConfig({
  test: {
    include: ['src/ledger/**/*.test.ts', 'src/lib/**/*.test.ts', 'src/views/**/*.test.ts'],
    environment: 'node',
  },
})
