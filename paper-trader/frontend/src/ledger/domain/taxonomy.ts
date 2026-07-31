/* Taxonomies — §3.3. User-editable, schema-versioned.
   These are seeds, not fixtures: Settings owns the live lists. */

import type { RegimeState, TaxonomyItem } from './types'

const item = (label: string): TaxonomyItem => ({
  id: label,
  label,
  retired: false,
})

/** §3.3 A flat, deliberately short list you curate. Each mistake accumulates
 *  frequency *and* attributable rupee cost. */
export const SEED_MISTAKES: TaxonomyItem[] = [
  'early-entry',
  'late-entry',
  'no-thesis',
  'off-book',
  'oversized',
  'moved-stop',
  'early-exit',
  'held-past-invalidation',
  'revenge',
  'over-limit',
  'chased',
  'averaged-down',
  'ignored-event',
].map(item)

/** §3.3 Recorded pre-trade where possible and again in review; the delta
 *  between the two is itself informative. */
export const SEED_EMOTIONS: TaxonomyItem[] = [
  'calm',
  'fomo',
  'fear',
  'greed',
  'bored',
  'tilt',
  'impatient',
  'hesitant',
  'confident',
  'distracted',
].map(item)

export const REGIMES: RegimeState[] = [
  'trending',
  'range',
  'expansion',
  'compression',
  'event-driven',
]

/** Mistakes the system applies on its own. They are never silently removed. */
export const AUTO_MISTAKES = {
  /** §1.2 A trade with no pre-commitment is not an error — it is logged and
   *  tagged, which is a statistic you will eventually want to see. */
  noThesis: 'no-thesis',
  /** §0.4 "off-book" is itself a tracked behaviour. */
  offBook: 'off-book',
  /** §2.2.4 When breached, every new trade gets auto-tagged. */
  overLimit: 'over-limit',
} as const

/** §5.2 Default document set, created per instrument, all editable. */
export const SEED_DOCS: { title: string; body: string }[] = [
  {
    title: 'Market opinion',
    body: 'Current view on this instrument. What do you believe, and what would change your mind?',
  },
  {
    title: 'Regime',
    body: 'Current state plus a dated log of every regime change and why.',
  },
  {
    title: 'Levels',
    body: 'The canonical ladder. The Cockpit view is a projection of this.',
  },
  { title: 'Volatility notes', body: '' },
  { title: 'Macro & events', body: '' },
  { title: 'Recurring observations', body: '' },
  { title: 'Things I have learned', body: '' },
  {
    title: 'Mistakes I keep making',
    body: 'A live index of every trade tagged with these mistakes, with aggregate cost.',
  },
  { title: 'Strategy ideas', body: '' },
  { title: 'Watchlist', body: '' },
]

/** §6.3 TemplatePicker — morning, review, weekly, monthly. */
export const TEMPLATES: Record<string, string> = {
  morning: `## Overnight developments

## What changed since yesterday

## What would make me wrong today
`,
  review: `## What I got right

## What I got wrong

## What I would do differently
`,
  weekly: `## The week in one paragraph

## What the evidence says

## What I am changing
`,
  monthly: `## Three months ago I believed

## I now believe

## What actually changed my mind
`,
  checklist: `- [ ] Regime confirmed
- [ ] Level respected on retest
- [ ] Event risk checked
- [ ] Size within envelope
`,
}
