/* Walkthrough — the short path from "I opened this thing" to "I know what it's for".
 *
 * See `app/walkthrough.ts` for why a tour exists at all in a product that deliberately
 * had none. In short: the no-tour principle was held for a month and produced a journal
 * with fourteen surfaces and zero rows in production.
 *
 * Three rules keep it from being the kind of tour that principle was protecting against:
 *
 *   1. It never blocks. Escape closes it, every step has "skip", and nothing in the app
 *      is gated on finishing it.
 *   2. It is resumable and reopenable — progress persists and it lives permanently in
 *      the sidebar. It is not a thing that happens once and vanishes.
 *   3. Every step that names a surface can NAVIGATE there, so reading it and using the
 *      product are the same act — the property that made the Guide worth keeping.
 */

import { useEffect, useState } from 'react'
import { closeOverlay, navigate } from '../../app/uiState'
import {
  WALKTHROUGH,
  loadProgress,
  saveProgress,
  type WalkStep,
} from '../../app/walkthrough'
import './overlays.css'

export function Walkthrough() {
  const [i, setI] = useState(() => loadProgress().step)
  const step: WalkStep | undefined = WALKTHROUGH[i]
  const last = i >= WALKTHROUGH.length - 1

  useEffect(() => { saveProgress({ step: i, done: false }) }, [i])

  // Escape always leaves. A walkthrough you cannot get out of is a modal trap, and the
  // whole complaint being answered here is that this product felt like it was in charge.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') dismiss()
      if (e.key === 'ArrowRight' || e.key === 'Enter') next()
      if (e.key === 'ArrowLeft') setI((n) => Math.max(0, n - 1))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  function dismiss() {
    saveProgress({ step: i, done: true })
    closeOverlay()
  }

  function next() {
    if (last) {
      saveProgress({ step: 0, done: true })
      closeOverlay()
      return
    }
    setI((n) => n + 1)
  }

  function show() {
    if (step?.surface) navigate({ surface: step.surface as never })
  }

  if (!step) return null

  return (
    <div className="walk__scrim" role="dialog" aria-modal="true"
         aria-label="Journal walkthrough">
      <div className="walk">
        <div className="walk__head">
          <span className="walk__count mono">
            {i + 1} / {WALKTHROUGH.length}
          </span>
          <button className="walk__skip" onClick={dismiss}>
            skip — you can reopen this any time
          </button>
        </div>

        <h2 className="walk__title">{step.title}</h2>
        <p className="walk__why">{step.why}</p>
        <p className="walk__action">{step.action}</p>

        <div className="walk__foot">
          <button className="walk__back" disabled={i === 0}
                  onClick={() => setI((n) => Math.max(0, n - 1))}>
            back
          </button>
          {step.surface && (
            <button className="walk__show" onClick={show}>
              take me there
            </button>
          )}
          <button className="walk__next" onClick={next}>
            {last ? 'done' : 'next'}
          </button>
        </div>

        <div className="walk__dots" aria-hidden="true">
          {WALKTHROUGH.map((s, n) => (
            <span key={s.id} className={`walk__dot ${n <= i ? 'is-on' : ''}`} />
          ))}
        </div>
      </div>
    </div>
  )
}
