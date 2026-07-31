/* QuickCapture — §4.4
 *
 * "A single 640px field over a dimmed shell, available from any module in the
 *  workstation and from the OS-level hotkey. Type, ⏎, gone. It infers:
 *  instrument from active workspace or from @, type from prefix (t trade,
 *  plain text observation, ! mistake note, ? question to answer later), and
 *  timestamp from now. Never asks a question."
 *
 * "This is the highest-value single feature for a discretionary trader.
 *  Observations die within ninety seconds of occurring."
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { useDB } from '../../data/hooks'
import { closeOverlay, toast, useUI } from '../../app/uiState'
import { addStreamEvent, sessionKey } from '../../data/actions'
import { today } from '../../domain/dates'
import type { StreamEventKind } from '../../domain/types'
import { Kbd } from '../primitives'
import './overlays.css'

interface Inferred {
  kind: StreamEventKind
  instrumentId: string
  text: string
  label: string
}

export function QuickCapture() {
  const db = useDB()
  const ui = useUI()
  const [value, setValue] = useState('')
  const ref = useRef<HTMLInputElement>(null)

  useEffect(() => ref.current?.focus(), [])

  const inferred = useMemo<Inferred>(() => {
    let text = value.trim()
    let instrumentId = ui.route.instrumentId

    // `@code` overrides the workspace instrument, anywhere in the line.
    const at = /(?:^|\s)@(\w+)/.exec(text)
    if (at) {
      const hit = db.instruments.find(
        (i) => i.code.toLowerCase() === at[1].toLowerCase(),
      )
      if (hit) {
        instrumentId = hit.id
        text = text.replace(at[0], ' ').trim()
      }
    }

    // Type from prefix. §4.4
    let kind: StreamEventKind = 'observation'
    let label = 'observation'
    if (/^t\s+/i.test(text)) {
      kind = 'trade'
      label = 'trade — opens the ticket'
      text = text.replace(/^t\s+/i, '')
    } else if (text.startsWith('!')) {
      kind = 'mistake-note'
      label = 'mistake note'
      text = text.slice(1).trim()
    } else if (text.startsWith('?')) {
      kind = 'question'
      label = 'question to answer later'
      text = text.slice(1).trim()
    }

    return { kind, instrumentId, text, label }
  }, [value, db.instruments, ui.route.instrumentId])

  const instrument = db.instruments.find((i) => i.id === inferred.instrumentId)

  function commit() {
    if (!inferred.text) return
    addStreamEvent({
      sessionId: sessionKey(inferred.instrumentId, today()),
      instrumentId: inferred.instrumentId,
      kind: inferred.kind,
      text: inferred.text,
      tags: [],
      // §1.4 stamped with the module and instrument you were looking at.
      capturedFrom: ui.route.surface,
      // Everything captured this way lands in the Inbox. §4.4
      inbox: true,
    })
    closeOverlay()
    toast(`Captured to inbox · ${instrument?.code ?? ''}`, true)
  }

  return (
    <div className="overlay overlay--capture" onMouseDown={closeOverlay}>
      <div
        className="capture"
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Quick capture"
      >
        <input
          ref={ref}
          className="capture__input"
          value={value}
          placeholder="Observation…  t trade · ! mistake · ? question · @bnf instrument"
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              commit()
            }
            if (e.key === 'Escape') {
              e.preventDefault()
              closeOverlay()
            }
          }}
        />
        {/* Never asks a question — it shows what it inferred and gets out. */}
        <div className="capture__meta">
          <span className="mono">{instrument?.code}</span>
          <span className="faint">·</span>
          <span className="faint">{inferred.label}</span>
          <span className="capture__keys">
            <Kbd>⏎</Kbd> capture <Kbd>esc</Kbd> dismiss
          </span>
        </div>
      </div>
    </div>
  )
}
