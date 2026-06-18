import { useEffect, useState } from 'react'
import { useLive } from '../state/LiveContext'
import { getOptionsCalc } from '../lib/api'
import { num } from '../lib/format'
import { PRIORITY } from '../lib/constants'
import type { OptionsCalc } from '../lib/types'

export default function OptionsCalcView() {
  const { state } = useLive()
  const enabled = state?.enabled?.length ? [...state.enabled].sort((a, b) => PRIORITY.indexOf(a) - PRIORITY.indexOf(b)) : PRIORITY
  const [sel, setSel] = useState<string>(enabled[0] || 'NIFTY')
  const [calc, setCalc] = useState<OptionsCalc | null>(null)

  useEffect(() => {
    const load = () => getOptionsCalc(sel).then(setCalc)
    load()
    const t = setInterval(load, 4000)
    return () => clearInterval(t)
  }, [sel])

  const chosenSym = calc?.chosen?.tradingsymbol

  return (
    <div className="flex flex-col gap-3">
      <div className="card p-3">
        <div className="stat-label mb-2">Option selection engine — pick an instrument</div>
        <div className="flex flex-wrap gap-2">
          {enabled.map((k) => (
            <button key={k} onClick={() => setSel(k)}
              className={`px-2.5 py-1 rounded text-xs border ${sel === k ? 'border-blue-500/60 bg-blue-500/10 text-blue-300' : 'border-edge bg-panel2 text-muted hover:text-zinc-300'}`}>
              {k}
            </button>
          ))}
        </div>
      </div>

      <div className="card p-3">
        <div className="flex items-center justify-between flex-wrap gap-2 mb-2">
          <div className="text-sm font-semibold text-zinc-100">{sel} — last evaluation</div>
          <div className="flex gap-4 text-xs text-muted">
            {calc?.direction && <span>direction <b className={calc.direction === 'LONG' ? 'text-up' : 'text-down'}>{calc.direction}</b></span>}
            {calc?.spot != null && <span>spot <b className="text-zinc-200">{num(calc.spot)}</b></span>}
            {calc?.expiry && <span>expiry <b className="text-zinc-200">{calc.expiry}</b></span>}
          </div>
        </div>
        <div className={`text-xs mb-3 p-2 rounded ${calc?.chosen ? 'bg-up/10 text-up' : 'bg-zinc-700/20 text-muted'}`}>
          {calc?.chosen ? '✓ ' : '⊘ '}{calc?.reason || 'no signal evaluated yet — the picker runs when a fresh entry fires'}
        </div>

        <table className="w-full text-xs">
          <thead className="text-muted text-left">
            <tr className="[&>th]:py-1 [&>th]:pr-3 [&>th]:font-medium">
              <th>Contract</th><th>Strike</th><th>Type</th><th>LTP</th><th>OI</th>
              <th>Spread%</th><th>IV</th><th>Delta</th><th>Liquid</th><th>In-band</th>
            </tr>
          </thead>
          <tbody>
            {(!calc?.candidates || calc.candidates.length === 0) &&
              <tr><td colSpan={10} className="py-6 text-center text-muted">no candidates yet</td></tr>}
            {calc?.candidates?.map((c) => {
              const chosen = c.tradingsymbol === chosenSym
              return (
                <tr key={c.tradingsymbol}
                  className={`border-t border-edge [&>td]:py-1 [&>td]:pr-3 tabular-nums ${chosen ? 'bg-up/15' : c.eligible ? 'bg-panel2' : ''}`}>
                  <td className="font-mono">{chosen && <span className="text-up mr-1">▶</span>}{c.tradingsymbol}</td>
                  <td>{num(c.strike, 0)}</td>
                  <td className={c.option_type === 'CE' ? 'text-up' : 'text-down'}>{c.option_type}</td>
                  <td>{num(c.ltp)}</td>
                  <td>{c.oi.toLocaleString('en-IN')}</td>
                  <td className={c.spread_pct <= 0.03 ? '' : 'text-down'}>{(c.spread_pct * 100).toFixed(2)}</td>
                  <td>{c.iv != null ? (c.iv * 100).toFixed(1) + '%' : '—'}</td>
                  <td>{c.delta != null ? c.delta.toFixed(3) : '—'}</td>
                  <td>{c.passed_liquidity ? <span className="text-up">✓</span> : <span className="text-down">✗</span>}</td>
                  <td>{c.in_delta_band ? <span className="text-up">✓</span> : <span className="text-muted">·</span>}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
