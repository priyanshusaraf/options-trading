# The pricing plane — IV vs RV, and a user-authored pricing engine

**Date:** 2026-08-10
**Status:** captured, **not scheduled**. Deliberately marked **post-v1** by the owner.
**Why this file exists:** the idea arrived as one night's notes. Written down with its
dependencies so it is deferred rather than forgotten, and so nobody starts it early.

---

## 1. The reframe that makes it worth building

The owner's original doubt was correct and should be preserved: **the options pricing tool is
not a predictor.** Black-Scholes does not tell you what an option is worth. Markets are not
wrong because BS disagrees with them, and a tool sold on that premise is selling a
misunderstanding.

What it *is* is a **measurement of disagreement**. `bs_price` produces the price implied by a
volatility assumption; the market produces a price. The gap between them is a number, it is
observable in real time, and it is a legitimate input to a strategy — as a signal, a filter, or
a risk gate. Framed as measurement rather than prediction, the feature is honest and the user
decides what the disagreement means.

That reframing is also what makes **IV vs RV** the right axis. Implied volatility is what the
market is charging for uncertainty; realised volatility is what actually happened. Their spread
is the same measurement with the ambiguity removed from the name.

## 2. What already exists — this is not a greenfield feature

| Piece | Where | State |
|---|---|---|
| Black-Scholes price | `app/options/pricing.py::bs_price` | built |
| Implied-vol solver | `app/options/pricing.py::implied_vol` | built, **and consumed** |
| Greeks / delta | `pricing.py::bs_greeks`, `bs_delta` | built |
| Microstructure gates | `app/options/picker.py:54-60` | built and live |

`picker.py:50` already solves implied vol **from the real market premium** and refuses any
contract where the solve fails. So the machinery for "compare BS to the market" is present; what
is missing is the realised-vol side, the spread as a first-class series, and any way for a user
to author their own model.

**Do not rebuild any of the above.** The reuse order applies (`CLAUDE.md`): Strategy OS itself
first, and Strategy OS already has the pricing kernel.

## 3. The three-tier shape

**Tier 1 — our engine, gated.** Ships as-is, behind entitlement. The owner's decision, and the
right one: a retail user trading futures, MTF or cash intraday has no use for an option-pricing
terminal, and giving it to them is cost without value. Gate it, sell it or grant it in
conversation.

**Tier 2 — the user's own engine, imported.** A user who believes they have a pricing edge
supplies the model. This is the differentiator; nobody in the retail Indian market offers it.

**Tier 3 — the engine built from nodes.** The long-term form, and the one consistent with the
product identity: pricing becomes a graph like everything else. **Explicitly last** — it needs
the Component IR to be settled, and RFC 0001 is still pending acceptance.

## 4. Answering the bloat concern directly

The owner's concern — "this might bloat the app and hurt our performance metrics" — is right to
raise and resolves into three separate costs, not one. They must not be argued as a single
question:

1. **Runtime cost on the hot path.** Real. A per-tick IV solve across a chain is Newton
   iterations per contract per tick. **Contained by construction:** the pricing plane is opt-in
   per deployment, so a futures-only user pays nothing. A user who enables it pays for it. This
   is the cost the concern is actually about and it is answerable with a benchmark, not an
   opinion.
2. **Surface-area cost.** Real and permanent. Every capability is a thing to support, document
   and keep correct. This is the argument for tiers 2 and 3 arriving late, not for tier 1
   changing.
3. **Cost of the code merely existing.** Near zero. `pricing.py` is a pure module; unused, it
   costs an import. Conflating this with (1) is what makes "bloat" feel bigger than it is.

**No unconditional work on the shared tick path.** That is the invariant this whole feature must
respect, and it is the one the 2026-07-23 outage was about (a poll doing full-table scans took
the engine down). Whatever ships here is per-deployment and skipped when disabled.

## 5. The owner's microstructure insight — keep it, and it generalises

> "the bid-ask spreads implied by options could actually tell more about liquidity premiums and
> signal further liquidity implications for generally liquid securities too"

This is the most immediately valuable idea in the set and it is **not** an options feature. The
option chain's spread and OI are a read on the *underlying's* liquidity, available to a strategy
that trades the future or the cash. `picker.py`'s gates already compute exactly these numbers and
throw them away outside the option-selection path.

Exposing them as an observable series usable by a non-options strategy is small, reuses live
code, and is the one part of this document that could be scheduled independently of the rest.
Worth pulling forward if a slot opens — but it still waits behind v1.

## 6. Hard dependencies — why this cannot start now

- **User-supplied code is a sandbox problem, and the sandbox exists.**
  `research/strategy/builder/validate.py` is a fail-closed AST allow-list with no-builtins exec.
  Tier 2 must route through it. Widening it for numerical libraries is a security decision, not a
  convenience — treat any widening as its own reviewed slice.
- **Entitlement does not exist.** Gating tier 1 needs phase 10 (authentication, resource
  ownership, cross-account isolation). Without it "gated" means an env flag, which is a
  configuration, not a product boundary.
- **Tier 3 needs RFC 0001 accepted.** A pricing node is a component; a second component model
  invented here would be disqualifying under the architecture review's own rule.
- **Realised vol needs a decided estimator.** Close-to-close, Parkinson and Garman-Klass give
  different answers on the same bars. Shipping one silently makes the IV−RV spread unreadable
  across users. This is a research-plane question and should be answered there first.

## 7. Frontend

**Owner gate #7 — the owner takes the frontend directly.** Requirements only, no code:

- an options page where the chain is shown with, per contract, market premium, BS price at the
  chosen vol input, the spread between them, solved IV, realised vol over a selectable window,
  and IV−RV;
- a visible selector for *which* engine produced the numbers (ours / the user's), because a
  number whose model is unnamed is not interpretable;
- the microstructure columns (OI, spread %) available to non-options strategies too, per §5;
- realised-vol estimator named on screen wherever RV appears, per §6.

Backend work stops at the API boundary. No endpoint is specified here either, because none should
be built until §6 clears.

## 8. What this is not

Not a plan, not a schedule, and not an estimate. It is the idea recorded with its reasoning and
its blockers, so that when v1 is done the work starts from here rather than from memory. The
performance question in §4.1 is stated as answerable, **not answered** — no benchmark has been
run.
