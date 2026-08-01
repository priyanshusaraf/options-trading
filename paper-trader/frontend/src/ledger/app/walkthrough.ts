/* The walkthrough's content and progress state.
 *
 * Why this exists at all: the Guide was built as a permanent 644-line reference and
 * explicitly NOT as a tour, on the principle that a tour "dismisses itself once and is
 * gone". Held for a month, the result was a journal with fourteen surfaces, a keyboard
 * grammar, and — measured on the production box on 2026-08-01 — one snapshot row, zero
 * manual fills and zero artifacts. Nobody used it, including the person who asked for it.
 *
 * The owner's verdict (2026-08-01): "the journal is still practically unusable, it's too
 * complicated and there is no real walkthrough." So the principle is reversed
 * deliberately, and narrowly:
 *
 *   • The Guide stays exactly where it is. Reference material is still reference material.
 *   • This adds the thing that was missing — a short, ordered path that says what the
 *     journal is FOR and has you do the three things that make it worth keeping.
 *   • It is RESUMABLE, not fire-and-forget: progress persists, it can be reopened from
 *     the sidebar at any time, and finishing it is not required to use anything.
 *
 * Content lives here rather than inside the component so the steps can be unit-tested —
 * a walkthrough that points at a surface which no longer exists is worse than none.
 */

export interface WalkStep {
  id: string
  title: string
  /** Why this matters — the part a feature tour usually skips. */
  why: string
  /** What to actually do, in one sentence. */
  action: string
  /** Surface this step is about, if navigating there helps. */
  surface?: string
}

export const WALKTHROUGH: WalkStep[] = [
  {
    id: 'what',
    title: 'What this is for',
    why:
      'Your broker already records what you traded. It cannot record WHY — and why is the '
      + 'only part you can actually improve. This journal exists to capture the reason at '
      + 'the moment you had it, before hindsight rewrites it.',
    action: 'Read this one screen. Everything after it takes seconds a day.',
  },
  {
    id: 'today',
    title: 'Today — the only screen you need most days',
    why:
      'Every trade the bot took, and every trade you took yourself, lands here '
      + 'automatically. You do not enter trades by hand; they are already in the ledger.',
    action: 'Open Today and look at the list. If the market has not opened yet, it is empty — that is correct.',
    surface: 'cockpit',
  },
  {
    id: 'why-entry',
    title: 'Say why you took it',
    why:
      'A reason written 30 seconds after entry is worth more than an hour of analysis a '
      + 'week later, because a week later you will reconstruct a reason that flatters you.',
    action: 'Pick any trade and write one line: what made you take it.',
    surface: 'blotter',
  },
  {
    id: 'why-exit',
    title: 'Say why you got out',
    why:
      'This is where the money is. On the production book, 45 of 72 real trades were '
      + 'closed by hand rather than by the bot\'s own exits — and nothing anywhere records '
      + 'what you were thinking when you closed them. That is the single biggest blind '
      + 'spot in the whole system.',
    action: 'On the same trade, add the exit reason. One line is enough.',
    surface: 'blotter',
  },
  {
    id: 'review',
    title: 'Look back once a week',
    why:
      'Individual trades are noise. The pattern across twenty of them is the signal — and '
      + 'you can only see it if the reasons are already written down.',
    action: 'Open Review. With a few trades logged, it starts grouping them by reason.',
    surface: 'review',
  },
  {
    id: 'rest',
    title: 'Everything else is optional',
    why:
      'Playbook, Timeline, Stats, Vault and the keyboard grammar are there when you want '
      + 'them. None of them are needed for the daily habit above, and treating them as '
      + 'required is exactly what made this feel unusable.',
    action: 'Turn on "Show every section" in the sidebar whenever you are curious. The Guide has the full reference.',
    surface: 'guide',
  },
]

const KEY = 'pt.ledger.walkthrough'

export interface WalkProgress {
  /** Index of the step to resume at. */
  step: number
  /** Finished or explicitly dismissed — controls whether it auto-opens. */
  done: boolean
}

export function loadProgress(): WalkProgress {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return { step: 0, done: false }
    const p = JSON.parse(raw)
    // Clamp: a stored index from an older, longer walkthrough must not leave the user
    // staring at a blank step.
    const step = Math.min(Math.max(0, Number(p.step) || 0), WALKTHROUGH.length - 1)
    return { step, done: Boolean(p.done) }
  } catch {
    return { step: 0, done: false }
  }
}

export function saveProgress(p: WalkProgress): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(p))
  } catch {
    /* private mode / quota — the walkthrough simply restarts next time */
  }
}

export function resetProgress(): void {
  saveProgress({ step: 0, done: false })
}
