import { chooseSelect } from '../../test/select'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiError, type StrategyApi } from '../../shell/api'
import type { MarketContext as Context } from '../../shell/contracts'
import { MarketContext } from './MarketContext'

afterEach(cleanup)
const address = (digit: string) => `sha256:${digit.repeat(64)}`
const bars = Array.from({ length: 3 }, (_, index) => ({ cursor: index + 1,
  event_time: `2026-01-01T10:0${index}:00.000Z`,
  completed_at: `2026-01-01T10:0${index + 1}:00.000Z`, open: 100 + index,
  high: 102 + index, low: 99 + index, close: 101 + index, volume: 10 + index }))
const value: Context = { schema: 'strategy-os-market-context/1', state: 'AVAILABLE',
  market_context_address: address('a'), projection_address: address('b'),
  source: { kind: 'VERIFIED_SAVED_RUN', address: address('c') }, graph: {},
  dataset_manifest_address: address('d'), canonical_instrument_address: address('e'),
  instrument_label: 'Canonical instrument · XNSE · EQUITY · SPOT', timeframe_seconds: 60,
  source_as_of: '2026-01-01T10:03:00.000Z', replay_at: '2026-01-01T10:03:00.000Z',
  bars, page: { after: 0, limit: 500, next_cursor: null, visible_count: 3 } }
const savedAnnotation = { annotation_id: '00000000-0000-0000-0000-000000000001', revision: 1,
  geometry: { schema: 'normalized-annotation-geometry/1', kind: 'LEVEL', price: '100' },
  geometry_address: address('f'), applicability: { schema: 'annotation-applicability/1',
    known_at: bars[0].completed_at, locked_at: bars[0].completed_at,
    effective_from: bars[0].completed_at, effective_to: null },
  applicability_address: address('1'), created_at: bars[0].completed_at,
  updated_at: bars[0].completed_at }

function mockApi(overrides: Record<string, unknown> = {}) {
  return { marketContext: vi.fn().mockResolvedValue(value),
    chartAnnotations: vi.fn().mockResolvedValue([]),
    createChartAnnotation: vi.fn().mockResolvedValue({
      annotation_id: '00000000-0000-0000-0000-000000000001', revision: 1,
      geometry: { kind: 'LEVEL', price: '100' }, geometry_address: address('f'),
      applicability: { known_at: bars[2].completed_at }, applicability_address: address('1'),
      created_at: bars[2].completed_at, updated_at: bars[2].completed_at }),
    updateChartAnnotation: vi.fn(), deleteChartAnnotation: vi.fn(), ...overrides } as unknown as StrategyApi
}

it('replays only completed candles with keyboard controls and table parity', async () => {
  Object.defineProperty(window, 'matchMedia', { configurable: true,
    value: vi.fn().mockReturnValue({ matches: false }) })
  render(<MarketContext api={mockApi()} projectId="project.a" runId={7} />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading Market context')
  expect(await screen.findByRole('heading', { name: 'Market context' })).toBeInTheDocument()
  expect(screen.getByText(/verified instrument · XNSE/i)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Start' }))
  expect(screen.getByText(/0 of 3 candles/)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Next candle' }))
  fireEvent.click(screen.getByText('Open candle data table'))
  expect(screen.getAllByRole('row')).toHaveLength(2)
  const table = screen.getByRole('table')
  expect(within(table).getByText(bars[0].completed_at)).toBeInTheDocument()
  expect(within(table).queryByText(bars[2].completed_at)).not.toBeInTheDocument()
})

it('creates a bounded review drawing and keeps protocol language out of routine copy', async () => {
  Object.defineProperty(window, 'matchMedia', { configurable: true,
    value: vi.fn().mockReturnValue({ matches: false }) })
  const api = mockApi(); const { container } = render(
    <MarketContext api={api} projectId="project.a" runId={7} />)
  await screen.findByRole('heading', { name: 'Review drawing' })
  fireEvent.change(screen.getByLabelText('First price'), { target: { value: '123.50' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save drawing' }))
  await waitFor(() => expect(api.createChartAnnotation).toHaveBeenCalledOnce())
  expect(await screen.findByText('Review drawing saved.')).toBeInTheDocument()
  const routine = [...container.querySelectorAll('*')].filter((element) => !element.closest('details'))
    .map((element) => element.childNodes.length === 1 ? element.textContent : '').join(' ')
  expect(routine).not.toMatch(/canonical/i)
  expect(container.textContent).not.toMatch(/sha256:|00000000-0000-0000-0000-000000000001/)
  expect(screen.getByText(/Data available as of/)).toHaveTextContent(value.source_as_of)
})

it('shows plain error and empty states without stale chart values', async () => {
  const failing = mockApi({ marketContext: vi.fn().mockRejectedValue(new Error('private detail')) })
  const { rerender } = render(<MarketContext api={failing} projectId="project.a" runId={7} />)
  expect(await screen.findByRole('heading', { name: 'Market context unavailable' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  const empty = mockApi({ marketContext: vi.fn().mockResolvedValue({ ...value, state: 'EMPTY', bars: [] }) })
  rerender(<MarketContext api={empty} projectId="project.a" runId={8} />)
  expect(await screen.findByRole('heading', { name: 'No verified candles are linked to this result' })).toBeInTheDocument()
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
})

it('clears prior chart bytes immediately when the selected run changes', async () => {
  let resolveSecond: ((next: Context) => void) | undefined
  const marketContext = vi.fn()
    .mockResolvedValueOnce(value)
    .mockImplementationOnce(() => new Promise<Context>((resolve) => { resolveSecond = resolve }))
  const api = mockApi({ marketContext })
  const { rerender } = render(<MarketContext api={api} projectId="project.a" runId={7} />)
  expect(await screen.findByRole('img', { name: /3 completed candles/ })).toBeInTheDocument()
  rerender(<MarketContext api={api} projectId="project.a" runId={8} />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading Market context')
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
  resolveSecond?.({ ...value, market_context_address: address('9') })
  expect(await screen.findByRole('img', { name: /3 completed candles/ })).toBeInTheDocument()
})

it('shows an optimistic edit conflict and moves focus to its recovery message', async () => {
  const updateChartAnnotation = vi.fn().mockRejectedValue(new ApiError('server', 'hidden', {
    code: 'REVIEW_DRAWING_CONFLICT', message: 'hidden',
  }))
  const api = mockApi({ chartAnnotations: vi.fn().mockResolvedValue([savedAnnotation]),
    updateChartAnnotation })
  render(<MarketContext api={api} projectId="project.a" runId={7} />)
  await screen.findByRole('heading', { name: 'Review drawing' })
  await chooseSelect('Saved drawing', savedAnnotation.annotation_id)
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('This review drawing changed elsewhere. Reload it and try again.')
  await waitFor(() => expect(alert).toHaveFocus())
  expect(updateChartAnnotation).toHaveBeenCalledOnce()
})

it.each(['create', 'update', 'delete'] as const)(
  'aborts a delayed %s and ignores its result across a run switch and A-B-A return', async (operation) => {
    let resolveMutation: ((value: typeof savedAnnotation | void) => void) | undefined
    let mutationSignal: AbortSignal | undefined
    const delayed = vi.fn((...args: unknown[]) => {
      mutationSignal = args[operation === 'update' ? 6 : 4] as AbortSignal
      return new Promise<typeof savedAnnotation | void>((resolve) => { resolveMutation = resolve })
    })
    const api = mockApi({
      marketContext: vi.fn((_project: string, selectedRun: number) => Promise.resolve({
        ...value, market_context_address: address(selectedRun === 8 ? '8' : '7'),
        instrument_label: selectedRun === 8 ? 'Run B instrument' : 'Run A instrument',
      })),
      chartAnnotations: vi.fn().mockResolvedValue(operation === 'create' ? [] : [savedAnnotation]),
      [`${operation}ChartAnnotation`]: delayed,
    })
    const view = render(<MarketContext api={api} projectId="project.a" runId={7} />)
    await screen.findByText(/Run A instrument/)
    if (operation !== 'create') await chooseSelect('Saved drawing', savedAnnotation.annotation_id)
    fireEvent.click(screen.getByRole('button', { name: operation === 'delete' ? 'Remove'
      : operation === 'update' ? 'Save changes' : 'Save drawing' }))
    await waitFor(() => expect(delayed).toHaveBeenCalledOnce())
    view.rerender(<MarketContext api={api} projectId="project.a" runId={8} />)
    await waitFor(() => expect(mutationSignal?.aborted).toBe(true))
    expect(await screen.findByText(/Run B instrument/)).toBeInTheDocument()
    view.rerender(<MarketContext api={api} projectId="project.a" runId={7} />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading Market context')
    expect(await screen.findByText(/Run A instrument/)).toBeInTheDocument()
    expect(screen.queryByText(/Review drawing (saved|updated|removed)/)).not.toBeInTheDocument()
    await act(async () => { resolveMutation?.(operation === 'delete' ? undefined : savedAnnotation) })
    expect(screen.getByText(/Run A instrument/)).toBeInTheDocument()
    expect(screen.queryByText(/Review drawing (saved|updated|removed)/)).not.toBeInTheDocument()
    expect(screen.queryByText('Saving…')).not.toBeInTheDocument()
  })

it.each(['create', 'update', 'delete'] as const)(
  'aborts a delayed %s on unmount without a late state write', async (operation) => {
    let resolveMutation: ((value: typeof savedAnnotation | void) => void) | undefined
    let mutationSignal: AbortSignal | undefined
    const delayed = vi.fn((...args: unknown[]) => {
      mutationSignal = args[operation === 'update' ? 6 : 4] as AbortSignal
      return new Promise<typeof savedAnnotation | void>((resolve) => { resolveMutation = resolve })
    })
    const api = mockApi({ chartAnnotations: vi.fn().mockResolvedValue(
      operation === 'create' ? [] : [savedAnnotation]), [`${operation}ChartAnnotation`]: delayed })
    const view = render(<MarketContext api={api} projectId="project.a" runId={7} />)
    await screen.findByRole('heading', { name: 'Review drawing' })
    if (operation !== 'create') await chooseSelect('Saved drawing', savedAnnotation.annotation_id)
    fireEvent.click(screen.getByRole('button', { name: operation === 'delete' ? 'Remove'
      : operation === 'update' ? 'Save changes' : 'Save drawing' }))
    await waitFor(() => expect(delayed).toHaveBeenCalledOnce())
    view.unmount()
    expect(mutationSignal?.aborted).toBe(true)
    await act(async () => { resolveMutation?.(operation === 'delete' ? undefined : savedAnnotation) })
    expect(view.container).toBeEmptyDOMElement()
  })

it('does not start timed playback when reduced motion is requested', async () => {
  Object.defineProperty(window, 'matchMedia', { configurable: true,
    value: vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }) })
  render(<MarketContext api={mockApi()} projectId="project.a" runId={7} />)
  const play = await screen.findByRole('button', { name: 'Play completed candle replay' })
  fireEvent.click(play)
  expect(screen.getByRole('button', { name: 'Play completed candle replay' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Pause completed candle replay' })).not.toBeInTheDocument()
})


it('uses selected drawing geometry and completed candles, and clears a saved selection', async () => {
  const api = mockApi()
  render(<MarketContext api={api} projectId="project.a" runId={7} />)
  await screen.findByRole('heading', { name: 'Review drawing' })
  await chooseSelect('Drawing type', 'LINE')
  await chooseSelect('First candle', bars[1].completed_at)
  await chooseSelect('Second candle', bars[2].completed_at)
  fireEvent.change(screen.getByLabelText('First price'), { target: { value: '100' } })
  fireEvent.change(screen.getByLabelText('Second price'), { target: { value: '103' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save drawing' }))
  await waitFor(() => expect(api.createChartAnnotation).toHaveBeenCalledOnce())
  expect(api.createChartAnnotation).toHaveBeenCalledWith('project.a', 7,
    expect.objectContaining({ kind: 'LINE', start: { time: bars[1].completed_at, price: '100' },
      end: { time: bars[2].completed_at, price: '103' }, slope_per_microsecond: { numerator: '1', denominator: '20000000' } }),
    expect.objectContaining({ known_at: bars[2].completed_at, locked_at: bars[2].completed_at }), expect.any(AbortSignal))
  await screen.findByRole('button', { name: 'Save changes' })
  await chooseSelect('Saved drawing', '')
  expect(screen.getByRole('button', { name: 'Save drawing' })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Start' }))
  expect(screen.getByText('Move replay forward to a completed candle before drawing.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Save drawing' })).toBeDisabled()
})
