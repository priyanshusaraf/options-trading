import { TraderSelect } from '../../components/TraderSelect'
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Pause, Play, RefreshCw, SkipBack, SkipForward, Trash2 } from 'lucide-react'
import { ApiError, errorMessage, type StrategyApi } from '../../shell/api'
import type { ChartAnnotation, MarketContext as MarketContextValue } from '../../shell/contracts'
import { MarketContextChart } from './MarketContextChart'
import './market-context.css'

type SourceToken = Readonly<{ key: string }>
type Load = { sourceToken: SourceToken | null; kind: 'loading' } | { sourceToken: SourceToken; kind: 'error'; message: string }
  | { sourceToken: SourceToken; kind: 'ready'; value: MarketContextValue; annotations: readonly ChartAnnotation[] }
type Tool = 'LEVEL' | 'ZONE' | 'LINE' | 'CHANNEL' | 'FIBONACCI'
type Fraction = { numerator: bigint; denominator: bigint }

function gcd(left: bigint, right: bigint): bigint { let a = left < 0n ? -left : left; let b = right < 0n ? -right : right; while (b) [a, b] = [b, a % b]; return a || 1n }
function reduced(numerator: bigint, denominator: bigint): Fraction { const sign = denominator < 0n ? -1n : 1n; const divisor = gcd(numerator, denominator); return { numerator: numerator / divisor * sign, denominator: denominator / divisor * sign } }
function decimalText(raw: string): string | null { const trimmed = raw.trim(); if (!/^-?\d+(?:\.\d+)?$/.test(trimmed)) return null; let [whole, part = ''] = trimmed.split('.'); const negative = whole.startsWith('-'); whole = whole.replace('-', '').replace(/^0+(?=\d)/, ''); part = part.replace(/0+$/, ''); const result = `${negative ? '-' : ''}${whole || '0'}${part ? `.${part}` : ''}`; return result === '-0' ? '0' : result }
function fraction(raw: string): Fraction { const value = decimalText(raw); if (value === null) throw new Error('Enter a valid price.'); const negative = value.startsWith('-'); const unsigned = value.replace('-', ''); const [whole, part = ''] = unsigned.split('.'); const denominator = 10n ** BigInt(part.length); return reduced((BigInt(whole) * denominator + BigInt(part || '0')) * (negative ? -1n : 1n), denominator) }
function subtract(left: Fraction, right: Fraction) { return reduced(left.numerator * right.denominator - right.numerator * left.denominator, left.denominator * right.denominator) }
function multiply(left: Fraction, right: Fraction) { return reduced(left.numerator * right.numerator, left.denominator * right.denominator) }
function rational(value: Fraction) { return { numerator: String(value.numerator), denominator: String(value.denominator) } }
function anchor(time: string, price: string) { const normalized = decimalText(price); if (normalized === null) throw new Error('Enter a valid price.'); return { time, price: normalized } }
function lineGeometry(startTime: string, endTime: string, first: string, second: string) { const start = anchor(startTime, first); const end = anchor(endTime, second); const elapsed = BigInt(Date.parse(endTime) - Date.parse(startTime)) * 1000n; if (elapsed <= 0n) throw new Error('Choose a later second candle.'); return { schema: 'normalized-annotation-geometry/1', kind: 'LINE', start, end, extension: 'SEGMENT', slope_per_microsecond: rational(reduced(subtract(fraction(second), fraction(first)).numerator, subtract(fraction(second), fraction(first)).denominator * elapsed)) } }
function geometry(tool: Tool, startTime: string, endTime: string, first: string, second: string) {
  const one = decimalText(first); const two = decimalText(second); if (one === null || two === null) throw new Error('Enter valid price values.')
  if (tool === 'LEVEL') return { schema: 'normalized-annotation-geometry/1', kind: tool, price: one }
  if (tool === 'ZONE') { if (Number(one) > Number(two)) throw new Error('Lower price must not exceed upper price.'); return { schema: 'normalized-annotation-geometry/1', kind: tool, lower: one, upper: two } }
  const line = lineGeometry(startTime, endTime, one, tool === 'CHANNEL' ? one : two)
  if (tool === 'LINE') return line
  if (tool === 'CHANNEL') return { schema: 'normalized-annotation-geometry/1', kind: tool, center: line, half_width: two }
  const movement = subtract(fraction(two), fraction(one)); if (movement.numerator === 0n) throw new Error('Fibonacci anchors need different prices.')
  const ratios = ['0.236', '0.382', '0.5', '0.618', '0.786']
  const levels = ratios.map((ratio) => rational(subtract(fraction(two), multiply(fraction(ratio), movement))))
  return { schema: 'normalized-annotation-geometry/1', kind: tool, start: anchor(startTime, one), end: anchor(endTime, two), direction: movement.numerator > 0n ? 'UP' : 'DOWN', mode: 'RETRACEMENT', ratios, levels }
}
function applicability(time: string) { return { schema: 'annotation-applicability/1', known_at: time, locked_at: time, effective_from: time, effective_to: null } }
function applies(annotation: ChartAnnotation, event: string, asOf: string) { const value = annotation.applicability; const locked = Date.parse(String(value.locked_at)); const effective = Date.parse(String(value.effective_from)); const expiry = value.effective_to === null ? null : Date.parse(String(value.effective_to)); const point = Date.parse(event); const known = Date.parse(asOf); return known >= point && known >= locked && point > locked && point >= effective && (expiry === null || point < expiry) }
function reducedMotionRequested() { return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches }
function plainProduct(value: string) { return value.replace(/canonical/gi, 'verified') }

export function MarketContext({ api, projectId, runId, tradeEvents = [] }: { api: StrategyApi; projectId: string; runId: number; tradeEvents?: readonly Readonly<Record<string, unknown>>[] }) {
  const [storedLoad, setLoad] = useState<Load>({ sourceToken: null, kind: 'loading' }); const [attempt, setAttempt] = useState(0)
  const sourceKey = `${projectId}\u0000${runId}\u0000${attempt}`
  const sourceToken = useMemo<SourceToken>(() => Object.freeze({ key: sourceKey }), [sourceKey])
  const load = useMemo<Load>(() => storedLoad.sourceToken === sourceToken
    ? storedLoad : { sourceToken, kind: 'loading' }, [sourceToken, storedLoad])
  const [replayCount, setReplayCount] = useState(0); const [playingFor, setPlayingFor] = useState<SourceToken | null>(null)
  const playing = playingFor === sourceToken
  const [tool, setTool] = useState<Tool>('LEVEL'); const [firstPrice, setFirstPrice] = useState('100'); const [secondPrice, setSecondPrice] = useState('1')
  const [startTime, setStartTime] = useState(''); const [endTime, setEndTime] = useState('')
  const [selectedFor, setSelectedFor] = useState<{ sourceToken: SourceToken | null; value: string }>({ sourceToken: null, value: '' }); const selected = selectedFor.sourceToken === sourceToken ? selectedFor.value : ''
  const [feedbackFor, setFeedbackFor] = useState<{ sourceToken: SourceToken | null; value: string }>({ sourceToken: null, value: '' }); const feedback = feedbackFor.sourceToken === sourceToken ? feedbackFor.value : ''
  const [pendingFor, setPendingFor] = useState<SourceToken | null>(null); const pending = pendingFor === sourceToken
  const feedbackRef = useRef<HTMLParagraphElement>(null); const currentSourceRef = useRef<SourceToken | null>(null)
  const mutationControllers = useRef(new Set<AbortController>())
  useEffect(() => { const controller = new AbortController(); const controllers = mutationControllers.current; currentSourceRef.current = sourceToken
    api.marketContext(projectId, runId, null, controller.signal).then(async (value) => {
      const annotations = await api.chartAnnotations(projectId, runId, value.market_context_address, controller.signal)
      if (!controller.signal.aborted && currentSourceRef.current === sourceToken) { setLoad({ sourceToken, kind: 'ready', value, annotations }); setReplayCount(value.bars.length); setStartTime(value.bars[0]?.completed_at ?? ''); setEndTime(value.bars.at(-1)?.completed_at ?? '') }
    }).catch((error: unknown) => { if (!controller.signal.aborted && currentSourceRef.current === sourceToken) setLoad({ sourceToken, kind: 'error', message: errorMessage(error) }) })
    return () => { if (currentSourceRef.current === sourceToken) currentSourceRef.current = null; controller.abort(); for (const mutation of controllers) mutation.abort(); controllers.clear() } }, [api, projectId, runId, sourceToken])
  useEffect(() => { const media = typeof window.matchMedia === 'function' ? window.matchMedia('(prefers-reduced-motion: reduce)') : null; const pauseHidden = () => { if (document.hidden) setPlayingFor(null) }; const pauseMotion = (event: MediaQueryListEvent) => { if (event.matches) setPlayingFor(null) }; document.addEventListener('visibilitychange', pauseHidden); media?.addEventListener?.('change', pauseMotion); return () => { document.removeEventListener('visibilitychange', pauseHidden); media?.removeEventListener?.('change', pauseMotion) } }, [])
  useEffect(() => { if (!playing || load.kind !== 'ready') return
    const timer = window.setInterval(() => setReplayCount((count) => { if (count >= load.value.bars.length) { window.clearInterval(timer); setPlayingFor(null); return count } return count + 1 }), 500)
    return () => window.clearInterval(timer) }, [playing, load])
  const bars = useMemo(() => load.kind === 'ready'
    ? load.value.bars.slice(0, replayCount) : [], [load, replayCount])
  const selectedStartTime = bars.some((bar) => bar.completed_at === startTime) ? startTime : bars[0]?.completed_at ?? ''
  const selectedEndTime = bars.some((bar) => bar.completed_at === endTime) ? endTime : bars.at(-1)?.completed_at ?? ''
  const replayAt = bars.at(-1)?.completed_at ?? (load.kind === 'ready' ? load.value.bars[0]?.event_time : '') ?? ''
  const shownAnnotations = useMemo(() => load.kind !== 'ready' ? [] : replayCount === load.value.bars.length ? load.annotations : load.annotations.filter((item) => bars.length && applies(item, bars.at(-1)!.event_time, replayAt)), [load, replayCount, bars, replayAt])
  const save = async (event: FormEvent) => { event.preventDefault(); if (load.kind !== 'ready' || !selectedStartTime || !selectedEndTime) return
    const capturedSource = sourceToken; const controller = new AbortController(); mutationControllers.current.add(controller)
    const currentNow = () => currentSourceRef.current === capturedSource && !controller.signal.aborted
    setPendingFor(capturedSource); setFeedbackFor({ sourceToken: capturedSource, value: '' })
    try { const shape = geometry(tool, selectedStartTime, selectedEndTime, firstPrice, secondPrice); const timing = applicability(replayAt || selectedEndTime); const current = load.annotations.find((item) => item.annotation_id === selected)
      const saved = current ? await api.updateChartAnnotation(projectId, runId, current.annotation_id, current.revision, shape, timing, controller.signal) : await api.createChartAnnotation(projectId, runId, shape, timing, controller.signal)
      if (!currentNow()) return
      setLoad({ ...load, annotations: Object.freeze(current ? load.annotations.map((item) => item.annotation_id === current.annotation_id ? saved : item) : [...load.annotations, saved]) }); setSelectedFor({ sourceToken: capturedSource, value: saved.annotation_id }); setFeedbackFor({ sourceToken: capturedSource, value: current ? 'Review drawing updated.' : 'Review drawing saved.' })
    } catch (error) { if (!currentNow()) return; setFeedbackFor({ sourceToken: capturedSource, value: error instanceof ApiError && error.envelope?.code === 'REVIEW_DRAWING_CONFLICT' ? 'This review drawing changed elsewhere. Reload it and try again.' : error instanceof Error && !(error instanceof ApiError) ? error.message : errorMessage(error) }); requestAnimationFrame(() => { if (currentSourceRef.current === capturedSource) feedbackRef.current?.focus() })
    } finally { mutationControllers.current.delete(controller); if (currentNow()) setPendingFor(null) } }
  const remove = async () => { if (load.kind !== 'ready') return; const current = load.annotations.find((item) => item.annotation_id === selected); if (!current) return
    const capturedSource = sourceToken; const controller = new AbortController(); mutationControllers.current.add(controller)
    const currentNow = () => currentSourceRef.current === capturedSource && !controller.signal.aborted
    setPendingFor(capturedSource)
    try { await api.deleteChartAnnotation(projectId, runId, current.annotation_id, current.revision, controller.signal); if (!currentNow()) return; setLoad({ ...load, annotations: Object.freeze(load.annotations.filter((item) => item.annotation_id !== current.annotation_id)) }); setSelectedFor({ sourceToken: capturedSource, value: '' }); setFeedbackFor({ sourceToken: capturedSource, value: 'Review drawing removed.' }); requestAnimationFrame(() => { if (currentSourceRef.current === capturedSource) document.getElementById('review-drawing-select')?.focus() })
    } catch (error) { if (!currentNow()) return; setFeedbackFor({ sourceToken: capturedSource, value: errorMessage(error) }); requestAnimationFrame(() => { if (currentSourceRef.current === capturedSource) feedbackRef.current?.focus() })
    } finally { mutationControllers.current.delete(controller); if (currentNow()) setPendingFor(null) } }
  if (load.kind === 'loading') return <section className="market-context-state" aria-label="Market context"><p role="status">Loading Market context…</p></section>
  if (load.kind === 'error') return <section className="market-context-state" aria-label="Market context"><h3>Market context unavailable</h3><p role="alert">{load.message}</p><button onClick={() => { setPlayingFor(null); setAttempt((value) => value + 1) }}><RefreshCw aria-hidden="true" />Retry</button></section>
  if (load.value.state === 'EMPTY') return <section className="market-context-state" aria-label="Market context"><h3>No verified candles are linked to this result</h3><p>The saved result has no completed price history to show.</p><p>Choose a result with saved candle history to review its market context.</p></section>
  const selectedAnnotation = load.annotations.find((item) => item.annotation_id === selected)
  function renderReplayControls(totalCandles: number) {
    return (
      <div className="replay-deck" aria-label="Completed candle replay controls"><button onClick={() => { setPlayingFor(null); setReplayCount(0) }}><SkipBack aria-hidden="true" />Start</button><button aria-label={playing ? 'Pause completed candle replay' : 'Play completed candle replay'} onClick={() => setPlayingFor(playing || reducedMotionRequested() ? null : sourceToken)}>{playing ? <Pause aria-hidden="true" /> : <Play aria-hidden="true" />}{playing ? 'Pause' : 'Play'}</button><button disabled={replayCount === 0} onClick={() => { setPlayingFor(null); setReplayCount((value) => Math.max(0, value - 1)) }}>Previous candle</button><input aria-label="Replay up to completed candle" type="range" min="0" max={totalCandles} value={replayCount} onChange={(event) => { setPlayingFor(null); setReplayCount(Number(event.target.value)) }} /><button disabled={replayCount >= totalCandles} onClick={() => { setPlayingFor(null); setReplayCount((value) => Math.min(totalCandles, value + 1)) }}>Next candle</button><button onClick={() => { setPlayingFor(null); setReplayCount(totalCandles) }}><SkipForward aria-hidden="true" />Latest</button><p className="sr-only" role="status" aria-live="polite">Replay up to {replayAt || 'before the first candle'}. {bars.length} candles visible.</p></div>
    )
  }

  function renderDrawingStudio(annotations: readonly ChartAnnotation[]) {
    return (
      <aside className="annotation-studio" aria-labelledby="annotation-title"><div className="annotation-copy"><span className="slate-eyebrow">Chart notes</span><h3 id="annotation-title">Review drawing</h3><p>This drawing does not change your strategy or research result</p></div><form onSubmit={(event) => void save(event)}><label>Drawing type<TraderSelect label="Drawing type" value={tool} onValueChange={(value) => setTool(value as Tool)} options={(['LEVEL', 'ZONE', 'LINE', 'CHANNEL', 'FIBONACCI'] as Tool[]).map((item) => ({ value: item, label: item[0] + item.slice(1).toLowerCase() }))} /></label><label>First price<input inputMode="decimal" value={firstPrice} onChange={(event) => setFirstPrice(event.target.value)} /></label><label>{tool === 'CHANNEL' ? 'Half-width (price)' : 'Second price'}<input inputMode="decimal" disabled={tool === 'LEVEL'} value={secondPrice} onChange={(event) => setSecondPrice(event.target.value)} /></label><label>First candle<TraderSelect label="First candle" value={selectedStartTime} onValueChange={setStartTime} options={bars.map((bar) => ({ value: bar.completed_at, label: bar.completed_at }))} /></label><label>Second candle<TraderSelect label="Second candle" value={selectedEndTime} onValueChange={setEndTime} options={bars.map((bar) => ({ value: bar.completed_at, label: bar.completed_at }))} /></label><label>Saved drawing<TraderSelect id="review-drawing-select" label="Saved drawing" value={selected} onValueChange={(value) => setSelectedFor({ sourceToken, value })} options={[{ value: '', label: 'Create a new drawing' }, ...annotations.map((item, index) => ({ value: item.annotation_id, label: `Review drawing ${index + 1} · ${String(item.geometry.kind).toLowerCase()}` }))]} /></label><div className="annotation-actions"><button className="workstation-primary" disabled={pending || bars.length === 0}>{pending ? 'Saving…' : selectedAnnotation ? 'Save changes' : 'Save drawing'}</button><button type="button" disabled={!selectedAnnotation || pending} onClick={() => void remove()}><Trash2 aria-hidden="true" />Remove</button></div><p ref={feedbackRef} tabIndex={-1} role={feedback.includes('changed elsewhere') ? 'alert' : 'status'}>{feedback}</p></form></aside>
    )
  }

  return <section className="market-context" aria-labelledby="market-context-title">
    <header className="market-context-heading"><div><span className="slate-eyebrow">Saved research · completed prices</span><h3 id="market-context-title">Market context</h3><p>{plainProduct(load.value.instrument_label)} · {load.value.timeframe_seconds / 60} minute candles</p></div><div className="market-source-mark"><span>Replay up to</span><strong>{replayAt || 'Before the first candle'}</strong><span>{bars.length.toLocaleString()} of {load.value.bars.length.toLocaleString()} candles</span></div></header>
    {renderReplayControls(load.value.bars.length)}
    <MarketContextChart bars={bars} annotations={shownAnnotations} tradeEvents={tradeEvents} />
    {renderDrawingStudio(load.annotations)}
    {bars.length === 0 && <p className="annotation-empty" role="status">Move replay forward to a completed candle before drawing.</p>}
    {load.annotations.length === 0 && <p className="annotation-empty">No review drawings are saved for this result.</p>}
    <p className="market-source-note">Data available as of <time dateTime={load.value.source_as_of}>{load.value.source_as_of}</time>.</p>
  </section>
}
