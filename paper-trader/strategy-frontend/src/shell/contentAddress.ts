function integerJson(value: number): string {
  if (!Number.isSafeInteger(value)) throw new TypeError('Document numbers must be safe integers.')
  return JSON.stringify(value)
}
function scalarJson(value: unknown): string | undefined {
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return JSON.stringify(value)
  return typeof value === 'number' ? integerJson(value) : undefined
}

/** Canonical JSON for the closed, integer-only documents used by these API contracts. */
export function canonicalJson(value: unknown, depth = 0): string {
  if (depth > 8) throw new TypeError('Document nesting exceeds the contract bound.')
  const scalar = scalarJson(value)
  if (scalar !== undefined) return scalar
  if (Array.isArray(value)) return `[${value.map((item) => canonicalJson(item, depth + 1)).join(',')}]`
  if (typeof value !== 'object' || Object.getPrototypeOf(value) !== Object.prototype) throw new TypeError('Document must contain plain JSON values.')
  const object = value as Record<string, unknown>
  return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(object[key], depth + 1)}`).join(',')}}`
}

export async function contentAddress(value: unknown): Promise<string> {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonicalJson(value)))
  return `sha256:${Array.from(new Uint8Array(bytes), (value) => value.toString(16).padStart(2, '0')).join('')}`
}
