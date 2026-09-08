import { TraderSelect } from '../../components/TraderSelect'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { FileCheck2, Upload } from 'lucide-react'
import { ApiError, type StrategyApi } from '../../shell/api'
import { dailyCsvFilesError, requireMatchingCsvImport, requireSessionInspection, type DailyCsvImport as ImportedCsv,
  type DailyCsvInspection, type DailyCsvMetadata } from './dailyCsvContracts'
import './data-library.css'

const DEFAULT_METADATA: DailyCsvMetadata = {
  instrument: 'NIFTY 50', source_label: 'NSE Indices historical export',
  venue_code: 'XNSE', asset_class: 'INDEX',
  columns: { instrument: 'Index Name', date: 'Date', open: 'Open', high: 'High', low: 'Low', close: 'Close', volume: null },
  date_format: '%d %b %Y', date_timezone: 'Asia/Kolkata', interval: 'day',
  contract_kind: 'SPOT', currency: 'INR',
}

const SESSION_ERRORS: Readonly<Record<string, string>> = {
  CSV_SESSION_METADATA_REFUSED: 'Check the session file: include every CSV date once, unique session IDs, timezone-aware opening and closing times, and the source of those times.',
  CSV_SESSION_METADATA_RETRY_MISMATCH: 'This CSV was already imported with different or absent session metadata. Import both files together on the first import, or use a separate project.',
  CSV_SESSION_METADATA_SIZE_INVALID: 'Choose session metadata no larger than 1 MiB. Keep the two files together within 1 MiB.',
}

function message(error: unknown, importing: boolean) {
  if (error instanceof ApiError) {
    if (error.kind === 'access') return error.message
    if (error.kind === 'input') return SESSION_ERRORS[error.envelope?.code ?? ''] ?? error.message
  }
  if (importing) return 'The import could not be confirmed. Refresh records to check whether it finished before retrying with the same files.'
  if (error instanceof ApiError) {
    if (error.kind === 'timeout') return 'The server did not respond in time. Inspect the file again.'
    if (error.kind === 'network') return 'The server could not be reached. Keep this file selected and try again.'
  }
  return 'The CSV response could not be verified. Inspect the file again.'
}

function date(value: string, exclusiveEnd = false) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeZone: 'Asia/Kolkata' }).format(new Date(Date.parse(value) - (exclusiveEnd ? 1 : 0)))
}

export function DailyCsvImport({ api, projectId, onImported, disabled = false }: {
  readonly api: StrategyApi
  readonly projectId: string
  readonly onImported: () => void
  readonly disabled?: boolean
}) {
  const [file, setFile] = useState<File | null>(null)
  const [sessionFile, setSessionFile] = useState<File | null>(null)
  const sessionMetadata = sessionFile ?? undefined
  const [metadata, setMetadata] = useState<DailyCsvMetadata>(DEFAULT_METADATA)
  const [inspection, setInspection] = useState<DailyCsvInspection | null>(null)
  const [imported, setImported] = useState<ImportedCsv | null>(null)
  const [pending, setPending] = useState<'inspect' | 'import' | null>(null)
  const [error, setError] = useState('')
  const controller = useRef<AbortController | null>(null)
  const generation = useRef(0)
  const mounted = useRef(true)
  const errorSummary = useRef<HTMLDivElement>(null)

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; generation.current += 1; controller.current?.abort() }
  }, [])

  useEffect(() => {
    if (disabled) {
      generation.current += 1; controller.current?.abort()
      queueMicrotask(() => { if (mounted.current) setPending(null) })
    }
  }, [disabled])

  useEffect(() => { if (error) errorSummary.current?.focus() }, [error])

  function invalidate() {
    generation.current += 1; controller.current?.abort(); setPending(null)
    setInspection(null); setImported(null); setError('')
  }

  function updateMetadata(next: DailyCsvMetadata) {
    invalidate(); setMetadata(next)
  }

  function updateColumn(name: keyof DailyCsvMetadata['columns'], value: string) {
    const optional = name === 'instrument' || name === 'volume'
    updateMetadata({ ...metadata, columns: { ...metadata.columns, [name]: value.trim() ? value : optional ? null : '' } })
  }

  function validate() {
    if (!file) return 'Choose a daily CSV file.'
    const filesError = dailyCsvFilesError(file, sessionMetadata)
    if (filesError) return filesError
    if (!metadata.instrument.trim()) return 'Enter the instrument name used in the file.'
    if (['date', 'open', 'high', 'low', 'close'].some((name) => !metadata.columns[name as keyof typeof metadata.columns])) {
      return 'Name the date, open, high, low and close columns.'
    }
    return ''
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const problem = validate()
    if (problem || !file) { setError(problem); return }
    void submit(file)
  }

  async function submit(file: File) {
    const owned = new AbortController(); controller.current?.abort(); controller.current = owned
    const ownedGeneration = ++generation.current
    const isCurrent = () => mounted.current && generation.current === ownedGeneration && !owned.signal.aborted
    setPending(inspection ? 'import' : 'inspect'); setError(''); setImported(null)
    try {
      if (!inspection) {
        const value = await api.inspectDailyCsv(projectId, file, metadata, owned.signal, sessionMetadata)
        requireSessionInspection(value, Boolean(sessionFile))
        if (isCurrent()) setInspection(value)
      } else {
        const value = await api.importDailyCsv(projectId, file, metadata, owned.signal, sessionMetadata)
        requireMatchingCsvImport(inspection, value)
        if (isCurrent()) {
          setImported(value); onImported()
        }
      }
    } catch (caught) {
      if (isCurrent()) setError(message(caught, inspection !== null))
    } finally {
      if (isCurrent()) setPending(null)
    }
  }

  const busy = pending !== null
  return <section className="data-import daily-csv" aria-labelledby="daily-csv-title">
    <div className="data-section-title"><div><p className="data-kicker">Personal research data</p><h2 id="daily-csv-title">Import daily OHLC data</h2></div><Upload aria-hidden="true" /></div>
    <p>Inspect the file and its explicit column mapping before adding it to this project.</p>
    {error && <div className="data-error-summary" role="alert" tabIndex={-1} ref={errorSummary}><h3>Check the CSV import</h3><p>{error}</p></div>}
    <form onSubmit={handleSubmit}>
      <div className="data-form-grid">
        <label>CSV file<input type="file" accept=".csv,text/csv" disabled={disabled} aria-describedby="daily-csv-file-help" onChange={(event) => { invalidate(); setFile(event.target.files?.[0] ?? null) }} /></label>
        <p id="daily-csv-file-help" className="data-help">Daily CSV, no more than 1 MiB or 2,000 data rows.</p>
        <label>Session metadata file · optional<input type="file" accept=".json,application/json" disabled={disabled} aria-describedby="daily-session-help" onChange={(event) => { invalidate(); setSessionFile(event.target.files?.[0] ?? null) }} /></label>
        <p id="daily-session-help" className="data-help">For strategies that need complete daily sessions, supply a JSON declaration with each date’s session ID, opening time, closing time and source. This is your declaration, not an official exchange calendar. Keep both files together within 1 MiB. Include both on the first import.</p>
        <label>Instrument name<input value={metadata.instrument} disabled={disabled} maxLength={128} onChange={(event) => updateMetadata({ ...metadata, instrument: event.target.value })} /></label>
        <label>Source label <span className="data-optional">Optional</span><input value={metadata.source_label ?? ''} disabled={disabled} maxLength={128} onChange={(event) => updateMetadata({ ...metadata, source_label: event.target.value || undefined })} /></label>
        <label>Venue<TraderSelect label="Venue" value={metadata.venue_code} disabled={disabled}
          onValueChange={(value) => updateMetadata({ ...metadata, venue_code: value as DailyCsvMetadata['venue_code'] })}
          options={[{ value: 'XNSE', label: 'NSE (XNSE)' }, { value: 'XBOM', label: 'BSE (XBOM)' }]} /></label>
        <label>Asset class<TraderSelect label="Asset class" value={metadata.asset_class} disabled={disabled}
          onValueChange={(value) => updateMetadata({ ...metadata, asset_class: value as DailyCsvMetadata['asset_class'] })}
          options={[{ value: 'INDEX', label: 'Index' }, { value: 'EQUITY', label: 'Equity' }]} /></label>
        <label>Date format<TraderSelect label="Date format" value={metadata.date_format} disabled={disabled}
          onValueChange={(value) => updateMetadata({ ...metadata, date_format: value as DailyCsvMetadata['date_format'] })}
          options={[{ value: '%d %b %Y', label: '04 Sep 2026' }, { value: '%Y-%m-%d', label: '2026-09-04' }]} /></label>
      </div>
      <details><summary>Session file format</summary><p>Use one row for every CSV date, oldest first, with unique IDs and timezone-aware times. Replace this synthetic example with your source’s actual sessions. Session close must be within the labelled date; sessions cannot overlap.</p><pre>{`{
  "schema": "user-declared-daily-sessions/1",
  "provenance": "USER_DECLARED",
  "source": "Synthetic example — replace with your source",
  "timezone": "Asia/Kolkata",
  "complete_full_sessions": true,
  "rows": [{
    "date_label": "2026-01-01",
    "session_id": "example-1",
    "session_open_at": "2026-01-01T04:00:00Z",
    "session_close_at": "2026-01-01T10:00:00Z"
  }]
}`}</pre></details>
      <fieldset className="daily-csv-columns"><legend>Column names</legend><p>Match these names exactly to the CSV header.</p><div className="data-form-grid">
        {(['instrument', 'date', 'open', 'high', 'low', 'close', 'volume'] as const).map((name) => <label key={name}>{name === 'instrument' ? 'Instrument column · optional' : name === 'volume' ? 'Volume column · optional' : `${name[0].toUpperCase()}${name.slice(1)} column`}<input value={metadata.columns[name] ?? ''} disabled={disabled} maxLength={128} onChange={(event) => updateColumn(name, event.target.value)} /></label>)}
      </div></fieldset>
      {metadata.asset_class === 'INDEX' && <p className="daily-csv-notice"><strong>Benchmark only.</strong> Index data can provide research context, but it cannot be traded directly.</p>}
      <p className="daily-csv-notice">Personal imported data is not certified for historical source availability or exchange-calendar coverage.</p>
      {inspection && <section className="daily-csv-inspection" aria-labelledby="daily-csv-inspection-title"><div><FileCheck2 aria-hidden="true" /><h3 id="daily-csv-inspection-title">Inspection passed</h3></div><dl><div><dt>Rows</dt><dd>{inspection.row_count.toLocaleString()}</dd></div><div><dt>Dates</dt><dd>{date(inspection.event_start)} to {date(inspection.event_end, true)}</dd></div><div><dt>Source order</dt><dd>{inspection.source_order === 'ASCENDING' ? 'Oldest first' : 'Newest first'}</dd></div><div><dt>Fields</dt><dd>{inspection.fields.join(', ')}</dd></div></dl>{!inspection.fields.includes('VOLUME') && <p>Volume is not present. The dataset will keep that field absent.</p>}</section>}
      {imported && <p className="daily-csv-success" role="status">Imported {imported.row_count.toLocaleString()} daily rows. The project data list is refreshing.</p>}
      {inspection?.session_metadata && <p role="status">Declared complete sessions: {inspection.session_metadata.row_count.toLocaleString()} · Source: {inspection.session_metadata.source}. Historical publication times remain unknown.</p>}
      <div className="data-form-actions"><button className="data-primary" disabled={disabled || busy || Boolean(imported)}>{pending === 'inspect' ? 'Inspecting…' : pending === 'import' ? 'Importing…' : inspection ? 'Import inspected CSV' : 'Inspect CSV'}</button>{inspection && !imported && <span>Inspection matches the current file and mapping.</span>}</div>
    </form>
  </section>
}
