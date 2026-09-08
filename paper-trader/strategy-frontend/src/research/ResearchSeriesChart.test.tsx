import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { ResearchSeriesChart } from './ResearchSeriesChart'

afterEach(cleanup)

it('renders 2,000 persisted points with keyboard controls and a data alternative within the chart budget', () => {
  const equity = Array.from({ length: 2000 }, (_, index) => ({ time: 1_700_000_000 + index * 900, value: 100_000 + Math.sin(index / 20) * 500 + index }))
  let peak = equity[0].value
  const drawdown = equity.map((point) => { peak = Math.max(peak, point.value); const absolute = peak - point.value; return { time: point.time, value: absolute / peak * 100, absolute } })
  const started = performance.now(); render(<ResearchSeriesChart equity={equity} drawdown={drawdown} />); expect(performance.now() - started).toBeLessThan(1000)
  expect(screen.getByRole('img', { name: /Net equity from INR/ })).toBeInTheDocument(); fireEvent.click(screen.getByRole('button', { name: 'Zoom in chart' })); fireEvent.click(screen.getByText('Open chart data table'))
  expect(screen.getByRole('columnheader', { name: 'Net equity (INR)' })).toBeInTheDocument()
})

it('renders separate entry and exit shapes for each persisted trade event pair', () => {
  const { container } = render(<ResearchSeriesChart equity={[{ time: 1, value: 100 }, { time: 3, value: 109 }]}
    drawdown={[{ time: 1, value: 0, absolute: 0 }, { time: 3, value: 0, absolute: 0 }]}
    events={[{ cursor: 1, event_kind: 'ENTRY', time: 1, direction: 'LONG' }, { cursor: 1, event_kind: 'EXIT', time: 2, direction: 'LONG' }]} />)
  expect(container.querySelectorAll('.chart-event--entry')).toHaveLength(1)
  expect(container.querySelectorAll('.chart-event--exit')).toHaveLength(1)
})
