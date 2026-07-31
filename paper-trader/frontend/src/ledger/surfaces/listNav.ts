/* The active surface publishes its list verbs here; the global keymap reads
   them. This keeps §9.4's j/k/space/⏎/x bindings identical across the blotter,
   the vault, the timeline and the playbook without each one re-registering a
   window listener. */

import { useEffect } from 'react'
import type { ListNav } from '../keys/useKeymap'

let current: ListNav | undefined

export function registerListNav(nav: ListNav): () => void {
  current = nav
  return () => {
    if (current === nav) current = undefined
  }
}

export function getListNav(): ListNav | undefined {
  return current
}

/** Convenience for surfaces that only need the effect wiring. */
export function useListNav(nav: ListNav, deps: unknown[]) {
  useEffect(
    () => registerListNav(nav),
    // The surface owns the dependency list; nav is rebuilt on each render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    deps,
  )
}
