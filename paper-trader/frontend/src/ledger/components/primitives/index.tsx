/* Primitives — §6.1
 *
 * Button (3 variants: quiet, default, primary — primary appears at most once
 * per screen) · Kbd · Chip · Tag · Badge · Toggle · Segment · Tooltip
 * (keyboard-shortcut-bearing, 400ms delay) · Divider · Rule.
 */

import {
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from 'react'
import './primitives.css'

type Variant = 'quiet' | 'default' | 'primary'

export function Button({
  variant = 'default',
  children,
  kbd,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  kbd?: string
}) {
  return (
    <button {...rest} className={`btn btn--${variant} ${rest.className ?? ''}`}>
      {children}
      {kbd && <Kbd>{kbd}</Kbd>}
    </button>
  )
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="kbd">{children}</kbd>
}

/** Removable filter token. §6.1 */
export function Chip({
  children,
  onRemove,
  tone = 'neutral',
  onClick,
  title,
}: {
  children: ReactNode
  onRemove?: () => void
  tone?: 'neutral' | 'attention' | 'interactive' | 'long' | 'short'
  onClick?: () => void
  title?: string
}) {
  return (
    <span
      className={`chip chip--${tone} ${onClick ? 'chip--clickable' : ''}`}
      onClick={onClick}
      title={title}
    >
      {children}
      {onRemove && (
        <button
          className="chip__x"
          aria-label="Remove"
          onClick={(e) => {
            e.stopPropagation()
            onRemove()
          }}
        >
          ×
        </button>
      )}
    </span>
  )
}

/** Nothing is a pill except tags. §7.4 */
export function Tag({
  children,
  onRemove,
  onClick,
  title,
}: {
  children: ReactNode
  onRemove?: () => void
  onClick?: () => void
  title?: string
}) {
  return (
    <span
      className={`tag ${onClick ? 'tag--clickable' : ''}`}
      onClick={onClick}
      title={title}
    >
      {children}
      {onRemove && (
        <button
          className="chip__x"
          aria-label="Remove"
          onClick={(e) => {
            e.stopPropagation()
            onRemove()
          }}
        >
          ×
        </button>
      )}
    </span>
  )
}

export function Badge({
  children,
  tone = 'neutral',
}: {
  children: ReactNode
  tone?: 'neutral' | 'attention' | 'interactive'
}) {
  return <span className={`badge badge--${tone}`}>{children}</span>
}

export function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label?: string
}) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      className={`toggle ${checked ? 'toggle--on' : ''}`}
      onClick={() => onChange(!checked)}
    >
      <span className="toggle__track">
        <span className="toggle__thumb" />
      </span>
      {label && <span className="toggle__label">{label}</span>}
    </button>
  )
}

/** Mode switch. §6.1 */
export function Segment<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T
  options: { value: T; label: string; kbd?: string }[]
  onChange: (v: T) => void
}) {
  return (
    <div className="segment" role="tablist">
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={value === o.value}
          className={`segment__item ${value === o.value ? 'is-active' : ''}`}
          onClick={() => onChange(o.value)}
          title={o.kbd}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

/** §6.1 Keyboard-shortcut-bearing, 400ms delay.
 *  §8 "no information exists only in a tooltip" — so this carries hints, never
 *  facts the user needs. */
export function Tooltip({
  children,
  content,
  kbd,
  side = 'top',
}: {
  children: ReactNode
  content: ReactNode
  kbd?: string
  side?: 'top' | 'bottom' | 'right'
}) {
  const [open, setOpen] = useState(false)
  const [timer, setTimer] = useState<ReturnType<typeof setTimeout> | null>(null)

  const show = () => {
    const t = setTimeout(() => setOpen(true), 400)
    setTimer(t)
  }
  const hide = () => {
    if (timer) clearTimeout(timer)
    setOpen(false)
  }

  return (
    <span
      className="tooltip-host"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {open && (
        <span className={`tooltip tooltip--${side}`} role="tooltip">
          {content}
          {kbd && <Kbd>{kbd}</Kbd>}
        </span>
      )}
    </span>
  )
}

/** Hairline, 1px, never coloured. §6.1 */
export function Divider() {
  return <div className="hr" role="separator" />
}

/** Labelled section divider. §6.1 */
export function Rule({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div className="rule">
      <span className="label">{children}</span>
      <span className="rule__line" />
      {right && <span className="rule__right">{right}</span>}
    </div>
  )
}

/** §8 Empty states are invitations with a keystroke. */
export function Empty({
  children,
  kbd,
}: {
  children: ReactNode
  kbd?: string
}) {
  return (
    <div className="empty">
      <span>{children}</span>
      {kbd && (
        <span className="empty__kbd">
          Press <Kbd>{kbd}</Kbd>
        </span>
      )}
    </div>
  )
}

/** Loading is a hairline progress line at the top of the pane — never a
 *  skeleton shimmer. §7.6 */
export function ProgressLine({ active }: { active: boolean }) {
  return <div className={`progress ${active ? 'is-active' : ''}`} />
}
