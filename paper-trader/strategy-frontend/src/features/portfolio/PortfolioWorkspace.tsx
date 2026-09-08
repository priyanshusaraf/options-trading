import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { errorMessage, type StrategyApi } from '../../shell/api'
import type { PaperPortfolio } from './portfolioContracts'
import '../home/home-portfolio.css'

const money = (value: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(value)
const date = (value: string) => new Date(value).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })

function HistoryChart({ portfolio }: { portfolio: PaperPortfolio }) {
  const values = portfolio.points.map((point) => point.realized_pnl)
  const low = Math.min(0, ...values)
  const high = Math.max(0, ...values)
  const range = high - low || 1
  const start = Date.parse(portfolio.points[0].timestamp)
  const duration = Date.parse(portfolio.points.at(-1)!.timestamp) - start || 1
  const coordinates = portfolio.points.map((point) => `${24 + (Date.parse(point.timestamp) - start) / duration * 752},${220 - (point.realized_pnl - low) / range * 196}`).join(' ')
  return <div className="portfolio-history">
    <div className="portfolio-scale"><span>{money(high)}</span><span>{money(low)}</span></div>
    <svg viewBox="0 0 800 244" role="img" aria-label={`Realized paper P&L: ${money(portfolio.realized_pnl)} across ${portfolio.closed_trades} closed trades`}>
      <line x1="24" x2="776" y1={220 + low / range * 196} y2={220 + low / range * 196} className="portfolio-zero" />
      <polyline points={coordinates} fill="none" className="portfolio-line" />
      {portfolio.points.length === 1 && <circle cx="24" cy={220 - (values[0] - low) / range * 196} r="3" className="portfolio-dot" />}
    </svg>
    <div className="portfolio-dates"><span>{date(portfolio.points[0].timestamp)}</span><span>{date(portfolio.points.at(-1)!.timestamp)}</span></div>
  </div>
}

export function PortfolioPanel({ api, breakdown = false }: { api: StrategyApi; breakdown?: boolean }) {
  const [state, setState] = useState<{ value?: PaperPortfolio; error?: string }>({})
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setState({})
    void api.paperPortfolio(controller.signal).then((value) => {
      if (!controller.signal.aborted) setState({ value })
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setState({ error: errorMessage(error) })
    })
    return () => controller.abort()
  }, [api, attempt])
  return <section className="home-portfolio" aria-label="Portfolio">
    <header className="home-portfolio-heading"><h2>Realized paper P&amp;L</h2>{!breakdown && <Link to="/portfolio">View portfolio</Link>}</header>
    {!state.value && !state.error && <p className="home-portfolio-empty" role="status">Loading paper portfolio…</p>}
    {state.error && <div className="home-portfolio-empty"><p role="alert">{state.error}</p><button onClick={() => setAttempt((value) => value + 1)}>Retry portfolio</button></div>}
    {state.value && <PortfolioRecords portfolio={state.value} breakdown={breakdown} />}
  </section>
}

function versionLabel(version: string | null) {
  if (version === null) return 'Version unavailable'
  return /^\d+$/.test(version) ? `Version ${version}` : 'Saved version'
}

function PortfolioTable({ portfolio }: { portfolio: PaperPortfolio }) {
  return <div className="portfolio-table-wrap"><table className="portfolio-table"><caption>By strategy</caption><thead><tr><th scope="col">Strategy</th><th scope="col">Closed trades</th><th scope="col">Realized P&amp;L</th></tr></thead><tbody>
    {portfolio.strategies.map((strategy) => <tr key={JSON.stringify([strategy.strategy_key, strategy.strategy_version])}><th scope="row">{strategy.display_name}<small>{versionLabel(strategy.strategy_version)}</small></th><td>{strategy.closed_trades}</td><td>{money(strategy.realized_pnl)}</td></tr>)}
    {portfolio.untraded_strategies.map((strategy) => <tr key={strategy.strategy_key}><th scope="row">{strategy.display_name}<small>{strategy.strategy_version === null ? 'Not saved yet' : versionLabel(strategy.strategy_version)}</small></th><td>No closed paper trades</td><td aria-label="No realized result">—</td></tr>)}
  </tbody></table></div>
}

function PortfolioRecords({ portfolio, breakdown }: { portfolio: PaperPortfolio; breakdown: boolean }) {
  return <>
    {portfolio.points.length ? <>
      <div className="portfolio-total"><strong>{money(portfolio.realized_pnl)}</strong><span>{portfolio.closed_trades} closed trades · Net of charges</span></div>
      <HistoryChart portfolio={portfolio} />
      <p className="portfolio-note">Closed paper trades only. Updated {date(portfolio.as_of)}.</p>
    </> : <div className="home-portfolio-plot"><div className="home-portfolio-grid" aria-hidden="true" /><div className="home-portfolio-empty"><h3>No closed paper trades yet</h3><p>Closed paper trades will appear here. Open positions and backtest results are not included.</p><Link className="slate-route-link" to="/strategies">View strategies</Link></div></div>}
    {breakdown && <PortfolioTable portfolio={portfolio} />}
  </>
}

export function PortfolioWorkspace({ api }: { api: StrategyApi }) {
  return <section className="slate-home" aria-labelledby="portfolio-heading"><header className="slate-heading"><h1 id="portfolio-heading">Portfolio</h1></header><PortfolioPanel api={api} breakdown /></section>
}
