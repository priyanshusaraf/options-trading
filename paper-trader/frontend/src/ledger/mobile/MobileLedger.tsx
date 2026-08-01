import { useState } from 'react'

import { PendingReasons } from '../components/domain/PendingReasons'
import { ensureSession, observe, sessionKey } from '../data/actions'
import { useDB } from '../data/hooks'
import { today } from '../domain/dates'
import { WALKTHROUGH, loadProgress, saveProgress } from '../app/walkthrough'
import './mobile.css'

type Screen = 'pending' | 'capture' | 'today'

/**
 * The phone journal: capture only.
 *
 * You place discretionary trades from the Zerodha app, so the reason prompt has
 * to be answerable with a thumb. Analysis does not — the blotter is a
 * 676px-minimum data grid with drag-resize columns, and the Research Bench
 * assumes ≥700px. Those say "open on your Mac" rather than degrading into
 * something unreadable, which is §10.4 of the source design doc.
 */
export default function MobileLedger() {
  const [screen, setScreen] = useState<Screen>('pending')
  const [walk, setWalk] = useState(() => !loadProgress().done)
  return (
    <div className="ml">
      <header className="ml__head">
        <span className="label">Journal</span>
        {/* Always reachable, not a card that vanishes after the first morning. */}
        <button className="ml__help" onClick={() => setWalk(true)}>
          what is this?
        </button>
      </header>
      {walk && <MobileWalkthrough onClose={() => setWalk(false)} />}
      <div className="ml__body">
        {screen === 'pending' && <PendingScreen />}
        {screen === 'capture' && <CaptureScreen />}
        {screen === 'today' && <TodayScreen />}
      </div>
      <nav className="ml__tabs">
        {(['pending', 'capture', 'today'] as Screen[]).map((s) => (
          <button
            key={s}
            className={s === screen ? 'is-active' : ''}
            onClick={() => setScreen(s)}
          >
            {s}
          </button>
        ))}
      </nav>
    </div>
  )
}

/**
 * The same walkthrough content as the desktop overlay, laid out for a thumb.
 *
 * The phone is where this journal is actually opened — before the market, one-handed —
 * and it was the one place with no explanation of what any of it was for. Six short
 * screens, resumable, dismissible, and reopenable from the header. The desktop Guide
 * remains the full reference for anyone who wants it.
 */
function MobileWalkthrough({ onClose }: { onClose: () => void }) {
  const [i, setI] = useState(() => loadProgress().step)
  const step = WALKTHROUGH[i]
  const last = i >= WALKTHROUGH.length - 1
  if (!step) return null

  function done() {
    saveProgress({ step: last ? 0 : i, done: true })
    onClose()
  }

  return (
    <section className="ml__walk">
      <div className="ml__walkhead">
        <span className="mono faint">{i + 1} / {WALKTHROUGH.length}</span>
        <button onClick={done}>skip</button>
      </div>
      <h2>{step.title}</h2>
      <p className="ml__walkwhy">{step.why}</p>
      <p className="ml__walkdo">{step.action}</p>
      <div className="ml__walkfoot">
        <button disabled={i === 0} onClick={() => setI((n) => Math.max(0, n - 1))}>
          back
        </button>
        <button className="ml__primary"
                onClick={() => {
                  if (last) return done()
                  const n = i + 1
                  setI(n)
                  saveProgress({ step: n, done: false })
                }}>
          {last ? 'got it' : 'next'}
        </button>
      </div>
    </section>
  )
}

function PendingScreen() {
  return (
    <>
      <PendingReasons compact />
      <EmptyIfNoPending />
    </>
  )
}

/** Rendered under PendingReasons, which returns null when the queue is empty. */
function EmptyIfNoPending() {
  return (
    <p className="ml__empty faint">
      Nothing waiting. Trades you place on Kite show up here for a reason —
      usually within a minute.
    </p>
  )
}

function CaptureScreen() {
  const [text, setText] = useState('')
  const [saved, setSaved] = useState(false)
  const db = useDB()
  const instrumentId = db.instruments[0]?.id

  function commit() {
    const body = text.trim()
    if (!body || !instrumentId) return
    // The design's claim is that observations die within ninety seconds of
    // occurring, so this never asks a question — it files and gets out of the
    // way. Prefix inference (! mistake, ? question) matches QuickCapture.
    const kind = body.startsWith('!') ? 'mistake-note' as const
      : body.startsWith('?') ? 'question' as const : 'observation' as const
    ensureSession(instrumentId, today())
    observe(sessionKey(instrumentId, today()), instrumentId, body, kind)
    setText('')
    setSaved(true)
    setTimeout(() => setSaved(false), 1500)
  }

  return (
    <div className="ml__capture">
      <textarea
        rows={5}
        value={text}
        placeholder="What did you notice?"
        onChange={(e) => setText(e.target.value)}
      />
      <p className="faint ml__hint">
        Start with <span className="mono">!</span> for a mistake,{' '}
        <span className="mono">?</span> for a question you want to answer later.
      </p>
      <button className="ml__primary" onClick={commit} disabled={!text.trim()}>
        {saved ? 'saved' : 'Capture'}
      </button>
    </div>
  )
}

function TodayScreen() {
  const db = useDB()
  const inst = db.instruments[0]
  const session = db.sessions.find(
    (s) => s.instrumentId === inst?.id && s.date === today(),
  )

  if (!session || !session.lockedAt) {
    return (
      <p className="ml__empty faint">
        No thesis locked for today. Writing one is a desk job — it needs
        scenarios and invalidations, which is not a phone task.
      </p>
    )
  }

  return (
    <div className="ml__today">
      {/* Read-only on purpose: the thesis is frozen at lock. That is the
          mechanic the whole journal is built around, and a phone is exactly
          where it would be most tempting to quietly revise it. */}
      <p className="prose paper">{session.thesis}</p>
      <div className="ml__scen">
        {session.scenarios.map((s) => (
          <div key={s.id} className="ml__scenrow">
            <span className="mono">{s.letter}</span>
            <span>{s.name}</span>
            <span className="faint mono">{s.status}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
