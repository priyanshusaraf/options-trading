/* Server-backed persistence.
 *
 * The source shipped a debounced whole-DB snapshot into IndexedDB. The shape is
 * unchanged — one blob, one key — but the key now lives on the backend so the
 * journal is the same on the Mac and on the phone. Everything above this file
 * (store.ts, actions.ts, all 43 mutators, undo/redo) is untouched, which is the
 * whole point: the business rules stay in the closures the design put them in.
 *
 * Concurrency is compare-and-set. We send the version we last read; a 409 means
 * another device moved first, and the caller reloads rather than clobbering.
 * For one user on two devices that is the honest trade — a merge strategy is
 * explicitly out of scope (design spec §3.1).
 *
 * The filename is a deliberate lie, kept for one reason: store.ts imports
 * `./idb`, and not changing that import is what makes this a one-file swap.
 */

const SNAPSHOT_URL = '/api/ledger/snapshot'
const ARTIFACT_URL = '/api/ledger/artifacts'

export class SnapshotConflictError extends Error {
  constructor(public current: number) {
    super(`snapshot conflict — server is at version ${current}`)
    this.name = 'SnapshotConflictError'
  }
}

let baseVersion: number | null = null

export function getBaseVersion(): number | null {
  return baseVersion
}

/** Test seam. Never called by application code. */
export function __resetForTests(): void {
  baseVersion = null
}

function authHeaders(): Record<string, string> {
  const token = import.meta.env.VITE_PT_TOKEN
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function loadSnapshot<T>(): Promise<T | null> {
  try {
    const res = await fetch(SNAPSHOT_URL, { headers: authHeaders() })
    if (res.status === 404) {
      baseVersion = null
      return null
    }
    if (!res.ok) return null
    const body = (await res.json()) as { version: number; payload: T }
    baseVersion = body.version
    return body.payload
  } catch {
    // A dead backend must never stop the journal from opening — the same
    // reasoning the IndexedDB version had for swallowing a blocked open. The
    // status dot reports the truth; the user can still read what is on screen.
    return null
  }
}

export async function saveSnapshot<T>(value: T): Promise<void> {
  const res = await fetch(SNAPSHOT_URL, {
    method: 'PUT',
    headers: { 'content-type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ base_version: baseVersion, payload: value }),
  })
  if (res.status === 409) {
    const body = (await res.json()) as { current: number }
    baseVersion = body.current
    throw new SnapshotConflictError(body.current)
  }
  if (!res.ok) throw new Error(`snapshot save failed: ${res.status}`)
  const body = (await res.json()) as { version: number }
  baseVersion = body.version
}

export async function clearSnapshot(): Promise<void> {
  // Settings → Reset. Writing a null payload is enough: boot() treats a falsy
  // payload the same as a missing one, so the next load re-seeds.
  await fetch(SNAPSHOT_URL, {
    method: 'PUT',
    headers: { 'content-type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ base_version: baseVersion, payload: null }),
  })
  baseVersion = null
}

// ── Artifacts ─────────────────────────────────────────────────────────────
// Screenshots are held OUT of the snapshot: the source stored them as base64
// data URLs inside the blob, so every debounced save rewrote every screenshot.
// Over HTTP that is untenable. See design spec §3.2.

export async function uploadArtifact(id: string, file: Blob): Promise<string> {
  const form = new FormData()
  form.append('artifact_id', id)
  form.append('file', file)
  const res = await fetch(ARTIFACT_URL, {
    method: 'POST', headers: authHeaders(), body: form,
  })
  if (!res.ok) throw new Error(`artifact upload failed: ${res.status}`)
  return artifactUrl(id)
}

export function artifactUrl(id: string): string {
  return `${ARTIFACT_URL}/${id}`
}

export async function deleteArtifactBytes(id: string): Promise<void> {
  await fetch(`${ARTIFACT_URL}/${id}`, { method: 'DELETE', headers: authHeaders() })
}
