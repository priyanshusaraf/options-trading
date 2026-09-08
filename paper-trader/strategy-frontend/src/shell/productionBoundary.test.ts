// @vitest-environment node
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import { build, loadConfigFromFile } from 'vite'
import { describe, expect, it } from 'vitest'

const root = fileURLToPath(new URL('../../', import.meta.url))
let cachedProductionBuild: ReturnType<typeof build> | null = null

async function productionBuild() {
  // Vitest uses NODE_ENV=test; Vite derives DEV from NODE_ENV, not build mode.
  // Match the real npm build environment to inspect the shipped graph.
  if (cachedProductionBuild === null) {
    const previous = process.env.NODE_ENV
    process.env.NODE_ENV = 'production'
    cachedProductionBuild = build({ root, logLevel: 'silent', build: { write: false } })
      .finally(() => { process.env.NODE_ENV = previous })
  }
  return cachedProductionBuild
}

function chunksFrom(result: Awaited<ReturnType<typeof build>>) {
  const outputs = (Array.isArray(result) ? result : [result]).flatMap((item) => 'output' in item ? item.output : [])
  return { outputs, chunks: outputs.filter((item) => item.type === 'chunk') }
}

describe('production dependency boundary', () => {
  it('build configuration ignores development certificate paths', async () => {
    const previousCert = process.env.STRATEGY_OS_DEV_TLS_CERT
    const previousKey = process.env.STRATEGY_OS_DEV_TLS_KEY
    process.env.STRATEGY_OS_DEV_TLS_CERT = '/missing/development-certificate.crt'
    process.env.STRATEGY_OS_DEV_TLS_KEY = '/missing/development-certificate.key'
    try {
      const loaded = await loadConfigFromFile({ command: 'build', mode: 'production' }, resolve(root, 'vite.config.ts'))
      expect(loaded?.config.server?.https).toBeUndefined()
    } finally {
      if (previousCert === undefined) delete process.env.STRATEGY_OS_DEV_TLS_CERT
      else process.env.STRATEGY_OS_DEV_TLS_CERT = previousCert
      if (previousKey === undefined) delete process.env.STRATEGY_OS_DEV_TLS_KEY
      else process.env.STRATEGY_OS_DEV_TLS_KEY = previousKey
    }
  })

  it('tree-shakes every prototype module and excludes fixture/execution surfaces from the artifact', async () => {
    const result = await productionBuild()
    const { outputs, chunks } = chunksFrom(result)
    expect(chunks.length).toBeGreaterThan(0)
    const modules = chunks.flatMap((chunk) => Object.keys(chunk.modules))
    expect(modules.some((name) => name.endsWith('/src/shell/PrecisionShell.tsx'))).toBe(true)
    expect(modules.some((name) => name.endsWith('/src/product/routes.tsx'))).toBe(true)
    const sharedSelectModules = new Set([
      resolve(root, 'src/components/TraderSelect.tsx'),
      resolve(root, 'src/components/trader-select.css'),
    ])
    expect(modules.filter((name) => /\/src\/(?:data|directions|components|pages|test)\/|PrototypeApp|prototype-entry/.test(name))
      .filter((name) => !sharedSelectModules.has(name))).toEqual([])
    expect(modules.some((name) => name.includes('/node_modules/@xyflow/react/'))).toBe(true)
    const code = chunks.map((chunk) => chunk.code).join('\n')
    for (const sentinel of ['NIFTY-ORB-15', 'BT-241', 'Stage paper deployment', 'Opening range window', 'Capital, exposure and strategy attribution', 'custom Workspace']) {
      expect(code).not.toContain(sentinel)
    }
    expect(code).toContain('/graphs/v2/create')
    expect(code).not.toContain('Canonical graph JSON')
    const styles = outputs.filter((item) => item.type === 'asset').filter((item) => item.fileName.endsWith('.css'))
    expect(styles.length).toBeGreaterThan(0)
    expect(styles.map((item) => String(item.source)).join('')).not.toMatch(/refined--|graph-node|builder-shell/)
  }, 30000)

  it('has one REST transport across the complete production module graph and no application socket', async () => {
    const { chunks } = chunksFrom(await productionBuild())
    const productionModules = [...new Set(chunks.flatMap((chunk) => Object.keys(chunk.modules))
      .map((name) => name.split('?', 1)[0])
      .filter((name) => name.startsWith(resolve(root, 'src')) && /\.[cm]?[jt]sx?$/.test(name)))]
    expect(productionModules.some((name) => name.endsWith('/src/auth/AuthGate.tsx'))).toBe(true)
    expect(productionModules.some((name) => name.endsWith('/src/product/routes.tsx'))).toBe(true)
    for (const file of productionModules.filter((name) => !name.endsWith('/src/shell/api.ts'))) {
      expect(readFileSync(file, 'utf8'), file).not.toMatch(/\bfetch\s*\(|XMLHttpRequest|new WebSocket|axios|EventSource/)
    }
    const transport = readFileSync(resolve(root, 'src/shell/api.ts'), 'utf8')
    expect(transport.match(/\bfetch\s*\(/g)).toHaveLength(1)
    expect(transport).not.toMatch(/XMLHttpRequest|new WebSocket|axios|EventSource/)
  })

  it('executes and kills a production fixture-import mutation', async () => {
    const previous = process.env.NODE_ENV
    process.env.NODE_ENV = 'production'
    try {
      const mutated = await build({ root, logLevel: 'silent', plugins: [{
        name: 'inject-forbidden-fixture-import', enforce: 'pre',
        transform(code, id) { return id.endsWith('/src/research/ResearchWorkspace.tsx')
          ? { code: `import '../data/fixtures.ts'\n${code}`, map: null } : null },
      }], build: { write: false } })
      const modules = chunksFrom(mutated).chunks.flatMap((chunk) => Object.keys(chunk.modules))
      expect(modules.some((name) => name.endsWith('/src/data/fixtures.ts'))).toBe(true)
      expect(modules.filter((name) => /\/src\/(?:data|directions|components|pages|test)\//.test(name))).not.toEqual([])
    } finally { process.env.NODE_ENV = previous }
  }, 30000)
})
