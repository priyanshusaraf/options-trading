/* Overlays — §6.5
 *  CommandPalette · QuickCapture · Drawer (right, 480px) · Inspector
 *  (persistent, 380px) · Peek · Toast (bottom-left, 4s, always undoable)
 *  · ShortcutSheet (?) · ConfirmRail (used exactly once)
 */

import { useEffect, type ReactNode } from 'react'
import { closeDrawer, dismissToast, useUI } from '../../app/uiState'
import { undo } from '../../data/store'
import { Kbd } from '../primitives'
import type { Command } from '../../keys/commands'
import './overlays.css'

export { CommandPalette } from './CommandPalette'
export { QuickCapture } from './QuickCapture'

/** §6.5 Drawer — right, 480px, for creation flows.
 *  §8 "No modal ever covers the thing you are writing about." */
export function Drawer({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeDrawer()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <aside className="drawer" role="dialog" aria-label={title}>
      <header className="drawer__head">
        <span className="label">{title}</span>
        <button className="drawer__x" onClick={closeDrawer} aria-label="Close">
          ×
        </button>
      </header>
      <div className="drawer__body scroll">{children}</div>
    </aside>
  )
}

/** §6.5 Toast — bottom-left, 4s, always undoable. */
export function Toasts() {
  const ui = useUI()
  if (!ui.toasts.length) return null
  return (
    <div className="toasts">
      {ui.toasts.map((t) => (
        <div className="toast glass" key={t.id}>
          <span>{t.text}</span>
          {t.undoable && (
            <button
              className="toast__undo"
              onClick={() => {
                undo()
                dismissToast(t.id)
              }}
            >
              Undo <Kbd>⌘Z</Kbd>
            </button>
          )}
        </div>
      ))}
    </div>
  )
}

/** §6.5 ShortcutSheet (?). §1.3 "The command palette and ? are the
 *  documentation" — which is why this is exhaustive rather than a summary. */
export function ShortcutSheet({
  commands,
  onClose,
}: {
  commands: Command[]
  onClose: () => void
}) {
  const sections = [...new Set(commands.map((c) => c.section))]
  return (
    <div className="overlay" onMouseDown={onClose}>
      <div
        className="sheet"
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Keyboard shortcuts"
      >
        <header className="sheet__head">
          <span className="label">Keyboard</span>
          <span className="faint">
            The mouse is an accessibility affordance and a reading tool.
          </span>
          <button className="drawer__x" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <div className="sheet__body scroll">
          {sections.map((s) => (
            <section className="sheet__section" key={s}>
              <div className="label sheet__sectionhead">{s}</div>
              {commands
                .filter((c) => c.section === s && c.kbd)
                .map((c) => (
                  <div className="sheet__row" key={c.id}>
                    <span className="sheet__title">{c.title}</span>
                    <Kbd>{c.kbd}</Kbd>
                  </div>
                ))}
            </section>
          ))}
          <section className="sheet__section">
            <div className="label sheet__sectionhead">Ticket grammar</div>
            {/* §9.6 "The parser is documented in the ? overlay and is the
                fastest path for experienced users." */}
            <pre className="sheet__grammar mono">{`bnf 52200ce b 60 @248.5 x51900 t52320 orb c4 fomo
│   │       │ │   │      │      │      │   │  └ emotion (optional)
│   │       │ │   │      │      │      │   └ confidence 1–5
│   │       │ │   │      │      │      └ setup shortcode (or 0 = off-book)
│   │       │ │   │      │      └ target (optional)
│   │       │ │   │      └ stop — defines 1R when R is stop-based
│   │       │ │   └ price
│   │       │ └ quantity
│   │       └ direction  b/buy/long · s/sell/short
│   └ strike + type (or FUT / EQ)
└ instrument shortcode

Tokens are matched by shape, not position, so order is flexible.
Anything omitted falls back to workspace defaults; anything
ambiguous highlights that token and waits.`}</pre>
          </section>
          <section className="sheet__section">
            <div className="label sheet__sectionhead">Query grammar</div>
            <pre className="sheet__grammar mono">{`setup:orb r:>1 date:2026-q2 -mistake:early-exit
grade:A or grade:B          boolean or within a group
r:0.5..2                    range
date:2026-06-01..2026-06-30 date range
again:no  offbook:yes  open:yes  conf:>3  capture:<0.5`}</pre>
          </section>
        </div>
      </div>
    </div>
  )
}
