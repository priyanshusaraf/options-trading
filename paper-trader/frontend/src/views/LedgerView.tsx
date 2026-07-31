import { useEffect, useState } from 'react'

import { App as LedgerApp } from '../ledger/app/App'
import MobileLedger from '../ledger/mobile/MobileLedger'
import { boot } from '../ledger/data/store'
import '../ledger/styles/tokens.css'
import '../ledger/styles/base.css'

// The same 768px breakpoint the rest of the app uses (App.tsx), so the phone
// header and the phone journal agree about what "mobile" means.
function useIsDesktop() {
  const [isDesktop, setIsDesktop] = useState(
    () => typeof window !== 'undefined'
      && window.matchMedia('(min-width: 768px)').matches,
  )
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 768px)')
    const onChange = () => setIsDesktop(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return isDesktop
}

/**
 * THE LEDGER, mounted full-bleed inside paper-trader.
 *
 * Two things this wrapper exists to guarantee:
 *
 * 1. `.ledger-root` is the CSS scope. Every LEDGER selector is prefixed under it
 *    at build time (see postcss.config.js) and its document-level reset is
 *    collapsed onto it, so neither stylesheet can reach the other.
 *
 * 2. LEDGER's `useKeymap` installs ONE window keydown listener that
 *    preventDefaults bare t/o/n/j/k/space/x/e/f and a pile of Cmd chords. That
 *    listener lives inside LedgerApp, so unmounting this component removes it.
 *    Which is why the journal must never be rendered behind a hidden tab — it
 *    would swallow keystrokes on every other view.
 *
 * `position: fixed; inset: 0` gives the full-bleed sub-app: LEDGER's shell wants
 * a fixed frame with its own internal scroll panes, and letting it flow inside
 * `<main className="flex-1 p-3">` would fight that.
 */
export default function LedgerView({ onExit }: { onExit: () => void }) {
  const isDesktop = useIsDesktop()
  // On desktop, LedgerApp owns boot(). The mobile shell does not mount
  // LedgerApp, so it has to boot the store itself or every surface reads an
  // empty seed.
  const [booted, setBooted] = useState(isDesktop)
  useEffect(() => {
    if (isDesktop) return
    let live = true
    void boot().then(() => { if (live) setBooted(true) })
    return () => { live = false }
  }, [isDesktop])

  // Theme/density/cvd are stamped onto this element by useAppearance inside
  // LedgerApp, not here — the defaults below just avoid an unstyled first paint.
  return (
    <div
      className="ledger-root"
      data-theme="dark"
      data-density="compact"
      style={{ position: 'fixed', inset: 0, zIndex: 40 }}
    >
      {/* The journal covers the whole viewport, including paper-trader's tab
          bar, so without this there is NO way back to any other view. Found by
          rendering it — the code looked fine. */}
      <button className="ledger-exit" onClick={onExit} title="Back to the cockpit">
        ← Cockpit
      </button>
      {isDesktop ? <LedgerApp /> : booted ? <MobileLedger /> : null}
    </div>
  )
}
