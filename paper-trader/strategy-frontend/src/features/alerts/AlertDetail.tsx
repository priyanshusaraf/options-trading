import { TraderSelect } from '../../components/TraderSelect'
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Check, CircleAlert, Eye, Inbox, X } from 'lucide-react'
import type { AttentionAction, ProtectionLevel, ReviewReason, SignalAlertViewModel, SignalReviewDraft, SignalReviewViewModel } from './viewModels'
import { alertTitle, evidenceLabel, levelValue, protectionValue, reviewNoteError, SAFETY_COPY } from './viewModels'
import './alerts.css'

export type AlertDetailProps = Readonly<{
  alert: SignalAlertViewModel | null
  reviewReasons: readonly ReviewReason[]
  existingReview?: SignalReviewViewModel | null
  pendingAction?: AttentionAction | 'REVIEW' | null
  errorMessage?: string | null
  readOnly?: boolean
  disabled?: boolean
  onAttention: (action: AttentionAction, expectedSequence: number) => void
  onReview: (draft: SignalReviewDraft) => void
}>

function ReviewForm({ reasons, pending, onReview }: {
  reasons: readonly ReviewReason[]
  pending: boolean
  onReview: (draft: SignalReviewDraft) => void
}) {
  const [disposition, setDisposition] = useState<'CONFIRMED' | 'REJECTED'>('CONFIRMED')
  const [reasonCode, setReasonCode] = useState(reasons[0]?.code ?? '')
  const [note, setNote] = useState('')
  const noteError = reviewNoteError(note)
  const noteBytes = useMemo(() => new TextEncoder().encode(note).length, [note])
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!reasonCode || noteError !== null || pending) return
    onReview({ disposition, reasonCode, note })
  }
  return <form onSubmit={submit}>
    <label>Decision<TraderSelect label="Decision" disabled={pending} value={disposition}
      onValueChange={(value) => setDisposition(value as 'CONFIRMED' | 'REJECTED')}
      options={[{ value: 'CONFIRMED', label: 'Confirmed' }, { value: 'REJECTED', label: 'Rejected' }]} /></label>
    <label>Reason<TraderSelect label="Reason" disabled={pending || reasons.length === 0} value={reasonCode}
      onValueChange={setReasonCode} options={reasons.map((reason) => ({ value: reason.code, label: reason.label }))} /></label>
    {reasons.length === 0 && <p className="alerts-review-unavailable" role="status">No review reasons are available. Refresh alerts to try again.</p>}
    <label>Optional note<textarea disabled={pending} value={note} onChange={(event) => setNote(event.target.value)} aria-describedby="alert-note-limit" aria-invalid={noteError !== null} /></label>
    <span id="alert-note-limit" role={noteError !== null ? 'alert' : undefined} className={noteError !== null ? 'alerts-note-limit alerts-note-limit--error' : 'alerts-note-limit'}>{noteBytes} / 4096 bytes{noteError ? ` · ${noteError}` : ' · One paragraph; no leading or trailing whitespace.'}</span>
    <button type="submit" disabled={!reasonCode || noteError !== null || pending}>{pending ? 'Saving review…' : 'Save review'}</button>
  </form>
}

function PriceRail({ alert }: { alert: SignalAlertViewModel }) {
  if ('status' in alert.stopLoss || 'status' in alert.takeProfit) return <dl className="alerts-facts" aria-label="Research signal reference and protections">
    <div><dt>Signal reference</dt><dd>{levelValue(alert.entryReferenceValue)} {alert.entryReferenceCurrency}<small>Completed candle close · not a simulated fill</small></dd></div>
    <div><dt>Stop loss</dt><dd>{protectionValue(alert.stopLoss)}</dd></div>
    <div><dt>Take profit</dt><dd>{protectionValue(alert.takeProfit)}</dd></div>
  </dl>
  const short = alert.action === 'SELL' || (alert.action === 'EXIT' && alert.previousState === 'SHORT')
  const levels = short
    ? [
        { key: 'sl', label: 'Stop loss', value: alert.stopLoss.resolvedValue },
        { key: 'entry', label: 'Entry reference', value: alert.entryReferenceValue },
        { key: 'tp', label: 'Take profit', value: alert.takeProfit.resolvedValue },
      ]
    : [
        { key: 'tp', label: 'Take profit', value: alert.takeProfit.resolvedValue },
        { key: 'entry', label: 'Entry reference', value: alert.entryReferenceValue },
        { key: 'sl', label: 'Stop loss', value: alert.stopLoss.resolvedValue },
      ]
  return <ol className="alerts-rail" data-geometry={alert.action === 'SELL' ? 'SHORT' : alert.action === 'BUY' ? 'LONG' : 'EXIT_EVIDENCE'} aria-label={`${alert.action} monitoring price geometry`}>
    {levels.map((level) => <li key={level.key} className={`alerts-rail__${level.key}`}>
      <span>{level.label}</span><strong>{levelValue(level.value)}</strong>
    </li>)}
  </ol>
}

function ProtectionRule({ level }: { level: ProtectionLevel }) {
  if (!('status' in level)) return <>{level.basis} · {level.authoredValue} {level.units}<small>Resolved {levelValue(level.resolvedValue)}</small></>
  if (level.status === 'DISABLED') return <>Not configured</>
  return <>{level.rules.map((rule) => <span key={rule.definitionAddress}>
    {rule.basis === 'ATR_RATCHET_STOP' ? 'ATR trailing stop' : `${(rule.fraction! * 100).toLocaleString('en-IN', { maximumFractionDigits: 8 })}% from simulated entry`}
    <small>{rule.resolvedValue === null ? 'Price available after simulated entry' : `Simulated level ${rule.resolvedValue}`}</small>
  </span>)}</>
}

function AttentionControls({ attention, pendingAction, disabled, onAttention }: { attention: SignalAlertViewModel['attention']; pendingAction: AlertDetailProps['pendingAction']; disabled: boolean; onAttention: AlertDetailProps['onAttention'] }) {
  const attentionPending = pendingAction !== null || disabled
  return <section className="alerts-attention" aria-labelledby="alert-attention-title">
      <div><span className="alerts-eyebrow">Attention state</span><h3 id="alert-attention-title">Handle this alert</h3></div>
      <div className="alerts-actions">
        <button type="button" disabled={attention.readAt !== null || attentionPending}
          onClick={() => onAttention('READ', attention.lastSequence)}><Eye aria-hidden="true" size={15} />{pendingAction === 'READ' ? 'Marking read…' : 'Mark read'}</button>
        <button type="button" disabled={attention.acknowledgedAt !== null || attentionPending}
          onClick={() => onAttention('ACKNOWLEDGE', attention.lastSequence)}><Check aria-hidden="true" size={15} />{pendingAction === 'ACKNOWLEDGE' ? 'Acknowledging…' : 'Acknowledge'}</button>
        <button type="button" disabled={attention.dismissedAt !== null || attentionPending}
          onClick={() => onAttention('DISMISS', attention.lastSequence)}><X aria-hidden="true" size={15} />{pendingAction === 'DISMISS' ? 'Dismissing…' : 'Dismiss'}</button>
      </div>
      <p role="status" aria-live="polite">{attention.isUnread ? 'Unread' : 'Read'}{attention.acknowledgedAt ? ' · Acknowledged' : ''}{attention.dismissedAt ? ' · Dismissed' : ''}</p>
    </section>
}

export function AlertDetail({
  alert, reviewReasons, existingReview = null, pendingAction = null,
  errorMessage = null, onAttention, onReview, readOnly = false, disabled = false,
}: AlertDetailProps) {
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus() }, [alert?.alertAddress])
  if (alert === null) return <section className="alerts-detail alerts-detail--empty" aria-labelledby="alert-detail-empty">
    <Inbox aria-hidden="true" size={22} />
    <h2 id="alert-detail-empty">Select an alert</h2>
    <p>Open a verified signal to inspect entry, SL, TP, freshness and review state.</p>
  </section>

  return <article className="alerts-detail" aria-labelledby="alert-detail-title">
    <header className="alerts-detail__header">
      <div>
        <span className="alerts-eyebrow">Signal evidence</span>
        <h2 id="alert-detail-title" ref={heading} tabIndex={-1}>{alertTitle(alert)}</h2>
        <p>{alert.previousState} → {alert.targetState} · {evidenceLabel(alert.evidenceState)}</p>
        {alert.researchDecision && <p>Pending {alert.researchDecision.kind.toLowerCase()} · Simulated position {alert.researchDecision.simulatedPosition.toLowerCase()}</p>}
      </div>
      <span className={`alerts-action alerts-action--${alert.action.toLowerCase()}`}>{alert.action}</span>
    </header>

    {errorMessage && <div className="alerts-inline-error" role="alert"><CircleAlert aria-hidden="true" size={17} />{errorMessage}</div>}
    <PriceRail alert={alert} />

    <dl className="alerts-facts">
      <div><dt>Entry evidence</dt><dd>{alert.entryReferenceKind} · {levelValue(alert.entryReferenceValue)} {alert.entryReferenceCurrency}</dd></div>
      <div><dt>Stop loss rule</dt><dd><ProtectionRule level={alert.stopLoss} /></dd></div>
      <div><dt>Take profit rule</dt><dd><ProtectionRule level={alert.takeProfit} /></dd></div>
      <div><dt>Monitoring window</dt><dd>Candle closed {alert.eventLabel}<small>Valid until {alert.validUntilLabel}</small></dd></div>
    </dl>

    <p className="alerts-safety alerts-safety--detail">{SAFETY_COPY}</p>

    <AttentionControls attention={alert.attention} pendingAction={pendingAction} disabled={readOnly || disabled} onAttention={onAttention} />

    <section className="alerts-review" aria-labelledby="alert-review-title">
      <span className="alerts-eyebrow">Research feedback</span><h3 id="alert-review-title">Your review</h3>
      {existingReview ? <dl className="alerts-facts"><div><dt>Decision</dt><dd>{existingReview.disposition === 'CONFIRMED' ? 'Confirmed' : 'Rejected'}<small>{reviewReasons.find((reason) => reason.code === existingReview.reasonCode)?.label ?? 'Reason unavailable'} · {existingReview.createdLabel}</small></dd></div>{existingReview.note && <div><dt>Note</dt><dd>{existingReview.note}</dd></div>}</dl>
        : readOnly ? <p>Your role can view alerts and your saved review. It cannot change attention or submit a review.</p> : <ReviewForm key={alert.alertAddress} reasons={reviewReasons} pending={pendingAction !== null || disabled} onReview={onReview} />}
    </section>
  </article>
}
