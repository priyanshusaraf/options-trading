# 07 — Adoption recommendation

**Nothing here has been adopted.** This is the decision sheet.

---

## 1. Recommendation in one line

**Adopt the corrections now; adopt the identity rewrite when the owner confirms the V1 scope;
do not adopt the V1 execution sequence until the scope is cut** (see
[`02-v1-classification.md`](02-v1-classification.md) §6).

The three are separable and should be decided separately — a good instinct that the current
documents already model, where `ARCHITECTURE.md` changes only by RFC amendment while
`CONTINUE.md` is rewritten every stop.

---

## 2. Tier 1 — adopt regardless of the V1 decision

These correct documents that are wrong *today*, independent of product direction. Each is small,
each is verifiable, none depends on the September scope.

| # | Change | Target | Source |
|---|---|---|---|
| 1 | Add the authority / execution-book / admission invariants and a `docs/engineering/decisions/` pointer | `CLAUDE.md` | [`01`](01-CLAUDE.proposed.md) §Hard invariants, §The agenda |
| 2 | Add `EXECUTION_PLAN.md` and the 2026-08-07 architecture review to the reading table | `CLAUDE.md` | [`01`](01-CLAUDE.proposed.md) |
| 3 | Replace `ROADMAP.md` §1 — its top priority is a completed slice | `ROADMAP.md` | [`00`](00-inventory.md) §2.4 |
| 4 | Record G-1, G-2 and L1.1–L1.4 in the slice table; correct the header date | `EXECUTION_PLAN.md` §3 | [`04`](04-v1-execution-addendum.proposed.md) §A |
| 5 | Reconcile the two conflicting acceptance figures (3,098 vs 3,184) by re-measuring, and correct the `PROGRESS.md` header date | `PROGRESS.md` §5 | [`00`](00-inventory.md) §2.6 |
| 6 | Re-score or strike `product-overview.md` §11's "the live order path has never fired", which the same document already corrects at §6 | `product-overview.md` | [`00`](00-inventory.md) §2.7 |
| 7 | Namespace `graph_artifacts.identifier` per owner **by convention** — free today, removes the tenancy collision entirely | code convention + `WS-07` | architecture review G-5 |

Items 1–6 are documentation. Item 7 is a convention with no schema change; it is listed here
because delay makes it more expensive and nothing else depends on the V1 decision.

---

## 3. Tier 2 — adopt when the owner confirms the product identity

| Change | Target | Replaces or supplements |
|---|---|---|
| The new "What this is" and the two do-not-hard-code rules | `CLAUDE.md` | **Replaces** the current opening |
| Agent-surface split (Claude backend/contracts, ChatGPT/Codex frontend) | `CLAUDE.md`, `EXECUTIVE.md` §5 | **New standing decision** |
| Extended reuse-first policy (four sources, four classes, OpenAlgo named with its AGPL consequence) | `CLAUDE.md` | **Replaces** the current `multiverse`-only section |
| Product identity document | `docs/product-identity.md` (new file) | **Supplements**, then supersedes, `product-overview.md` — see §5 |
| Two invariants + one identity sentence | `ARCHITECTURE.md` §1, §3 | **Supplements**. Note §6: this document changes by RFC amendment. The two invariants record enforced behaviour and are errata-shaped; the identity sentence is informative. Confirm the owner agrees before editing rather than amending |

---

## 4. Tier 3 — do **not** adopt yet

| Item | Blocked on |
|---|---|
| The V1 slice sequence (`04` §B) | **A scope cut.** As briefed it is roughly 3–4× over-committed against this repository's demonstrated pace. `02` §6 offers a deliverable version |
| Payments / subscriptions of any kind | An owner answer on Indian algo registration / order tagging — flagged unconfirmed since 2026-07 and never resolved |
| Live IR authority as V1 scope | The written design of `CONTINUE.md` §4, owner-reviewed. Write the design in V1; do not implement it |
| Cross-instrument execution on the live path | The above, plus multi-instrument observation, plus splitting observed from traded in `ExecutionBinding` |
| Brokers 3…N | One second broker plus a conformance suite proving the seam |
| Hosting posture for a multi-user product | An owner decision — see §6.3 |

---

## 5. What should stay permanently historical

Never rewritten, never treated as current state, never deleted:

- `docs/product-overview.md` — an accurate portrait of the platform **as an autonomous options
  bot**, with unusually honest limitations. If a successor is adopted, this becomes a dated
  companion, not a deletion. Add one header line: *"Describes the platform as of 2026-07 in its
  autonomous-options-bot form. Superseded as the product statement by …; retained as an honest
  record."*
- `docs/reports/*` (18 files) — frozen point-in-time audits, autopsies and teardowns. The index
  already flags five as containing stale claims. **The OpenAlgo teardown and the 2026-08-07
  architecture review are the two most V1-relevant documents in the repository** and neither
  should be edited; the review in particular should be *promoted* in `CLAUDE.md`'s reading table
  rather than absorbed.
- `docs/incidents/*`, `docs/audit/ground-truth-2026-07-28.md` — post-mortems. Their value is
  that they are contemporaneous.
- `docs/engineering/decisions/0001…0013` — ADRs are append-only by nature. A superseded ADR is
  superseded by a **new** ADR, never by an edit.

---

## 6. Owner decisions this review cannot make

Ordered by how much else waits on them.

1. **Is the September scope the briefed nine items, or the cut list in `02` §6?**
   Everything downstream depends on this. A committed date against the full list means either
   missing the date or lowering the evidence bar, and the evidence discipline is this
   repository's most valuable asset.

2. **Unblock the two production actions.** The eight-phase architecture migration is committed,
   verified and off the box for several sessions; the VPS needs an OS reboot and a 1 GB → 2 GB
   resize. `PROGRESS.md` §1 records "Deployed from this branch: **nothing.**" **This, not code,
   is the September critical path.**

3. **Where does the multi-user product run?** Onboarding users onto the box that trades the
   owner's live account is a safety question, not an infrastructure preference: a backtest sweep
   already shares the process with the risk lane, hard invariant 2 says nothing may block an
   exit, and the droplet has OOM'd twice with the engine running.

4. **The regulatory position on charging for order routing in India.** Gates payments entirely.

5. **Does the owner want the ten-row `runtime_config` table kept inline in `CLAUDE.md`?**
   The proposal moves it out; the argument for keeping it is real (see [`06`](06-current-vs-proposed.md) §1).
   Twelve lines, and the cost of an agent not seeing the divergence is higher than the cost of
   it going stale.

6. **Is the `ARCHITECTURE.md` addition an erratum or an amendment?** RFC 0001 §6 governs, and
   the document's own §6 says it changes by amendment rather than editing. The two proposed
   invariants record behaviour that is already enforced by code and ADRs, which is erratum-shaped
   — but that is the owner's call, and making it casually is exactly the drift `EXECUTIVE.md` §1
   exists to catch.

---

## 7. If Tier 1 is accepted, the next session should

1. Apply items 1–6 as **one documentation commit**, no code, no tests changed.
2. Re-measure the acceptance run before writing any number into `PROGRESS.md` — do not carry a
   figure forward from another document. Both current figures cannot be right.
3. Leave this directory in place, unmodified, as the record of what was proposed and what was
   declined.
