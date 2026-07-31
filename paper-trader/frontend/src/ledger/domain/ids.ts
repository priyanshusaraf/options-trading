/* Stable IDs. §8 "Every trade, note, session, setup and screenshot has a
   stable ID" — which is what makes peek/open/split/copy-link uniform. */

let counter = 0

export function uid(prefix = 'x'): string {
  counter += 1
  const t = Date.now().toString(36)
  const r = Math.random().toString(36).slice(2, 7)
  return `${prefix}_${t}${counter.toString(36)}${r}`
}

/** §8 ⌘⇧C copies a link to any object. */
export function objectUrl(kind: string, id: string): string {
  return `ledger://${kind}/${id}`
}
