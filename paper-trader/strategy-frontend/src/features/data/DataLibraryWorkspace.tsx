import { TraderSelect } from '../../components/TraderSelect'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { AlertTriangle, CircleCheck, Database, FileSpreadsheet, Table2, Upload } from 'lucide-react'
import type {
  ColumnDataType,
  ColumnMapping,
  ColumnRole,
  CsvImportMapping,
  CsvInspection,
  DataLibraryClient,
  DataLibraryItem,
  DataLibraryPreview,
  ImportOutcome,
  InstrumentChoice,
  SeriesKind,
  TimestampMeaning,
} from './dataLibraryContracts'
import { DATA_LIBRARY_UPLOAD_LIMIT_BYTES } from './dataLibraryContracts'
import './data-library.css'

type Load<T> = { kind: 'loading' } | { kind: 'error' } | { kind: 'ready'; value: T }

const ROLE_OPTIONS: readonly ColumnRole[] = [
  'TIMESTAMP', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'VOLUME', 'FEATURE', 'IGNORE',
]
const TYPE_OPTIONS: readonly ColumnDataType[] = ['NUMBER', 'BOOLEAN', 'TEXT']

function intervalLabel(seconds: number) {
  if (seconds % 86_400 === 0) return `${seconds / 86_400} day${seconds === 86_400 ? '' : 's'}`
  if (seconds % 3_600 === 0) return `${seconds / 3_600} hour${seconds === 3_600 ? '' : 's'}`
  if (seconds % 60 === 0) return `${seconds / 60} min`
  return `${seconds} sec`
}

function formatDate(value: string) {
  const date = new Date(value)
  return Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
    : 'Unknown'
}

function qualityLabel(item: DataLibraryItem) {
  return item.quality_state === 'VALID' ? 'Valid' : 'Valid with warnings'
}

function resultLabel(result: ImportOutcome) {
  if (result.analysis.state === 'VALID') return 'Valid'
  if (result.analysis.state === 'VALID_WITH_WARNINGS') return 'Valid with warnings'
  return 'Invalid'
}

function DatasetStatus({ item }: { readonly item: DataLibraryItem }) {
  return (
    <span className={`data-status data-status--${item.quality_state.toLowerCase()}`}>
      {item.quality_state === 'VALID' ? <CircleCheck aria-hidden="true" /> : <AlertTriangle aria-hidden="true" />}
      {qualityLabel(item)}
    </span>
  )
}

interface Props {
  readonly client: DataLibraryClient
  readonly instruments?: readonly InstrumentChoice[]
}

export function DataLibraryWorkspace({ client, instruments = [] }: Props) {
  const [datasets, setDatasets] = useState<Load<readonly DataLibraryItem[]>>({ kind: 'loading' })
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const [loadMoreError, setLoadMoreError] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const [preview, setPreview] = useState<Load<DataLibraryPreview> | null>(null)
  const [showImport, setShowImport] = useState(false)
  const [versionDatasetId, setVersionDatasetId] = useState<string | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [inspection, setInspection] = useState<Load<CsvInspection> | null>(null)
  const [columns, setColumns] = useState<readonly ColumnMapping[]>([])
  const [datasetName, setDatasetName] = useState('')
  const [seriesKind, setSeriesKind] = useState<SeriesKind>('INSTRUMENT')
  const [instrumentAddress, setInstrumentAddress] = useState('')
  const [seriesLabel, setSeriesLabel] = useState('')
  const [logicalSeriesId, setLogicalSeriesId] = useState('')
  const [timezone, setTimezone] = useState('Asia/Kolkata')
  const [intervalSeconds, setIntervalSeconds] = useState(900)
  const [timestampMeaning, setTimestampMeaning] = useState<TimestampMeaning>('BAR_OPEN')
  const [submitting, setSubmitting] = useState(false)
  const [result, setResult] = useState<ImportOutcome | null>(null)
  const [formErrors, setFormErrors] = useState<Readonly<Record<string, string>>>({})
  const errorSummary = useRef<HTMLDivElement>(null)
  const importAttempt = useRef<{ fingerprint: string; importId: string } | null>(null)

  const load = () => {
    const controller = new AbortController()
    setDatasets({ kind: 'loading' })
    client.list(null, controller.signal).then((page) => {
      setDatasets({ kind: 'ready', value: page.items }); setNextCursor(page.next_cursor)
      setSelected((current) => current && page.items.some((item) => item.manifest_address === current)
        ? current : page.items[0]?.manifest_address ?? null)
    }).catch((error: unknown) => {
      if (!(error instanceof DOMException && error.name === 'AbortError')) setDatasets({ kind: 'error' })
    })
    return controller
  }

  async function loadMore() {
    if (!nextCursor || datasets.kind !== 'ready') return
    const controller = new AbortController(); setLoadingMore(true); setLoadMoreError(false)
    try {
      const page = await client.list(nextCursor, controller.signal)
      setDatasets({ kind: 'ready', value: [...datasets.value, ...page.items] })
      setNextCursor(page.next_cursor)
    } catch {
      setLoadMoreError(true)
    } finally {
      setLoadingMore(false)
    }
  }

  useEffect(() => {
    const controller = load()
    return () => controller.abort()
    // The client instance is the request authority for this mounted workspace.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client])

  useEffect(() => {
    if (!selected) { setPreview(null); return }
    const controller = new AbortController()
    setPreview({ kind: 'loading' })
    client.preview(selected, controller.signal).then((value) => {
      setPreview({ kind: 'ready', value })
    }).catch((error: unknown) => {
      if (!(error instanceof DOMException && error.name === 'AbortError')) setPreview({ kind: 'error' })
    })
    return () => controller.abort()
  }, [client, selected])

  useEffect(() => {
    if (Object.keys(formErrors).length || result?.analysis.state === 'INVALID') errorSummary.current?.focus()
  }, [formErrors, result])

  const selectedItem = useMemo(() => datasets.kind === 'ready'
    ? datasets.value.find((item) => item.manifest_address === selected) : undefined, [datasets, selected])

  async function inspect(next: File | null) {
    setFile(next); setInspection(null); setColumns([]); setResult(null); setFormErrors({})
    importAttempt.current = null
    if (!next) return
    if (next.size > DATA_LIBRARY_UPLOAD_LIMIT_BYTES) {
      setFormErrors({ file: 'Choose a CSV no larger than 8 MiB.' })
      return
    }
    const controller = new AbortController()
    setInspection({ kind: 'loading' })
    try {
      const value = await client.inspect(next, controller.signal)
      setInspection({ kind: 'ready', value })
      setColumns(value.suggested_columns)
      if (!datasetName) setDatasetName(next.name.replace(/\.csv$/i, '').slice(0, 160))
    } catch {
      setInspection({ kind: 'error' })
    }
  }

  function updateColumn(index: number, patch: Partial<ColumnMapping>) {
    setColumns((current) => current.map((column, position) => position === index
      ? { ...column, ...patch } : column))
  }

  function validateForm() {
    const errors: Record<string, string> = {}
    if (!file) errors.file = 'Choose a CSV file.'
    if (!datasetName.trim()) errors.datasetName = 'Enter a dataset name.'
    if (!seriesLabel.trim()) errors.seriesLabel = 'Enter the series or instrument name.'
    if (seriesKind === 'INSTRUMENT' && !instrumentAddress) errors.instrument = 'Select an instrument.'
    if (seriesKind === 'LOGICAL_SERIES' && !/^[a-z][a-z0-9_.-]{0,127}$/.test(logicalSeriesId)) {
      errors.logicalSeries = 'Use a lowercase series key such as breadth.composite.'
    }
    if (columns.filter((column) => column.role === 'TIMESTAMP').length !== 1) {
      errors.columns = 'Map exactly one timestamp column.'
    }
    const mappedOhlc = new Set(columns.filter((column) => ['OPEN', 'HIGH', 'LOW', 'CLOSE'].includes(column.role)).map((column) => column.role))
    if (mappedOhlc.size !== 4) errors.columns = 'Map open, high, low and close together.'
    if (!columns.some((column) => column.role === 'VOLUME')) errors.columns = 'Map a volume column for this import slice.'
    const targets = columns.filter((column) => column.role === 'FEATURE').map((column) => column.target_name)
    if (targets.some((target) => !target || !/^[a-z][a-z0-9_]{0,63}$/.test(target))) {
      errors.columns = 'Give each feature a lowercase target name.'
    }
    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }

  async function submit(event: FormEvent) {
    event.preventDefault(); setResult(null)
    if (!validateForm() || !file) return
    const mapping: CsvImportMapping = {
      dataset_name: datasetName.trim(), timezone, interval_seconds: intervalSeconds,
      timestamp_meaning: timestampMeaning, timestamp_format: null,
      series: {
        kind: seriesKind, label: seriesLabel.trim(),
        instrument_address: seriesKind === 'INSTRUMENT' ? instrumentAddress : null,
        logical_series_id: seriesKind === 'LOGICAL_SERIES' ? logicalSeriesId : null,
      },
      columns,
    }
    const fingerprint = JSON.stringify({
      source: inspection?.kind === 'ready' ? inspection.value.source_content_address : null,
      mapping,
      datasetId: versionDatasetId,
    })
    if (importAttempt.current?.fingerprint !== fingerprint) {
      importAttempt.current = {
        fingerprint,
        importId: globalThis.crypto.randomUUID().replaceAll('-', ''),
      }
    }
    const controller = new AbortController(); setSubmitting(true)
    try {
      const outcome = await client.import(
        file, mapping, versionDatasetId, importAttempt.current.importId, controller.signal,
      )
      setResult(outcome)
      if (outcome.item) {
        load()
        setSelected(outcome.item.manifest_address)
      }
    } catch {
      setFormErrors({ submit: 'The import could not be completed. Check the mapping and try again.' })
    } finally {
      setSubmitting(false)
    }
  }

  function startNewImport() {
    setVersionDatasetId(null); setDatasetName(''); setSeriesLabel(''); setInstrumentAddress('')
    setLogicalSeriesId(''); setFile(null); setInspection(null); setColumns([]); setResult(null)
    setFormErrors({}); importAttempt.current = null; setShowImport(true)
  }

  function startNewVersion(item: DataLibraryItem) {
    setVersionDatasetId(item.dataset_id); setDatasetName(item.dataset_name)
    setSeriesKind(item.series_kind); setSeriesLabel(item.series_label)
    setInstrumentAddress(item.instrument_address ?? '')
    setLogicalSeriesId(item.logical_series_id ?? '')
    setTimezone(item.timezone); setIntervalSeconds(item.interval_seconds)
    setTimestampMeaning(item.timestamp_meaning); setFile(null); setInspection(null)
    setColumns([]); setResult(null); setFormErrors({}); importAttempt.current = null
    setShowImport(true)
  }

  function renderImportFields() {
    return (
      <div className="data-form-grid">
            <label>CSV file<input id="data-file" type="file" accept=".csv,text/csv" onChange={(event) => void inspect(event.target.files?.[0] ?? null)} aria-invalid={Boolean(formErrors.file)} aria-describedby={formErrors.file ? 'data-file-error' : 'data-file-help'} /></label>
            <p id="data-file-help" className="data-help">UTF-8, up to 8 MiB and 2,000 rows. The file stays inside Strategy OS.</p>
            {formErrors.file && <p id="data-file-error" className="data-field-error">{formErrors.file}</p>}
            <label>Dataset name<input id="data-datasetName" aria-label="Dataset name" value={datasetName} maxLength={160} onChange={(event) => setDatasetName(event.target.value)} aria-invalid={Boolean(formErrors.datasetName)} aria-describedby={formErrors.datasetName ? 'data-datasetName-error' : undefined} />{formErrors.datasetName && <span id="data-datasetName-error" className="data-field-error">{formErrors.datasetName}</span>}</label>
            <label>Series type<TraderSelect label="Series type" value={seriesKind} onValueChange={(value) => setSeriesKind(value as SeriesKind)} options={[{ value: 'INSTRUMENT', label: 'Instrument' }, { value: 'LOGICAL_SERIES', label: 'Custom series' }]} /></label>
            <label>Series or instrument name<input id="data-seriesLabel" aria-label="Series or instrument name" value={seriesLabel} maxLength={160} onChange={(event) => setSeriesLabel(event.target.value)} aria-invalid={Boolean(formErrors.seriesLabel)} aria-describedby={formErrors.seriesLabel ? 'data-seriesLabel-error' : undefined} placeholder="NIFTY 50 spot" />{formErrors.seriesLabel && <span id="data-seriesLabel-error" className="data-field-error">{formErrors.seriesLabel}</span>}</label>
            {seriesKind === 'INSTRUMENT' ? <label>Strategy OS instrument<TraderSelect id="data-instrument" label="Strategy OS instrument" value={instrumentAddress}
              onValueChange={setInstrumentAddress} invalid={Boolean(formErrors.instrument)}
              describedBy={formErrors.instrument ? 'data-instrument-error' : instruments.length === 0 ? 'data-instrument-help' : undefined}
              options={[{ value: '', label: 'Select an instrument' }, ...instruments.map((instrument) => ({ value: instrument.address, label: instrument.label }))]} />
              {instruments.length === 0 && <span id="data-instrument-help" className="data-optional">No instruments are available to choose right now.</span>}{formErrors.instrument && <span id="data-instrument-error" className="data-field-error">{formErrors.instrument}</span>}</label>
              : <label>Series key<input id="data-logicalSeries" aria-label="Series key" value={logicalSeriesId} onChange={(event) => setLogicalSeriesId(event.target.value)} aria-invalid={Boolean(formErrors.logicalSeries)} aria-describedby={formErrors.logicalSeries ? 'data-logicalSeries-error' : undefined} placeholder="breadth.composite" />{formErrors.logicalSeries && <span id="data-logicalSeries-error" className="data-field-error">{formErrors.logicalSeries}</span>}</label>}
            <label>Interval<TraderSelect label="Interval" value={String(intervalSeconds)} onValueChange={(value) => setIntervalSeconds(Number(value))} options={[{ value: '900', label: '15 minutes' }, { value: '1800', label: '30 minutes' }, { value: '3600', label: '1 hour' }]} /></label>
            <label>Timezone<input value={timezone} onChange={(event) => setTimezone(event.target.value)} placeholder="Asia/Kolkata" /></label>
            <label>Timestamp marks<TraderSelect label="Timestamp marks" value={timestampMeaning} onValueChange={(value) => setTimestampMeaning(value as TimestampMeaning)} options={[{ value: 'BAR_OPEN', label: 'Bar open' }, { value: 'BAR_CLOSE', label: 'Bar close' }]} /></label>
          </div>
    )
  }

  function renderColumnMapping() {
    return (
      <fieldset className="data-columns" id="data-columns">
            <legend>Column mapping</legend>
            <p>Confirm what each column means. Extra fields stay attached to this dataset version.</p>
            {formErrors.columns && <p className="data-field-error" role="alert">{formErrors.columns}</p>}
            <div className="data-column-list">
              {columns.map((column, index) => <div className="data-column-row" key={column.source}>
                <strong>{column.source}</strong>
                <label><span>Role</span><TraderSelect label={`${column.source} role`} value={column.role} onValueChange={(value) => {
                  const role = value as ColumnRole
                  updateColumn(index, { role, target_name: role === 'FEATURE' ? (column.target_name ?? column.source.toLowerCase().replace(/\W+/g, '_')) : null, data_type: role === 'FEATURE' ? (column.data_type ?? 'NUMBER') : null })
                }} options={ROLE_OPTIONS.map((role) => ({ value: role, label: role.toLowerCase().replace('_', ' ') }))} /></label>
                {column.role === 'FEATURE' ? <><label><span>Research name</span><input aria-label={`${column.source} research name`} value={column.target_name ?? ''} onChange={(event) => updateColumn(index, { target_name: event.target.value })} /></label><label><span>Type</span><TraderSelect label={`${column.source} type`} value={column.data_type ?? 'NUMBER'} onValueChange={(value) => updateColumn(index, { data_type: value as ColumnDataType })} options={TYPE_OPTIONS.map((type) => ({ value: type, label: type.toLowerCase() }))} /></label></> : <span className="data-fixed-target">{column.role === 'IGNORE' ? 'Not imported' : column.role === 'TIMESTAMP' ? 'Time axis' : column.role.toLowerCase()}</span>}
              </div>)}
            </div>
          </fieldset>
    )
  }

  function renderImportResult() {
    return <>
      {result && result.analysis.state !== 'INVALID' && <div className={`data-admission data-admission--${result.analysis.state.toLowerCase()}`} role="status"><CircleCheck aria-hidden="true" /><div><strong>{resultLabel(result)}</strong><span>{result.analysis.row_count.toLocaleString()} rows · {result.analysis.column_count} columns · quality {result.analysis.quality_score}/100</span></div></div>}
          {result?.analysis.issues.some((issue) => issue.severity === 'WARNING') && <ul className="data-warning-list">{result.analysis.issues.filter((issue) => issue.severity === 'WARNING').map((issue) => <li key={`${issue.code}-${issue.column}`}><AlertTriangle aria-hidden="true" />{issue.message}</li>)}</ul>}
    </>
  }

  function renderImport() {
    return (
      <section className="data-import" aria-labelledby="data-import-title">
        <div className="data-section-title"><div><p className="data-kicker">{versionDatasetId ? 'Add a version' : 'New dataset'}</p><h2 id="data-import-title">Map the file before import</h2></div><FileSpreadsheet aria-hidden="true" /></div>
        <form noValidate onSubmit={submit}>
          {(Object.keys(formErrors).length > 0 || result?.analysis.state === 'INVALID') && <div className="data-error-summary" role="alert" tabIndex={-1} ref={errorSummary}>
            <h3>Check the import</h3>
            <ul>
              {Object.entries(formErrors).map(([field, message]) => <li key={field}><a href={`#data-${field}`} onClick={(event) => { event.preventDefault(); document.getElementById(`data-${field}`)?.focus() }}>{message}</a></li>)}
              {result?.analysis.issues.filter((issue) => issue.severity === 'ERROR').map((issue) => <li key={`${issue.code}-${issue.column}`}>{issue.message}{issue.count > 1 ? ` (${issue.count} rows)` : ''}</li>)}
            </ul>
          </div>}
          {renderImportFields()}

          {inspection?.kind === 'loading' && <p role="status" className="data-feedback">Reading the file…</p>}
          {inspection?.kind === 'error' && <p role="alert" className="data-feedback data-feedback--error">The file could not be inspected. Save it as UTF-8 CSV and try again.</p>}
          {inspection?.kind === 'ready' && inspection.value.issues.some((issue) => issue.severity === 'ERROR') && <div role="alert" className="data-feedback data-feedback--error"><strong>The file needs attention.</strong>{inspection.value.issues.map((issue) => <span key={`${issue.code}-${issue.column}`}>{issue.message}</span>)}</div>}
          {inspection?.kind === 'ready' && renderColumnMapping()}

          {renderImportResult()}
          <div className="data-form-actions" id="data-submit"><button type="submit" className="data-primary" disabled={submitting || inspection?.kind !== 'ready'}>{submitting ? 'Importing…' : 'Import dataset'}</button><span>Imports are for research.</span></div>
        </form>
      </section>
    )
  }

  function renderLibrary() {
    return (
      <section className="data-library" aria-labelledby="data-library-title">
        <div className="data-section-title"><div><p className="data-kicker">Your imported data</p><h2 id="data-library-title">Datasets and versions</h2></div><Database aria-hidden="true" /></div>
        {datasets.kind === 'loading' && <p role="status" className="data-feedback">Loading datasets…</p>}
        {datasets.kind === 'error' && <div role="alert" className="data-feedback data-feedback--error"><p>Datasets could not be loaded.</p><button type="button" onClick={load}>Retry</button></div>}
        {datasets.kind === 'ready' && datasets.value.length === 0 && <div className="data-empty"><FileSpreadsheet aria-hidden="true" /><h3>No imported data yet</h3><p>Import a CSV to create the first saved dataset.</p><button type="button" onClick={startNewImport}>Import first CSV</button></div>}
        {datasets.kind === 'ready' && datasets.value.length > 0 && <><div className="data-ledger"><div className="data-ledger-head" aria-hidden="true"><span>Dataset</span><span>Range</span><span>Rows</span><span>Quality</span><span>Imported</span></div>{datasets.value.map((item) => <button type="button" key={item.manifest_address} className="data-ledger-row" aria-current={selected === item.manifest_address ? 'true' : undefined} onClick={() => setSelected(item.manifest_address)}><span className="data-dataset-name"><strong>{item.dataset_name}</strong><small>{item.series_label} · Version {item.version_number} · {intervalLabel(item.interval_seconds)} · {item.timezone}</small></span><span><small className="data-mobile-label">Range</small>{formatDate(item.event_start)}<br />to {formatDate(item.event_end)}</span><span><small className="data-mobile-label">Rows</small>{item.row_count.toLocaleString()}</span><span><small className="data-mobile-label">Quality</small><DatasetStatus item={item} /></span><span><small className="data-mobile-label">Imported</small>{formatDate(item.imported_at)}</span></button>)}</div>{nextCursor && <button type="button" className="data-load-more" onClick={() => void loadMore()} disabled={loadingMore}>{loadingMore ? 'Loading more…' : 'Load more versions'}</button>}{loadMoreError && <p role="alert" className="data-feedback data-feedback--error">More dataset versions could not be loaded. Try again.</p>}</>}
      </section>
    )
  }

  function renderPreview(item: DataLibraryItem) {
    return (
      <section className="data-preview" aria-labelledby="data-preview-title">
        <div className="data-section-title"><div><p className="data-kicker">Version {item.version_number}</p><h2 id="data-preview-title">{item.dataset_name} preview</h2></div><div className="data-preview-actions"><button type="button" onClick={() => startNewVersion(item)}>Import new version</button><Table2 aria-hidden="true" /></div></div>
        <dl className="data-facts"><div><dt>Series</dt><dd>{item.series_label}</dd></div><div><dt>Interval</dt><dd>{intervalLabel(item.interval_seconds)}</dd></div><div><dt>Timezone</dt><dd>{item.timezone}</dd></div><div><dt>Rows</dt><dd>{item.row_count.toLocaleString()}</dd></div><div><dt>Market truth</dt><dd>User supplied; market rules and corporate actions are not independently verified</dd></div><div><dt>Research use</dt><dd>{item.backtest_compatible ? 'Ready for the current backtest dataset selector' : 'This import can be previewed here, but cannot currently be selected for a backtest.'}</dd></div></dl>
        {preview?.kind === 'loading' && <p role="status" className="data-feedback">Loading the preview…</p>}
        {preview?.kind === 'error' && <p role="alert" className="data-feedback data-feedback--error">The preview could not be verified.</p>}
        {preview?.kind === 'ready' && <>
          <div className="data-role-rail" aria-label="Mapped column roles">{preview.value.columns.map((column) => <span key={`${column.source}-${column.target}`}><strong>{column.source}</strong><small>{column.role === 'FEATURE' ? `${column.target} · ${column.data_type?.toLowerCase()}` : column.role.toLowerCase()}</small></span>)}</div>
          <div className="data-table-scroll" tabIndex={0} aria-label="Scrollable dataset preview">
            <table><caption>{item.dataset_name}, version {item.version_number}. Showing {preview.value.rows.length} of {item.row_count.toLocaleString()} rows{preview.value.truncated ? '; preview is bounded' : ''}.</caption><thead><tr>{preview.value.columns.map((column) => <th scope="col" key={`${column.source}-${column.target}`}>{column.target ?? column.source}</th>)}</tr></thead><tbody>{preview.value.rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((value, columnIndex) => <td key={preview.value.columns[columnIndex]?.source}>{value === null ? <span className="data-missing">Missing</span> : String(value)}</td>)}</tr>)}</tbody></table>
          </div>
        </>}
      </section>
    )
  }

  return (
    <main className="data-workspace" aria-labelledby="data-title">
      <header className="data-heading">
        <div>
          <p className="slate-eyebrow">Research data</p>
          <h1 id="data-title">Data library</h1>
          <p>Import your own completed-bar history and keep every research run tied to the exact version it used.</p>
        </div>
        <button type="button" className="data-primary" onClick={() => showImport ? setShowImport(false) : startNewImport()} aria-expanded={showImport}>
          <Upload aria-hidden="true" /> {showImport ? 'Close import' : 'Import CSV'}
        </button>
      </header>

      {showImport && renderImport()}

      {renderLibrary()}

      {selectedItem && renderPreview(selectedItem)}
    </main>
  )
}
