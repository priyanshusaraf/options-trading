export const DATA_LIBRARY_UPLOAD_LIMIT_BYTES = 8 * 1024 * 1024

export type DataQualityState = 'VALID' | 'VALID_WITH_WARNINGS' | 'INVALID'
export type SeriesKind = 'INSTRUMENT' | 'LOGICAL_SERIES'
export type TimestampMeaning = 'BAR_OPEN' | 'BAR_CLOSE'
export type ColumnRole = 'TIMESTAMP' | 'OPEN' | 'HIGH' | 'LOW' | 'CLOSE' | 'VOLUME' | 'FEATURE' | 'IGNORE'
export type ColumnDataType = 'NUMBER' | 'BOOLEAN' | 'TEXT'

export interface DataLibraryIssue {
  readonly code: string
  readonly severity: 'ERROR' | 'WARNING'
  readonly message: string
  readonly count: number
  readonly first_row: number | null
  readonly column: string | null
}

export interface ColumnMapping {
  readonly source: string
  readonly role: ColumnRole
  readonly target_name: string | null
  readonly data_type: ColumnDataType | null
}

export interface CsvInspection {
  readonly source_content_address: string
  readonly columns: readonly string[]
  readonly suggested_columns: readonly ColumnMapping[]
  readonly rows: readonly (readonly string[])[]
  readonly row_count_seen: number
  readonly rows_truncated: boolean
  readonly columns_truncated: boolean
  readonly issues: readonly DataLibraryIssue[]
}

export interface CsvImportMapping {
  readonly dataset_name: string
  readonly timezone: string
  readonly interval_seconds: number
  readonly timestamp_meaning: TimestampMeaning
  readonly timestamp_format: string | null
  readonly series: Readonly<{
    kind: SeriesKind
    label: string
    instrument_address: string | null
    logical_series_id: string | null
  }>
  readonly columns: readonly ColumnMapping[]
}

export interface DataLibraryItem {
  readonly dataset_id: string
  readonly import_id: string
  readonly version_number: number
  readonly manifest_address: string
  readonly dataset_name: string
  readonly series_kind: SeriesKind
  readonly series_label: string
  readonly instrument_address: string | null
  readonly logical_series_id: string | null
  readonly interval_seconds: number
  readonly timezone: string
  readonly timestamp_meaning: TimestampMeaning
  readonly event_start: string
  readonly event_end: string
  readonly row_count: number
  readonly column_count: number
  readonly quality_state: Exclude<DataQualityState, 'INVALID'>
  readonly quality_score: number
  readonly imported_at: string
  readonly fields: readonly string[]
  readonly extra_columns: readonly Readonly<{
    source: string
    target: string
    data_type: ColumnDataType
  }>[]
  readonly warnings: readonly DataLibraryIssue[]
  readonly market_truth_state: 'USER_DECLARED_RECONSTRUCTED'
  readonly backtest_compatible: boolean
  readonly source_content_address: string
  readonly mapping_address: string
  readonly normalized_content_address: string
}

export interface CsvAnalysis {
  readonly state: DataQualityState
  readonly row_count: number
  readonly column_count: number
  readonly quality_score: number
  readonly issues: readonly DataLibraryIssue[]
  readonly backtest_compatible: boolean
}

export interface ImportOutcome {
  readonly analysis: CsvAnalysis
  readonly item: DataLibraryItem | null
}

export interface DataLibraryPreview {
  readonly item: DataLibraryItem
  readonly columns: readonly Readonly<{
    source: string
    role: ColumnRole
    target: string | null
    data_type: ColumnDataType | null
  }>[]
  readonly rows: readonly (readonly (string | boolean | null)[])[]
  readonly truncated: boolean
}

export interface DataLibraryPage {
  readonly items: readonly DataLibraryItem[]
  readonly next_cursor: string | null
}

export interface DataLibraryClient {
  list(after: string | null, signal: AbortSignal): Promise<DataLibraryPage>
  inspect(file: File, signal: AbortSignal): Promise<CsvInspection>
  import(
    file: File,
    mapping: CsvImportMapping,
    datasetId: string | null,
    importId: string,
    signal: AbortSignal,
  ): Promise<ImportOutcome>
  preview(manifestAddress: string, signal: AbortSignal): Promise<DataLibraryPreview>
}

export interface InstrumentChoice {
  readonly address: string
  readonly label: string
}
