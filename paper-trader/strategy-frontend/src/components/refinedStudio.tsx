import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  Asterisk, Bell, ChevronDown, ChevronRight, CircleHelp, FileCheck2, Menu,
  PanelLeftClose, PanelLeftOpen, PanelRight, Search, ShieldCheck, X,
} from 'lucide-react'
import { directionById, type DirectionId } from '../data/directions'
import { primaryStrategy } from '../data/fixtures'
import type { Strategy } from '../data/model'
import { SurfaceRouter, allSurfaceIds, strategyStageIds, surfaceMeta, type SurfaceId } from './surfaces'
import { IconButton, cx } from './ui'

type RefinedId = Extract<DirectionId, 'd7' | 'd8' | 'd9' | 'd10' | 'd11'>

const primaryNavigation: SurfaceId[] = ['home', 'strategies', 'portfolio', 'activity', 'workspace']
const systemNavigation: SurfaceId[] = ['connections', 'mobile', 'settings']
const variantIds: RefinedId[] = ['d7', 'd8', 'd9', 'd10', 'd11']

const variantMeta: Record<RefinedId, { className: string; motion: string; label: string }> = {
  d7: { className: 'refined--precision', motion: 'motion-none', label: 'Precision Slate' },
  d8: { className: 'refined--lightning', motion: 'motion-trace', label: 'Lightning Desk' },
  d9: { className: 'refined--day', motion: 'motion-fade', label: 'Clear Day' },
  d10: { className: 'refined--ink', motion: 'motion-slide', label: 'Signal Ink' },
  d11: { className: 'refined--warm', motion: 'motion-gentle', label: 'Warm Current' },
}

function isSurface(value: string | null): value is SurfaceId {
  return Boolean(value && allSurfaceIds.includes(value as SurfaceId))
}

function RefinedBrand({ collapsed }: { collapsed: boolean }) {
  return <div className="refined-brand"><span><Asterisk size={17} /></span>{collapsed ? null : <strong>STRATEGY <b>OS</b></strong>}</div>
}

function NavigationItem({ id, active, collapsed, onNavigate }: { id: SurfaceId; active: boolean; collapsed: boolean; onNavigate: (id: SurfaceId) => void }) {
  const meta = surfaceMeta[id]
  const Icon = meta.icon
  return (
    <button type="button" className={cx('refined-nav-item', active && 'is-active')} aria-label={meta.label} title={collapsed ? meta.label : undefined} onClick={() => onNavigate(id)}>
      <Icon size={17} />
      {collapsed ? null : <span>{meta.short}</span>}
      {collapsed ? null : <ChevronRight size={13} />}
    </button>
  )
}

function StrategyLocalNavigation({ surface, strategy, onNavigate }: { surface: SurfaceId; strategy: Strategy; onNavigate: (id: SurfaceId) => void }) {
  return (
    <div className="refined-strategy-local">
      <div className="refined-strategy-object">
        <span>{strategy.code}</span>
        <strong>{strategy.name}</strong>
        <small>draft {strategy.draftId} · validated {strategy.validatedId ?? 'none'} · deployed {strategy.deployedId ?? 'none'}</small>
      </div>
      <nav aria-label="Selected strategy sections">
        {strategyStageIds.map((id) => {
          const Icon = surfaceMeta[id].icon
          return <button type="button" key={id} className={surface === id ? 'is-active' : ''} onClick={() => onNavigate(id)}><Icon size={13} /><span>{surfaceMeta[id].short}</span></button>
        })}
      </nav>
    </div>
  )
}

function ContextDrawer({ onClose, strategy }: { onClose: () => void; strategy: Strategy }) {
  return (
    <aside className="refined-context-drawer" aria-label="Strategy context">
      <header><div><span>Strategy context</span><strong>{strategy.name}</strong></div><IconButton label="Close context" onClick={onClose}><X size={15} /></IconButton></header>
      <section><h3>Version register</h3><dl><div><dt>Draft</dt><dd>{strategy.draftId}</dd></div><div><dt>Validated</dt><dd>{strategy.validatedId ?? 'None'}</dd></div><div><dt>Deployed</dt><dd>{strategy.deployedId ?? 'None'}</dd></div></dl></section>
      <section><h3>Evidence status</h3><p><ShieldCheck size={15} /> Completed-bar causality confirmed</p><p><FileCheck2 size={15} /> Net-of-charges artefact BT-241</p></section>
      <section className="refined-context-note"><h3>Current limitation</h3><p>Paper deployment v1.7.2 has not been rebound to validated definition v1.8.0.</p></section>
      <footer>Static prototype · no live authority</footer>
    </aside>
  )
}

function CommandMenu({ active, onNavigate, onClose }: { active: SurfaceId; onNavigate: (id: SurfaceId) => void; onClose: () => void }) {
  const [query, setQuery] = useState('')
  const visible = allSurfaceIds.filter((id) => surfaceMeta[id].label.toLowerCase().includes(query.toLowerCase()))
  return (
    <div className="refined-command-backdrop" onMouseDown={onClose}>
      <div className="refined-command" onMouseDown={(event) => event.stopPropagation()}>
        <label><Search size={17} /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Open a surface or strategy object" /><kbd>esc</kbd></label>
        <div>{visible.map((id) => { const Icon = surfaceMeta[id].icon; return <button type="button" key={id} className={active === id ? 'is-active' : ''} onClick={() => { onNavigate(id); onClose() }}><Icon size={16} /><span><strong>{surfaceMeta[id].label}</strong><small>{surfaceMeta[id].group}</small></span><ChevronRight size={13} /></button> })}</div>
      </div>
    </div>
  )
}

function MobileNavigation({ surface, onNavigate, onMore }: { surface: SurfaceId; onNavigate: (id: SurfaceId) => void; onMore: () => void }) {
  const items: SurfaceId[] = ['home', 'strategies', 'portfolio', 'activity']
  return <nav className="refined-mobile-nav">{items.map((id) => { const Icon = surfaceMeta[id].icon; return <button type="button" key={id} className={surface === id ? 'is-active' : ''} onClick={() => onNavigate(id)}><Icon size={18} /><span>{surfaceMeta[id].short}</span></button> })}<button type="button" onClick={onMore}><Menu size={18} /><span>More</span></button></nav>
}

function MobileMenu({ surface, onNavigate, onClose }: { surface: SurfaceId; onNavigate: (id: SurfaceId) => void; onClose: () => void }) {
  return <div className="refined-mobile-menu"><div><header><strong>All surfaces</strong><IconButton label="Close menu" onClick={onClose}><X size={16} /></IconButton></header>{allSurfaceIds.map((id) => <NavigationItem key={id} id={id} active={surface === id} collapsed={false} onNavigate={(next) => { onNavigate(next); onClose() }} />)}<Link to="/">Compare all directions</Link></div></div>
}

export function RefinedStudio({ id }: { id: RefinedId }) {
  const [params, setParams] = useSearchParams()
  const initialSurface = isSurface(params.get('surface')) ? params.get('surface') as SurfaceId : 'home'
  const [surface, setSurface] = useState<SurfaceId>(initialSurface)
  const [strategy, setStrategy] = useState<Strategy>(primaryStrategy)
  const [collapsed, setCollapsed] = useState(false)
  const [contextOpen, setContextOpen] = useState(false)
  const [commandOpen, setCommandOpen] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const isStrategySurface = strategyStageIds.includes(surface)
  const meta = variantMeta[id]
  const direction = directionById[id]

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setCommandOpen((value) => !value) }
      if (event.key === 'Escape') { setCommandOpen(false); setContextOpen(false) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const navigate = (next: SurfaceId) => {
    setSurface(next)
    setParams({ surface: next }, { replace: true })
    setContextOpen(false)
    window.scrollTo({ top: 0, behavior: id === 'd7' ? 'auto' : 'smooth' })
  }

  return (
    <div className={cx('refined-root', meta.className, meta.motion, collapsed && 'is-nav-collapsed', surface === 'build' && 'is-builder')} data-direction={direction.name}>
      <aside className="refined-sidebar">
        <div className="refined-sidebar-head"><RefinedBrand collapsed={collapsed} /><IconButton label={collapsed ? 'Expand navigation' : 'Collapse navigation'} onClick={() => setCollapsed((value) => !value)}>{collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}</IconButton></div>
        <div className="refined-nav-group">{collapsed ? null : <span>Workspace</span>}{primaryNavigation.map((item) => <NavigationItem key={item} id={item} active={surface === item || (item === 'strategies' && isStrategySurface)} collapsed={collapsed} onNavigate={navigate} />)}</div>
        {isStrategySurface && !collapsed ? <button type="button" className="refined-selected-strategy" onClick={() => navigate('overview')}><span>{strategy.code.slice(0, 2)}</span><div><small>Selected strategy</small><strong>{strategy.name}</strong></div><ChevronRight size={13} /></button> : null}
        <div className="refined-nav-group refined-nav-group--system">{collapsed ? null : <span>System</span>}{systemNavigation.map((item) => <NavigationItem key={item} id={item} active={surface === item} collapsed={collapsed} onNavigate={navigate} />)}</div>
        <Link className="refined-all-directions" to="/">{collapsed ? <CircleHelp size={17} /> : 'Compare all directions'}</Link>
      </aside>

      <div className="refined-application">
        <header className="refined-topbar">
          <button type="button" className="refined-search" onClick={() => setCommandOpen(true)}><Search size={15} /><span>Search strategies, evidence, or commands</span><kbd>⌘ K</kbd></button>
          <div className="refined-market-line"><span>NIFTY 24,837.40</span><b>+0.42%</b><span>21 Aug · 14:09 IST</span></div>
          <label className="refined-variant"><span>Variant</span><select value={id} onChange={(event) => { window.location.assign(`/${event.target.value}?surface=${surface}`) }}>{variantIds.map((variant) => <option value={variant} key={variant}>{variantMeta[variant].label}</option>)}</select><ChevronDown size={12} /></label>
          {isStrategySurface ? <IconButton label="Open strategy context" onClick={() => setContextOpen(true)}><PanelRight size={16} /></IconButton> : null}
          <IconButton label="Notifications"><Bell size={16} /></IconButton>
          <span className="refined-avatar">PS</span>
        </header>

        {isStrategySurface ? <StrategyLocalNavigation surface={surface} strategy={strategy} onNavigate={navigate} /> : null}

        <main className="refined-workspace" key={`${id}-${surface}`}>
          <SurfaceRouter direction={id} surface={surface} strategy={strategy} onStrategyChange={(next) => { setStrategy(next); navigate('overview') }} onNavigate={navigate} openEvidence={() => setContextOpen(true)} />
        </main>
      </div>

      {contextOpen ? <ContextDrawer strategy={strategy} onClose={() => setContextOpen(false)} /> : null}
      {commandOpen ? <CommandMenu active={surface} onNavigate={navigate} onClose={() => setCommandOpen(false)} /> : null}
      <MobileNavigation surface={surface} onNavigate={navigate} onMore={() => setMobileOpen(true)} />
      {mobileOpen ? <MobileMenu surface={surface} onNavigate={navigate} onClose={() => setMobileOpen(false)} /> : null}
    </div>
  )
}
