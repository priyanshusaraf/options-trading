import { App as LedgerApp } from '../ledger/app/App'
import '../ledger/styles/tokens.css'
import '../ledger/styles/base.css'

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
export default function LedgerView() {
  // Theme/density/cvd are stamped onto this element by useAppearance inside
  // LedgerApp, not here — the defaults below just avoid an unstyled first paint.
  return (
    <div
      className="ledger-root"
      data-theme="dark"
      data-density="compact"
      style={{ position: 'fixed', inset: 0, zIndex: 40 }}
    >
      <LedgerApp />
    </div>
  )
}
