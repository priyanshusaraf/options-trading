import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'
import App from './PrototypeApp'
import { connectionForInsertedNode } from './components/graphUtils'

function renderAt(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>)
}

afterEach(cleanup)

describe('Strategy OS interface exploration', () => {
  it('presents the original six and the five refined variants', () => {
    renderAt('/prototype')
    expect(screen.getByRole('heading', { name: 'Calm Strategy Studio' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Adaptive Trading Workstation' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Strategy Lifecycle Studio' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Progressive Operating System' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Evidence Ledger' })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { name: 'Obsidian Strategy OS' }).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('heading', { name: 'Precision Slate' }).length).toBeGreaterThan(0)
    expect(screen.getByRole('heading', { name: 'Lightning Desk' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Clear Day' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Signal Ink' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Warm Current' })).toBeInTheDocument()
    expect(screen.getByText('154 ROUTED SURFACE EXPERIENCES')).toBeInTheDocument()
  })

  it('switches the shared strategy definition from graph to code projection', async () => {
    renderAt('/d6?surface=build')
    expect(screen.getByRole('heading', { name: 'Build the strategy' })).toBeInTheDocument()
    const codeTab = await screen.findByRole('tab', { name: 'Code' })
    expect((await screen.findAllByText('Opening range')).length).toBeGreaterThan(0)
    fireEvent.click(codeTab)
    expect(screen.getByLabelText('Read-only code projection')).toHaveTextContent('strategy "NIFTY-ORB-15"')
    expect(screen.getByText('No unsaved edits')).toBeInTheDocument()
  })

  it('fails the paper preflight closed and exposes no live route', () => {
    renderAt('/d3?surface=deploy')
    expect(screen.getByRole('heading', { name: 'Preflight a deployment' })).toBeInTheDocument()
    expect(screen.getByText('RECEIPT_STALE: wait for a fresh completed-bar receipt. Existing exit protection remains available.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Live mode unavailable' })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Stage paper deployment/i })).toBeDisabled()
    expect(screen.getByText(/no live authority, credentials, provider session or order route/i)).toBeInTheDocument()
  })

  it('navigates between routed surfaces without losing the strategy shell', () => {
    renderAt('/d1?surface=home')
    fireEvent.click(screen.getAllByRole('button', { name: 'Portfolio' })[0])
    expect(screen.getByRole('heading', { name: 'Capital, exposure and strategy attribution' })).toBeInTheDocument()
    expect(screen.getAllByText('NIFTY Opening Range').length).toBeGreaterThan(0)
  })

  it('scopes local lifecycle navigation to strategy surfaces and collapses global navigation', () => {
    renderAt('/d7?surface=home')
    expect(screen.queryByRole('navigation', { name: 'Selected strategy sections' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Collapse navigation' }))
    expect(screen.getByRole('button', { name: 'Expand navigation' })).toBeInTheDocument()
    cleanup()
    renderAt('/d7?surface=overview')
    expect(screen.getByRole('navigation', { name: 'Selected strategy sections' })).toBeInTheDocument()
  })

  it('lets the refined builder surrender both side panes to the graph canvas', async () => {
    renderAt('/d8?surface=build')
    expect(await screen.findByRole('heading', { name: 'Node library' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Inspector' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Focus canvas' }))
    expect(screen.queryByRole('heading', { name: 'Node library' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Inspector' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Exit canvas focus' })).toBeInTheDocument()
  })

  it('opens the Blender-style node palette with Shift+A and edits the local draft', async () => {
    renderAt('/d7?surface=build')
    await screen.findByRole('heading', { name: 'Node library' })
    fireEvent.keyDown(window, { key: 'A', shiftKey: true })
    const palette = screen.getByRole('dialog', { name: 'Add node' })
    expect(palette).toBeInTheDocument()
    fireEvent.click(within(palette).getByRole('button', { name: /Options chain/i }))
    expect(screen.getByText('Draft edited')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Opening range window'), { target: { value: '20m' } })
    expect(screen.getByLabelText('Opening range window')).toHaveValue('20m')
    fireEvent.change(screen.getByLabelText('X'), { target: { value: '440' } })
    expect(screen.getByLabelText('X')).toHaveValue(440)
    fireEvent.change(screen.getByLabelText('Connect selected node output'), { target: { value: 'market' } })
    fireEvent.click(screen.getByRole('button', { name: 'Connect' }))
    expect(screen.getByText('7 nodes · 7 edges')).toBeInTheDocument()
  })

  it('stages a local CSV as an editable data node without claiming backend authority', async () => {
    renderAt('/d7?surface=build')
    await screen.findByRole('heading', { name: 'Node library' })
    const input = document.querySelector<HTMLInputElement>('input[type="file"][accept*=".csv"]')
    expect(input).not.toBeNull()
    const file = new File([
      'timestamp,open,high,low,close,volume\n2026-08-21T09:15:00+05:30,24810,24825,24804,24821,1200',
    ], 'nifty-5m.csv', { type: 'text/csv' })
    fireEvent.change(input!, { target: { files: [file] } })
    await waitFor(() => expect(screen.getByText(/nifty-5m\.csv · 1 rows staged locally/i)).toBeInTheDocument())
    expect(screen.getByLabelText('CSV dataset file')).toHaveValue('nifty-5m.csv')
    expect(screen.getByLabelText('CSV dataset authority')).toHaveValue('local only')
    expect(screen.getByText('7 nodes · 6 edges')).toBeInTheDocument()
  })

  it('preserves connector direction when a loose edge inserts a new node', () => {
    expect(connectionForInsertedNode({ nodeId: 'opening-range', nodeTitle: 'Opening range', handleId: 'output', handleType: 'source' }, 'and-gate')).toEqual({
      source: 'opening-range', target: 'and-gate', sourceHandle: 'output', targetHandle: 'input-0',
    })
    expect(connectionForInsertedNode({ nodeId: 'atr-risk', nodeTitle: 'ATR protection', handleId: 'input-1', handleType: 'target' }, 'and-gate')).toEqual({
      source: 'and-gate', target: 'atr-risk', sourceHandle: 'output', targetHandle: 'input-1',
    })
  })
})
