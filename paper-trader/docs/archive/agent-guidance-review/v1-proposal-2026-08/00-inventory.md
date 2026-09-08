# 00 — Inventory of current Claude-facing guidance

**Method.** Every markdown file that a session is instructed to load, plus everything those
files point at. Freshness was judged against the code and against the newest documents in the
tree (`CONTINUE.md`, the 2026-08-07 architecture review), never against prose alone. Where a
claim could be checked cheaply from the filesystem it was.

**Repository facts verified while writing this** (commands in §6):

- Branch `feat/exec-completeness`, clean tree, HEAD `b47e8f5`.
- Migration head on disk is `0013` (`20260807_0013_ir_paper_deployments.py`).
- `app/ir/library.py` exists — G-1 is shipped, as claimed.
- `app/api/auth.py` is **one shared bearer token** (`PT_API_TOKEN`, empty = disabled).
  `app/api/principal.py` resolves an `ANONYMOUS_OWNER`. There are **no user accounts**.
- No payment/subscription code of any kind exists.
- `app/providers/` holds `base.py, factory.py, kite.py, live_kite.py, mock.py, replay.py,
  safe_kite.py` — **one broker family**.
- 269 markdown files in the repository.

---

## 1. The documents that instruct Claude

| # | Document | Purpose | Freshness | Verdict |
|---|---|---|---|---|
| 1 | `paper-trader/CLAUDE.md` | The always-loaded instruction file | **Mostly correct, structurally out of date** | Replace — see `01` |
| 2 | `docs/ARCHITECTURE.md` | Cross-workstream invariants | **Correct** | Keep, add two invariants |
| 3 | `docs/rfcs/0001-component-ir.md` | The constitution | **Correct** | Keep unchanged |
| 4 | `docs/PROGRESS.md` | One-page state | Content current to 2026-08-07; **header date and one test count are stale** | Keep, correct |
| 5 | `docs/CONTINUE.md` | Session handoff | **Current** (2026-08-07/08) and the most accurate document in the tree | Keep |
| 6 | `docs/ROADMAP.md` | Cross-workstream order | **Stale — §1 names completed work as "next"** | Replace §1 |
| 7 | `docs/engineering/EXECUTION_PLAN.md` | The sequential programme | **Header stale; L1 band under-specified** | Supersede §5, keep §1–§4 |
| 8 | `docs/engineering/WORKSTREAMS.md` | Which stream owns what | **Correct** | Keep |
| 9 | `docs/engineering/EXECUTIVE.md` | Coordination, standing decisions | **Correct** | Keep, add V1 decisions |
| 10 | `docs/engineering/DEPENDENCIES.md` | Dependency graph | Correct | Keep |
| 11 | `docs/engineering/workstreams/WS-01…08` | Per-stream agendas | Correct; WS-05 explicitly unstarted | Keep |
| 12 | `docs/engineering/decisions/0001…0013` | ADRs | **Current and load-bearing** | Keep — and **surface them**, see §3 |
| 13 | `docs/engineering/reference/architecture-extension-review-2026-08-07.md` | The V1 feasibility study, already taken | **Current, and the single most useful V1 document that exists** | Promote |
| 14 | `docs/engineering/reference/multiverse-index.md` | Reference-library map | Correct | Keep |
| 15 | `docs/engineering/reference/engine-internals.md` | Engine detail | Correct | Keep |
| 16 | `docs/product-overview.md` | Business-facing overview | **Materially stale and now contradicts the product identity** | Replace — see `03` |
| 17 | `docs/operations.md` | Deploy/ops | Correct | Keep |
| 18 | `docs/reports/*` (18 files) | Frozen point-in-time | Correctly labelled; `README.md` flags five as stale | Keep, historical |
| 19 | `docs/incidents/*`, `docs/audit/*` | Post-mortems | Historical by design | Keep |
| 20 | `~/.claude/.../memory/MEMORY.md` | Cross-session memory | Broadly accurate; predates the V1 direction | Update after adoption |

Not instruction files, but they do shape sessions: `.claude/workflows/*.js` (two review
workflows), `docs/superpowers/plans|specs`.

---

## 2. Stale assumptions, with the exact claim

These are the ones that would change what a session does. Ranked by cost of being believed.

### 2.1 `CLAUDE.md:7` — the product identity is the old bot

> "A single-user autonomous trading platform for Indian markets… It runs the EMA50 +
> displacement (z-score) strategy across a portfolio of underlyings…"

This is a true description of the *running process* and a false description of the *product*.
A session that loads only `CLAUDE.md` learns nothing about the Component IR, the visual editor,
graph versions, research admission or execution binding — i.e. nothing about the ~90% of recent
work. `CLAUDE.md` mentions `docs/rfcs/0001-component-ir.md` once, in a table row labelled "the
constitution", with no statement of what it constitutes.

**Cost:** a new session's first instinct is to edit the engine. The whole L1 band exists to stop
exactly that.

### 2.2 `CLAUDE.md` — the current safety invariants are not in the hard-invariants list

`CLAUDE.md` §"Hard invariants" lists six, all of them from the pre-Strategy-OS era. The
invariants that now govern the most dangerous surface in the tree are **absent**:

| Invariant, live in code today | Where it is documented | In `CLAUDE.md`? |
|---|---|---|
| `AUTHORITY_BY_SOURCE` / `GRANTS` — a source of logic gains execution rights at one reviewed line | ADR 0012, `app/core/execution_binding.py` | **No** |
| `(ir_graph, live, authoritative)` is ABSENT and is the standing owner gate | ADR 0011/0012, CONTINUE §1 | **No** |
| Paper and live are separate *books*; resolution fails closed to `live` | ADR 0012 §6, `app/core/execution_book.py` | **No** |
| Research approval is **admission consumed once**, not a lease | ADR 0013 | **No** |
| Graph versions are append-only and content-addressed; presentation state never enters identity | RFC F13/F14, ADR 0001 | **No** |

**Cost:** the highest. These are the invariants most likely to be weakened by an agent that has
not read the ADRs, and `CLAUDE.md` never tells it the ADRs exist.

### 2.3 `CLAUDE.md` — `docs/engineering/decisions/` is never mentioned

Thirteen ADRs, several of which settle questions a session will otherwise re-litigate (0011
adoption gates, 0012 execution-state ownership, 0013 admission-not-lease). `CLAUDE.md`'s "The
agenda" table lists seven documents and none of them is the ADR index. `PROGRESS.md` §6's table
also omits `decisions/`.

### 2.4 `ROADMAP.md` §1 — names finished work as next

> "| 1 | WS-04 Editor | S1.2 conflict-safe layout load, move and save | no |"

`EXECUTION_PLAN.md` §3 records S1.2 as **done**, and S3.x/S4.x all completed after it. The
whole priority table (research plane → UI → futures/MTF → exit tuning, set 2026-08-01) predates
the L1 execution band that has consumed every session since 2026-08-04.

Also stale in the same file: the header's "2,719 passed" against `CONTINUE.md`'s 3,184.

### 2.5 `EXECUTION_PLAN.md` header and §3 — a week behind

> "**Status date:** 2026-08-03 · **Current slice:** S4.6d immutable project review snapshots"

S4.6d is complete. Since then: G-1, G-2, L1.2, L1.2b, L1.3A, L1.3B, L1.3C, L1.4 — eight
increments, three migrations (`0011`, `0012`, `0013`), and the ADRs 0011–0013. **None of them
appears in §3's slice table.** They exist only as the one-paragraph "L1 — execution integration"
at §5. The document that claims to be the sequential programme has not recorded the last week of
sequential programme.

### 2.6 `PROGRESS.md` — header date and one figure

Header says "Updated 2026-08-04" but §4 describes work closed 2026-08-07. §5 quotes
`3,098 passed · 6 skipped`; `CONTINUE.md` §3 quotes `3,184 passed · 6 skipped` on 2026-08-07.
Both are presented as the current acceptance run. Only one can be.

### 2.7 `product-overview.md` — three separate contradictions

1. §1/§2/§3 describe an **options** platform driven by one hard-coded strategy. `CLAUDE.md:22`
   itself says options are lowest priority and index-only, and 70 of 72 real trades are
   `equity_intraday`.
2. §11's maturity table says **"Production readiness | 3 | … the live order path has never
   fired"** — contradicted *within the same document* at §6, which corrects that claim with
   evidence. The stale row was never re-scored.
3. §1 and §7: "architected for a single disciplined account, not as multi-tenant software" /
   "Single-user, single-process, single-account by design." Under V1 this is no longer a design
   statement, it is a **gap statement**. Left as-is it reads to an agent as an instruction not to
   build tenancy.

### 2.8 `CLAUDE.md` invariant 5 — obsolete stream naming

> "`PT_RESEARCH_ENABLED=0` until **Workstream A** opens."

Workstream A/B/C/D/E/F naming was superseded by WS-01…WS-08 (`ROADMAP.md` §5 records the
mapping). Harmless, but it is the visible edge of a document that has been patched rather than
rewritten.

### 2.9 `CLAUDE.md` — dated live figures presented without a measurement date discipline

"72 real trades … as of 2026-08-01 (net −₹166.37)" and the ten-row `runtime_config` table
("measured 2026-08-01"). These are honestly dated and the file is emphatic that deployment
state must be measured, not read. That discipline is correct and should survive verbatim into
any successor. The *numbers* will rot; the rule will not.

---

## 3. Missing V1 context — what no current document tells a session

| Missing | Why it matters now | Nearest existing home |
|---|---|---|
| **The product is a visual node platform**, and the IR is the machinery under it | Determines what "done" means for every slice | Nothing states it. RFC §1.2 names an Editor plane; no document says the editor *is* the product |
| **A dated release target** (first week of September 2026) | Every "safe to defer" judgement in the tree was made with no deadline in it | None. `EXECUTION_PLAN.md` is explicitly sequence-not-schedule |
| **Connections are not brokers** — data provider vs execution broker as separate roles with declared capabilities | Blocks multi-broker, blocks the Upstox-data/Zerodha-execution example | `MarketDataProvider` and `Broker`/`ExecutionVenue` are already separate seams, but nothing declares the *connection* concept above them |
| **Canonical instrument identity across providers** | Every other V1 item silently depends on it | L3 in `EXECUTION_PLAN.md` §5, at product-outcome resolution only |
| **Cross-instrument observation vs cross-instrument execution target** are different problems with different gates | V1 conflates them; the second touches the money path | Architecture review §B rows 4 and 5 keep them separate — the only place that does |
| **Auth, ownership, tenancy** as V1 work rather than L5 work | `graph_artifacts.identifier` is a global PK (G-5); every table is global | G-5 says "SAFE TO DEFER, with a free hedge". Under V1 that judgement changes |
| **Payments/subscriptions and the regulatory question they raise** | Charging for order routing in India is a legal gate, not a task | `product-overview.md` §6 flags algo registration as unconfirmed; nothing connects it to monetisation |
| **Hosting posture**: the owner's real-money engine and a multi-user product on one box | Hard invariant 2 says nothing may block an exit; a customer load event on a 1 GB droplet can | Architecture review §F treats ~100 users abstractly and never asks where the owner's live account sits |
| **Which agent owns which surface** (Claude backend, ChatGPT/Codex frontend) | Changes what Claude should even attempt in WS-08 | `ROADMAP.md` §4.6 records a *model* split (Fable/Sonnet/Opus), not a *surface* split |

---

## 4. What is genuinely healthy and must not be disturbed

Recorded here because a rewrite is the moment these get lost.

- **The evidence discipline.** "Assertions are not evidence"; a guard must be proven able to go
  red; never assert deployment state from prose. This is the most valuable thing in the
  repository and it was learned expensively — five shapes of vacuous test, two mis-measured
  suites, a week of decisions driven by a false doc claim.
- **The `CLAUDE.md` "Production divergence" section**, which exists specifically because prose
  lied once. Its correction history is load-bearing and should be carried forward, not tidied.
- **`runtime_config` overrides are owner decisions, not drift** (ten rows). The rule "when the
  doc and the box disagree, fix the doc" must survive verbatim.
- **The three-document loading rule** (`ARCHITECTURE.md` + your workstream + its declared
  dependencies). It is what keeps context small; V1 must not turn `CLAUDE.md` into a PRD.
- **The 2026-08-07 architecture review.** It already asked, and answered with executed drills,
  most of what the V1 brief asks. Any V1 planning that ignores it is re-doing paid work.

---

## 5. Files inspected

`paper-trader/CLAUDE.md`; `docs/ARCHITECTURE.md`, `PROGRESS.md`, `CONTINUE.md`, `ROADMAP.md`,
`product-overview.md`, `operations.md`; `docs/rfcs/0001-component-ir.md`;
`docs/engineering/EXECUTION_PLAN.md`, `EXECUTIVE.md`, `WORKSTREAMS.md`, `DEPENDENCIES.md`;
`docs/engineering/workstreams/WS-01…WS-08` (WS-01 §5, WS-02 §3, WS-05 §1–2, WS-08 §1–3 read in
full, the rest surveyed); `docs/engineering/decisions/` (index; 0011–0013 by reference from
CONTINUE/PROGRESS); `docs/engineering/reference/architecture-extension-review-2026-08-07.md`
(full), `multiverse-index.md`, `engine-internals.md`;
`docs/reports/2026-08-02-openalgo-competitive-teardown.md` (§0–§2.3, §11–§12);
`docs/reports/README.md`; `backend/app/api/auth.py`, `principal.py`; `backend/app/ir/` (listing);
`backend/app/providers/` (listing); `backend/migrations/versions/` (listing);
`~/dev/openalgo/broker/` (listing), `~/dev/openalgo/LICENSE`;
`~/dev/multiverse-of-ideas/reviews/` (listing).

## 6. Commands run

```
$ git status --short                      # (empty — clean)
$ git branch --show-current               # feat/exec-completeness
$ find . -name "*.md" … | wc -l           # 269
$ ls backend/migrations/versions | tail    # …20260807_0013_ir_paper_deployments.py
$ ls backend/app/ir/                       # …library.py present
$ ls backend/app/providers/                # base factory kite live_kite mock replay safe_kite
$ ls ~/dev/openalgo/broker | wc -l         # 37 entries (35 broker dirs + __init__ + __pycache__)
$ head -5 ~/dev/openalgo/LICENSE           # GNU AFFERO GENERAL PUBLIC LICENSE Version 3
```

No test suite was run: this is a documentation-only task and the brief forbids it.
