import tailwindcss from 'tailwindcss'
import autoprefixer from 'autoprefixer'

const SCOPE = '.ledger-root'

/**
 * THE LEDGER ships ~40 generic global class names (.grid .panel .chip .label
 * .num .badge .toast .empty .stat .surface .card .tile) plus a document-level
 * reset including `body { overflow: hidden }`. Dropped into this app unscoped it
 * would collide with Tailwind in BOTH directions and freeze page scrolling
 * everywhere.
 *
 * So every selector in a stylesheet under src/ledger/ is nested beneath the
 * scope element that LedgerView renders. Four selector shapes need care:
 *
 *   :root       -> becomes the scope ITSELF, not a descendant, or the design
 *                  tokens never apply to anything.
 *   :root[attr] -> keeps its attribute selector ON the scope element, so
 *                  data-theme / data-density / data-cvd still switch themes.
 *   html/body   -> collapse onto the scope, so frame properties land on an
 *                  element that is full-viewport rather than on the document.
 *   *           -> becomes `.ledger-root *`, which also keeps the bare
 *                  box-sizing reset away from the host's DOM.
 *
 * Keyframe steps (`from`, `to`, `50%`) must never be prefixed, hence the
 * atrule check.
 */
function scopeSelector(sel) {
  const s = sel.trim()
  if (s === ':root' || s === 'html' || s === 'body' || s === '#root') return SCOPE
  if (s.startsWith(':root')) return SCOPE + s.slice(':root'.length)
  if (s.startsWith(SCOPE)) return s
  return `${SCOPE} ${s}`
}

const ledgerScope = {
  postcssPlugin: 'ledger-scope',
  Once(root) {
    const from = root.source?.input?.file || ''
    if (!from.includes('/src/ledger/')) return
    root.walkRules((rule) => {
      // Inside @keyframes the "selectors" are offsets, not elements.
      const parent = rule.parent
      if (parent?.type === 'atrule' && /keyframes$/.test(parent.name)) return
      rule.selectors = rule.selectors.map(scopeSelector)
    })
  },
}

export default {
  plugins: [tailwindcss, autoprefixer, ledgerScope],
}
