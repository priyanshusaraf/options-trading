import { chooseSelect } from '../../test/select'
import { readFileSync } from 'node:fs'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { DataLibraryWorkspace } from './DataLibraryWorkspace'
import { DailyCsvImport } from './DailyCsvImport'
import { parseDailyCsvImport, parseDailyCsvInspection, requireMatchingCsvImport } from './dailyCsvContracts'
import { ApiError, type StrategyApi } from '../../shell/api'
import type {
  CsvInspection,
  DataLibraryClient,
  DataLibraryItem,
  DataLibraryPreview,
  ImportOutcome,
} from './dataLibraryContracts'

afterEach(cleanup)

const address = (character: string) => `sha256:${character.repeat(64)}`

const item: DataLibraryItem = {
  dataset_id: 'desk-history', import_id: '1'.repeat(32), version_number: 2, manifest_address: address('a'),
  dataset_name: 'Desk research history', series_kind: 'INSTRUMENT', series_label: 'NIFTY 50 spot',
  instrument_address: address('f'), logical_series_id: null,
  interval_seconds: 900, timezone: 'Asia/Kolkata', timestamp_meaning: 'BAR_OPEN',
  event_start: '2026-01-01T03:45:00+00:00', event_end: '2026-01-31T10:00:00+00:00',
  row_count: 2000, column_count: 7, quality_state: 'VALID_WITH_WARNINGS', quality_score: 96,
  imported_at: '2026-02-01T06:00:00+00:00', fields: ['CLOSE', 'HIGH', 'LOW', 'OPEN', 'VOLUME'],
  extra_columns: [{ source: 'sentiment', target: 'sentiment_score', data_type: 'NUMBER' }],
  warnings: [{ code: 'INTERVAL_GAP', severity: 'WARNING', message: 'The file has missing intervals.', count: 1, first_row: null, column: null }],
  market_truth_state: 'USER_DECLARED_RECONSTRUCTED',
  backtest_compatible: false, source_content_address: address('b'), mapping_address: address('c'),
  normalized_content_address: address('d'),
}

const inspection: CsvInspection = {
  source_content_address: address('b'),
  columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'sentiment'],
  suggested_columns: [
    { source: 'timestamp', role: 'TIMESTAMP', target_name: null, data_type: null },
    { source: 'open', role: 'OPEN', target_name: null, data_type: null },
    { source: 'high', role: 'HIGH', target_name: null, data_type: null },
    { source: 'low', role: 'LOW', target_name: null, data_type: null },
    { source: 'close', role: 'CLOSE', target_name: null, data_type: null },
    { source: 'volume', role: 'VOLUME', target_name: null, data_type: null },
    { source: 'sentiment', role: 'FEATURE', target_name: 'sentiment_score', data_type: 'NUMBER' },
  ],
  rows: [['2026-01-01T09:15:00', '100', '102', '98', '101', '1000', '0.2']],
  row_count_seen: 1, rows_truncated: false, columns_truncated: false, issues: [],
}

const preview: DataLibraryPreview = {
  item,
  columns: [
    { source: 'timestamp', role: 'TIMESTAMP', target: 'event_time', data_type: null },
    { source: 'open', role: 'OPEN', target: 'open', data_type: 'NUMBER' },
    { source: 'sentiment', role: 'FEATURE', target: 'sentiment_score', data_type: 'NUMBER' },
  ],
  rows: [['2026-01-01T03:45:00+00:00', '100', '0.2']],
  truncated: true,
}

function client(items: readonly DataLibraryItem[] = []): DataLibraryClient & {
  list: ReturnType<typeof vi.fn<DataLibraryClient['list']>>
  inspect: ReturnType<typeof vi.fn<DataLibraryClient['inspect']>>
  import: ReturnType<typeof vi.fn<DataLibraryClient['import']>>
  preview: ReturnType<typeof vi.fn<DataLibraryClient['preview']>>
} {
  return {
    list: vi.fn<DataLibraryClient['list']>().mockResolvedValue({ items, next_cursor: null }),
    inspect: vi.fn<DataLibraryClient['inspect']>().mockResolvedValue(inspection),
    import: vi.fn<DataLibraryClient['import']>(),
    preview: vi.fn<DataLibraryClient['preview']>().mockResolvedValue(preview),
  }
}

describe('Data Library states and human-first disclosure', () => {
  it('shows a useful empty state and opens the import workflow', async () => {
    render(<DataLibraryWorkspace client={client()} />)
    expect(await screen.findByRole('heading', { name: 'No imported data yet' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Import CSV' }))
    expect(screen.getByRole('heading', { name: 'Map the file before import' })).toBeInTheDocument()
    expect(screen.getByText('Imports are for research.')).toBeInTheDocument()
  })

  it('loads useful version details without internal identities', async () => {
    render(<DataLibraryWorkspace client={client([item])} />)
    expect(await screen.findByText('Desk research history')).toBeInTheDocument()
    expect(screen.getByText(/NIFTY 50 spot · Version 2 · 15 min/)).toBeInTheDocument()
    expect(screen.getByText('Valid with warnings')).toBeInTheDocument()
    expect(await screen.findByRole('table')).toHaveAccessibleName(/Showing 1 of 2,000 rows/)
    expect(screen.getByRole('columnheader', { name: 'sentiment_score' })).toBeInTheDocument()
    expect(screen.getByLabelText('Mapped column roles')).toHaveTextContent('sentiment_score · number')
    expect(screen.getByText('User supplied; market rules and corporate actions are not independently verified')).toBeInTheDocument()
    for (const value of [item.manifest_address, item.source_content_address, item.mapping_address, item.normalized_content_address]) expect(screen.queryByText(value)).not.toBeInTheDocument()
    expect(screen.getByText('This import can be previewed here, but cannot currently be selected for a backtest.')).toBeInTheDocument()
  })

  it('removes stale rows on list error and supports retry', async () => {
    const api = client([item])
    api.list.mockRejectedValueOnce(new Error('private detail')).mockResolvedValueOnce({ items: [], next_cursor: null })
    render(<DataLibraryWorkspace client={api} />)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Datasets could not be loaded.')
    expect(screen.queryByText(item.dataset_name)).not.toBeInTheDocument()
    fireEvent.click(within(alert).getByRole('button', { name: 'Retry' }))
    expect(await screen.findByRole('heading', { name: 'No imported data yet' })).toBeInTheDocument()
  })
})

describe('mapping, errors and import authority', () => {
  it('inspects locally selected file through the injected client and renders every mapped column', async () => {
    const api = client()
    render(<DataLibraryWorkspace client={api} instruments={[{ address: address('f'), label: 'NIFTY 50 · NSE' }]} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Import CSV' }))
    const file = new File(['timestamp,open\n'], 'desk.csv', { type: 'text/csv' })
    fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [file] } })
    await waitFor(() => expect(api.inspect).toHaveBeenCalledWith(file, expect.any(AbortSignal)))
    expect(await screen.findByRole('group', { name: 'Column mapping' })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'timestamp role' })).toHaveTextContent('timestamp')
    expect(screen.getByLabelText('sentiment research name')).toHaveValue('sentiment_score')
    expect(screen.getByRole('combobox', { name: 'sentiment type' })).toHaveTextContent('number')
    expect(screen.getByLabelText('Dataset name')).toHaveValue('desk')
  })

  it('focuses a linked error summary and keeps inline form errors', async () => {
    const api = client()
    render(<DataLibraryWorkspace client={api} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Import CSV' }))
    fireEvent.submit(screen.getByRole('button', { name: 'Import dataset' }).closest('form')!)
    const summary = screen.getByRole('alert')
    await waitFor(() => expect(summary).toHaveFocus())
    expect(screen.getByText('Enter a dataset name.', { selector: '.data-field-error' })).toBeInTheDocument()
    const link = screen.getByRole('link', { name: 'Enter a dataset name.' })
    fireEvent.click(link)
    expect(screen.getByLabelText('Dataset name')).toHaveFocus()
    expect(screen.getByRole('combobox', { name: 'Strategy OS instrument' })).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('combobox', { name: 'Strategy OS instrument' })).toHaveAttribute('aria-describedby', 'data-instrument-error')
    expect(screen.getByText('No instruments are available to choose right now.')).toBeInTheDocument()
    expect(api.import).not.toHaveBeenCalled()
  })

  it('submits explicit time, series and column semantics and reports warnings', async () => {
    const api = client()
    const outcome: ImportOutcome = {
      analysis: { state: 'VALID_WITH_WARNINGS', row_count: 60, column_count: 7, quality_score: 98,
        issues: [{ code: 'INTERVAL_GAP', severity: 'WARNING', message: 'The file has missing intervals.', count: 1, first_row: null, column: null }], backtest_compatible: false },
      item,
    }
    api.import.mockResolvedValue(outcome)
    api.list.mockResolvedValueOnce({ items: [], next_cursor: null }).mockResolvedValueOnce({ items: [item], next_cursor: null })
    render(<DataLibraryWorkspace client={api} instruments={[{ address: address('f'), label: 'NIFTY 50 · NSE' }]} />)
    fireEvent.click(await screen.findByRole('button', { name: 'Import CSV' }))
    const file = new File(['csv'], 'desk.csv', { type: 'text/csv' })
    fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [file] } })
    await screen.findByRole('group', { name: 'Column mapping' })
    fireEvent.change(screen.getByLabelText('Series or instrument name'), { target: { value: 'NIFTY 50 spot' } })
    await chooseSelect('Strategy OS instrument', address('f'))
    await chooseSelect('Strategy OS instrument', '')
    expect(screen.getByRole('combobox', { name: 'Strategy OS instrument' })).toHaveTextContent('Select an instrument')
    await chooseSelect('Strategy OS instrument', address('f'))
    fireEvent.click(screen.getByRole('button', { name: 'Import dataset' }))
    await waitFor(() => expect(api.import).toHaveBeenCalledTimes(1))
    const [, submitted, datasetId, importId] = api.import.mock.calls[0]
    expect(submitted).toMatchObject({
      dataset_name: 'desk', timezone: 'Asia/Kolkata', interval_seconds: 900,
      timestamp_meaning: 'BAR_OPEN',
      series: { kind: 'INSTRUMENT', label: 'NIFTY 50 spot', instrument_address: address('f') },
    })
    expect(submitted.columns).toHaveLength(7)
    expect(datasetId).toBeNull()
    expect(importId).toMatch(/^[0-9a-f]{32}$/)
    expect(await screen.findByText('The file has missing intervals.')).toBeInTheDocument()
  })

  it('reuses the import id after an ambiguous failure and preserves dataset id for a new version', async () => {
    const api = client([item])
    api.import.mockRejectedValueOnce(new Error('ambiguous network failure')).mockResolvedValueOnce({
      analysis: { state: 'VALID', row_count: 60, column_count: 7, quality_score: 100, issues: [], backtest_compatible: true },
      item,
    })
    api.list.mockResolvedValue({ items: [item], next_cursor: null })
    render(<DataLibraryWorkspace client={api} instruments={[{ address: address('f'), label: 'NIFTY 50 · NSE' }]} />)
    await screen.findByText(item.dataset_name)
    fireEvent.click(screen.getByRole('button', { name: 'Import new version' }))
    const file = new File(['csv'], 'next.csv', { type: 'text/csv' })
    fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [file] } })
    await screen.findByRole('group', { name: 'Column mapping' })
    fireEvent.click(screen.getByRole('button', { name: 'Import dataset' }))
    await screen.findByText('The import could not be completed. Check the mapping and try again.')
    fireEvent.click(screen.getByRole('button', { name: 'Import dataset' }))
    await waitFor(() => expect(api.import).toHaveBeenCalledTimes(2))
    expect(api.import.mock.calls[0][2]).toBe(item.dataset_id)
    expect(api.import.mock.calls[1][2]).toBe(item.dataset_id)
    expect(api.import.mock.calls[1][3]).toBe(api.import.mock.calls[0][3])
  })

  it('loads later version pages through the opaque cursor', async () => {
    const older = { ...item, manifest_address: address('e'), import_id: '2'.repeat(32), version_number: 1 }
    const api = client()
    api.list.mockResolvedValueOnce({ items: [item], next_cursor: item.manifest_address })
      .mockResolvedValueOnce({ items: [older], next_cursor: null })
    render(<DataLibraryWorkspace client={api} />)
    await screen.findByText(item.dataset_name)
    fireEvent.click(screen.getByRole('button', { name: 'Load more versions' }))
    await waitFor(() => expect(api.list).toHaveBeenLastCalledWith(item.manifest_address, expect.any(AbortSignal)))
    expect(screen.getByText(/Version 1/)).toBeInTheDocument()
  })

  it('does not own fetch, storage, credentials, providers or execution controls', () => {
    const source = readFileSync('src/features/data/DataLibraryWorkspace.tsx', 'utf8')
    for (const forbidden of ['fetch(', 'localStorage', 'sessionStorage', 'credential', 'broker', 'execution/arm']) {
      expect(source).not.toContain(forbidden)
    }
  })

  it('keeps focus, reduced motion and narrow reflow in the feature stylesheet', () => {
    const css = readFileSync('src/features/data/data-library.css', 'utf8')
    expect(css).toContain(':focus-visible')
    expect(css).toContain('@media (prefers-reduced-motion: reduce)')
    expect(css).toContain('@media (max-width: 600px)')
    expect(css).toContain('overflow: auto')
  })
})

const dailyInspection = {
  schema: 'strategy-os-user-csv-inspection/1' as const, source_type: 'USER_SUPPLIED' as const,
  source_sha256: 'd'.repeat(64), byte_count: 120, row_count: 2,
  source_order: 'DESCENDING' as const, fields: ['OPEN', 'HIGH', 'LOW', 'CLOSE'], interval: 'day' as const,
  event_start: '2026-09-03T00:00:00+05:30', event_end: '2026-09-05T00:00:00+05:30',
  historical_source_availability: 'NOT_SUPPLIED' as const, calendar_coverage: 'NOT_ASSERTED' as const,
  rights_scope: 'PERSONAL_RESEARCH_ONLY' as const,
}

function dailyApi(inspect = vi.fn().mockResolvedValue(dailyInspection)) {
  return { inspectDailyCsv: inspect, importDailyCsv: vi.fn().mockResolvedValue({
    ...dailyInspection, schema: 'strategy-os-user-csv-import/1', project_id: 'project.a',
    manifest_address: address('a'), instrument_address: address('b'),
    imported_at: '2026-09-05T00:00:00Z', ready_as_of: '2026-09-04T18:30:00Z',
  }) } as unknown as StrategyApi
}

describe('daily CSV inspect-before-import flow', () => {
  it('uses explicit NIFTY mapping without inventing volume, then refreshes after import', async () => {
    const api = dailyApi(); const onImported = vi.fn()
    render(<DailyCsvImport api={api} projectId="project.a" onImported={onImported} />)
    expect(screen.getByLabelText('Volume column · optional')).toHaveValue('')
    expect(screen.getByText(/Benchmark only/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Import inspected CSV' })).not.toBeInTheDocument()
    const file = new File(['Index Name,Date,Open,High,Low,Close\n'], 'nifty.csv', { type: 'text/csv' })
    fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Inspect CSV' }))
    await waitFor(() => expect(api.inspectDailyCsv).toHaveBeenCalled())
    expect(vi.mocked(api.inspectDailyCsv).mock.calls[0][2].columns.volume).toBeNull()
    const dates = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeZone: 'Asia/Kolkata' })
    expect(await screen.findByText(`${dates.format(new Date('2026-09-03T00:00:00+05:30'))} to ${dates.format(new Date('2026-09-04T00:00:00+05:30'))}`)).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Inspection passed' })).toBeInTheDocument()
    expect(screen.getByText('Volume is not present. The dataset will keep that field absent.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Import inspected CSV' }))
    await waitFor(() => expect(api.importDailyCsv).toHaveBeenCalledWith(
      'project.a', file, expect.any(Object), expect.any(AbortSignal), undefined,
    ))
    expect(onImported).toHaveBeenCalledOnce()
  })

  it('aborts and ignores a stale inspection when the mapping changes', async () => {
    let resolve!: (value: typeof dailyInspection) => void
    const pending = new Promise<typeof dailyInspection>((done) => { resolve = done })
    const inspect = vi.fn().mockReturnValue(pending); const api = dailyApi(inspect)
    render(<DailyCsvImport api={api} projectId="project.a" onImported={vi.fn()} />)
    const file = new File(['csv'], 'nifty.csv', { type: 'text/csv' })
    fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Inspect CSV' }))
    await waitFor(() => expect(inspect).toHaveBeenCalled())
    const signal = inspect.mock.calls[0][3] as AbortSignal
    fireEvent.change(screen.getByLabelText('Instrument name'), { target: { value: 'NIFTY 500' } })
    expect(signal.aborted).toBe(true)
    await act(async () => resolve(dailyInspection))
    expect(screen.queryByRole('heading', { name: 'Inspection passed' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Instrument name')).toHaveValue('NIFTY 500')
  })

  it('aborts inspection when the import component unmounts', async () => {
    const inspect = vi.fn().mockReturnValue(new Promise(() => {})); const api = dailyApi(inspect)
    const view = render(<DailyCsvImport api={api} projectId="project.a" onImported={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('CSV file'), {
      target: { files: [new File(['csv'], 'nifty.csv', { type: 'text/csv' })] },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Inspect CSV' }))
    await waitFor(() => expect(inspect).toHaveBeenCalled())
    const signal = inspect.mock.calls[0][3] as AbortSignal
    view.unmount()
    expect(signal.aborted).toBe(true)
  })

  it('aborts and ignores an inspection when importing becomes disabled', async () => {
    let resolve!: (value: typeof dailyInspection) => void
    const inspect = vi.fn().mockReturnValue(new Promise<typeof dailyInspection>((done) => { resolve = done }))
    const api = dailyApi(inspect); const onImported = vi.fn()
    const view = render(<DailyCsvImport api={api} projectId="project.a" onImported={onImported} />)
    fireEvent.change(screen.getByLabelText('CSV file'), {
      target: { files: [new File(['csv'], 'nifty.csv', { type: 'text/csv' })] },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Inspect CSV' }))
    await waitFor(() => expect(inspect).toHaveBeenCalledOnce())
    view.rerender(<DailyCsvImport api={api} projectId="project.a" onImported={onImported} disabled />)
    expect(inspect.mock.calls[0][3].aborted).toBe(true)
    await act(async () => resolve(dailyInspection))
    expect(screen.queryByRole('heading', { name: 'Inspection passed' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Inspect CSV' })).toBeDisabled()
    for (const label of ['Venue', 'Asset class', 'Date format']) expect(screen.getByRole('combobox', { name: label })).toBeDisabled()
    expect(onImported).not.toHaveBeenCalled()
  })

  it('preserves the selected file and mapping after a typed inspection error', async () => {
    const api = dailyApi(vi.fn().mockRejectedValue(new ApiError('input', 'Check the named columns.')))
    render(<DailyCsvImport api={api} projectId="project.a" onImported={vi.fn()} />)
    const file = new File(['bad'], 'nifty.csv', { type: 'text/csv' })
    fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [file] } })
    fireEvent.change(screen.getByLabelText('Date column'), { target: { value: 'Trading Date' } })
    fireEvent.click(screen.getByRole('button', { name: 'Inspect CSV' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Check the named columns.')
    expect(screen.getByLabelText('Date column')).toHaveValue('Trading Date')
    expect((screen.getByLabelText('CSV file') as HTMLInputElement).files?.[0]).toBe(file)
  })
})


describe('daily CSV import receipt validation', () => {
  it.each([
    ['project_id', 'project.other'], ['manifest_address', 'invalid'],
    ['instrument_address', null], ['imported_at', 123], ['imported_at', 'invalid'],
    ['ready_as_of', null], ['ready_as_of', 'invalid'],
  ])('rejects invalid %s before exposing an imported dataset', (field, value) => {
    const receipt = { ...dailyInspection, schema: 'strategy-os-user-csv-import/1',
      project_id: 'project.a', manifest_address: address('a'), instrument_address: address('b'),
      imported_at: '2026-09-05T00:00:00Z', ready_as_of: '2026-09-04T18:30:00Z' }
    expect(parseDailyCsvImport(receipt, 'project.a')).toEqual(receipt)
    expect(() => parseDailyCsvImport({ ...receipt, [field]: value }, 'project.a')).toThrow()
  })
})

const sessionInspection = {
  ...dailyInspection, schema: 'strategy-os-user-csv-inspection/2' as const,
  session_metadata: { state: 'USER_DECLARED_COMPLETE' as const, schema: 'user-declared-daily-sessions/1' as const,
    source: 'Synthetic short sessions', row_count: 2, source_sha256: 'e'.repeat(64), byte_count: 200 },
}
const sessionImport = { ...sessionInspection, schema: 'strategy-os-user-csv-import/2' as const,
  project_id: 'project.a', manifest_address: address('a'), instrument_address: address('b'),
  imported_at: '2026-09-05T00:00:00Z', ready_as_of: '2026-09-05T00:00:01Z' }

describe('explicit daily session files', () => {
  it('checks the versioned declaration and binds the imported receipt to both inspected files', () => {
    const inspection = parseDailyCsvInspection(sessionInspection)
    const imported = parseDailyCsvImport(sessionImport, 'project.a')
    expect(inspection.calendar_coverage).toBe('NOT_ASSERTED')
    expect(inspection.historical_source_availability).toBe('NOT_SUPPLIED')
    expect(() => requireMatchingCsvImport(inspection, imported)).not.toThrow()
    for (const changed of [{ source_sha256: 'f'.repeat(64) }, { byte_count: 121 },
      { session_metadata: { ...imported.session_metadata!, source_sha256: 'f'.repeat(64) } },
      { session_metadata: undefined }]) {
      expect(() => requireMatchingCsvImport(inspection, { ...imported, ...changed })).toThrow()
    }
  })

  it.each([
    { state: 'OFFICIAL' }, { schema: 'unknown' }, { row_count: 1 }, { source: '' },
    { source: 'x'.repeat(2049) }, { source_sha256: 'invalid' }, { byte_count: 0 },
    { byte_count: 1024 * 1024 + 1 }, { unexpected: true },
  ])('refuses forged session declarations %j', (change) => {
    expect(() => parseDailyCsvInspection({ ...sessionInspection,
      session_metadata: { ...sessionInspection.session_metadata, ...change } })).toThrow()
  })

  it('refuses missing declarations and undeclared extensions on legacy responses', () => {
    expect(() => parseDailyCsvInspection({ ...sessionInspection, session_metadata: undefined })).toThrow()
    expect(() => parseDailyCsvInspection({ ...sessionInspection, schema: dailyInspection.schema })).toThrow()
    expect(() => parseDailyCsvInspection({ ...sessionInspection, schema: 'strategy-os-user-csv-inspection/3' })).toThrow()
  })

  it('passes both files through inspection and import, then invalidates inspection when either changes', async () => {
    const api = dailyApi(vi.fn().mockResolvedValue(sessionInspection))
    vi.mocked(api.importDailyCsv).mockResolvedValue(sessionImport)
    const onImported = vi.fn()
    render(<DailyCsvImport api={api} projectId="project.a" onImported={onImported} />)
    const csv = new File(['csv'], 'daily.csv'), sessions = new File(['{}'], 'sessions.json')
    fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [csv] } })
    fireEvent.change(screen.getByLabelText('Session metadata file · optional'), { target: { files: [sessions] } })
    fireEvent.click(screen.getByRole('button', { name: 'Inspect CSV' }))
    expect(await screen.findByText(/Declared complete sessions: 2/)).toHaveTextContent('Synthetic short sessions')
    expect(api.inspectDailyCsv).toHaveBeenCalledWith('project.a', csv, expect.any(Object), expect.any(AbortSignal), sessions)
    fireEvent.click(screen.getByRole('button', { name: 'Import inspected CSV' }))
    await waitFor(() => expect(onImported).toHaveBeenCalledOnce())
    expect(api.importDailyCsv).toHaveBeenCalledWith('project.a', csv, expect.any(Object), expect.any(AbortSignal), sessions)
    fireEvent.change(screen.getByLabelText('Session metadata file · optional'), { target: { files: [] } })
    expect(screen.queryByRole('heading', { name: 'Inspection passed' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Inspect CSV' })).toBeEnabled()
  })

  it('keeps files selected and refuses a mismatched imported session receipt', async () => {
    const api = dailyApi(vi.fn().mockResolvedValue(sessionInspection)); const onImported = vi.fn()
    vi.mocked(api.importDailyCsv).mockResolvedValue({ ...sessionImport,
      session_metadata: { ...sessionImport.session_metadata, source_sha256: 'f'.repeat(64) } })
    render(<DailyCsvImport api={api} projectId="project.a" onImported={onImported} />)
    const sessions = new File(['{}'], 'sessions.json')
    fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [new File(['csv'], 'daily.csv')] } })
    fireEvent.change(screen.getByLabelText('Session metadata file · optional'), { target: { files: [sessions] } })
    fireEvent.click(screen.getByRole('button', { name: 'Inspect CSV' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Import inspected CSV' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('The import could not be confirmed.')
    expect(onImported).not.toHaveBeenCalled()
    expect((screen.getByLabelText('Session metadata file · optional') as HTMLInputElement).files?.[0]).toBe(sessions)
  })
})

it.each([false, true])('refuses a session inspection that disagrees with selected files (%s)', async (selected) => {
  const api = dailyApi(vi.fn().mockResolvedValue(selected ? dailyInspection : sessionInspection))
  render(<DailyCsvImport api={api} projectId="project.a" onImported={vi.fn()} />)
  fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [new File(['csv'], 'daily.csv')] } })
  if (selected) fireEvent.change(screen.getByLabelText('Session metadata file · optional'), { target: { files: [new File(['{}'], 'sessions.json')] } })
  fireEvent.click(screen.getByRole('button', { name: 'Inspect CSV' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('response could not be verified')
  expect(screen.queryByRole('button', { name: 'Import inspected CSV' })).not.toBeInTheDocument()
})

it.each([
  [1024 * 1024 + 1, 'Choose session metadata no larger than 1 MiB.'],
  [1024 * 1024, 'Keep the two files together within 1 MiB'],
])('refuses oversized session files before uploading (%s bytes)', async (size, expected) => {
  const api = dailyApi()
  render(<DailyCsvImport api={api} projectId="project.a" onImported={vi.fn()} />)
  fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [new File(['csv'], 'daily.csv')] } })
  fireEvent.change(screen.getByLabelText('Session metadata file · optional'), {
    target: { files: [new File([new Uint8Array(size)], 'sessions.json')] },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Inspect CSV' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(expected)
  expect(api.inspectDailyCsv).not.toHaveBeenCalled()
})

it.each([
  ['CSV_SESSION_METADATA_REFUSED', 'include every CSV date once'],
  ['CSV_SESSION_METADATA_RETRY_MISMATCH', 'Import both files together on the first import, or use a separate project.'],
  ['CSV_SESSION_METADATA_SIZE_INVALID', 'Choose session metadata no larger than 1 MiB.'],
])('explains the safe next action for %s without reflecting private server text', async (code, expected) => {
  const api = dailyApi(vi.fn().mockRejectedValue(new ApiError('input', 'Check the named columns.', {
    code, message: 'private server details',
  })))
  render(<DailyCsvImport api={api} projectId="project.a" onImported={vi.fn()} />)
  fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [new File(['csv'], 'daily.csv')] } })
  fireEvent.change(screen.getByLabelText('Session metadata file · optional'), { target: { files: [new File(['{}'], 'sessions.json')] } })
  fireEvent.click(screen.getByRole('button', { name: 'Inspect CSV' }))
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent(expected)
  expect(alert).not.toHaveTextContent('private server details')
})

it.each([
  ['access', 'Workspace membership changed.'],
  ['timeout', 'The server did not respond in time. Inspect the file again.'],
  ['network', 'The server could not be reached. Keep this file selected and try again.'],
  ['server', 'The CSV response could not be verified. Inspect the file again.'],
] as const)('retains files with useful %s recovery guidance', async (kind, expected) => {
  const api = dailyApi(vi.fn().mockRejectedValue(new ApiError(kind, 'Workspace membership changed.')))
  render(<DailyCsvImport api={api} projectId="project.a" onImported={vi.fn()} />)
  const file = new File(['csv'], 'daily.csv')
  fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [file] } })
  fireEvent.click(screen.getByRole('button', { name: 'Inspect CSV' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(expected)
  expect((screen.getByLabelText('CSV file') as HTMLInputElement).files?.[0]).toBe(file)
})

it.each(['timeout', 'network', 'server', 'unverified'] as const)('keeps an uncertain %s import separate from inspection failure', async (kind) => {
  const api = dailyApi()
  const onImported = vi.fn()
  vi.mocked(api.importDailyCsv).mockRejectedValue(kind === 'unverified' ? new Error('untrusted response') : new ApiError(kind, 'private server details'))
  render(<DailyCsvImport api={api} projectId="project.a" onImported={onImported} />)
  const file = new File(['csv'], 'daily.csv')
  fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [file] } })
  fireEvent.click(screen.getByRole('button', { name: 'Inspect CSV' }))
  await screen.findByRole('heading', { name: 'Inspection passed' })
  fireEvent.click(screen.getByRole('button', { name: 'Import inspected CSV' }))
  const alert = await screen.findByRole('alert')
  expect(alert).toHaveTextContent('The import could not be confirmed. Refresh records to check whether it finished before retrying with the same files.')
  expect(alert).not.toHaveTextContent('Inspect the file again')
  expect(alert).not.toHaveTextContent('private server details')
  expect((screen.getByLabelText('CSV file') as HTMLInputElement).files?.[0]).toBe(file)
  expect(onImported).not.toHaveBeenCalled()
  expect(screen.getByRole('button', { name: 'Import inspected CSV' })).toBeEnabled()
})


it('keeps both CSV files and sends selected menu values after requiring a new inspection', async () => {
  const api = dailyApi(vi.fn().mockResolvedValue(sessionInspection))
  render(<DailyCsvImport api={api} projectId="project.a" onImported={vi.fn()} />)
  const csv = new File(['csv'], 'daily.csv'), sessions = new File(['{}'], 'sessions.json')
  fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [csv] } })
  fireEvent.change(screen.getByLabelText('Session metadata file · optional'), { target: { files: [sessions] } })
  fireEvent.click(screen.getByRole('button', { name: 'Inspect CSV' }))
  await screen.findByRole('heading', { name: 'Inspection passed' })
  await chooseSelect('Venue', 'XBOM')
  expect(screen.queryByRole('heading', { name: 'Inspection passed' })).not.toBeInTheDocument()
  await chooseSelect('Asset class', 'EQUITY')
  await chooseSelect('Date format', '%Y-%m-%d')
  expect(screen.getByRole('combobox', { name: 'Venue' })).toHaveTextContent('BSE (XBOM)')
  expect(screen.getByRole('combobox', { name: 'Asset class' })).toHaveTextContent('Equity')
  expect(screen.getByRole('combobox', { name: 'Date format' })).toHaveTextContent('2026-09-04')
  expect(screen.queryByText(/Benchmark only/)).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Inspect CSV' }))
  await waitFor(() => expect(api.inspectDailyCsv).toHaveBeenCalledTimes(2))
  expect(api.inspectDailyCsv).toHaveBeenLastCalledWith('project.a', csv,
    expect.objectContaining({ venue_code: 'XBOM', asset_class: 'EQUITY', date_format: '%Y-%m-%d' }),
    expect.any(AbortSignal), sessions)
})


it('sends custom-series, time and column choices from the real mapping menus', async () => {
  const api = client(); api.import.mockRejectedValue(new Error('Synthetic rejection'))
  render(<DataLibraryWorkspace client={api} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Import CSV' }))
  fireEvent.change(screen.getByLabelText('CSV file'), { target: { files: [new File(['csv'], 'desk.csv')] } })
  await screen.findByRole('group', { name: 'Column mapping' })
  await chooseSelect('Series type', 'LOGICAL_SERIES')
  fireEvent.change(screen.getByLabelText('Series key'), { target: { value: 'breadth.composite' } })
  fireEvent.change(screen.getByLabelText('Series or instrument name'), { target: { value: 'Market breadth' } })
  await chooseSelect('Interval', '3600')
  await chooseSelect('Timestamp marks', 'BAR_CLOSE')
  await chooseSelect('sentiment role', 'IGNORE')
  expect(screen.queryByLabelText('sentiment research name')).not.toBeInTheDocument()
  await chooseSelect('sentiment role', 'FEATURE')
  await chooseSelect('sentiment type', 'TEXT')
  fireEvent.click(screen.getByRole('button', { name: 'Import dataset' }))
  await waitFor(() => expect(api.import).toHaveBeenCalledOnce())
  const submitted = api.import.mock.calls[0][1]
  expect(submitted).toMatchObject({ interval_seconds: 3600, timestamp_meaning: 'BAR_CLOSE',
    series: { kind: 'LOGICAL_SERIES', label: 'Market breadth', instrument_address: null, logical_series_id: 'breadth.composite' } })
  expect(submitted.columns.find((column) => column.source === 'sentiment')).toEqual({
    source: 'sentiment', role: 'FEATURE', target_name: 'sentiment', data_type: 'TEXT' })
})
