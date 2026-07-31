/* DataGrid — §6.2
 *
 * "Virtualised, resizable, reorderable columns; sticky summary row; per-column
 *  type (mono numeric, text, chip, glyph); selection model with range select;
 *  group-by."
 *
 * §1.2 "Density is respect." Default row height is 28px and a 27" monitor
 * should show 40 rows without scrolling — so nothing here adds padding for
 * atmosphere.
 */

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useWindow } from './index'
import './grid.css'

export interface Column<T> {
  key: string
  label: string
  width: number
  type?: 'text' | 'num' | 'chip' | 'glyph'
  render: (row: T) => ReactNode
  /** Sort key; omit to make the column unsortable. */
  sortable?: boolean
  align?: 'left' | 'right' | 'center'
}

export interface GroupedRows<T> {
  key: string
  label: string
  rows: T[]
  summary?: ReactNode
}

interface Props<T> {
  rows: T[]
  columns: Column<T>[]
  rowKey: (row: T) => string
  rowHeight?: number
  /** Sticky summary row — recomputes for the current filter. §5.3 */
  summary?: ReactNode
  selection?: string[]
  cursorKey?: string | null
  onCursor?: (key: string) => void
  onOpen?: (row: T) => void
  onPeek?: (row: T) => void
  onToggleSelect?: (key: string, range?: boolean) => void
  groups?: GroupedRows<T>[] | null
  sort?: { key: string; dir: 'asc' | 'desc' }
  onSort?: (key: string) => void
  empty?: ReactNode
  /** Extra class for the row, used for the commit sweep animation. §7.6 */
  rowClass?: (row: T) => string
}

export function DataGrid<T>({
  rows,
  columns,
  rowKey,
  rowHeight = 28,
  summary,
  selection = [],
  cursorKey,
  onCursor,
  onOpen,
  onPeek,
  onToggleSelect,
  groups,
  sort,
  onSort,
  empty,
  rowClass,
}: Props<T>) {
  const viewportRef = useRef<HTMLDivElement>(null)
  const [scrollTop, setScrollTop] = useState(0)
  const [height, setHeight] = useState(600)
  const [widths, setWidths] = useState<Record<string, number>>(() =>
    Object.fromEntries(columns.map((c) => [c.key, c.width])),
  )
  const [order, setOrder] = useState<string[]>(() => columns.map((c) => c.key))
  const [dragKey, setDragKey] = useState<string | null>(null)

  // Columns can change between surfaces; keep width/order maps in sync without
  // discarding the user's adjustments for columns that persist.
  useEffect(() => {
    setWidths((prev) => {
      const next: Record<string, number> = {}
      for (const c of columns) next[c.key] = prev[c.key] ?? c.width
      return next
    })
    setOrder((prev) => {
      const known = prev.filter((k) => columns.some((c) => c.key === k))
      const added = columns.filter((c) => !known.includes(c.key)).map((c) => c.key)
      return [...known, ...added]
    })
  }, [columns])

  useLayoutEffect(() => {
    const el = viewportRef.current
    if (!el) return
    const ro = new ResizeObserver(() => setHeight(el.clientHeight))
    ro.observe(el)
    setHeight(el.clientHeight)
    return () => ro.disconnect()
  }, [])

  const ordered = order
    .map((k) => columns.find((c) => c.key === k))
    .filter((c): c is Column<T> => Boolean(c))

  // Grouping flattens into a single row list with header rows interleaved, so
  // virtualisation and keyboard movement stay uniform. §5.3
  type Line =
    | { kind: 'group'; group: GroupedRows<T> }
    | { kind: 'row'; row: T }

  const lines: Line[] = groups
    ? groups.flatMap((g) => [
        { kind: 'group' as const, group: g },
        ...g.rows.map((row) => ({ kind: 'row' as const, row })),
      ])
    : rows.map((row) => ({ kind: 'row' as const, row }))

  const win = useWindow(lines.length, rowHeight, height, scrollTop)
  const slice = lines.slice(win.first, win.last)

  // Keep the cursor row in view when it moves by keyboard.
  useEffect(() => {
    if (!cursorKey) return
    const idx = lines.findIndex(
      (l) => l.kind === 'row' && rowKey(l.row) === cursorKey,
    )
    if (idx < 0) return
    const el = viewportRef.current
    if (!el) return
    const top = idx * rowHeight
    if (top < el.scrollTop) el.scrollTop = top
    else if (top + rowHeight > el.scrollTop + el.clientHeight) {
      el.scrollTop = top - el.clientHeight + rowHeight
    }
  }, [cursorKey, lines, rowHeight, rowKey])

  const startResize = useCallback(
    (key: string, startX: number, startWidth: number) => {
      const move = (e: MouseEvent) => {
        setWidths((w) => ({
          ...w,
          [key]: Math.max(40, startWidth + e.clientX - startX),
        }))
      }
      const up = () => {
        window.removeEventListener('mousemove', move)
        window.removeEventListener('mouseup', up)
      }
      window.addEventListener('mousemove', move)
      window.addEventListener('mouseup', up)
    },
    [],
  )

  const template = ordered.map((c) => `${widths[c.key] ?? c.width}px`).join(' ')

  if (!lines.length && empty) {
    return (
      <div className="grid">
        <GridHeader
          columns={ordered}
          template={template}
          sort={sort}
          onSort={onSort}
          onResize={startResize}
          widths={widths}
          dragKey={dragKey}
          setDragKey={setDragKey}
          setOrder={setOrder}
        />
        {empty}
      </div>
    )
  }

  return (
    <div className="grid">
      <GridHeader
        columns={ordered}
        template={template}
        sort={sort}
        onSort={onSort}
        onResize={startResize}
        widths={widths}
        dragKey={dragKey}
        setDragKey={setDragKey}
        setOrder={setOrder}
      />

      <div
        className="grid__viewport scroll"
        ref={viewportRef}
        onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
      >
        <div style={{ height: win.padTop }} />
        {slice.map((line, i) => {
          if (line.kind === 'group') {
            return (
              <div
                className="grid__grouphead"
                key={`g_${line.group.key}`}
                style={{ height: rowHeight }}
              >
                <span className="label">{line.group.label}</span>
                <span className="grid__groupsummary">{line.group.summary}</span>
              </div>
            )
          }
          const key = rowKey(line.row)
          const selected = selection.includes(key)
          const isCursor = cursorKey === key
          return (
            <div
              key={key}
              className={`grid__row ${selected ? 'is-selected' : ''} ${
                isCursor ? 'is-cursor' : ''
              } ${rowClass?.(line.row) ?? ''}`}
              style={{ height: rowHeight, gridTemplateColumns: template }}
              // §7.6 Row selection is 0ms — instant, always.
              onMouseDown={() => onCursor?.(key)}
              onDoubleClick={() => onOpen?.(line.row)}
              onClick={(e) => {
                if (e.metaKey || e.ctrlKey) onToggleSelect?.(key)
                else if (e.shiftKey) onToggleSelect?.(key, true)
                else onPeek?.(line.row)
              }}
              data-index={win.first + i}
            >
              {ordered.map((c) => (
                <div
                  key={c.key}
                  className={`grid__cell grid__cell--${c.type ?? 'text'} ${
                    c.align ? `is-${c.align}` : ''
                  }`}
                >
                  {c.render(line.row)}
                </div>
              ))}
            </div>
          )
        })}
        <div style={{ height: win.padBottom }} />
      </div>

      {/* §5.3 The summary row recomputes for the current filter and always
          shows sample size and interval. */}
      {summary && <div className="grid__summary">{summary}</div>}
    </div>
  )
}

function GridHeader<T>({
  columns,
  template,
  sort,
  onSort,
  onResize,
  widths,
  dragKey,
  setDragKey,
  setOrder,
}: {
  columns: Column<T>[]
  template: string
  sort?: { key: string; dir: 'asc' | 'desc' }
  onSort?: (key: string) => void
  onResize: (key: string, startX: number, startWidth: number) => void
  widths: Record<string, number>
  dragKey: string | null
  setDragKey: (k: string | null) => void
  setOrder: (fn: (prev: string[]) => string[]) => void
}) {
  return (
    <div className="grid__head" style={{ gridTemplateColumns: template }}>
      {columns.map((c) => (
        <div
          key={c.key}
          className={`grid__headcell ${c.align ? `is-${c.align}` : ''} ${
            c.type === 'num' ? 'is-right' : ''
          }`}
          draggable
          onDragStart={() => setDragKey(c.key)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={() => {
            if (!dragKey || dragKey === c.key) return
            setOrder((prev) => {
              const next = prev.filter((k) => k !== dragKey)
              next.splice(next.indexOf(c.key), 0, dragKey)
              return next
            })
            setDragKey(null)
          }}
        >
          <button
            className="grid__sortbtn label"
            onClick={() => c.sortable && onSort?.(c.key)}
            disabled={!c.sortable}
          >
            {c.label}
            {sort?.key === c.key && (
              <span className="grid__sortmark">
                {sort.dir === 'asc' ? '↑' : '↓'}
              </span>
            )}
          </button>
          <span
            className="grid__resize"
            onMouseDown={(e) => {
              e.preventDefault()
              onResize(c.key, e.clientX, widths[c.key] ?? c.width)
            }}
          />
        </div>
      ))}
    </div>
  )
}
