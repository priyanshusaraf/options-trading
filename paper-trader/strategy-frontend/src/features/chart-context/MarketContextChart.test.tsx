import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import type { ChartAnnotation, MarketContextBar } from '../../shell/contracts'
import { MarketContextChart } from './MarketContextChart'

afterEach(cleanup)
const address = (digit: string) => `sha256:${digit.repeat(64)}`
const bars: MarketContextBar[] = Array.from({ length: 2000 }, (_, index) => ({
  cursor: index + 1, event_time: new Date(Date.UTC(2026, 0, 1, 9, index)).toISOString(),
  completed_at: new Date(Date.UTC(2026, 0, 1, 9, index + 1)).toISOString(),
  open: 100 + index, high: 102 + index, low: 99 + index, close: 101 + index,
  volume: 1000 + index,
}))
const level: ChartAnnotation = {
  annotation_id: '00000000-0000-0000-0000-000000000001', revision: 1,
  geometry: { schema: 'normalized-annotation-geometry/1', kind: 'LEVEL', price: '150' },
  geometry_address: address('a'), applicability: { schema: 'annotation-applicability/1' },
  applicability_address: address('b'), created_at: '2026-01-01T09:00:00Z',
  updated_at: '2026-01-01T09:00:00Z',
}

it('renders OHLCV, overlay and trade shapes, and a paged semantic table', () => {
  const { container } = render(<MarketContextChart bars={bars} annotations={[level]}
    tradeEvents={[{ cursor: 1, event_kind: 'ENTRY',
      time: Date.parse(bars[2].event_time) / 1000, price: 102 }]} />)
  expect(screen.getByRole('img', { name: /2,000 completed candles/ })).toBeInTheDocument()
  expect(container.querySelectorAll('.candle')).toHaveLength(2000)
  expect(container.querySelector('.review-level')).toBeInTheDocument()
  expect(container.querySelector('.causal-playhead')).toBeInTheDocument()
  fireEvent.click(screen.getByText('Open candle data table'))
  expect(screen.getByRole('columnheader', { name: 'Candle closed (UTC)' })).toBeInTheDocument()
  expect(screen.getAllByRole('row')).toHaveLength(101)
  fireEvent.click(screen.getByRole('button', { name: 'Next candles' }))
  expect(screen.getByText('101–200 of 2000')).toBeInTheDocument()
})
