# Reference library index — `multiverse-of-ideas`

**What this is.** An index over the local competitor-research library so an agent can open
**two or three files** instead of scanning eleven cloned repositories. The library is at
`~/dev/multiverse-of-ideas` (`repos/` clones, `reviews/` architecture reviews, `_meta/` licence
ledger and backlog).

**Status of this index, 2026-08-03.** Written during the L1 reconciliation. Verified by reading
the library's own `README.md`, `_meta/LICENCES.md` and `_meta/BACKLOG.md`, and by grepping this
repository for traces of copied code.

---

## 1. The rule that governs everything here

The library's `README.md` states it, and this repository is bound by it:

> **The review documents in `reviews/` are the only artefact allowed to cross from this folder
> into our thinking.** Prose describing an abstraction is ours. A file is theirs.

Nothing in `repos/` is ever copied, vendored or imported. This is not caution — it is a
**licensing necessity**. The three repositories that teach us the most about the Component IR
(ComfyUI, backtrader, OpenAlgo) are all GPL-family, and OpenAlgo is AGPL-3.0 whose §13 network
clause triggers on merely *serving* users. Lifting code would relicense the platform and end
the hosted/marketplace path.

**Read `reviews/`. Do not read `repos/` unless a review names a specific file and you need to
check one claim.**

---

## 2. Provenance audit — what this repository actually took

**Verified 2026-08-03: no source code from any reference repository exists in this codebase.**

Method: grepped `backend/app/` and `backend/research/` for every reference project's name.
Exactly two hits, both **prose comments citing a system as design rationale**, neither containing
borrowed code:

| File | What it says |
|---|---|
| `backend/app/ir/validate.py:472` | Cites vectorbt building parameter sweeps into its indicator contract — as the **counter-example** justifying C14 ("components compute; searchers search"). |
| `backend/app/ir/schema.py:44` | Cites ComfyUI's ecosystem freezing around the opposite choice. |

Classification for the whole library: **architecture used as inspiration only.** Nothing copied,
nothing adapted, no attribution obligation incurred. RFC 0001 cites the reviews as its evidence
base; it does not reproduce their code.

**Existing citations verified correct.** RFC 0001 (`:54`, `:509`, `:740`, `:828`), WS-01 and the
two 2026-08-02 spec/plan documents all cite `~/dev/multiverse-of-ideas/reviews/` with the right
path and the right section numbers. `git grep 'dev/il/'` over the committed tree returns nothing,
so no stale library path exists anywhere in this repository.

---

## 3. The index

Relevance is to **this repository's open questions**, not to the projects' fame.

| Repo | Licence | Review | Relevant to | Consult when |
|---|---|---|---|---|
| **nautilus_trader** | LGPL-3.0 | `reviews/nautilus-trader.md` | **L1 execution**, WS-01, WS-02 | Backtest/live parity, warmup derivation, reset semantics, injected clock. **The single most L1-relevant document in the library.** |
| **comfyui** | GPL-3.0 | `reviews/comfyui.md` | WS-01, WS-04, L4 marketplace | Node/component model, custom nodes indistinguishable from built-ins, cache keys. |
| **vectorbt** | Apache-2.0 **+ Commons Clause** ⚠️ | `reviews/vectorbt.md` | WS-01, WS-03 | Vectorised indicator composition. **Never a dependency** — see §4. |
| **xyflow** (React Flow) | **MIT** | `reviews/xyflow.md` | WS-04 editor | Choosing the graph-rendering substrate. The one repo we may legitimately depend on. |
| **blender** (geometry nodes) | GPL-2.0+ | `reviews/blender-geometry-nodes.md` | WS-01, WS-04 | Node groups, exposed inputs, field-vs-value semantics. |
| **node-red** | Apache-2.0 | `reviews/node-red.md` | WS-04, L4 | Subflows-as-nodes, package/distribution mechanics. |
| **prefect** | Apache-2.0 | `reviews/prefect.md` | WS-03, WS-07 | Dynamic DAGs, run persistence. |
| **airflow** | Apache-2.0 | `reviews/airflow.md` | WS-03 | The mature counter-example: rigid static DAGs at scale. |
| **langflow** | MIT | `reviews/langflow.md` | WS-04 | Component→JSON→runtime round trip. Mostly cautionary. |
| **openalgo** (`~/dev/openalgo`, outside the library) | **AGPL-3.0** | `docs/reports/2026-08-02-openalgo-competitive-teardown.md` — **in this repo** | L1 execution, broker abstraction | Indian-market broker adapters, order lifecycle. Strictest licence in the set. |
| backtrader | GPL-3.0 | **none — cloned, unreviewed** | L1 | Line/indicator abstraction. See §5. |
| freqtrade | GPL-3.0 | **none — cloned, unreviewed** | L1 | Strategy-as-a-class ergonomics, deployment story. See §5. |

---

## 4. Licence hazards that must not be rediscovered the hard way

1. **vectorbt is not open source.** Its `LICENSE.md` is Apache-2.0 with a **Commons Clause
   rider** removing the right to "Sell", explicitly including *"fees for hosting"* a product
   whose value derives substantially from the software. A hosted Strategy OS with vectorbt
   inside is precisely the prohibited case. **Ideas only; never a dependency.**
2. **Never classify a licence by grep.** Pattern-matching `"Apache License"` matches the
   *embedded* Apache text inside vectorbt's file and reports it as permissive. Read the first
   fifteen lines with your eyes. A rider sits above the base licence, and every pattern you
   would think to write matches the base.
3. **xyflow being MIT is load-bearing.** It means the visual builder's rendering substrate is a
   buy, not a build.
4. **Anything adopted from a GPL/AGPL project must be re-derived from the review's prose**, never
   transcribed. If a future change does copy code, that is an owner/legal decision, and it must be
   recorded here before the code lands.

---

## 5. Gaps worth knowing before L1

`backtrader` and `freqtrade` are **cloned but unreviewed** (`_meta/BACKLOG.md` Tier 3, status
`queued`), and both are nominally L1-relevant. Two reasons this is not currently blocking:

- Both are GPL-3.0, so neither can contribute code regardless of what a review finds.
- Their listed lessons (line/indicator abstraction; strategy-as-a-class ergonomics) address
  problems this repository has already solved differently — the `Strategy` contract in
  `backend/app/strategy/registry/base.py` and the Component IR both predate any review.

**Trigger to review them:** a concrete L1 question their prose could answer — most plausibly
freqtrade's *deployment/rollback story*, if the staged L1 rollout needs prior art. Do not review
them speculatively.

---

## 6. When to consult, and when not to

**Consult** when the question is architectural and open: how should warmup compose through a
nested graph; what does backtest/live parity by construction look like; what is a sane
component/plugin boundary; what did a mature project regret. Open the **review**, find the named
section, and stop.

**Do not consult** for: how to write code in this repository (the existing code and its
invariants are authoritative); anything already decided in RFC 0001 or an ADR; routine
implementation; or "let me see how project X does it" curiosity. A review that has already been
distilled into RFC 0001 has done its job — re-reading it does not re-open the decision.

**Never** let a reference repository introduce a second graph schema, ledger, validator,
deployment model, or execution authority. This codebase's documented defining defect is
mechanisms built and wired to nothing; importing a second way to do something already done is the
fastest route to another one.
