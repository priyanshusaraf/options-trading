import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle, ArrowLeft, ArrowRight, Asterisk, CheckCircle2, ChevronDown,
  ChevronRight, Command, FileCheck2, FlaskConical, Grid2X2, LockKeyhole, Menu,
  PanelRight, PanelRightClose, ReceiptText, Search, ShieldCheck, X,
} from 'lucide-react'
import { directionById, directions, type DirectionId } from '../data/directions'
import { primaryStrategy, strategies } from '../data/fixtures'
import type { Strategy } from '../data/model'
import { Badge, Button, IconButton, KeyValue, Progress, cx } from './ui'
import { SurfaceRouter, allSurfaceIds, strategyStageIds, surfaceMeta, type SurfaceId } from './surfaces'

const globalIds: SurfaceId[] = ['home', 'strategies', 'portfolio', 'activity', 'workspace']
const systemIds: SurfaceId[] = ['connections', 'mobile', 'settings']

function isSurface(value: string | null): value is SurfaceId {
  return Boolean(value && allSurfaceIds.includes(value as SurfaceId))
}

function Brand({ compact = false }: { compact?: boolean }) {
  return <div className={cx('brand', compact && 'brand--compact')}><span className="brand__mark"><Asterisk size={compact ? 16 : 19} /></span>{compact ? null : <span><strong>STRATEGY</strong><em>OS</em></span>}</div>
}

function SurfaceButton({ id, active, onClick, iconOnly = false, showGroup = false }: { id: SurfaceId; active: boolean; onClick: () => void; iconOnly?: boolean; showGroup?: boolean }) {
  const meta = surfaceMeta[id]
  const Icon = meta.icon
  return <button type="button" title={iconOnly ? meta.label : undefined} aria-label={meta.label} className={cx('surface-button', active && 'is-active', iconOnly && 'surface-button--icon')} onClick={onClick}>{showGroup ? <small>{meta.group}</small> : null}<Icon size={16} /><span>{meta.short}</span>{iconOnly ? null : <ChevronRight size={13} />}</button>
}

function DirectionSwitcher({ current }: { current: DirectionId }) {
  return (
    <div className="direction-switcher">
      <span>Direction</span>
      <select aria-label="Switch design direction" value={current} onChange={(event) => { window.location.assign(`/${event.target.value}`) }}>
        {directions.map((direction) => <option value={direction.id} key={direction.id}>{direction.number} · {direction.shortName}</option>)}
      </select>
    </div>
  )
}

function StrategyPicker({ strategy, onChange }: { strategy: Strategy; onChange: (strategy: Strategy) => void }) {
  return <label className="strategy-picker"><span className="strategy-picker__mark">{strategy.name.split(' ').slice(0, 2).map((word) => word[0]).join('')}</span><span><small>Current strategy</small><select value={strategy.id} onChange={(event) => onChange(strategies.find((item) => item.id === event.target.value) ?? strategy)}>{strategies.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</select></span><ChevronDown size={13} /></label>
}

function StrategyStageBar({ active, onNavigate, numbered = false }: { active: SurfaceId; onNavigate: (id: SurfaceId) => void; numbered?: boolean }) {
  return <nav className={cx('strategy-stagebar', numbered && 'strategy-stagebar--numbered')} aria-label="Strategy lifecycle">{strategyStageIds.map((id, index) => { const meta = surfaceMeta[id]; const Icon = meta.icon; return <button type="button" className={active === id ? 'is-active' : ''} onClick={() => onNavigate(id)} key={id}>{numbered ? <span>{String(index + 1).padStart(2, '0')}</span> : <Icon size={14} />}<strong>{meta.short}</strong>{id === 'research' ? <Badge tone="good">admitted</Badge> : id === 'live' ? <Badge tone="warn">gated</Badge> : null}</button> })}</nav>
}

function EvidencePanel({ onClose, embedded = false }: { onClose?: () => void; embedded?: boolean }) {
  return <aside className={cx('evidence-panel', embedded && 'evidence-panel--embedded')}><header><div><span className="eyebrow">Evidence drawer</span><h2>Why this claim holds</h2></div>{onClose ? <IconButton label="Close evidence" onClick={onClose}><X size={16} /></IconButton> : null}</header><div className="evidence-claim"><Badge tone="good">SUPPORTED</Badge><p>The 15-minute opening range remains stable after costs and walk-forward testing.</p></div><div className="evidence-chain"><div><FlaskConical size={15} /><span><strong>Claim</strong>15-minute range reduces false breaks</span><Badge tone="good">accepted</Badge></div><i /><div><Grid2X2 size={15} /><span><strong>Experiment</strong>RS-117 parameter sweep</span><Badge tone="warn">1 region rejected</Badge></div><i /><div><FileCheck2 size={15} /><span><strong>Artefact</strong>BT-241 · v1.8.0</span><Badge tone="good">complete</Badge></div><i /><div><ShieldCheck size={15} /><span><strong>Decision</strong>Admitted for paper review</span><Badge tone="violet">20 Aug</Badge></div></div><div className="evidence-checks"><KeyValue label="Look-ahead" value="Passed" /><KeyValue label="Charges" value="Included" /><KeyValue label="OOS share" value="31%" /><KeyValue label="Artefact hash" value="a42b…91ec" mono /></div><div className="evidence-rejection"><AlertTriangle size={15} /><div><strong>Rejected evidence</strong><p>1.2 ATR protection is fragile across neighbouring parameters.</p></div></div><Button variant="secondary"><ReceiptText size={14} /> Open full packet</Button></aside>
}

function ContextDeck({ surface, strategy }: { surface: SurfaceId; strategy: Strategy }) {
  return <aside className="context-deck"><header><span className="eyebrow">Context</span><strong>{surfaceMeta[surface].label}</strong></header><div className="context-deck__version"><span>Object</span><strong>{strategy.code}</strong><small>{strategy.draftId}</small></div><div className="context-deck__section"><span className="label">Current facts</span><KeyValue label="Draft" value={strategy.draftId} mono /><KeyValue label="Validated" value={strategy.validatedId ?? 'None'} mono /><KeyValue label="Deployed" value={strategy.deployedId ?? 'None'} mono /></div><div className="context-deck__section"><span className="label">Fast links</span>{['Backtest artefact', 'Parameter sweep', 'Paper deployment'].map((item) => <button type="button" key={item}>{item}<ArrowRight size={12} /></button>)}</div><div className="context-deck__footer"><LockKeyhole size={13} />Static fixture · no authority</div></aside>
}

function BottomMobileNav({ active, onNavigate, onMenu }: { active: SurfaceId; onNavigate: (id: SurfaceId) => void; onMenu: () => void }) {
  const ids: SurfaceId[] = ['home', 'strategies', 'live', 'portfolio']
  return <nav className="mobile-bottom-nav">{ids.map((id) => { const Icon = surfaceMeta[id].icon; return <button type="button" key={id} onClick={() => onNavigate(id)} className={active === id ? 'is-active' : ''}><Icon size={18} /><span>{surfaceMeta[id].short}</span></button> })}<button type="button" onClick={onMenu}><Menu size={18} /><span>More</span></button></nav>
}

function MoreMenu({ active, onNavigate, onClose }: { active: SurfaceId; onNavigate: (id: SurfaceId) => void; onClose: () => void }) {
  return <div className="mobile-more"><div className="mobile-more__sheet"><header><Brand /><IconButton label="Close menu" onClick={onClose}><X size={17} /></IconButton></header><div>{allSurfaceIds.map((id) => <SurfaceButton key={id} id={id} active={id === active} onClick={() => { onNavigate(id); onClose() }} />)}</div><Link to="/">Compare design directions</Link></div></div>
}

function AppContent({ direction, surface, strategy, onStrategyChange, onNavigate, openEvidence }: { direction: DirectionId; surface: SurfaceId; strategy: Strategy; onStrategyChange: (strategy: Strategy) => void; onNavigate: (surface: SurfaceId) => void; openEvidence: () => void }) {
  return <SurfaceRouter direction={direction} surface={surface} strategy={strategy} onStrategyChange={onStrategyChange} onNavigate={onNavigate} openEvidence={openEvidence} />
}

interface ShellProps {
  id: DirectionId
  surface: SurfaceId
  strategy: Strategy
  onStrategyChange: (strategy: Strategy) => void
  onNavigate: (surface: SurfaceId) => void
  evidenceOpen: boolean
  setEvidenceOpen: (value: boolean) => void
  paletteOpen: boolean
  setPaletteOpen: (value: boolean) => void
}

function CalmShell(props: ShellProps) {
  const { id, surface, strategy, onStrategyChange, onNavigate, evidenceOpen, setEvidenceOpen } = props
  return <div className="direction-shell dir-calm"><aside className="calm-rail"><Brand /><div className="calm-rail__nav">{globalIds.map((item) => <SurfaceButton key={item} id={item} active={surface === item} onClick={() => onNavigate(item)} />)}</div><div className="calm-rail__system">{systemIds.map((item) => <SurfaceButton key={item} id={item} active={surface === item} onClick={() => onNavigate(item)} />)}<Link to="/"><ArrowLeft size={14} /> All directions</Link></div></aside><div className="calm-app"><header className="calm-topbar"><StrategyPicker strategy={strategy} onChange={onStrategyChange} /><div><Badge tone="warn" dot>Fixture only</Badge><DirectionSwitcher current={id} /><IconButton label="Open evidence" onClick={() => setEvidenceOpen(true)}><ReceiptText size={16} /></IconButton><span className="avatar">PS</span></div></header><StrategyStageBar active={surface} onNavigate={onNavigate} /><main className="calm-content"><AppContent direction={id} surface={surface} strategy={strategy} onStrategyChange={onStrategyChange} onNavigate={onNavigate} openEvidence={() => setEvidenceOpen(true)} /></main></div>{evidenceOpen ? <div className="drawer-backdrop" onClick={() => setEvidenceOpen(false)}><div onClick={(event) => event.stopPropagation()}><EvidencePanel onClose={() => setEvidenceOpen(false)} /></div></div> : null}</div>
}

function WorkstationShell(props: ShellProps) {
  const { id, surface, strategy, onStrategyChange, onNavigate, evidenceOpen, setEvidenceOpen, paletteOpen, setPaletteOpen } = props
  return <div className="direction-shell dir-workstation"><header className="ws-menubar"><Brand compact /><button type="button" className="ws-command" onClick={() => setPaletteOpen(true)}><Search size={14} /><span>Jump to strategy, surface or record</span><kbd>⌘ K</kbd></button><div className="ws-ticker"><span>NIFTY <b className="positive">24,837.40 +0.42%</b></span><span>BANKNIFTY <b className="negative">54,192.15 −0.18%</b></span><span>VIX <b>12.84</b></span></div><DirectionSwitcher current={id} /><IconButton label="Evidence" onClick={() => setEvidenceOpen(!evidenceOpen)}><ReceiptText size={15} /></IconButton><span className="avatar">PS</span></header><div className="ws-status"><Badge tone="warn" dot>DATA STALE 38s</Badge><span>PAPER-IND-02</span><span>1 open position</span><span>Entries gated · exits active</span><span className="ws-status__clock">14:09:00 IST</span></div><aside className="ws-dock">{allSurfaceIds.map((item) => <SurfaceButton iconOnly key={item} id={item} active={surface === item} onClick={() => onNavigate(item)} />)}<Link title="All directions" to="/"><ArrowLeft size={15} /></Link></aside><div className={cx('ws-workarea', evidenceOpen && 'with-evidence')}><main><AppContent direction={id} surface={surface} strategy={strategy} onStrategyChange={onStrategyChange} onNavigate={onNavigate} openEvidence={() => setEvidenceOpen(true)} /></main><ContextDeck surface={surface} strategy={strategy} />{evidenceOpen ? <EvidencePanel onClose={() => setEvidenceOpen(false)} /> : null}</div><footer className="ws-telemetry"><span><i className="status-dot status-dot--good" />Paper adapter 86ms</span><span>Graph valid · draft unchanged</span><span>Open risk ₹1.13L</span><span>Last record EV-901</span></footer>{paletteOpen ? <CommandPalette active={surface} onNavigate={onNavigate} onClose={() => setPaletteOpen(false)} /> : null}</div>
}

function LifecycleShell(props: ShellProps) {
  const { id, surface, strategy, onStrategyChange, onNavigate, evidenceOpen, setEvidenceOpen } = props
  const stageIndex = Math.max(0, strategyStageIds.indexOf(surface))
  const stageCopy = [
    ['Define the strategy object', 'Confirm thesis, role semantics and version facts.'],
    ['Compose a typed draft', 'The graph is a projection of one immutable definition.'],
    ['Prove deterministic behaviour', 'Replay completed bars with charges and causal explanation.'],
    ['Reject fragile claims', 'Review out-of-sample tests and bias checks before admission.'],
    ['Resolve a deployment binding', 'Preflight version, mode, capability, instruments and risk.'],
    ['Operate attributed records', 'Watch health, protection, positions and causal events.'],
  ][stageIndex]
  return <div className="direction-shell dir-lifecycle"><header className="life-header"><Brand /><nav>{globalIds.map((item) => <SurfaceButton key={item} id={item} active={surface === item} onClick={() => onNavigate(item)} />)}</nav><DirectionSwitcher current={id} /><Badge tone="warn" dot>Mock workspace</Badge><span className="avatar">PS</span></header><div className="life-objectbar"><StrategyPicker strategy={strategy} onChange={onStrategyChange} /><span>Draft <b>{strategy.draftId}</b></span><span>Validated <b>{strategy.validatedId}</b></span><span>Deployed <b>{strategy.deployedId}</b></span><button type="button" onClick={() => setEvidenceOpen(true)}><ReceiptText size={14} /> Evidence packet</button></div><StrategyStageBar active={surface} onNavigate={onNavigate} numbered /><div className="life-layout"><aside className="life-brief"><span className="life-brief__number">{String(stageIndex + 1).padStart(2, '0')}</span><div className="eyebrow">Current stage</div><h2>{stageCopy?.[0] ?? surfaceMeta[surface].label}</h2><p>{stageCopy?.[1] ?? 'Global Strategy OS surface.'}</p><div className="stage-gates"><span className="label">Stage gates</span><div><CheckCircle2 size={14} /><span>Object identified</span></div><div><CheckCircle2 size={14} /><span>Inputs attributable</span></div><div><AlertTriangle size={14} /><span>1 review required</span></div></div><Progress value={[92, 74, 100, 82, 64, 71][stageIndex] ?? 80} label="Stage completeness" /><div className="life-other"><span className="label">Other surfaces</span>{[...systemIds, 'workspace' as SurfaceId].map((item) => <SurfaceButton key={item} id={item} active={surface === item} onClick={() => onNavigate(item)} />)}</div><Link to="/"><ArrowLeft size={14} /> Compare directions</Link></aside><main className="life-content"><AppContent direction={id} surface={surface} strategy={strategy} onStrategyChange={onStrategyChange} onNavigate={onNavigate} openEvidence={() => setEvidenceOpen(true)} /></main>{evidenceOpen ? <EvidencePanel onClose={() => setEvidenceOpen(false)} /> : null}</div></div>
}

function ProgressiveShell(props: ShellProps) {
  const { id, surface, strategy, onStrategyChange, onNavigate, evidenceOpen, setEvidenceOpen, paletteOpen, setPaletteOpen } = props
  return <div className="direction-shell dir-progressive"><header className="progressive-header"><Link to="/"><Brand /></Link><button type="button" className="progressive-launch" onClick={() => setPaletteOpen(true)}><Command size={15} /><span>Open anything</span><kbd>⌘ K</kbd></button><div><Badge tone="warn" dot>Fixture</Badge><DirectionSwitcher current={id} /><span className="avatar">PS</span></div></header><div className="progressive-context"><button type="button" onClick={() => setPaletteOpen(true)}>{surfaceMeta[surface].label}<ChevronDown size={13} /></button><span>/</span><StrategyPicker strategy={strategy} onChange={onStrategyChange} /><span className="progressive-context__facts"><Badge tone="good">validated {strategy.validatedId}</Badge><Badge tone="info">deployed {strategy.deployedId}</Badge></span><IconButton label="Reveal evidence" onClick={() => setEvidenceOpen(!evidenceOpen)}>{evidenceOpen ? <PanelRightClose size={15} /> : <PanelRight size={15} />}</IconButton></div><main className={cx('progressive-canvas', evidenceOpen && 'with-sheet')}><AppContent direction={id} surface={surface} strategy={strategy} onStrategyChange={onStrategyChange} onNavigate={onNavigate} openEvidence={() => setEvidenceOpen(true)} />{evidenceOpen ? <div className="progressive-sheet"><EvidencePanel onClose={() => setEvidenceOpen(false)} embedded /></div> : null}</main><div className="progressive-recents"><span>Recent</span>{(['build', 'research', 'live'] as SurfaceId[]).map((item) => <button type="button" key={item} onClick={() => onNavigate(item)}>{surfaceMeta[item].label}</button>)}<Link to="/">Compare directions</Link></div>{paletteOpen ? <CommandPalette active={surface} onNavigate={onNavigate} onClose={() => setPaletteOpen(false)} spacious /> : null}</div>
}

function EvidenceShell(props: ShellProps) {
  const { id, surface, strategy, onStrategyChange, onNavigate } = props
  return <div className="direction-shell dir-evidence"><header className="ledger-header"><Brand /><div className="ledger-title"><span>Evidence Ledger</span><b>/</b><strong>{surfaceMeta[surface].label}</strong></div><DirectionSwitcher current={id} /><Badge tone="good" dot>Ledger consistent</Badge><span className="avatar">PS</span></header><aside className="ledger-index"><StrategyPicker strategy={strategy} onChange={onStrategyChange} /><label className="input-shell"><Search size={13} /><input placeholder="Filter objects" /></label><span className="label">Object index</span>{allSurfaceIds.map((item) => <SurfaceButton key={item} id={item} active={surface === item} onClick={() => onNavigate(item)} />)}<Link to="/"><ArrowLeft size={14} /> All directions</Link></aside><main className="ledger-main"><div className="ledger-main__bar"><Badge tone="violet">CLAIM-CENTRIC VIEW</Badge><span>Every visible conclusion must resolve to evidence.</span><Button variant="ghost"><ReceiptText size={13} /> Export ledger</Button></div><AppContent direction={id} surface={surface} strategy={strategy} onStrategyChange={onStrategyChange} onNavigate={onNavigate} openEvidence={() => undefined} /></main><aside className="ledger-decision"><div className="eyebrow">Decision queue</div><h2>3 claims need review</h2><div className="decision-card decision-card--bad"><Badge tone="bad">REJECT</Badge><strong>Tight stops improve risk</strong><p>Neighbouring parameters fail after costs.</p><small>RS-117 · 1.2 ATR row</small></div><div className="decision-card"><Badge tone="warn">REVIEW</Badge><strong>Breadth gate remains useful</strong><p>Ablation shows modest stressed-open protection.</p><small>RS-102 · v1.8.0</small></div><EvidencePanel embedded /></aside></div>
}

function SynthesisShell(props: ShellProps) {
  const { id, surface, strategy, onStrategyChange, onNavigate, evidenceOpen, setEvidenceOpen, paletteOpen, setPaletteOpen } = props
  return <div className="direction-shell dir-synthesis"><aside className="syn-rail"><Brand compact /><div>{globalIds.map((item) => <SurfaceButton iconOnly key={item} id={item} active={surface === item} onClick={() => onNavigate(item)} />)}</div><div>{systemIds.map((item) => <SurfaceButton iconOnly key={item} id={item} active={surface === item} onClick={() => onNavigate(item)} />)}<Link title="All directions" to="/"><ArrowLeft size={15} /></Link></div></aside><div className="syn-app"><header className="syn-header"><StrategyPicker strategy={strategy} onChange={onStrategyChange} /><button type="button" className="syn-command" onClick={() => setPaletteOpen(true)}><Search size={14} /><span>Find object or command</span><kbd>⌘ K</kbd></button><Badge tone="warn" dot>Receipt stale</Badge><DirectionSwitcher current={id} /><IconButton label="Toggle evidence" onClick={() => setEvidenceOpen(!evidenceOpen)}><ReceiptText size={15} /></IconButton><span className="avatar">PS</span></header><div className="syn-context"><StrategyStageBar active={surface} onNavigate={onNavigate} /><div><span>Draft <b>{strategy.draftId}</b></span><span>Validated <b>{strategy.validatedId}</b></span><span>Deployed <b>{strategy.deployedId}</b></span></div></div><main className={cx('syn-workspace', evidenceOpen && 'with-evidence')}><div className="syn-workspace__content"><AppContent direction={id} surface={surface} strategy={strategy} onStrategyChange={onStrategyChange} onNavigate={onNavigate} openEvidence={() => setEvidenceOpen(true)} /></div>{evidenceOpen ? <EvidencePanel onClose={() => setEvidenceOpen(false)} /> : null}</main><footer className="syn-footer"><span><i className="status-dot status-dot--good" />Graph valid</span><span>Static Indian-market fixture</span><span>No credentials · no backend · no live authority</span><Badge tone="violet">V1 synthesis</Badge></footer></div>{paletteOpen ? <CommandPalette active={surface} onNavigate={onNavigate} onClose={() => setPaletteOpen(false)} /> : null}</div>
}

function CommandPalette({ active, onNavigate, onClose, spacious = false }: { active: SurfaceId; onNavigate: (id: SurfaceId) => void; onClose: () => void; spacious?: boolean }) {
  const [query, setQuery] = useState('')
  const visible = allSurfaceIds.filter((id) => surfaceMeta[id].label.toLowerCase().includes(query.toLowerCase()))
  useEffect(() => {
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [onClose])
  return <div className="command-backdrop" onMouseDown={onClose}><div className={cx('command-palette', spacious && 'command-palette--spacious')} onMouseDown={(event) => event.stopPropagation()}><header><Search size={18} /><input autoFocus aria-label="Command search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search surfaces, strategy objects and commands…" /><kbd>ESC</kbd></header><div className="command-results"><span className="label">Navigate</span>{visible.map((id) => { const Icon = surfaceMeta[id].icon; return <button type="button" key={id} className={active === id ? 'is-active' : ''} onClick={() => { onNavigate(id); onClose() }}><Icon size={16} /><span><strong>{surfaceMeta[id].label}</strong><small>{surfaceMeta[id].group} surface</small></span><kbd>↵</kbd></button> })}{!visible.length ? <p>No matching surface. Try “backtest” or “portfolio”.</p> : null}</div><footer><span><kbd>↑↓</kbd> move</span><span><kbd>↵</kbd> open</span><span>Static prototype commands only</span></footer></div></div>
}

export function DirectionStudio({ id }: { id: DirectionId }) {
  const [params, setParams] = useSearchParams()
  const initialSurface = isSurface(params.get('surface')) ? params.get('surface') as SurfaceId : (id === 'd2' ? 'live' : id === 'd3' ? 'overview' : id === 'd5' ? 'research' : 'home')
  const [surface, setSurface] = useState<SurfaceId>(initialSurface)
  const [strategy, setStrategy] = useState<Strategy>(primaryStrategy)
  const [evidenceOpen, setEvidenceOpen] = useState(id === 'd5')
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
  const definition = directionById[id]

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setPaletteOpen((value) => !value) }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const navigate = (next: SurfaceId) => {
    setSurface(next)
    setParams({ surface: next }, { replace: true })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const props: ShellProps = { id, surface, strategy, onStrategyChange: setStrategy, onNavigate: navigate, evidenceOpen, setEvidenceOpen, paletteOpen, setPaletteOpen }
  const shell = id === 'd1' ? <CalmShell {...props} /> : id === 'd2' ? <WorkstationShell {...props} /> : id === 'd3' ? <LifecycleShell {...props} /> : id === 'd4' ? <ProgressiveShell {...props} /> : id === 'd5' ? <EvidenceShell {...props} /> : <SynthesisShell {...props} />
  return <div className={cx('direction-root', `direction-root--${id}`)} data-direction={definition.name}>{shell}<BottomMobileNav active={surface} onNavigate={navigate} onMenu={() => setMoreOpen(true)} />{moreOpen ? <MoreMenu active={surface} onNavigate={navigate} onClose={() => setMoreOpen(false)} /> : null}</div>
}
