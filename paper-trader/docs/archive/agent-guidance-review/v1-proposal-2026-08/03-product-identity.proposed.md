# PROPOSED successor to `docs/product-overview.md` — not adopted

> `docs/product-overview.md` is unchanged and remains the accepted overview until the owner says
> otherwise. It should be **retained permanently as a historical document** — it is an accurate
> and unusually honest portrait of the platform as an autonomous options bot, and that is what it
> was written to describe.
>
> This proposal exists because that document is now the single largest conflict with the V1
> product identity, in three specific ways recorded in [`00-inventory.md`](00-inventory.md) §2.7.

---

# Strategy OS — what the product is

## 1. In one paragraph

**Strategy OS is a visual, node-based platform for building trading strategies.** A trader
connects indicators, price action, conditions, instruments, reusable components, data sources
and execution rules into a graph; researches and backtests that graph against real market data
with honest, net-of-cost accounting; and then deploys and monitors it through their own broker.
Every graph version is immutable and content-addressed, so the strategy that produced a result
is the strategy that trades, and can be reconstructed from any trade.

## 2. What is underneath, and why it is not the pitch

The typed Component IR, the single resolver, research lineage, execution authority and
provenance are **machinery**. They exist to make one promise credible: *the thing you drew is
the thing that was tested, and the thing that was tested is the thing that trades.*

That promise is what most competing builders cannot make. The teardown of the strongest Indian
retail node builder (`docs/reports/2026-08-02-openalgo-competitive-teardown.md`) found a
polished 60-node canvas over an **untyped control-flow graph with a global string-keyed variable
bag**, where a typo resolves to `_UNRESOLVED` and stringifies through, and a diamond in the graph
still fires an order node twice. Their own code comment records the symptom: *"two orders from
one crossover."*

Here, a socket is typed on value × structure × domain and an ill-typed edge is refused before it
can be saved; a graph is a dataflow graph, not a control-flow walk; and a node's identity is the
content address of its body. That is why the machinery is worth its cost — and why it belongs in
the second paragraph of the pitch, not the first.

## 3. The differentiators that are actually differentiating

1. **Typed graphs, refused early.** An instrument mismatch on an edge is a *type error*, caught
   at authoring: `"F7 … 'NIFTY' does not match 'SENSEX'; the domain is part of the type"`. The
   accidental version of the most dangerous thing a multi-instrument builder can do fails closed
   by construction.
2. **Immutable, content-addressed versions bound to their evidence.** Every experiment carries
   the graph version, every resolved component version, node identities and a data digest —
   *derived from resolution, never supplied by a caller* (F14). Given a trade, the exact graph
   that produced it is recoverable.
3. **Research approval is admission, not marketing.** A graph reaches an execution book by
   passing statistical gates and an explicit, immutable, once-consumed approval (ADR 0013). It
   cannot be promoted by a config row.
4. **Composition is free and already proven.** A selection of nodes becomes a reusable component
   whose body reproduces the *exact* content address it had inline, and re-resolves to
   byte-identical node and cache ids. Reuse is not a feature bolted on; it is the same mechanism
   as the language.
5. **Net-of-everything accounting, reconciled to the paisa.** A segment-aware Indian cost model
   (brokerage, STT/CTT, exchange and regulatory fees, GST, stamp duty) applies to every figure
   the platform reports, and a headless check asserts the ledger reconciles exactly.
6. **A safety architecture that survived real money.** Paper-by-default is structural, not a
   toggle: the data client physically disables every order route, live requires three aligned
   gates plus a per-session ARM that resets on restart, paper and live are separate *books* that
   fail closed to the stricter one, and a source of logic gains the right to execute at exactly
   one reviewed line.

## 4. Where it is going, and what the architecture already allows

Two capabilities define the category the product is aiming at:

```
NIFTY options + NIFTY futures + India VIX   →   trade SENSEX
Upstox market data   →   Strategy OS graph  →   Zerodha execution
```

Neither is delivered today. Both are **bounded extensions, not redesigns**, and the reasons are
measured rather than asserted (`docs/engineering/reference/architecture-extension-review-2026-08-07.md`):

- Instrument identity is already part of the type system; multi-domain *composition* is not
  implemented, and the runtime is domain-blind in one file.
- Market-data provider and execution broker were **never one interface** —
  `MarketDataProvider` and `Broker`/`ExecutionVenue` are separate seams already.
- Money attribution is already keyed on the *traded* instrument, so observing more instruments
  does not disturb it.

What must be built for them is stated honestly in
[`02-v1-classification.md`](02-v1-classification.md) §2.2 and §1.3, including the parts that are
money-path changes and therefore owner-gated.

## 5. What is true today — stated plainly

**Built and verified** (committed; see `docs/PROGRESS.md` for the current list): the Component
IR — format, validator, single resolver, runtime, experiment binding — with all 29 normative RFC
clauses enforced by tests, each proven able to fail; a visual editor with durable semantic
authoring, separately revisioned presentation state, undo/redo and lossless reload; a research
plane with immutable graph runs, evidence, findings, operation receipts, comparison, daily
review and immutable snapshots; managed shadow and **paper-authoritative** IR deployments with
verified content addresses, evidence lineage and deterministic reload; separated execution
books; and canonical execution binding and attribution.

**Running for real:** a hand-written strategy on a Bangalore VPS, trading the owner's own
capital since 2026-06-29, with 72 live trades booked as of 2026-08-01. Strategy OS does not
control it. `(ir_graph, live, authoritative)` is absent from the authority grants and is
designed nowhere.

**Not built:** accounts and multi-tenancy (auth today is one shared bearer token); any broker
other than Zerodha Kite; payments; canonical instrument identity across providers; multi-instrument
runtime; multi-leg intent; packaging and marketplace; typed non-OHLCV data sources.

**Not proven:** the economics. There is no verified, statistically established, net-of-cost edge
on the traded instrument. Across 72 live trades `TARGET` has fired zero times, and the median
trade travels further against the position than for it. The platform's honest position is that
it is *rigorous measurement infrastructure for an open question* — and that a visual builder
makes the question easier to ask, not easier to answer. Research, backtesting and admission are
how the answer gets pursued; nothing about the canvas substitutes for it.

## 6. Who it is for

A quantitatively literate trader or small desk on Indian markets who wants to build systematic
strategies visually without giving up backtest honesty, execution discipline or ownership of
their broker relationship — and who would rather see a rejected wire and an exact rejection
reason than a plausible dashboard.

Not for: anyone wanting a proven money-maker (the edge is unproven and stated so); anyone
needing institutional multi-account or high-availability infrastructure today; anyone outside
the Indian market structure, since the cost model, instrument handling and broker integrations
are India-specific.

## 7. What this document is not

Not a plan and not a schedule. Product sequence lives in
`docs/engineering/EXECUTION_PLAN.md`; current state lives in `docs/PROGRESS.md`; the resume
point lives in `docs/CONTINUE.md`. Where this document and any of those disagree, **they win and
this document is the defect** — which is precisely the failure mode that made the previous
overview stale in three places at once.
