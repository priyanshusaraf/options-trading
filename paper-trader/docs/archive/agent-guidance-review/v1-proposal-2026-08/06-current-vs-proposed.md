# 06 — Current vs proposed, side by side

What each change is, what it costs, and what breaks if it is wrong.

---

## 1. `CLAUDE.md`

| | Current | Proposed |
|---|---|---|
| Opening identity | "A single-user autonomous trading platform… runs the EMA50 + displacement strategy" | "Strategy OS — a visual, node-based platform… the typed IR is the machinery underneath" |
| Live-money framing | Front and centre, correct | Retained verbatim in substance, moved under the identity as "this is not greenfield, and one part of it trades real money" |
| Hard invariants | 6, all pre-Strategy-OS | 14, grouped Money / Authority / Language / Delivery. The 6 survive; 8 are added from ADR 0011/0012/0013 and the RFC — **all already true in code, none new** |
| ADRs | Never mentioned | A row in the reading table, called out as "a question settled here is not re-litigated in a session" |
| `EXECUTION_PLAN.md` | Not in the reading table | Added |
| Architecture review | Not mentioned | Added — "read before proposing any product extension" |
| Agent surface split | Absent (only a model split, in `ROADMAP.md` §4.6) | Explicit: Claude backend/contracts, ChatGPT/Codex frontend |
| Reuse policy | Present, `multiverse` only | Extended to the four-source order and the four-way classification; OpenAlgo named with its AGPL consequence |
| Cross-instrument / multi-broker | Absent | Two "do not hard-code" rules, stated once, in the identity section |
| Production divergence section | ~50 lines of correction history | **Compressed, not deleted.** The *rule* ("never assert deployment state from prose") is kept verbatim and promoted into an Evidence section; the dated incident narrative moves to `PROGRESS.md`/`CONTINUE.md` where dated facts belong |
| Sizing / `runtime_config` | Full ten-row measured table inline | Rule kept verbatim and emphasised; the **table moves out**, because a measured table in an always-loaded file is a rot generator and the file itself says to read `/api/settings` |
| Length | 363 lines | ~250 lines |

**Risk of adopting.** Two specific things could get worse.

1. **Dropping the ten-row override table from the always-loaded file.** Today an agent sees the
   divergence without asking. Mitigation in the proposal: the *rule* is stated more strongly than
   before ("fix the doc, never the box"; `intraday_enabled` named explicitly as the single most
   load-bearing row). **If the owner is uncomfortable, keep the table.** It is 12 lines and the
   cost of losing it is higher than the cost of it rotting.
2. **Compressing the production-divergence narrative.** That section exists because prose lied
   once and drove a week of decisions. The narrative is a warning, and warnings work by being
   uncomfortable to read. The proposal keeps the rule and the reason; it does not keep the
   blow-by-blow.

**Risk of not adopting.** Higher, and already realised: a session that loads only `CLAUDE.md`
does not know that `GRANTS` exists, that `(ir_graph, live, authoritative)` is the standing gate,
that paper and live are separate books, or that thirteen ADRs settle questions it is about to
re-open.

---

## 2. `docs/product-overview.md`

| | Current | Proposed successor |
|---|---|---|
| Product | An autonomous **options** bot | A **visual node-based platform**; the bot is one strategy it can run |
| Multi-tenancy | "single-account by design" (§1, §7) | Named as a gap with a plan, not a design choice |
| Live path | §6 correct; §11's maturity row still says "the live order path has never fired" | One consistent statement |
| Differentiators | Safety, parity, net-of-cost accounting | Those three **plus** typed graphs refused early, immutable evidence-bound versions, admission-not-marketing, free composition |
| Edge honesty | Excellent — "the engineering is mature; the proof of edge is not" | **Kept, and sharpened**: a visual builder makes the question easier to ask, not easier to answer |
| Length | 552 lines | ~120 lines |

**Risk.** The current document's candour is its best feature and the main thing worth losing
sleep over in a rewrite. The proposal preserves every honest limitation and adds one. The real
risk is the opposite: leaving a document in the tree that tells a reader — human or agent — that
multi-tenancy is a *design choice* while V1 is building it.

---

## 3. `docs/ROADMAP.md`

| | Current | Proposed |
|---|---|---|
| §1 order of work | research plane → UI → futures/MTF → exit tuning; top item is S1.2, which is **done** | Replaced by the V1 sequence in [`04`](04-v1-execution-addendum.proposed.md) §B |
| Header evidence | "2,719 passed", 2026-08-03 | Re-measured, or removed in favour of pointing at `CONTINUE.md` |
| §2 owner blockers | 3 items, all still true | **Unchanged, and promoted** — they are the September critical path |
| §3 parked, §4 session protocol, §5 history | Correct | Unchanged |

**Risk of adopting: low.** §1 is simply wrong today. **Risk of not adopting: a session picks up
a completed slice as "next".**

---

## 4. `docs/engineering/EXECUTION_PLAN.md`

| | Current | Proposed |
|---|---|---|
| §3 slice table | Ends at S4.6d | Ten rows added recording G-1/G-2 and L1.1–L1.4 as executed, plus L1.5 (the written design) as ready |
| §5 later sequence | L1–L5 ordered by dependency readiness | A V1 band inserted ahead, with the reordering **stated as a reordering**; L2–L5 keep their content, change their order |
| §1, §2, §4, §6–§9 | Correct | Unchanged |

**Risk.** Pulling parts of L5 (accounts, brokers) ahead of L2/L3 means auth and multi-broker land
on an implicit data layer. The proposal mitigates this by making **canonical instrument identity
(V1.1) the first slice** and by keeping everything temporal in L3. If V1.1 slips, the reordering
becomes the expensive kind.

---

## 5. `docs/ARCHITECTURE.md`

**Recommendation: keep, with two additions.** It is 93 lines, correct, and its "the RFC wins and
this document is the defect" clause is exactly right.

Additions proposed:

- Invariant 9: **authority is granted at one reviewed line, recomputed at the point of use**
  (ADR 0012) — currently only in an ADR, though it is now as load-bearing as anything in §3.
- Invariant 10: **research approval is admission consumed once, not a lease** (ADR 0013).
- One sentence in §1: what the system *is to a user* — a visual node-based platform — beside
  what it is architecturally.

**Risk: minimal.** These record existing enforced behaviour; they do not change it.

---

## 6. What deliberately does not change

| Document | Why it stays exactly as it is |
|---|---|
| `docs/rfcs/0001-component-ir.md` | The constitution. V1 needs **no amendment** — verified against every V1 direction. Cross-domain composition arrives as typed cross-domain operations under the mechanism A.5 already states; subgraph reuse is already C15; sandboxing is already excluded to the kernel registry, which is where V1 leaves it |
| `docs/CONTINUE.md` | The most accurate document in the tree. Its rewrite-every-stop discipline is why |
| `docs/engineering/WORKSTREAMS.md`, `DEPENDENCIES.md` | Eight streams still map V1 cleanly. Connections/brokers are WS-02; instrument identity is WS-07; components are WS-01/WS-04; auth is WS-07; cockpit is WS-08. **V1 needs no new workstream** |
| `docs/engineering/EXECUTIVE.md` | Correct. Two standing decisions to add: the agent-surface split, and that the V1 reordering of L2–L5 was deliberate |
| `docs/engineering/workstreams/WS-01…08` | Their §5 lists already hold most of V1's deferred items with named homes. WS-05 must keep its "no transport without a sandbox" rule |
| `docs/operations.md`, `docs/incidents/`, `docs/audit/`, `docs/reports/` | Operational truth and frozen history. Never rewrite a report; the index already flags the stale ones |

---

## 7. The changes ranked by value

| Rank | Change | Value | Risk |
|---|---|---|---|
| 1 | Add the authority/book/admission invariants and the ADR pointer to `CLAUDE.md` | **Highest.** Closes the gap most likely to cause a real defect | Very low — documents existing behaviour |
| 2 | Fix `ROADMAP.md` §1 | High — it currently misdirects the first action of a session | None |
| 3 | Record L1.1–L1.4 in `EXECUTION_PLAN.md` §3 | High — the programme document does not contain the programme | None |
| 4 | New product identity in `CLAUDE.md` | High — every V1 slice is judged against it | Low |
| 5 | Successor to `product-overview.md` | Medium-high — it is the document an outsider reads | Medium: candour must survive the rewrite |
| 6 | The V1 band in `EXECUTION_PLAN.md` §5 | Medium — valuable only if the scope is cut to something deliverable | **Highest of any change here.** See [`02`](02-v1-classification.md) §0 |
| 7 | Move the `runtime_config` table out of `CLAUDE.md` | Low | Medium — see §1. Consider not doing it |
