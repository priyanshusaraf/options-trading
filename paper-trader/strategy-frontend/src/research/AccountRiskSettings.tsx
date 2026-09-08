import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useBrowserIdentity } from '../auth/AuthGate'
import { ApiError, errorMessage, type StrategyApi } from '../shell/api'
import { accountRiskFields, canEditAccountRisk, type AccountRiskKey, type AccountRiskSetting } from './accountRiskContracts'

function accountRiskError(error: unknown) {
  return error instanceof ApiError && error.envelope?.code === 'ACCOUNT_RISK_FORBIDDEN'
    ? 'Your workspace role cannot change account entry limits. Ask an owner or administrator; your entered amount is unchanged.' : errorMessage(error)
}

export function AccountRiskSettings({ api }: { api: StrategyApi }) {
  const editable = canEditAccountRisk(useBrowserIdentity())
  const [rows, setRows] = useState<readonly AccountRiskSetting[]>([])
  const [values, setValues] = useState<Partial<Record<AccountRiskKey, string>>>({})
  const [pending, setPending] = useState(true)
  const [message, setMessage] = useState('')
  const [attempt, setAttempt] = useState(0)
  const blocked = pending || !editable
  const request = useRef<AbortController | null>(null)
  useEffect(() => {
    const controller = new AbortController(); request.current = controller; setPending(true)
    void api.accountRiskSettings(controller.signal).then((result) => {
      if (controller.signal.aborted) return
      setRows(result); setValues(Object.fromEntries(result.map((row) => [row.key, String(row.value)]))); setMessage('')
    }).catch((error) => { if (!controller.signal.aborted) setMessage(accountRiskError(error)) })
      .finally(() => { if (!controller.signal.aborted) setPending(false) })
    return () => controller.abort()
  }, [api, attempt])
  useEffect(() => () => request.current?.abort(), [])
  async function save(event: FormEvent, key: AccountRiskKey) {
    event.preventDefault()
    if (blocked) return
    const raw = values[key]
    if (!raw?.trim()) { setMessage('Enter an amount. Use 0 to disable this limit.'); return }
    request.current?.abort(); const controller = new AbortController(); request.current = controller
    setPending(true); setMessage('')
    try {
      const saved = await api.saveAccountRiskSetting(key, Number(raw), controller.signal)
      if (controller.signal.aborted) return
      setRows((current) => current.map((row) => row.key === key ? { ...row, value: saved, overridden: true } : row))
      setMessage('Entry limit saved. Risk-reducing exits remain available.')
    } catch (error) { if (!controller.signal.aborted) setMessage(accountRiskError(error)) }
    finally { if (!controller.signal.aborted) setPending(false) }
  }
  return <section aria-labelledby="account-entry-limits"><h2 id="account-entry-limits">Account entry limits</h2>
    <p>Workspace limits applied separately to each broker account and paper/live book. Strategy overrides cannot change these limits.</p>
    <p>These limits halt new entries; they do not close positions. Risk-reducing exits remain available. Use 0 to disable a limit. Single-strategy backtests do not enforce account-wide limits.</p>
    {!editable && <p>Only workspace owners and administrators can change account entry limits.</p>}
    {accountRiskFields.map((field) => {
      const row = rows.find((item) => item.key === field.key)
      return <form key={field.key} onSubmit={(event) => void save(event, field.key)} className="account-risk-field">
        <label htmlFor={field.key}>{field.label}</label>
        <input id={field.key} aria-describedby={`${field.key}-help`} type="number" min="0" max="100000000" step="any" required value={values[field.key] ?? ''} disabled={blocked || !row} onChange={(event) => setValues((current) => ({ ...current, [field.key]: event.target.value }))} />
        <p id={`${field.key}-help`}>{field.help}</p>
        {row && <small>{row.overridden ? 'Workspace override' : 'Configured default'} · Saved value ₹{row.value.toLocaleString('en-IN')}</small>}
        <button type="submit" disabled={blocked || !row}>Save {field.label.toLowerCase()}</button>
      </form>
    })}
    <button disabled={pending} onClick={() => setAttempt((value) => value + 1)}>Reload account entry limits</button>
    {pending && <p role="status">Checking account entry limits…</p>}{message && <p role="status">{message}</p>}
  </section>
}
