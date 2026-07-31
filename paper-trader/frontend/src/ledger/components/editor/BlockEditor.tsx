/* BlockEditor + SlashMenu — §6.3
 *
 * "Markdown-first with live formatting, / slash menu, drag handles,
 *  collapsible toggles, code blocks, tables, callouts, and inline entity
 *  chips. Autosave with a hairline 'saved 2s ago'."
 *
 * Implemented as a markdown textarea on the paper material with a live preview
 * and the domain slash menu, rather than a full block-tree editor with CRDT
 * (§3.4). The editing *affordances* the workflow depends on are here — slash
 * commands, templates, promote-to-evergreen, autosave, entity links — but
 * block drag handles and per-block revision history are not. That is the
 * largest deliberate scope reduction in this implementation.
 */

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from 'react'
import { TEMPLATES } from '../../domain/taxonomy'
import { relativeDays } from '../../domain/dates'
import './editor.css'

export interface SlashCommand {
  id: string
  label: string
  hint: string
  /** Text inserted at the cursor. */
  insert?: string
  /** Or a side effect — /scenario opens the scenario editor, for instance. */
  run?: () => void
}

interface Props {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  readOnly?: boolean
  /** Extra domain commands merged into the default slash menu. §6.3 */
  commands?: SlashCommand[]
  autoFocus?: boolean
  minRows?: number
  savedAt?: number | null
  /** §5.2 ⌘⇧P promotes the current selection to an evergreen doc. */
  onPromote?: (text: string) => void
  className?: string
}

const BASE_COMMANDS: SlashCommand[] = [
  { id: 'checklist', label: '/checklist', hint: 'Pre-trade checklist', insert: TEMPLATES.checklist },
  { id: 'table', label: '/table', hint: 'Markdown table', insert: '\n| | |\n|---|---|\n| | |\n' },
  { id: 'toggle', label: '/toggle', hint: 'Collapsible section', insert: '\n> ▸ Toggle\n> \n' },
  { id: 'quote', label: '/quote', hint: 'Callout', insert: '\n> ' },
  { id: 'code', label: '/code', hint: 'Code block', insert: '\n```\n\n```\n' },
  { id: 'tmpl-morning', label: '/template morning', hint: 'Morning template', insert: TEMPLATES.morning },
  { id: 'tmpl-review', label: '/template review', hint: 'Review template', insert: TEMPLATES.review },
]

export function BlockEditor({
  value,
  onChange,
  placeholder,
  readOnly,
  commands = [],
  autoFocus,
  minRows = 6,
  savedAt,
  onPromote,
  className,
}: Props) {
  const ref = useRef<HTMLTextAreaElement>(null)
  const [slashOpen, setSlashOpen] = useState(false)
  const [slashQuery, setSlashQuery] = useState('')
  const [slashIndex, setSlashIndex] = useState(0)
  const [savedLabel, setSavedLabel] = useState<string | null>(null)

  const all = useMemo(() => [...commands, ...BASE_COMMANDS], [commands])
  const filtered = useMemo(
    () =>
      all.filter((c) =>
        c.label.toLowerCase().includes(slashQuery.toLowerCase()),
      ),
    [all, slashQuery],
  )

  // Autosave indicator — a hairline note, never a spinner. §6.3
  useEffect(() => {
    if (!savedAt) return
    const tick = () => setSavedLabel(relativeSaved(savedAt))
    tick()
    const t = setInterval(tick, 5000)
    return () => clearInterval(t)
  }, [savedAt])

  useEffect(() => {
    if (autoFocus) ref.current?.focus()
  }, [autoFocus])

  function insertAtCursor(text: string, replaceSlash = false) {
    const el = ref.current
    if (!el) return
    const start = el.selectionStart
    const end = el.selectionEnd
    let from = start
    if (replaceSlash) {
      const before = value.slice(0, start)
      const idx = before.lastIndexOf('/')
      if (idx >= 0) from = idx
    }
    const next = value.slice(0, from) + text + value.slice(end)
    onChange(next)
    requestAnimationFrame(() => {
      const pos = from + text.length
      el.selectionStart = el.selectionEnd = pos
      el.focus()
    })
  }

  function handleKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (slashOpen) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSlashIndex((i) => Math.min(filtered.length - 1, i + 1))
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSlashIndex((i) => Math.max(0, i - 1))
        return
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault()
        const cmd = filtered[slashIndex]
        setSlashOpen(false)
        setSlashQuery('')
        if (cmd?.run) {
          // Remove the typed `/…` before handing off to the side effect.
          insertAtCursor('', true)
          cmd.run()
        } else if (cmd?.insert) {
          insertAtCursor(cmd.insert, true)
        }
        return
      }
      if (e.key === 'Escape') {
        e.preventDefault()
        setSlashOpen(false)
        setSlashQuery('')
        return
      }
    }

    // §9.5 ⌘⇧P promote block to evergreen doc.
    if (e.key.toLowerCase() === 'p' && e.metaKey && e.shiftKey && onPromote) {
      e.preventDefault()
      const el = ref.current!
      const sel = value.slice(el.selectionStart, el.selectionEnd)
      const text = sel.trim() || currentParagraph(value, el.selectionStart)
      if (text) onPromote(text)
      return
    }

    // §9.5 ⌥↑/↓ move block (paragraph), ⌘D duplicate block.
    if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown')) {
      e.preventDefault()
      const el = ref.current!
      onChange(moveParagraph(value, el.selectionStart, e.key === 'ArrowUp' ? -1 : 1))
      return
    }
    if (e.key.toLowerCase() === 'd' && e.metaKey) {
      e.preventDefault()
      const el = ref.current!
      const para = currentParagraph(value, el.selectionStart)
      if (para) insertAtCursor(`\n\n${para}`)
      return
    }
  }

  function handleChange(next: string) {
    onChange(next)
    const el = ref.current
    if (!el) return
    const before = next.slice(0, el.selectionStart)
    const m = /(?:^|\s)\/([\w\s-]*)$/.exec(before)
    if (m) {
      setSlashOpen(true)
      setSlashQuery(m[1])
      setSlashIndex(0)
    } else {
      setSlashOpen(false)
    }
  }

  if (readOnly) {
    return (
      <div className={`editor editor--locked ${className ?? ''}`}>
        <Markdown text={value} />
      </div>
    )
  }

  return (
    <div className={`editor ${className ?? ''}`}>
      <textarea
        ref={ref}
        className="editor__input paper"
        value={value}
        rows={minRows}
        placeholder={placeholder}
        spellCheck
        onChange={(e) => handleChange(e.target.value)}
        onKeyDown={handleKey}
        onBlur={() => setSlashOpen(false)}
      />
      {slashOpen && filtered.length > 0 && (
        <div className="slash glass">
          {filtered.slice(0, 9).map((c, i) => (
            <button
              key={c.id}
              className={`slash__item ${i === slashIndex ? 'is-active' : ''}`}
              // mousedown, not click: blur would close the menu first.
              onMouseDown={(e) => {
                e.preventDefault()
                setSlashOpen(false)
                if (c.run) {
                  insertAtCursor('', true)
                  c.run()
                } else if (c.insert) insertAtCursor(c.insert, true)
              }}
            >
              <span className="slash__label mono">{c.label}</span>
              <span className="slash__hint">{c.hint}</span>
            </button>
          ))}
        </div>
      )}
      {savedLabel && <div className="editor__saved">{savedLabel}</div>}
    </div>
  )
}

function relativeSaved(at: number): string {
  const secs = Math.round((Date.now() - at) / 1000)
  if (secs < 3) return 'saved'
  if (secs < 60) return `saved ${secs}s ago`
  if (secs < 3600) return `saved ${Math.round(secs / 60)}m ago`
  return `saved ${relativeDays(at)}`
}

function currentParagraph(text: string, pos: number): string {
  const start = text.lastIndexOf('\n\n', Math.max(0, pos - 1))
  const end = text.indexOf('\n\n', pos)
  return text.slice(start < 0 ? 0 : start + 2, end < 0 ? text.length : end).trim()
}

function moveParagraph(text: string, pos: number, dir: -1 | 1): string {
  const paras = text.split('\n\n')
  let acc = 0
  let idx = 0
  for (let i = 0; i < paras.length; i++) {
    acc += paras[i].length + 2
    if (pos < acc) {
      idx = i
      break
    }
  }
  const target = idx + dir
  if (target < 0 || target >= paras.length) return text
  const next = [...paras]
  ;[next[idx], next[target]] = [next[target], next[idx]]
  return next.join('\n\n')
}

/* A deliberately small markdown renderer. The product's prose needs headings,
   emphasis, lists, quotes, code and entity chips — nothing else, and pulling
   in a full parser for that would be the kind of dependency §1.2 argues
   against. */
export function Markdown({ text }: { text: string }) {
  const html = useMemo(() => renderMarkdown(text), [text])
  return (
    <div
      className="prose paper measure"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

export function renderMarkdown(src: string): string {
  const lines = escapeHtml(src).split('\n')
  const out: string[] = []
  let inCode = false
  let listOpen = false

  const closeList = () => {
    if (listOpen) {
      out.push('</ul>')
      listOpen = false
    }
  }

  for (const raw of lines) {
    if (raw.trim().startsWith('```')) {
      closeList()
      out.push(inCode ? '</code></pre>' : '<pre class="mono"><code>')
      inCode = !inCode
      continue
    }
    if (inCode) {
      out.push(raw)
      continue
    }
    const line = raw.trimEnd()
    if (!line.trim()) {
      closeList()
      continue
    }
    const h = /^(#{1,3})\s+(.*)$/.exec(line)
    if (h) {
      closeList()
      const level = h[1].length + 2
      out.push(`<h${level}>${inline(h[2])}</h${level}>`)
      continue
    }
    const li = /^\s*[-*]\s+(.*)$/.exec(line)
    if (li) {
      if (!listOpen) {
        out.push('<ul>')
        listOpen = true
      }
      const task = /^\[([ x])\]\s+(.*)$/.exec(li[1])
      if (task) {
        out.push(
          `<li class="task"><span class="task__box mono">${
            task[1] === 'x' ? '☑' : '☐'
          }</span>${inline(task[2])}</li>`,
        )
      } else {
        out.push(`<li>${inline(li[1])}</li>`)
      }
      continue
    }
    if (line.startsWith('&gt;')) {
      closeList()
      out.push(`<blockquote>${inline(line.replace(/^&gt;\s?/, ''))}</blockquote>`)
      continue
    }
    closeList()
    out.push(`<p>${inline(line)}</p>`)
  }
  closeList()
  if (inCode) out.push('</code></pre>')
  return out.join('\n')
}

/** Inline entity chips: @instrument, @trade, @date, @setup, @backtest. §6.3
 *  §1.4 cross-module entity links render as inline chips. */
function inline(s: string): string {
  return s
    .replace(/`([^`]+)`/g, '<code class="mono">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(
      /@(instrument|trade|date|setup|backtest|session)\/([\w:-]+)/g,
      '<span class="entity-chip mono" data-kind="$1">$1 · $2</span>',
    )
    .replace(/@(\w[\w-]*)/g, '<span class="entity-chip mono">@$1</span>')
}
