import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  __resetForTests, clearSnapshot, getBaseVersion, loadSnapshot,
  saveSnapshot, SnapshotConflictError,
} from './idb'

function mockFetch(handler: (url: string, init?: RequestInit) => Response) {
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => handler(url, init)))
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status, headers: { 'content-type': 'application/json' },
  })

beforeEach(() => {
  __resetForTests()
  vi.unstubAllGlobals()
})

describe('the snapshot client', () => {
  it('returns null and records no version when the server has nothing', async () => {
    mockFetch(() => json({ detail: 'no snapshot' }, 404))
    expect(await loadSnapshot()).toBeNull()
    expect(getBaseVersion()).toBeNull()
  })

  it('returns the payload and records the version', async () => {
    mockFetch(() => json({ version: 7, payload: { trades: [] } }))
    expect(await loadSnapshot()).toEqual({ trades: [] })
    expect(getBaseVersion()).toBe(7)
  })

  it('sends the recorded version as base_version and advances it on success', async () => {
    let seen: any = null
    mockFetch((_url, init) => {
      if (init?.method === 'PUT') {
        seen = JSON.parse(String(init.body))
        return json({ version: 8 })
      }
      return json({ version: 7, payload: {} })
    })
    await loadSnapshot()
    await saveSnapshot({ trades: [] })
    expect(seen.base_version).toBe(7)
    expect(getBaseVersion()).toBe(8)
  })

  it('sends base_version null before anything has been loaded', async () => {
    let seen: any = null
    mockFetch((_u, init) => {
      seen = JSON.parse(String(init!.body))
      return json({ version: 1 })
    })
    await saveSnapshot({ trades: [] })
    expect(seen.base_version).toBeNull()
  })

  it('throws SnapshotConflictError on 409 and adopts the server version', async () => {
    mockFetch(() => json({ detail: 'version conflict', current: 12 }, 409))
    await expect(saveSnapshot({})).rejects.toBeInstanceOf(SnapshotConflictError)
    expect(getBaseVersion()).toBe(12)
  })

  it('propagates a write failure so the store can show "error"', async () => {
    mockFetch(() => json({ detail: 'boom' }, 500))
    await expect(saveSnapshot({})).rejects.toThrow()
  })

  it('never throws out of loadSnapshot — a dead backend must not stop the journal opening', async () => {
    vi.stubGlobal('fetch', vi.fn(() => { throw new Error('offline') }))
    expect(await loadSnapshot()).toBeNull()
  })

  it('clearSnapshot resets the tracked version', async () => {
    mockFetch(() => json({ version: 3, payload: {} }))
    await loadSnapshot()
    expect(getBaseVersion()).toBe(3)
    mockFetch(() => json({ version: 4 }))
    await clearSnapshot()
    expect(getBaseVersion()).toBeNull()
  })
})
