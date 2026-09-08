import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Asterisk, ArrowRight, BarChart3, Boxes, Check, ChevronRight, CircleDot,
  Columns3, Command, FlaskConical, GitBranch, Grid2X2, Layers3, LayoutDashboard,
  LockKeyhole, MonitorDot, Network, ReceiptText, Rocket, ShieldCheck,
  Smartphone, Sparkles, Workflow,
} from 'lucide-react'
import { DirectionComparisonInline } from '../components/surfaces'
import { Badge, Button, Panel, Table, cx } from '../components/ui'
import { directions, type DirectionDefinition, type DirectionId } from '../data/directions'

function Logo() {
  return <div className="launcher-logo"><span><Asterisk size={21} /></span><strong>STRATEGY</strong><em>OS</em></div>
}

function Preview({ id }: { id: DirectionId }) {
  if (id === 'd1') return <div className="preview preview--calm"><i className="preview-rail" /><div className="preview-top" /><div className="preview-doc"><span /><strong /><p /><p /><div /></div><i className="preview-inspector" /></div>
  if (id === 'd2') return <div className="preview preview--ws"><div className="preview-command" /><i className="preview-dock" /><div className="preview-pane preview-pane--a"><span /><b /></div><div className="preview-pane preview-pane--b"><span /><b /><b /></div><div className="preview-pane preview-pane--c"><span /></div><i className="preview-status" /></div>
  if (id === 'd3') return <div className="preview preview--life"><div className="preview-life-steps">{[1, 2, 3, 4, 5, 6].map((item) => <i key={item}>{item}</i>)}</div><aside /><main><span /><strong /><p /><p /><div /></main></div>
  if (id === 'd4') return <div className="preview preview--progress"><div className="preview-launchbar"><Command size={9} /></div><main><span /><strong /><p /><div /></main><aside><i /><i /><i /></aside></div>
  if (id === 'd5') return <div className="preview preview--ledger"><aside><i /><i /><i /><i /></aside><main>{[1, 2, 3].map((item) => <div key={item}><CircleDot size={8} /><span /><p /></div>)}</main><section><b /><p /><b /><p /></section></div>
  if (id === 'd6') return <div className="preview preview--syn"><i className="preview-syn-rail" /><div className="preview-syn-head" /><div className="preview-syn-stages">{[1, 2, 3, 4, 5, 6].map((item) => <i key={item} />)}</div><main><span /><strong /><div /></main><aside><ReceiptText size={9} /><b /><p /></aside></div>
  return <div className={cx('preview', 'preview--refined', `preview--${id}`)}><aside><b /><i /><i /><i /><i /></aside><header><span /><em /></header><main><small /><strong /><p /><div className="preview-refined-rule" /><div className="preview-refined-data"><i /><i /><i /></div></main></div>
}

function DirectionCard({ direction, selected, onSelect }: { direction: DirectionDefinition; selected: boolean; onSelect: () => void }) {
  const refined = Number(direction.id.slice(1)) >= 7
  const badge = direction.id === 'd7' ? 'REFINED BASELINE' : refined ? 'CONTROLLED VARIANT' : direction.id === 'd6' ? 'ORIGINAL SYNTHESIS' : 'ORIGINAL DIRECTION'
  return (
    <article className={cx('direction-card', `direction-card--${direction.id}`, selected && 'is-selected', direction.id === 'd7' && 'direction-card--recommended')} onMouseEnter={onSelect}>
      <div className="direction-card__top"><span className="direction-card__number">{direction.number}</span><Badge tone={refined ? 'violet' : 'neutral'}>{badge}</Badge></div>
      <Preview id={direction.id} />
      <div className="direction-card__body"><h2>{direction.name}</h2><p>{direction.thesis}</p><div className="direction-card__facts"><span><strong>{direction.density}</strong> density</span><span><strong>{direction.centralInteraction.split('.')[0]}</strong></span></div></div>
      <Link to={`/${direction.id}`} className="direction-card__open">Open complete direction <ArrowRight size={15} /></Link>
    </article>
  )
}

function DirectionDetail({ direction }: { direction: DirectionDefinition }) {
  const facts = [
    ['Central interaction', direction.centralInteraction], ['First impression', direction.firstImpression],
    ['Navigation', direction.navigation], ['Lifecycle', direction.lifecycle], ['Workspace', direction.workspace],
    ['Progressive disclosure', direction.disclosure], ['Expert path', direction.expertPath],
  ]
  return <Panel className="direction-detail"><div className="direction-detail__intro"><span className="direction-detail__number">{direction.number}</span><div><div className="eyebrow">Selected direction</div><h2>{direction.name}</h2><p>{direction.thesis}</p></div><Link to={`/${direction.id}`}><Button variant="primary">Explore all 14 surfaces <ArrowRight size={15} /></Button></Link></div><div className="direction-detail__facts">{facts.map(([label, value]) => <div key={label}><span>{label}</span><p>{value}</p></div>)}</div><div className="direction-detail__tradeoff"><div><Check size={15} /><span><strong>Advantage</strong>{direction.advantage}</span></div><div><span className="tradeoff-minus">−</span><span><strong>Weakness</strong>{direction.weakness}</span></div></div></Panel>
}

function RefinedComparison() {
  const rows = [
    ['Typography', 'Inter Variable', 'Barlow + Inter', 'Source Sans 3', 'IBM Plex Sans + Mono', 'Manrope'],
    ['Palette', 'Slate + clear blue', 'Midnight + blue + yellow', 'Cool white + cobalt', 'Ink navy + cyan', 'Stone + lake blue'],
    ['Motion', 'None', '150–180ms trace', '120ms fade', '150ms horizontal slide', '180ms gentle movement'],
    ['Best fit', 'Neutral baseline', 'Energetic research', 'Long evidence sessions', 'Precise analyst work', 'Approachable daily use'],
  ]
  return <Panel className="refined-comparison-panel"><Table compact><thead><tr><th>Variable</th><th>Precision Slate</th><th>Lightning Desk</th><th>Clear Day</th><th>Signal Ink</th><th>Warm Current</th></tr></thead><tbody>{rows.map((row) => <tr key={row[0]}>{row.map((cell, index) => <td key={cell}>{index === 0 ? <strong>{cell}</strong> : cell}</td>)}</tr>)}</tbody></Table></Panel>
}

export default function Launcher() {
  const [selectedId, setSelectedId] = useState<DirectionId>('d7')
  const selected = directions.find((direction) => direction.id === selectedId) ?? directions[6]
  const originalDirections = directions.slice(0, 6)
  const refinedDirections = directions.slice(6)
  return (
    <div className="launcher">
      <header className="launcher-header"><Logo /><nav><a href="#directions">Refined five</a><a href="#originals">Original six</a><a href="#scope">V1 scope</a></nav><div><Badge tone="warn" dot>Mock data only</Badge><Link to="/d7"><Button variant="primary">Open refined baseline <ArrowRight size={14} /></Button></Link></div></header>
      <main>
        <section className="launcher-hero">
          <div className="launcher-hero__copy"><Badge tone="violet">REFINED INTERFACE EXPLORATION · 22 AUG 2026</Badge><h1>A calmer operating system for the whole strategy lifecycle.</h1><p>Five new controlled variants share one corrected structure: collapsible primary navigation, strategy-only local tabs, a full-size builder, cardless hierarchy, restrained status treatment, varied typography, and optional micro-motion.</p><div className="launcher-hero__actions"><Link to="/d7"><Button variant="primary">Explore refined baseline <ArrowRight size={15} /></Button></Link><a href="#directions"><Button>Compare the new five <Columns3 size={15} /></Button></a></div><div className="boundary-line"><LockKeyhole size={14} /><span>Standalone visual prototype · static Indian-market fixtures · no backend, credentials, provider session, real orders, deployment, or live authority</span></div></div>
          <div className="hero-system">
            <div className="hero-system__status"><Badge tone="good" dot>Definition valid</Badge><span>NIFTY-ORB-15</span><Badge tone="warn">PAPER GATED</Badge></div>
            <div className="hero-system__graph"><div className="hero-node"><span>DATA</span><strong>NIFTY market</strong><small>5m completed bars</small></div><i /><div className="hero-node hero-node--violet"><span>SIGNAL</span><strong>Opening range</strong><small>15 minutes</small></div><i /><div className="hero-node hero-node--green"><span>GATE</span><strong>Admission</strong><small>breadth · volatility</small></div><i /><div className="hero-node hero-node--orange"><span>RISK</span><strong>ATR protection</strong><small>2.0 × initial</small></div></div>
            <div className="hero-system__metrics"><div><span>Net return</span><strong>+18.42%</strong></div><div><span>Max DD</span><strong>−7.84%</strong></div><div><span>Sharpe</span><strong>1.46</strong></div><div><span>OOS</span><strong>31%</strong></div></div>
            <svg className="hero-curve" viewBox="0 0 600 105" preserveAspectRatio="none"><line x1="0" y1="85" x2="600" y2="85" /><polyline points="0,88 38,82 74,84 111,73 145,76 190,59 225,63 264,49 302,52 341,34 380,42 418,27 461,31 499,18 544,22 600,8" /></svg>
            <div className="hero-system__footer"><span><ShieldCheck size={13} /> Completed-bar causal</span><span><ReceiptText size={13} /> Evidence attached</span><span><MonitorDot size={13} /> Synthetic paper only</span></div>
          </div>
        </section>

        <section className="lifecycle-band"><span>One strategy object</span>{['Build', 'Backtest', 'Analyze', 'Validate', 'Deploy', 'Monitor', 'Review', 'Improve'].map((item, index) => <div key={item}><i>{String(index + 1).padStart(2, '0')}</i><strong>{item}</strong>{index < 7 ? <ChevronRight size={13} /> : null}</div>)}</section>

        <section className="directions-section" id="directions"><div className="section-heading"><div><span className="eyebrow">Five controlled variants</span><h2>One corrected product structure, five different feels.</h2></div><p>Typography, palette, and micro-motion change. Navigation, builder area, warnings, hierarchy, and all fourteen routed surfaces remain comparable.</p></div><div className="direction-grid direction-grid--refined">{refinedDirections.map((direction) => <DirectionCard key={direction.id} direction={direction} selected={selectedId === direction.id} onSelect={() => setSelectedId(direction.id)} />)}</div><RefinedComparison /><DirectionDetail direction={selected} /></section>

        <section className="directions-section directions-section--original" id="originals"><div className="section-heading"><div><span className="eyebrow">Original exploration</span><h2>The first six remain available as references.</h2></div><p>They preserve the earlier ideas and make the structural improvements in the refined family easier to judge.</p></div><div className="direction-grid">{originalDirections.map((direction) => <DirectionCard key={direction.id} direction={direction} selected={selectedId === direction.id} onSelect={() => setSelectedId(direction.id)} />)}</div></section>

        <section className="comparison-section" id="comparison"><div className="section-heading"><div><span className="eyebrow">Decision matrix</span><h2>Comparison before synthesis</h2></div><p>The sixth direction keeps the strongest interaction from each proposal and accepts explicit costs.</p></div><Panel className="comparison-panel"><DirectionComparisonInline /></Panel><div className="synthesis-rationale"><div className="synthesis-rationale__mark"><Sparkles size={20} /></div><div><Badge tone="violet">06 · RECOMMENDED</Badge><h3>Obsidian Strategy OS</h3><p>It combines the calm object focus of Direction 1, the adaptive context of Direction 2, the explicit version and lifecycle facts of Direction 3, the controlled disclosure of Direction 4, and the rejection-first evidence model of Direction 5.</p></div><div className="synthesis-rationale__rules"><span><Check /> Stable global rail</span><span><Check /> Lifecycle without a wizard</span><span><Check /> Focus, split and review workspaces</span><span><Check /> Persistent evidence drawer</span><span><Check /> True mobile companion</span></div><Link to="/d6"><Button variant="primary">Open synthesis <ArrowRight size={14} /></Button></Link></div></section>

        <section className="scope-section" id="scope"><div className="section-heading"><div><span className="eyebrow">Finished V1 coverage</span><h2>Fourteen connected surfaces in every direction</h2></div><Badge tone="good">154 ROUTED SURFACE EXPERIENCES</Badge></div><div className="scope-grid">{[
          [LayoutDashboard, 'Home', 'Today, risk, work to resume'], [Layers3, 'Strategies', 'Registry and version facts'], [Workflow, 'Build', 'Graph, form, tree and code'], [BarChart3, 'Backtest', 'Metrics, costs and trade explanation'], [FlaskConical, 'Validate', 'Sweeps, walk-forward, Monte Carlo'], [Rocket, 'Deploy', 'Bindings and fail-closed preflight'], [MonitorDot, 'Live', 'Paper and signal cockpit'], [Network, 'Portfolio', 'Exposure and exact attribution'], [Grid2X2, 'Workspace', 'Presentation-only customization'], [Boxes, 'Connections', 'Provider and broker separation'], [Smartphone, 'Mobile', 'Today, Live and Activity'], [ReceiptText, 'Activity', 'Causal provenance ledger'],
        ].map(([Icon, title, copy]) => { const Component = Icon as typeof LayoutDashboard; return <div key={title as string}><Component size={17} /><span><strong>{title as string}</strong><small>{copy as string}</small></span></div> })}</div></section>

        <section className="principles-section"><div><span className="eyebrow">Design rules</span><h2>Safety facts are interface facts.</h2></div><div className="principle-grid"><div><GitBranch /><strong>One typed definition</strong><p>Graph, form, tree and code are projections, never parallel sources of truth.</p></div><div><ReceiptText /><strong>Evidence before admission</strong><p>Weak claims are rejected and their reasons stay visible.</p></div><div><ShieldCheck /><strong>Authority stays explicit</strong><p>Requested assignment, resolved capability, deployment and money records never blend.</p></div><div><LockKeyhole /><strong>Fail closed to live</strong><p>This prototype exposes no live path, credential input or real provider action.</p></div></div></section>
      </main>
      <footer className="launcher-footer"><Logo /><p>Standalone Strategy OS interface exploration. Designed around static Indian-market fixtures.</p><span>Obsidian Violet · no gradients · no glass · 2026</span></footer>
    </div>
  )
}
