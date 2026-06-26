import { useState } from 'react'
import { addBulkToPortfolio } from '../lib/api'
import { inr, num, pnlColor } from '../lib/format'
import type { BTResult } from '../lib/types'

type Row = {
  r: BTResult
  product: 'options' | 'equity_intraday'
  include: boolean
}

export default function BulkAddModal(
  { winners, stratLabel, onClose, onDone }:
  { winners: BTResult[]; stratLabel: (k: string) => string; onClose: () => void; onDone: (addedKeys: string[]) => void }) {
  // over-budget for an options name = ATM option cost over budget; intraday names are
  // effectively always sizeable, so they default to included.
  const [rows, setRows] = useState<Row[]>(() => winners.map((r) => {
    const product: Row['product'] = r.has_options === false ? 'equity_intraday' : 'options'
    const overBudget = product === 'options' && r.affordable_options === false
    return { r, product, include: !overBudget }
  }))
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{ added: { key: string }[]; skipped: { key: string; reason: string }[] } | null>(null)

  const setRow = (i: number, patch: Partial<Row>) =>
    setRows((rs) => rs.map((row, j) => (j === i ? { ...row, ...patch } : row)))

  const confirm = async () => {
    setBusy(true)
    const items = rows.filter((x) => x.include).map((x) => ({
      key: x.r.instrument_key, interval: x.r.interval,
      strategy_key: x.r.strategy_key, product: x.product, on_home: true,
    }))
    try {
      const res = await addBulkToPortfolio(items)
      setResult(res)
      onDone(res.added.map((a: { key: string }) => a.key))   // mark ONLY what the API actually added
    } catch {
      setResult({ added: [], skipped: items.map((it) => ({ key: it.key, reason: 'request failed' })) })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="card w-full max-w-4xl p-4 flex flex-col gap-3 max-h-[92vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between shrink-0">
          <span className="text-lg font-semibold text-zinc-100">Add top {rows.length} to portfolio</span>
          <button onClick={onClose} className="btn">✕ close</button>
        </div>
        {result ? (
          <div className="text-sm">
            <div className="text-up mb-1">Added {result.added.length}.</div>
            {result.skipped.length > 0 && (
              <div className="text-amber-400">Skipped {result.skipped.length}: {result.skipped.map((s) => `${s.key} (${s.reason})`).join(', ')}</div>
            )}
            <button onClick={onClose} className="btn mt-3">done</button>
          </div>
        ) : (
          <>
            <div className="text-[11px] text-muted shrink-0">
              Each name is preset to its best strategy + timeframe. Over-budget options names are unticked by default; tick to include. Included names are added AND enabled for live trading.
            </div>
            <div className="card p-2 overflow-auto">
              <table className="w-full text-xs">
                <thead className="text-muted text-left"><tr className="[&>th]:py-1 [&>th]:pr-3">
                  <th>Add</th><th>Instrument</th><th>Strategy</th><th>TF</th><th>Product</th><th>Return%</th><th>Affordable</th></tr></thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={row.r.instrument_key} className="border-t border-edge [&>td]:py-1 [&>td]:pr-3 tabular-nums">
                      <td><input type="checkbox" checked={row.include} onChange={(e) => setRow(i, { include: e.target.checked })} /></td>
                      <td className="font-semibold text-zinc-100">{row.r.name || row.r.instrument_key}</td>
                      <td className="text-muted">{stratLabel(row.r.strategy_key)}</td>
                      <td className="text-muted">{row.r.interval}</td>
                      <td>
                        <select value={row.product} onChange={(e) => setRow(i, { product: e.target.value as Row['product'] })}
                          className="bg-panel2 border border-edge rounded px-1 py-0.5 text-[11px]">
                          <option value="options">Options</option>
                          <option value="equity_intraday">Intraday-equity</option>
                        </select>
                      </td>
                      <td className={pnlColor(row.r.return_pct)}>{num(row.r.return_pct, 1)}</td>
                      <td className={row.product === 'options' && row.r.affordable_options === false ? 'text-amber-400' : 'text-up/80'}>
                        {row.product === 'equity_intraday' ? 'MIS' : (row.r.affordable_options === false ? `over (${row.r.option_cost ? inr(row.r.option_cost) : '—'})` : 'yes')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end shrink-0">
              <button onClick={confirm} disabled={busy || !rows.some((x) => x.include)} className="btn border-up/50 text-up">
                {busy ? 'adding…' : `add ${rows.filter((x) => x.include).length} enabled`}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
