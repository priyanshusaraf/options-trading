/* oxlint-disable react/only-export-components -- shared primitives intentionally co-locate tiny helpers */
import type { ButtonHTMLAttributes, HTMLAttributes, PropsWithChildren, ReactNode } from 'react'
import { ChevronRight, Info, X } from 'lucide-react'

export function cx(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(' ')
}

export function Panel({ className, children, ...props }: PropsWithChildren<HTMLAttributes<HTMLDivElement>>) {
  return (
    <section className={cx('panel', className)} {...props}>
      {children}
    </section>
  )
}

export function PanelHeader({
  title,
  eyebrow,
  action,
  compact = false,
}: {
  title: ReactNode
  eyebrow?: ReactNode
  action?: ReactNode
  compact?: boolean
}) {
  return (
    <header className={cx('panel-header', compact && 'panel-header--compact')}>
      <div>
        {eyebrow ? <div className="eyebrow">{eyebrow}</div> : null}
        <h3>{title}</h3>
      </div>
      {action ? <div className="panel-header__action">{action}</div> : null}
    </header>
  )
}

export type Tone = 'neutral' | 'violet' | 'good' | 'warn' | 'bad' | 'info'

export function Badge({ children, tone = 'neutral', dot = false }: { children: ReactNode; tone?: Tone; dot?: boolean }) {
  return (
    <span className={cx('badge', `badge--${tone}`)}>
      {dot ? <span className="badge__dot" /> : null}
      {children}
    </span>
  )
}

export function Button({ className, children, variant = 'secondary', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger' }) {
  return (
    <button className={cx('button', `button--${variant}`, className)} type="button" {...props}>
      {children}
    </button>
  )
}

export function IconButton({ label, className, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button aria-label={label} title={label} className={cx('icon-button', className)} type="button" {...props}>
      {children}
    </button>
  )
}

export function Metric({ label, value, sub, tone = 'neutral', compact = false }: { label: string; value: ReactNode; sub?: ReactNode; tone?: Tone; compact?: boolean }) {
  return (
    <div className={cx('metric', `metric--${tone}`, compact && 'metric--compact')}>
      <div className="metric__label">{label}</div>
      <div className="metric__value">{value}</div>
      {sub ? <div className="metric__sub">{sub}</div> : null}
    </div>
  )
}

export function Segmented<T extends string>({ value, items, onChange, ariaLabel }: { value: T; items: readonly { value: T; label: string }[]; onChange: (value: T) => void; ariaLabel: string }) {
  return (
    <div className="segmented" role="tablist" aria-label={ariaLabel}>
      {items.map((item) => (
        <button
          type="button"
          role="tab"
          aria-selected={value === item.value}
          className={cx('segmented__item', value === item.value && 'is-active')}
          key={item.value}
          onClick={() => onChange(item.value)}
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}

export function Progress({ value, label, tone = 'violet' }: { value: number; label?: string; tone?: Tone }) {
  return (
    <div className="progress-wrap">
      {label ? <div className="progress-label"><span>{label}</span><span>{Math.round(value)}%</span></div> : null}
      <div className="progress" aria-label={label} aria-valuenow={value} role="progressbar" aria-valuemin={0} aria-valuemax={100}>
        <span className={cx('progress__fill', `progress__fill--${tone}`)} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
      </div>
    </div>
  )
}

export function Disclosure({ summary, meta, children, defaultOpen = false }: PropsWithChildren<{ summary: ReactNode; meta?: ReactNode; defaultOpen?: boolean }>) {
  return (
    <details className="disclosure" open={defaultOpen}>
      <summary>
        <span>{summary}</span>
        <span className="disclosure__meta">{meta}<ChevronRight size={14} /></span>
      </summary>
      <div className="disclosure__body">{children}</div>
    </details>
  )
}

export function Notice({ tone = 'info', title, children, onClose }: PropsWithChildren<{ tone?: Tone; title: string; onClose?: () => void }>) {
  return (
    <div className={cx('notice', `notice--${tone}`)} role="status">
      <Info size={16} />
      <div><strong>{title}</strong><div>{children}</div></div>
      {onClose ? <IconButton label="Dismiss" className="notice__close" onClick={onClose}><X size={14} /></IconButton> : null}
    </div>
  )
}

export function KeyValue({ label, value, mono = false }: { label: ReactNode; value: ReactNode; mono?: boolean }) {
  return <div className="key-value"><span>{label}</span><strong className={mono ? 'mono' : undefined}>{value}</strong></div>
}

export function Table({ children, compact = false, className }: PropsWithChildren<{ compact?: boolean; className?: string }>) {
  return <div className={cx('table-wrap', compact && 'table-wrap--compact', className)}><table>{children}</table></div>
}

export function EmptyState({ icon, title, children, action }: PropsWithChildren<{ icon?: ReactNode; title: string; action?: ReactNode }>) {
  return <div className="empty-state">{icon}<h3>{title}</h3><p>{children}</p>{action}</div>
}
