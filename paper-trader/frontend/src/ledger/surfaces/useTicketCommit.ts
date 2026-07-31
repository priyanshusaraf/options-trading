/* Shared ticket commit — the ticket appears on the Cockpit, the Blotter and
   from Quick Capture, and all three must produce identical records. */

import { useCallback } from 'react'
import { useDB } from '../data/hooks'
import { addTrade } from '../data/actions'
import { parseTicket } from '../domain/ticketGrammar'
import { toast, useUI } from '../app/uiState'

export function useTicketCommit() {
  const db = useDB()
  const ui = useUI()

  return useCallback(
    (line: string): string | null => {
      const inst =
        db.instruments.find((i) => i.id === ui.route.instrumentId) ??
        db.instruments[0]
      const parsed = parseTicket(line, {
        instruments: db.instruments,
        playbook: db.playbook.filter((p) => !p.archived),
        defaultInstrumentId: inst.id,
        defaultQty: inst.lotSize,
        emotions: db.settings.emotions.map((e) => e.label),
      })

      // §9.6 anything ambiguous waits rather than guessing.
      if (parsed.ambiguous.length) {
        toast(`${parsed.ambiguous[0].text} — ${parsed.ambiguous[0].reason}`)
        return null
      }
      if (parsed.missing.length || parsed.direction == null || parsed.price == null) {
        toast(`Needs ${parsed.missing.join(', ')}`)
        return null
      }

      const id = addTrade({
        instrumentId: parsed.instrumentId ?? inst.id,
        date: ui.route.date,
        direction: parsed.direction,
        contract: parsed.contract ?? 'FUT',
        strike: parsed.strike,
        optionType: parsed.optionType,
        qty: parsed.qty ?? inst.lotSize,
        price: parsed.price,
        stop: parsed.stop,
        target: parsed.target,
        setupId: parsed.setupId,
        offBook: parsed.offBook,
        confidence: parsed.confidence ?? 3,
        emotionAtEntry: parsed.emotion,
      })
      toast('Trade logged', true)
      return id
    },
    [db, ui.route.instrumentId, ui.route.date],
  )
}
