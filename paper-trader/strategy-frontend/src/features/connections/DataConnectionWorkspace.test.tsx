import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { useLayoutEffect } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DataConnectionWorkspace } from './DataConnectionWorkspace'
import { DataConnectionContractError, DataConnectionRequestError, type DataConnectionClient, type DataConnectionState, type DataConnectionStatus, type ProviderInstrumentSearchResult } from './dataConnectionClient'

const allowed: Readonly<Record<DataConnectionState, readonly string[]>> = {
  CONNECTION_REQUIRED: ['create'], APP_KEYS_REQUIRED: ['write_app_keys', 'revoke'],
  REAUTH_REQUIRED: ['rotate_app_keys', 'reauthenticate', 'revoke'],
  SESSION_PRESENT_UNVERIFIED: ['rotate_app_keys', 'reauthenticate', 'revoke'],
  REVOKED: ['create'], UNAVAILABLE: [],
}

function status(state: DataConnectionState): DataConnectionStatus {
  const actions = allowed[state]
  return Object.freeze({
    schema: 'strategy-os-data-connection-status/1', state, provider: 'ZERODHA', role: 'DATA',
    ready: false, credential_expiry: 'UNVERIFIED', rate_quota: 'UNVERIFIED',
    actions: Object.freeze({
      create: actions.includes('create'), write_app_keys: actions.includes('write_app_keys'),
      rotate_app_keys: actions.includes('rotate_app_keys'), reauthenticate: actions.includes('reauthenticate'),
      revoke: actions.includes('revoke'),
    }),
  })
}

function client(initial: DataConnectionState): DataConnectionClient {
  return {
    status: vi.fn().mockResolvedValue(status(initial)),
    create: vi.fn().mockResolvedValue(status('APP_KEYS_REQUIRED')),
    storeAppKeys: vi.fn().mockResolvedValue(status('REAUTH_REQUIRED')),
    rotateAppKeys: vi.fn().mockResolvedValue(status('REAUTH_REQUIRED')),
    initiate: vi.fn().mockResolvedValue({ login_url: 'https://fake-provider.invalid/login?state=synthetic' }),
    revoke: vi.fn().mockResolvedValue(status('REVOKED')),
    searchInstruments: vi.fn().mockResolvedValue(searchResult()),
    resolveInstrument: vi.fn(),
    selectInstrument: vi.fn(),
  }
}

function searchResult(query = 'NIFTY', exchange = 'ALL'): ProviderInstrumentSearchResult {
  return { schema: 'strategy-os-provider-instrument-search/2', provider: 'ZERODHA', reference_type: 'CURRENT_PROVIDER_REFERENCE',
    query, exchange, available_exchanges: ['NSE', 'BSE', 'NFO', 'MCX'], has_more: false,
    items: [{ token: 256265, symbol: 'NIFTY 50', name: 'NIFTY 50', exchange: exchange === 'ALL' ? 'NSE' : exchange,
      segment: 'INDICES', instrument_type: 'EQ', expiry: null, strike: '0', lot_size: '1', tick_size: '0.05' }] }
}

async function search(query = 'nifty') {
  fireEvent.change(await screen.findByRole('searchbox', { name: 'Symbol or name' }), { target: { value: query } })
  fireEvent.click(screen.getByRole('button', { name: 'Search instruments' }))
}

function show(subject: DataConnectionClient, navigateExternal = vi.fn()) {
  return { navigateExternal, ...render(<MemoryRouter><DataConnectionWorkspace client={subject} navigateExternal={navigateExternal} /></MemoryRouter>) }
}

afterEach(() => cleanup())

describe('DataConnectionWorkspace', () => {
  it('offers current provider instrument search in the connected page', async () => {
    show(client('SESSION_PRESENT_UNVERIFIED'))
    expect(await screen.findByRole('heading', { name: 'Find an instrument' })).toBeInTheDocument()
    expect(screen.getByRole('searchbox', { name: 'Symbol or name' })).toBeInTheDocument()
  })

  it('renders server truth as explicitly unverified and never as ready', async () => {
    show(client('SESSION_PRESENT_UNVERIFIED'))
    expect(await screen.findByRole('heading', { name: 'Zerodha data connection' })).toBeInTheDocument()
    expect(screen.getByText('Session stored, provider not verified')).toBeInTheDocument()
    expect(screen.getByText('Not ready')).toBeInTheDocument()
    expect(screen.getAllByText('Unverified')).toHaveLength(2)
    expect(screen.queryByText(/^Ready$/)).not.toBeInTheDocument()
  })

  it('runs create then initial keys with labels, feedback and cleared secret fields', async () => {
    const subject = client('CONNECTION_REQUIRED')
    show(subject)
    fireEvent.click(await screen.findByRole('button', { name: 'Create connection' }))
    expect(await screen.findByRole('heading', { name: 'Add application keys' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Application key'), { target: { value: 'KEY-SENTINEL' } })
    fireEvent.change(screen.getByLabelText('Application secret'), { target: { value: 'SECRET-SENTINEL' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save keys' }))
    await waitFor(() => expect(subject.storeAppKeys).toHaveBeenCalledOnce())
    expect(await screen.findByText('Reconnect this browser session')).toBeInTheDocument()
    expect(screen.queryByDisplayValue('KEY-SENTINEL')).not.toBeInTheDocument()
    expect(document.body.textContent).not.toContain('SECRET-SENTINEL')
  })

  it('announces validation errors and supports explicit rotation cancellation', async () => {
    show(client('REAUTH_REQUIRED'))
    fireEvent.click(await screen.findByRole('button', { name: 'Rotate keys' }))
    fireEvent.click(screen.getByRole('button', { name: 'Rotate keys' }))
    const error = await screen.findByRole('alert')
    expect(error).toHaveTextContent('Enter both')
    expect(error).toHaveFocus()
    fireEvent.change(screen.getByLabelText('Application key'), { target: { value: 'volatile' } })
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByDisplayValue('volatile')).not.toBeInTheDocument()
  })

  it('clears both secret inputs after a partially populated invalid submission', async () => {
    show(client('APP_KEYS_REQUIRED'))
    await screen.findByRole('heading', { name: 'Add application keys' })
    fireEvent.change(screen.getByLabelText('Application key'), {
      target: { value: 'PARTIAL-KEY-SENTINEL' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save keys' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Enter both')
    expect(screen.getByLabelText('Application key')).toHaveValue('')
    expect(screen.getByLabelText('Application secret')).toHaveValue('')
    expect(document.body.textContent).not.toContain('PARTIAL-KEY-SENTINEL')
  })

  it('clears both secret inputs after an oversized invalid submission', async () => {
    show(client('REAUTH_REQUIRED'))
    fireEvent.click(await screen.findByRole('button', { name: 'Rotate keys' }))
    fireEvent.change(screen.getByLabelText('Application key'), {
      target: { value: `OVERSIZED-KEY-SENTINEL-${'x'.repeat(4096)}` },
    })
    fireEvent.change(screen.getByLabelText('Application secret'), {
      target: { value: 'OVERSIZED-SECRET-SENTINEL' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Rotate keys' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('4,096 bytes or fewer')
    expect(screen.getByLabelText('Application key')).toHaveValue('')
    expect(screen.getByLabelText('Application secret')).toHaveValue('')
    expect(document.body.textContent).not.toContain('OVERSIZED-')
  })

  it('navigates only to the verified login URL returned by the client', async () => {
    const subject = client('REAUTH_REQUIRED')
    const { navigateExternal } = show(subject)
    fireEvent.click(await screen.findByRole('button', { name: 'Reconnect' }))
    await waitFor(() => expect(navigateExternal).toHaveBeenCalledWith(
      'https://fake-provider.invalid/login?state=synthetic'))
  })

  it('requires explicit revocation confirmation and projects the revoked state', async () => {
    const subject = client('REAUTH_REQUIRED')
    show(subject)
    fireEvent.click(await screen.findByRole('button', { name: 'Disconnect provider' }))
    expect(subject.revoke).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Confirm disconnect' }))
    expect(await screen.findByText('Provider disconnected')).toBeInTheDocument()
    expect(subject.revoke).toHaveBeenCalledOnce()
  })

  it('shows no stale state after a load failure and offers retry', async () => {
    const subject = client('SESSION_PRESENT_UNVERIFIED')
    vi.mocked(subject.status).mockRejectedValueOnce(new Error('offline'))
    show(subject)
    expect(await screen.findByRole('alert')).toHaveTextContent('No cached state is shown')
    expect(screen.queryByText('Session stored, provider not verified')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('Session stored, provider not verified')).toBeInTheDocument()
  })

  it('contains no storage, analytics, websocket or execution dependency', () => {
    const source = DataConnectionWorkspace.toString()
    for (const forbidden of ['localStorage', 'sessionStorage', 'WebSocket', 'analytics', '/api/orders', '/api/positions']) {
      expect(source).not.toContain(forbidden)
    }
  })

  it('renders plain provider copy without internal state codes or misleading storage wording', async () => {
    show(client('REAUTH_REQUIRED'))
    await screen.findByRole('heading', { name: 'Zerodha data connection' })
    expect(screen.getByText('Connection details')).toBeInTheDocument()
    expect(screen.getByText('Your app keys are stored. This browser needs a fresh Zerodha sign-in.')).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/REAUTH_REQUIRED|SESSION_PRESENT_UNVERIFIED|APP_KEYS_REQUIRED|CONNECTION_REQUIRED|REVOKED|canonical|Store application keys locally/)
  })

  it('searches only on submission and exposes current references without implying mapped history', async () => {
    const subject = client('SESSION_PRESENT_UNVERIFIED')
    show(subject)
    const input = await screen.findByRole('searchbox', { name: 'Symbol or name' })
    fireEvent.change(input, { target: { value: 'nifty' } })
    expect(subject.searchInstruments).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Search instruments' }))
    expect(await screen.findByRole('table')).toHaveAccessibleName('Current provider references for “NIFTY” · ALL')
    expect(subject.searchInstruments).toHaveBeenCalledWith('nifty', 'ALL', expect.any(AbortSignal))
    expect(within(screen.getByRole('table')).getByRole('cell', { name: 'INDICES / EQ' })).toBeInTheDocument()
    expect(screen.getByText(/Backtests need verified instrument details/)).toBeInTheDocument()
    expect(screen.getByText('Not ready')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /add to|use instrument/i })).not.toBeInTheDocument()
  })

  it.each(['CONNECTION_REQUIRED', 'APP_KEYS_REQUIRED', 'REAUTH_REQUIRED', 'REVOKED', 'UNAVAILABLE'] as const)('keeps search unavailable for %s', async (state) => {
    const subject = client(state)
    show(subject)
    expect(await screen.findByRole('button', { name: 'Search instruments' })).toBeDisabled()
    expect(screen.getByRole('searchbox')).toBeDisabled()
    expect(screen.getByRole('combobox', { name: 'Exchange' })).toBeDisabled()
    expect(subject.searchInstruments).not.toHaveBeenCalled()
  })

  it('retains query and exchange on reconnect errors, focuses explanation and retries explicitly', async () => {
    const subject = client('SESSION_PRESENT_UNVERIFIED')
    vi.mocked(subject.searchInstruments).mockResolvedValueOnce(searchResult()).mockRejectedValueOnce(new DataConnectionRequestError(409, 'DATA_REAUTH_REQUIRED'))
      .mockResolvedValueOnce(searchResult('NIFTY', 'BSE'))
    show(subject)
    await search(); await screen.findByRole('table')
    fireEvent.change(screen.getByRole('combobox', { name: 'Exchange' }), { target: { value: 'BSE' } })
    await search()
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Reconnect to Zerodha above')
    expect(alert).toHaveFocus()
    expect(screen.getByRole('searchbox')).toHaveValue('nifty')
    expect(screen.getByRole('combobox', { name: 'Exchange' })).toHaveValue('BSE')
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Search instruments' }))
    expect(await screen.findByRole('table')).toHaveAccessibleName(/BSE/)
    expect(subject.searchInstruments).toHaveBeenCalledTimes(3)
  })

  it.each([
    [new DataConnectionRequestError(422, 'INVALID_INSTRUMENT_SEARCH'), /Enter 2–64/],
    [new DataConnectionRequestError(503, 'DATA_PROVIDER_BUSY'), /temporarily unavailable/],
    [new DataConnectionRequestError(403), /Sign in again/],
    [new DataConnectionRequestError(409), /not accepted/],
    [new DataConnectionContractError(), /could not be verified/],
    [new Error('private provider payload'), /could not be reached/],
  ])('keeps inputs and shows safe search recovery for %s', async (failure, expected) => {
    const subject = client('SESSION_PRESENT_UNVERIFIED')
    vi.mocked(subject.searchInstruments).mockRejectedValue(failure)
    show(subject)
    await search()
    expect(await screen.findByRole('alert')).toHaveTextContent(expected as RegExp)
    expect(screen.getByRole('searchbox')).toHaveValue('nifty')
    expect(document.body.textContent).not.toContain('private provider payload')
  })

  it('discards an older response after query editing, even if the request ignores abort', async () => {
    const subject = client('SESSION_PRESENT_UNVERIFIED')
    let finish: (result: ProviderInstrumentSearchResult) => void = () => undefined
    vi.mocked(subject.searchInstruments).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    show(subject)
    await search()
    const signal = vi.mocked(subject.searchInstruments).mock.calls[0][2]
    expect(screen.getByRole('button', { name: 'Search instruments' })).toBeDisabled()
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'reliance' } })
    expect(signal.aborted).toBe(true)
    await act(async () => finish(searchResult()))
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getByRole('searchbox')).toHaveValue('reliance')
  })

  it('clears prior results on exchange edits and distinguishes empty results from truncated results', async () => {
    const subject = client('SESSION_PRESENT_UNVERIFIED')
    vi.mocked(subject.searchInstruments).mockResolvedValueOnce({ ...searchResult(), has_more: true,
      items: Array.from({ length: 20 }, (_, index) => ({ ...searchResult().items[0], token: index + 1 })) })
      .mockResolvedValueOnce({ ...searchResult('NIFTY', 'BSE'), items: [] })
    show(subject)
    await search()
    expect(await screen.findByText(/Showing the first 20/)).toBeInTheDocument()
    fireEvent.change(screen.getByRole('combobox', { name: 'Exchange' }), { target: { value: 'BSE' } })
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Search instruments' }))
    expect(await screen.findByText(/No current references match/)).toHaveTextContent('BSE')
  })

  it('aborts search and hides current results when the connection is disconnected', async () => {
    const subject = client('SESSION_PRESENT_UNVERIFIED')
    let finish: (result: ProviderInstrumentSearchResult) => void = () => undefined
    vi.mocked(subject.searchInstruments).mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    show(subject)
    await search()
    const signal = vi.mocked(subject.searchInstruments).mock.calls[0][2]
    fireEvent.click(screen.getByRole('button', { name: 'Disconnect provider' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm disconnect' }))
    expect(await screen.findByText('Provider disconnected')).toBeInTheDocument()
    expect(signal.aborted).toBe(true)
    await act(async () => finish(searchResult()))
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Search instruments' })).toBeDisabled()
  })

  it('aborts on unmount and clears the prior query when the client identity changes', async () => {
    const first = client('SESSION_PRESENT_UNVERIFIED')
    vi.mocked(first.searchInstruments).mockImplementation(() => new Promise(() => undefined))
    const shown = show(first)
    await search()
    const oldSignal = vi.mocked(first.searchInstruments).mock.calls[0][2]
    const second = client('SESSION_PRESENT_UNVERIFIED')
    shown.rerender(<MemoryRouter><DataConnectionWorkspace client={second} /></MemoryRouter>)
    expect(await screen.findByRole('searchbox')).toHaveValue('')
    expect(oldSignal.aborted).toBe(true)
    vi.mocked(second.searchInstruments).mockImplementation(() => new Promise(() => undefined))
    await search()
    const signal = vi.mocked(second.searchInstruments).mock.calls[0][2]
    shown.unmount()
    expect(signal.aborted).toBe(true)
  })

  it('hides the previous client query and references in the first changed-client commit', async () => {
    const commits = vi.fn()
    function Probe({ subject }: { subject: DataConnectionClient }) {
      useLayoutEffect(() => {
        commits({ query: document.querySelector<HTMLInputElement>('input[type="search"]')?.value,
          text: document.body.textContent })
      }, [subject])
      return <MemoryRouter><DataConnectionWorkspace client={subject} /></MemoryRouter>
    }
    const first = client('SESSION_PRESENT_UNVERIFIED')
    const shown = render(<Probe subject={first} />)
    await search()
    await screen.findByRole('table')
    commits.mockClear()
    shown.rerender(<Probe subject={client('SESSION_PRESENT_UNVERIFIED')} />)
    expect(commits).toHaveBeenCalledOnce()
    expect(commits.mock.calls[0][0].query).toBe('')
    expect(commits.mock.calls[0][0].text).not.toContain('NIFTY 50')
    await screen.findByRole('searchbox')
  })
})
