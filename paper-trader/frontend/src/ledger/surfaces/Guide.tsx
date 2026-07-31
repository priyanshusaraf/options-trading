/* Guide — `g u`
 *
 * The walkthrough, in the app rather than beside it.
 *
 * This is deliberately NOT an onboarding tour, which CLAUDE.md lists as an
 * anti-feature: no coach marks, no scrim, no forced sequence, nothing that
 * dismisses itself once and is gone. It is a permanent surface, reachable at
 * any time from the sidebar, the palette and `g u`, and it is the only place
 * in the product that explains *why* rather than *what*.
 *
 * What earns it a place instead of a README: every keystroke in it is live.
 * `<Run>` renders a real key cap that executes the real command out of the
 * one registry in `src/keys/commands.ts` — so the guide cannot drift from the
 * keymap, for the same reason the palette cannot. Reading it and using it are
 * the same act.
 *
 * Material: paper, serif, 68ch, chapter rail on the left — the Session Review
 * frame (§5.8), because this is prose to be read, not data to be scanned.
 */

import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { buildCommands } from '../keys/commands'
import { navigate, toast, useUI } from '../app/uiState'
import { useDB, useInstrument } from '../data/hooks'
import { Kbd, Rule } from '../components/primitives'
import './guide.css'

/* ── Live key caps ────────────────────────────────────────────────────────
 * A key cap that runs its command. The label is the keystroke; the action is
 * looked up by command id, so a rebinding in the registry changes both. */

function Run({ id, children }: { id: string; children: ReactNode }) {
  const commands = useMemo(() => buildCommands(), [])
  const cmd = commands.find((c) => c.id === id)
  return (
    <button
      className="guide__run"
      title={cmd ? `${cmd.title} — runs now` : 'Unknown command'}
      onClick={() => {
        if (!cmd) return toast('That command no longer exists')
        cmd.run()
      }}
    >
      <Kbd>{children}</Kbd>
    </button>
  )
}

/** A key cap that is being *described*, not offered — `j`/`k`, or a chord that
 *  only means something on another surface. Never clickable, so the guide
 *  never presents a control that would do nothing. */
function Key({ children }: { children: ReactNode }) {
  return <Kbd>{children}</Kbd>
}

function Chapter({
  id,
  n,
  title,
  children,
}: {
  id: string
  n: number
  title: string
  children: ReactNode
}) {
  return (
    <section className="guide__chapter" id={`guide-${id}`} data-chapter={id}>
      <h2 className="guide__h2">
        <span className="guide__n mono">{String(n).padStart(2, '0')}</span>
        {title}
      </h2>
      {children}
    </section>
  )
}

const CHAPTERS = [
  { id: 'open', title: 'There is no login screen after this one' },
  { id: 'frame', title: 'The frame you never leave' },
  { id: 'modes', title: 'The app knows what time it is' },
  { id: 'morning', title: 'The morning, and the lock' },
  { id: 'live', title: 'During the session' },
  { id: 'evening', title: 'The evening' },
  { id: 'long', title: 'The surfaces that pay off in months' },
  { id: 'machinery', title: 'The machinery underneath' },
  { id: 'refuses', title: 'What it refuses to do' },
  { id: 'ninety', title: 'Ninety seconds' },
]

export function Guide() {
  const ui = useUI()
  const db = useDB()
  const inst = useInstrument(ui.route.instrumentId)
  const [active, setActive] = useState(CHAPTERS[0].id)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Chapter rail follows the reading position. Observing the sections is
  // cheaper and steadier than measuring on every scroll event.
  useEffect(() => {
    const root = scrollRef.current
    if (!root) return
    const seen = new Map<string, number>()
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          const id = (e.target as HTMLElement).dataset.chapter!
          seen.set(id, e.intersectionRatio)
        }
        let best: string | null = null
        let bestRatio = 0
        for (const [id, ratio] of seen) {
          if (ratio > bestRatio) {
            bestRatio = ratio
            best = id
          }
        }
        if (best) setActive(best)
      },
      { root, threshold: [0, 0.25, 0.5, 0.75, 1] },
    )
    root.querySelectorAll('[data-chapter]').forEach((el) => io.observe(el))
    return () => io.disconnect()
  }, [])

  function jump(id: string) {
    const el = document.getElementById(`guide-${id}`)
    el?.scrollIntoView({ block: 'start' })
  }

  const tradeCount = db.trades.filter((t) => !t.deletedAt).length
  const setupCount = db.playbook.filter((p) => !p.archived).length

  return (
    <div className="guide">
      {/* Chapter rail — the Review surface's progress rail, reused. */}
      <nav className="guide__rail" aria-label="Chapters">
        {CHAPTERS.map((c, i) => (
          <button
            key={c.id}
            className={`guide__railitem ${active === c.id ? 'is-active' : ''}`}
            onClick={() => jump(c.id)}
          >
            <span className="guide__railn mono">{String(i + 1).padStart(2, '0')}</span>
            <span className="guide__railtitle">{c.title}</span>
          </button>
        ))}
      </nav>

      <div className="guide__scroll" ref={scrollRef}>
        <div className="guide__col">
          <header className="guide__head">
            <h1 className="guide__h1">THE LEDGER</h1>
            <p className="guide__lede">
              A trading journal built on one idea: that what you believed before
              the market answered is a different kind of fact from what
              happened, and a journal that lets you edit the first one after
              learning the second is not a journal.
            </p>
            <p className="guide__meta mono">
              Every key cap below is live. Click it and it runs.
              <br />
              This page is permanent — <Run id="go-guide">g u</Run> returns here
              from anywhere.
            </p>
          </header>

          <Chapter id="open" n={1} title="There is no login screen after this one">
            <p>
              The gate you just passed records that you meant to open this
              workspace. Behind it there is no account, no server and no network
              call. The journal lives in this browser’s IndexedDB and never
              leaves the machine.
            </p>
            <p>
              Which is why this device did not start empty. A journal with no
              history cannot demonstrate the one thing this product is built to
              do — refuse to show you a number it has too little evidence for.
              So a working journal was seeded: five instrument workspaces,{' '}
              <strong>{setupCount} playbook setups</strong> and{' '}
              <strong>{tradeCount} trades</strong> of history
              {inst ? <>, opened on {inst.name}</> : null}.
            </p>
            <p>
              The sample sizes in that playbook are uneven on purpose. Two of
              the setups sit at n=14 and n=9, below the evidence threshold, and
              the app will show you <code className="mono">░░░ n=9</code> and no
              number at all. You are meant to hit that wall in the first two
              minutes. <Run id="go-playbook">g p</Run>
            </p>
            <p className="guide__aside">
              When you have your own history, replace the seed from Settings →
              Danger. Everything here is yours to delete.
            </p>
          </Chapter>

          <Chapter id="frame" n={2} title="The frame you never leave">
            <p>
              Every surface lives in one frame, and none of it resizes. That is
              a position, not an oversight: fixed geometry is what lets muscle
              memory form. There are four widths in the entire product.
            </p>
            <pre className="guide__ascii mono">{`┌──┬───────────────┬──────────────────────────┬─────────────┐
│ I│  CONTEXT      │   breadcrumb        ⌘K   │  INSPECTOR  │
│ N│  SIDEBAR      │                          │   (⌘.)      │
│ S│               │      CONTENT PANE        │             │
│ T│  ── pinned ── │                          │             │
│ R│  Queries      ├──────────────────────────┤             │
│  │  Levels       │ ● synced  PREP  n=142 …  │             │
└──┴───────────────┴──────────────────────────┴─────────────┘
  48px    216px            flexible               380px`}</pre>
            <p>
              <strong>The rail</strong> is one tile per instrument.{' '}
              <Key>⌘1</Key>–<Key>⌘9</Key> jumps between them; drag reorders and
              the order persists. Switching instruments switches the whole
              workspace — levels, playbook, notebook, regime.
            </p>
            <p>
              <strong>The sidebar</strong> (<Run id="toggle-sidebar">⌘\</Run>)
              prints each destination’s keystroke next to its label, so it
              teaches you to stop needing it.
            </p>
            <p>
              <strong>The inspector</strong> (<Run id="toggle-inspector">⌘.</Run>
              ) is detail for whatever the cursor is on. Never a different app.
            </p>
            <p>
              <strong>The status bar</strong> carries a local-save dot, the
              mode, and the one that matters — the{' '}
              <strong>sample size of the current view</strong>. You can never
              read a screen here without knowing how much it rests on.
            </p>
          </Chapter>

          <Chapter id="modes" n={3} title="The app knows what time it is">
            <p>
              There are no morning screens and evening screens. There are three
              modes, and the app picks one from the instrument’s session clock.
              Choose manually and your choice wins until you change instrument.
            </p>
            <ul className="guide__modes">
              <li>
                <Run id="mode-prep">⌘⇧1</Run> <strong>Prep</strong> — the
                Cockpit becomes a writing surface with market context beside it.
              </li>
              <li>
                <Run id="mode-live">⌘⇧2</Run> <strong>Live</strong> — analytics
                leave. P&amp;L collapses to a glyph. What remains is the ticket,
                the observation stream, your levels and your invalidations.
              </li>
              <li>
                <Run id="mode-review">⌘⇧3</Run> <strong>Review</strong> — the
                evening surfaces come forward.
              </li>
            </ul>
            <p>
              Live mode hiding your P&amp;L is not a gimmick. It removes the
              number you would otherwise stare at instead of the market.{' '}
              <Run id="toggle-pnl">⌘E</Run> reveals it when you genuinely need
              it.
            </p>
          </Chapter>

          <Chapter id="morning" n={4} title="The morning, and the lock">
            <p>
              <Run id="go-today">g d</Run> is home. In Prep it is mostly prose: a
              thesis, your levels, the day’s macro events, positions carried
              over, anything left unresolved yesterday.
            </p>
            <p>
              You write a thesis. You add <strong>scenarios</strong> — A, B, C —
              and each one needs an <strong>invalidation</strong>: the specific
              thing that would prove it wrong. Then you lock it.
            </p>

            <div className="guide__lock">
              <Rule>The thesis lock</Rule>
              <p>
                This is the mechanic the product is built around, and{' '}
                <strong>
                  the only confirmation dialog that exists anywhere in the app
                </strong>
                .
              </p>
              <p>
                Before it seals, the lock checks your work and speaks in
                directions rather than errors:
              </p>
              <ul className="guide__blockers">
                <li>Can’t lock — the thesis is empty.</li>
                <li>Can’t lock — a thesis needs at least two scenarios.</li>
                <li>Can’t lock — scenario B has no invalidation level.</li>
              </ul>
              <p>
                Two scenarios minimum, every one with an invalidation — with a
                single carve-out: a scenario named{' '}
                <em>“Chop, no trade”</em> may have none, because standing aside
                is already a complete thought.
              </p>
              <p>
                Once it seals, your belief is <strong>frozen</strong>. From that
                moment one operation can touch the session: append. You can add.
                You can never revise.
              </p>
              <p className="guide__aside">
                That is the whole difference between a record and a hindsight
                machine, and it is why this dialog is the one thing in the
                product that undo does not reach.
              </p>
            </div>
          </Chapter>

          <Chapter id="live" n={5} title="During the session">
            <p>
              <Run id="new-trade">T</Run> opens the ticket. You type a trade the
              way you would say it:
            </p>
            <pre className="guide__ascii mono">{`bnf 52200ce b 60 @248.5 orb c4 fomo
│   │       │ │   │      │   │  └ emotion
│   │       │ │   │      │   └ confidence 1–5
│   │       │ │   │      └ setup shortcode
│   │       │ │   └ price
│   │       │ └ quantity
│   │       └ direction
│   └ strike + type (or FUT / EQ)
└ instrument`}</pre>
            <p>
              The parser classifies tokens <strong>by shape, not position</strong>
              , so <code className="mono">b bnf 60 @248.5</code> parses too —
              because that is what you actually type at 09:34. Omissions fall
              back to workspace defaults. Anything ambiguous highlights that one
              token and waits. <strong>No dialog ever appears.</strong>
            </p>

            <Rule>Quick capture</Rule>
            <p>
              <Run id="capture">⌘⇧Space</Run> is one field over a dimmed shell.
              Type, <Key>⏎</Key>, gone. It infers the rest:
            </p>
            <table className="guide__table">
              <tbody>
                <tr>
                  <td className="mono">banks leading, index lagging</td>
                  <td>an observation</td>
                </tr>
                <tr>
                  <td className="mono">! chased the third entry</td>
                  <td>a mistake note</td>
                </tr>
                <tr>
                  <td className="mono">? is ORB regime-dependent</td>
                  <td>a question to answer later</td>
                </tr>
                <tr>
                  <td className="mono">t bnf fut b 30 @52180</td>
                  <td>a trade — opens the ticket</td>
                </tr>
                <tr>
                  <td className="mono">@cl crude bid thinning</td>
                  <td>routes to the Crude workspace instead</td>
                </tr>
              </tbody>
            </table>
            <p>
              It never asks a question. Observations die within ninety seconds
              of occurring, and this feature is built against that clock.
            </p>

            <Rule>Rules that fire while you work</Rule>
            <p>
              These live in the data layer, never in a component, so no future
              screen can route around them:
            </p>
            <ul className="guide__rules">
              <li>
                <strong>Risk envelope.</strong> Max trades, max loss in R, max
                concurrent positions. Breaching it does not block the trade — it{' '}
                <em>auto-tags</em> it. The journal records that you did it.
              </li>
              <li>
                <strong>Setup attribution is mandatory.</strong> A trade with no
                playbook setup is marked <strong>off-book</strong>, and the
                Playbook tracks off-book trades as their own group with their
                own statistics. You will find out what your improvisation is
                worth.
              </li>
              <li>
                <strong>No thesis, tagged.</strong> Trading a session you never
                wrote a thesis for is recorded as such.
              </li>
              <li>
                <strong>Regime is inherited at trade timestamp</strong>, not at
                review time, so a regime change mid-session splits your trades
                correctly.
              </li>
            </ul>
          </Chapter>

          <Chapter id="evening" n={6} title="The evening">
            <p>
              <Run id="go-review">g r</Run> — full width, single column, serif,
              no chrome but a progress rail. The warmest surface in the product,
              because it is the one you open at 15:35 after a losing day.
            </p>
            <ol className="guide__steps">
              <li>Reconcile — do the fills match what happened</li>
              <li>Grade each trade — on execution, not outcome</li>
              <li>MFE / MAE — how far it went for you, and against</li>
              <li className="is-reveal">
                Reveal <span className="guide__pointer">← the P&amp;L appears here, and not a step earlier</span>
              </li>
              <li>One line for tomorrow</li>
            </ol>
            <p>
              The mask over steps 1–3 is enforced in the surface and re-arms
              every time a review is opened. You grade your decisions before you
              know what they paid. That ordering is the entire argument.
            </p>
            <p>
              Step 2 is also where the <strong>thesis diff</strong> appears: what
              you believed at lock, beside what happened, each scenario marked
              resolved or invalidated.
            </p>
          </Chapter>

          <Chapter id="long" n={7} title="The surfaces that pay off in months">
            <p>
              These are thin on day one and hard to argue with on day two
              hundred.
            </p>

            <dl className="guide__surfaces">
              <dt>
                <Run id="go-trades">g t</Run> Trades
              </dt>
              <dd>
                A real keyboard-driven grid. <strong>R is the primary column,
                not P&amp;L</strong> — you can toggle to ₹, but the default is
                teaching an instinct. Group by setup, weekday, regime, emotion or
                mistake; filter in a real query language (
                <code className="mono">setup:orb regime:trend r:&lt;0</code>).
                <Key>j</Key> <Key>k</Key> <Key>space</Key> <Key>⏎</Key>{' '}
                <Key>x</Key> behave identically on every list in the app.
              </dd>

              <dt>Trade Detail</dt>
              <dd>
                Three columns, and the split is philosophical:{' '}
                <strong>Fact</strong> (glass — cold, mono, hairline) │{' '}
                <strong>Narrative</strong> (paper) │{' '}
                <strong>Judgement</strong> (paper). Fills and realised R are
                immutable, the thesis is locked, and your grades and lessons stay
                editable forever. You can see at a glance which parts were
                written before the market answered.
              </dd>

              <dt>
                <Run id="go-playbook">g p</Run> Playbook
              </dt>
              <dd>
                Where the product’s opinion is strongest: a setup you cannot
                define in two sentences is not a setup, it is a mood. Expanded,
                each shows its definition, its invalidation, its R distribution,
                performance split by regime and weekday, its{' '}
                <strong>worst five trades</strong>, and an{' '}
                <strong>edit history</strong> — so you can see when you changed
                the rules and whether it helped.
              </dd>

              <dt>
                <Run id="go-stats">g s</Run> Research Bench
              </dt>
              <dd>
                Not a dashboard. A fixed workbench of analyses — two ledgers, R
                distribution, expectancy grid, calibration, decision × outcome,
                thesis accuracy, exit quality, mistake ledger, adherence,
                behavioural sequences, instrument comparison, weekday and
                time-of-day. Each states its own n and interval and carries a
                plain-language “what this would change” line. Every one is
                expressible as a query, so any interesting cell drills straight
                into a filtered blotter.
              </dd>

              <dt>
                <Run id="go-timeline">g l</Run> Timeline
              </dt>
              <dd>
                Three zooms on one surface. Year: one cell per session, fill = R,
                amber border if unreviewed. Month: one row per session — reading
                a month in ten seconds is the point. Day: the stream expanded.
              </dd>

              <dt>
                <Run id="go-notebook">g n</Run> Notebook
              </dt>
              <dd>
                The living research document — evergreen docs on the left, paper
                editor at 68ch on the right, with backlinks and version history.
                The mechanic that makes it fill itself is{' '}
                <strong>promotion</strong>: a throwaway observation from a
                Tuesday becomes a permanent doc once it turns out to be a real
                idea.
              </dd>

              <dt>
                <Run id="go-vault">g v</Run> Vault
              </dt>
              <dd>
                Every screenshot, grouped by session.{' '}
                <strong>Untagged screenshots surface first</strong> — a
                screenshot with no context is a note you failed to finish.
              </dd>

              <dt>
                <Run id="search">⌘⇧F</Run> Search
              </dt>
              <dd>
                Query bar, facet rail, grouped results. Facet counts are{' '}
                <strong>exact, not estimated</strong> — “14 trades tagged
                early-exit in Q2” is a number you can quote.
              </dd>
            </dl>
          </Chapter>

          <Chapter id="machinery" n={8} title="The machinery underneath">
            <p>
              Four things run under every surface and explain most of what you
              have just read.
            </p>
            <p>
              <strong>Undo is total.</strong> Every mutation snapshots first, so{' '}
              <Run id="undo">⌘Z</Run> undoes anything and a toast says what it
              undid. That is precisely <em>why</em> there are no confirmation
              dialogs — you need not be asked when nothing is irreversible.
              Except the lock, which is irreversible on purpose, and is
              therefore the one thing you are asked about.
            </p>
            <p>
              <strong>Three layers, never conflated.</strong> Belief (locked at
              commit, append-only after) · Fact (immutable) · Judgement
              (editable forever). Every field in the schema is annotated with
              its layer, and the layer decides both mutability and material —
              glass or paper.
            </p>
            <p>
              <strong>No bare numbers.</strong> The metrics engine never returns
              one. Everything carries its n, an interval and an evidence state,
              and below the threshold the UI renders the sample size and no
              number. One component renders metrics and it accepts a statistic
              rather than a number, so the discipline cannot be bypassed by
              accident.
            </p>
            <p>
              <strong>Commands are defined once.</strong> One registry feeds the
              keymap, the palette and this page — which is why{' '}
              <Run id="palette">⌘K</Run> and <Run id="shortcuts">?</Run> are the
              documentation, and why the key caps you have been clicking cannot
              go stale.
            </p>
          </Chapter>

          <Chapter id="refuses" n={9} title="What it refuses to do">
            <p>
              Worth stating, because the refusals are as designed as the
              features.
            </p>
            <p>
              No live P&amp;L ticker in the chrome. No streaks, no XP. Win rate
              is never a headline metric. No social feed, no leaderboard. No
              auto-generated “insights” asserting causation — the Research Bench
              surfaces <strong>questions and sample sizes</strong>, never
              conclusions. No configurable dashboards. No pie, donut, gauge or 3D
              charts. No onboarding tour, which is why this page is a permanent
              surface you chose to open rather than a sequence that ambushed you
              on first run.
            </p>
            <p>
              Colour is semantic only: green and red appear on signed numbers,
              direction glyphs and R meters — never on backgrounds or buttons.
              Amber means one thing, unresolved or breached or invalidated.
              Direction is always <em>also</em> a glyph (▲▼), never hue alone.
            </p>
            <p>
              Every component here had to answer one question:{' '}
              <strong>what decision does this change?</strong>
            </p>
          </Chapter>

          <Chapter id="ninety" n={10} title="Ninety seconds">
            <p>Read nothing else. Run these in order.</p>
            <ol className="guide__try">
              <li>
                <Run id="shortcuts">?</Run> the whole keymap
              </li>
              <li>
                <Run id="go-today">g d</Run> the Cockpit, on a real session
              </li>
              <li>
                <Run id="mode-live">⌘⇧2</Run> Live mode — watch the analytics
                leave
              </li>
              <li>
                <Run id="capture">⌘⇧Space</Run> type{' '}
                <code className="mono">! chased the third entry</code>
              </li>
              <li>
                <Run id="new-trade">T</Run> type{' '}
                <code className="mono">bnf 52200ce b 60 @248.5 orb c4</code>
              </li>
              <li>
                <Run id="go-playbook">g p</Run> expand Event fade — n=9, and no
                number
              </li>
              <li>
                <Run id="go-stats">g s</Run> read a “what this would change”
                line
              </li>
              <li>
                <Run id="go-review">g r</Run> try to reach the P&amp;L before
                step 4
              </li>
              <li>
                <Run id="undo">⌘Z</Run> undo the last thing you did
              </li>
            </ol>
            <p className="guide__aside">
              You will land on another surface. <Run id="go-guide">g u</Run>{' '}
              brings you back, always.
            </p>
          </Chapter>

          <footer className="guide__foot">
            <button className="guide__begin" onClick={() => navigate({ surface: 'cockpit' })}>
              Begin — open today’s Cockpit
              <Kbd>g d</Kbd>
            </button>
          </footer>
        </div>
      </div>
    </div>
  )
}
