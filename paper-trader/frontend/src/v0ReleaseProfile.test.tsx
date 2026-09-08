import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AppForReleaseState, v0TabsFor } from './App'
import { V0MobileTopBar } from './components/MobileTopBar'
import { V0ReleaseBanner } from './components/SessionBanner'
import { V0TopBar } from './components/TopBar'
import { getReleaseProfile, parseReleaseProfileManifest } from './lib/api'
import type { ReleaseProfileManifest } from './lib/types'


const manifest: ReleaseProfileManifest = {
  schema: 'strategy-os-release-profile/1',
  release_profile: 'v0_research_signal',
  research_enabled: true,
  service_role: 'api',
  allowed_service_roles: ['api', 'research_worker', 'monitor', 'scheduler'],
  required_readiness_planes: ['execution', 'ledger', 'research'],
  execution_authority: false,
  capabilities: {
    strategy_graph: { state: 'ENABLED', ui_navigation: true },
    backtesting: {
      state: 'ENABLED_WITH_LIMIT',
      ui_navigation: false,
      reason: 'current cockpit is withheld',
    },
    execution: { state: 'UNAVAILABLE' },
    orders: { state: 'UNAVAILABLE' },
    positions: { state: 'UNAVAILABLE' },
    execution_stream: { state: 'UNAVAILABLE' },
  },
  route_rules: [{
    method: 'POST', template: '/api/execution/arm', state: 'UNAVAILABLE',
    capability: 'execution', reason: 'execution control',
  }],
}

const standardManifest: ReleaseProfileManifest = {
  schema: 'strategy-os-release-profile/1',
  release_profile: 'standard',
  research_enabled: false,
  service_role: null,
  allowed_service_roles: ['api', 'execution_worker'],
  required_readiness_planes: [],
  execution_authority: null,
  capabilities: { legacy_application: { state: 'ENABLED' } },
  route_rules: [],
}


describe('V0 server-owned navigation', () => {
  it('renders only surfaces explicitly enabled for navigation by the manifest', () => {
    expect(v0TabsFor(manifest)).toEqual([['graph', 'Strategy Graph']])
  })

  it('contains no trading cockpit controls in desktop or 390px headers', () => {
    const tabs = v0TabsFor(manifest)
    const setTab = () => undefined
    const markup = [
      renderToStaticMarkup(createElement(V0TopBar, { tab: 'graph', setTab, tabs })),
      renderToStaticMarkup(createElement(V0MobileTopBar, { tab: 'graph', setTab, tabs })),
      renderToStaticMarkup(createElement(V0ReleaseBanner)),
    ].join('\n')
    expect(markup).toContain('V0 Research')
    expect(markup).toContain('Strategy Graph')
    expect(markup).not.toMatch(/\bLIVE\b|\bARM(?:ED)?\b|\bKILL\b/i)
    expect(markup).not.toMatch(/\b(?:orders?|positions?|capital)\b/i)
  })
})


describe('behavioral release boundary', () => {
  it('mounts V0, standard, loading and failure states as distinct shells', () => {
    const v0 = renderToStaticMarkup(createElement(AppForReleaseState, {
      manifest, profileUnavailable: false,
    }))
    const standard = renderToStaticMarkup(createElement(AppForReleaseState, {
      manifest: standardManifest, profileUnavailable: false,
    }))
    const loading = renderToStaticMarkup(createElement(AppForReleaseState, {
      manifest: null, profileUnavailable: false,
    }))
    const failure = renderToStaticMarkup(createElement(AppForReleaseState, {
      manifest: null, profileUnavailable: true,
    }))

    expect(v0).toContain('V0 Research')
    expect(v0).not.toMatch(/\bKILL\b|Options Paper Trader/i)
    expect(standard).toContain('PAPER')
    expect(standard).toContain('KILL')
    expect(loading).toContain('Loading release profile')
    expect(failure).toContain('Product surfaces remain unavailable')
    expect(failure).not.toMatch(/\bKILL\b|Options Paper Trader/i)
  })

  it('rejects malformed or authority-weak V0 manifests', () => {
    const invalid = [
      null,
      {},
      { ...manifest, capabilities: null },
      { ...manifest, route_rules: null },
      { ...manifest, execution_authority: true },
      { ...manifest, service_role: 'other' },
      { ...manifest, route_rules: [] },
      { ...manifest, capabilities: { ...manifest.capabilities, orders: { state: 'ENABLED' } } },
      { ...manifest, capabilities: { ...manifest.capabilities, strategy_graph: { state: 'ENABLED', ui_navigation: 'yes' } } },
    ]
    invalid.forEach((value) => expect(() => parseReleaseProfileManifest(value)).toThrow())
    expect(parseReleaseProfileManifest(manifest)).toEqual(manifest)
    expect(parseReleaseProfileManifest(standardManifest)).toEqual(standardManifest)
  })

  it('uses the same strict parser for fetched manifests and rejects HTTP failure', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => manifest,
    })))
    await expect(getReleaseProfile()).resolves.toEqual(manifest)

    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: false,
      status: 503,
      json: async () => ({}),
    })))
    await expect(getReleaseProfile()).rejects.toThrow('release profile unavailable')
  })
})

afterEach(() => vi.unstubAllGlobals())
