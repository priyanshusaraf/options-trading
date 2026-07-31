/* Vault — §5.9, `gv`
 *
 * "A tight grid of every screenshot, 5–7 per row, grouped by session.
 *  Filterable by instrument, tag, trade attachment, and OCR text. Space peeks
 *  full-size, ⏎ opens with its parent trade in the inspector. Untagged
 *  screenshots surface first — a screenshot with no context is a note you
 *  failed to finish."
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { useArtifacts, useDB, useInstrument } from '../data/hooks'
import { navigate, peek, setCursor, setUI, toast, useUI } from '../app/uiState'
import { uploadArtifact } from '../data/idb'
import { uid } from '../domain/ids'
import {
  addArtifact,
  deleteArtifact,
  reparentArtifact,
  tagArtifact,
} from '../data/actions'
import { ScreenshotTile } from '../components/domain'
import { Button, Chip, Empty, Kbd, Tag } from '../components/primitives'
import { formatDate, formatTime } from '../domain/dates'
import { today } from '../domain/dates'
import { sessionKey } from '../data/actions'
import { registerListNav } from './listNav'
import './surfaces.css'

export function Vault() {
  const ui = useUI()
  const db = useDB()
  const inst = useInstrument(ui.route.instrumentId)
  const artifacts = useArtifacts(ui.route.instrumentId)
  const [filter, setFilter] = useState('')
  const [onlyUntagged, setOnlyUntagged] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase()
    let list = artifacts
    if (onlyUntagged) list = list.filter((a) => a.tags.length === 0)
    if (q) {
      list = list.filter(
        (a) =>
          a.name.toLowerCase().includes(q) ||
          a.ocrText.toLowerCase().includes(q) ||
          a.tags.some((t) => t.toLowerCase().includes(q)),
      )
    }
    // Untagged first, then newest. §5.9
    return [...list].sort((a, b) => {
      const au = a.tags.length === 0 ? 0 : 1
      const bu = b.tags.length === 0 ? 0 : 1
      return au - bu || b.at - a.at
    })
  }, [artifacts, filter, onlyUntagged])

  // Grouped by session, as the design specifies.
  const groups = useMemo(() => {
    const map = new Map<string, typeof filtered>()
    for (const a of filtered) {
      const key = a.sessionId ?? 'unattached'
      map.set(key, [...(map.get(key) ?? []), a])
    }
    return [...map.entries()].sort((a, b) => b[0].localeCompare(a[0]))
  }, [filtered])

  const cursorIndex = filtered.findIndex((a) => a.id === ui.cursorId)
  useEffect(
    () =>
      registerListNav({
        move: (delta) => {
          const next = Math.max(
            0,
            Math.min(filtered.length - 1, (cursorIndex < 0 ? 0 : cursorIndex) + delta),
          )
          if (filtered[next]) setCursor(filtered[next].id)
        },
        peek: () => peek(ui.cursorId),
        open: () => {
          const a = filtered.find((x) => x.id === ui.cursorId)
          if (a?.tradeId) {
            navigate({ surface: 'trade', objectId: a.tradeId })
          } else if (a) {
            setUI({ inspectorOpen: true })
          }
        },
        top: () => filtered[0] && setCursor(filtered[0].id),
        bottom: () =>
          filtered.length && setCursor(filtered[filtered.length - 1].id),
      }),
    [filtered, cursorIndex, ui.cursorId],
  )

  function onFiles(files: FileList | null) {
    if (!files || !inst) return
    for (const file of Array.from(files)) {
      // Upload the bytes FIRST, under an id we mint here, then record the
      // artifact pointing at the URL. The source read the file into a base64
      // data URL and stored it inside the snapshot, which meant every debounced
      // save rewrote every screenshot — untenable now that the snapshot goes
      // over the network. See the design spec §3.2.
      const id = uid('af')
      void uploadArtifact(id, file)
        .then((url) => {
          addArtifact({
            id,
            instrumentId: inst.id,
            sessionId: sessionKey(inst.id, ui.route.date || today()),
            // §2.3 If a trade is open, it auto-associates with that trade.
            tradeId:
              db.trades.find(
                (t) => t.instrumentId === inst.id && t.closedAt == null,
              )?.id ?? null,
            kind: 'screenshot',
            name: file.name,
            data: url,
            // §2.3 OCR'd in the background so it's searchable. Without an OCR
            // engine the field stays empty rather than being faked — the filter
            // then honestly matches on name and tags only.
            ocrText: '',
            tags: [],
          })
          toast('Screenshot added', true)
        })
        .catch(() => {
          // No record is written if the bytes did not land, so the Vault never
          // shows a thumbnail that resolves to nothing.
          toast(`Could not upload ${file.name}`)
        })
    }
  }

  if (!inst) return null

  return (
    <div className="surface">
      <div className="surface__head">
        <span className="surface__title">Vault · {inst.name}</span>
        <input
          className="blotter__query"
          value={filter}
          placeholder="filter by name, tag or OCR text"
          onChange={(e) => setFilter(e.target.value)}
        />
        <Chip
          tone={onlyUntagged ? 'attention' : 'neutral'}
          onClick={() => setOnlyUntagged((v) => !v)}
        >
          untagged only
        </Chip>
        <span className="surface__spacer" />
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          multiple
          hidden
          onChange={(e) => {
            onFiles(e.target.files)
            e.target.value = ''
          }}
        />
        <Button variant="quiet" onClick={() => fileRef.current?.click()} kbd="⌘⇧4">
          + screenshot
        </Button>
      </div>

      <div
        className="surface__body vault"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault()
          onFiles(e.dataTransfer.files)
        }}
      >
        {filtered.length === 0 ? (
          <Empty kbd="⌘⇧4">
            No screenshots yet. Drop an image anywhere on this pane.
          </Empty>
        ) : (
          groups.map(([sessionId, items]) => (
            <div className="vault__group" key={sessionId}>
              <div className="label vault__grouphead">
                {sessionId === 'unattached'
                  ? 'Unattached'
                  : formatDate(sessionId.split('|')[1] ?? '')}
                <span className="faint"> · {items.length}</span>
              </div>
              <div className="vault__grid">
                {items.map((a) => (
                  <div
                    className={`vault__cell ${
                      ui.cursorId === a.id ? 'is-cursor' : ''
                    }`}
                    key={a.id}
                    draggable
                    onDragStart={(e) => e.dataTransfer.setData('text/plain', a.id)}
                  >
                    <ScreenshotTile
                      src={a.data}
                      name={a.name}
                      untagged={a.tags.length === 0}
                      onClick={() => {
                        setCursor(a.id)
                        setUI({ inspectorOpen: true })
                      }}
                    />
                    <div className="vault__meta">
                      <span className="mono faint">{formatTime(a.at, false)}</span>
                      {a.tradeId && (
                        <button
                          className="vault__link"
                          onClick={() =>
                            navigate({ surface: 'trade', objectId: a.tradeId! })
                          }
                        >
                          trade
                        </button>
                      )}
                      <button
                        className="vault__link"
                        onClick={() => {
                          const t = window.prompt('Tag')
                          if (t) {
                            tagArtifact(a.id, t)
                            toast('Tagged', true)
                          }
                        }}
                      >
                        + tag
                      </button>
                      <button
                        className="vault__link"
                        onClick={() => {
                          deleteArtifact(a.id)
                          toast('Screenshot deleted', true)
                        }}
                      >
                        ×
                      </button>
                    </div>
                    <div className="vault__tags">
                      {a.tags.map((t) => (
                        <Tag key={t}>{t}</Tag>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              {/* §2.3 …and can be re-parented later by drag. */}
              <div
                className="vault__droptrade"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  const id = e.dataTransfer.getData('text/plain')
                  if (!id) return
                  const tradeId = window.prompt('Attach to trade id (blank to detach)')
                  reparentArtifact(id, tradeId?.trim() || null)
                  toast('Re-parented', true)
                }}
              >
                <span className="faint">
                  Drop a screenshot here to re-parent it to another trade
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

/** Inspector view for an artifact. */
export function ArtifactInspector({ id }: { id: string }) {
  const db = useDB()
  const a = db.artifacts.find((x) => x.id === id)
  if (!a) return null
  const trade = db.trades.find((t) => t.id === a.tradeId)
  return (
    <div className="insp">
      <div className="insp__head">
        <span className="mono">▣ {a.name}</span>
      </div>
      {a.data && <img className="insp__img" src={a.data} alt={a.name} />}
      <div className="insp__grid">
        <span className="label">captured</span>
        <span className="mono">{formatTime(a.at)}</span>
        <span className="label">trade</span>
        <span>
          {trade ? (
            <button
              className="td__link"
              onClick={() => navigate({ surface: 'trade', objectId: trade.id })}
            >
              open
            </button>
          ) : (
            <span className="faint">unattached</span>
          )}
        </span>
      </div>
      <div className="insp__tags">
        {a.tags.map((t) => (
          <Tag key={t}>{t}</Tag>
        ))}
      </div>
      <div className="insp__foot faint">
        <Kbd>space</Kbd> peek · <Kbd>⏎</Kbd> open parent trade
      </div>
    </div>
  )
}
