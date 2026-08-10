# ADR 0015: Three planes, decided on recovery — and where a broker credential lives

- **Status:** **ACCEPTED (2026-08-10).** Verdict is **KEEP + HARDEN**: the three planes become
  a *logical* boundary now, enforced in code and schema; the *physical* split stays deferred
  behind ADR 0014's topology trigger. Durable per-owner broker connections are assigned a home
  by this ADR, which is what unblocks them.
- **Date:** 2026-08-10
- **Owners:** WS-02 execution, WS-07 infrastructure
- **Question asked:** WS-02 §5 blocked durable per-owner connections on "the three-plane database
  ADR". This is that ADR. It must answer two things: what the planes are and how they are
  enforced, and **which plane holds a broker credential** — the question that actually blocks
  the work.
- **Depends on / consulted rather than redone:**
  - ADR 0014 — SQLite stays until *topology*, not headcount, forces Postgres. Its §4 names
    "durable encrypted broker connections and accounts" as part of the tenancy schema change.
  - `reference/2026-08-10-multi-user-failure-modes.md` §3 — the recovery-requirement table this
    ADR adopts, and F-2/F-3/F-5, which it does not fix but does place.
  - `reference/architecture-extension-review-2026-08-07.md` — "the trigger is a measured
    lock-wait, not a headcount."

---

## 1. The planes, and why recovery is the right axis

Three planes, distinguished by **what it costs to lose them**, not by what it costs to serve
them. Performance would have produced a different and wrong split.

| Plane | Contents | If lost | Durability it therefore needs |
|---|---|---|---|
| **Market** | candles, quotes, option dumps, instrument masters, sweep datasets | re-fetchable — costs money and rate limit, never correctness | cheapest available. Content-addressed, ideally object storage. **Never on the same failure domain as money** |
| **User** | projects, graphs, layouts, research, notes, saved views | gone — irreplaceable creative work | real backups, PITR, per-owner export |
| **Money** | ledger, positions, trades, execution intents and events, attribution, **and connections** | legally significant | strictest. Append-only where possible, off-host replication, restore drills |

The market plane is the largest by volume and the cheapest to lose; the money plane is the
smallest and the most expensive. Any migration ordered by throughput would move them in exactly
the wrong order, which is the whole reason this is decided here rather than during an incident.

## 2. The decision that unblocks the work: a credential lives in the money plane

A stored broker connection is `(owner, broker, scope, capabilities, encrypted credential, token
state)`. Three readings of where it belongs, and they disagree:

- **By recovery cost** it is *user*-plane or lower. Lose it and the user re-authenticates; Kite
  tokens expire daily anyway, so the system is built to survive losing one every morning.
- **By confidentiality** it is in a class of its own — the highest in the system.
- **By blast radius** it is *money*. A row in this table is the authority to place real orders on
  a real account. Changing one changes who can move money.

**Verdict: the money plane**, on blast radius, with two supporting reasons that are practical
rather than philosophical:

1. **Referential integrity stays inside one plane.** `ExecutionIntent.connection_scope` already
   decides which unresolved entries a broker may adopt on restart. If connections lived in a
   different plane from intents, that relationship would have to be maintained across a boundary
   this ADR is about to make real — and a dangling `connection_scope` is not a broken join, it is
   a live order nobody can attribute.
2. **"Who changed this credential, and when" is an audit question**, and the money plane is the
   one that already has append-only event history and the strictest durability. Putting the
   credential in the user plane would answer it with a backup, not a record.

**The encryption key is not in any plane.** Ciphertext lives in the money plane; the key comes
from the process environment (and later a KMS). A database compromise alone must not be a
credential compromise, and that property is only true if the key is never a row.

## 3. What "logical, not physical" means, concretely

Enforced now:

- **Every table is assigned to exactly one plane, in code**, and the assignment is asserted by a
  test. A new table with no plane is a build failure, not a judgement call made later.
- **No *new* foreign key crosses a plane boundary.** Cross-plane references are by value (a
  scope string, a content address), not by FK. This is the constraint that makes the physical
  split a later operation rather than a rewrite.

  **Correction, same day.** This rule was first written as an absolute, and implementing the
  check immediately found that the schema already breaks it **seven times**. All seven are one
  shape — a money-plane deployment referencing the user-plane artefact it runs:

  | From (money) | To (user) | Via |
  |---|---|---|
  | `deployments` | `watchlists` | `watchlist_id` |
  | `ir_paper_deployments` | `graph_versions` | `graph_version`, `graph_identifier` |
  | `ir_paper_deployments` | `projects` | `project_id` |
  | `ir_shadow_deployments` | `graph_versions` | `graph_version`, `graph_identifier` |
  | `ir_shadow_deployments` | `projects` | `project_id` |

  Those relationships are *correct* — they are the "results bind to the versions that produced
  them" invariant. Only their enforcement mechanism is the problem. So the rule becomes a
  **ratchet**: the seven are enumerated in `app/db/planes.py::GRANDFATHERED_CROSS_PLANE_FKS`,
  every new crossing fails the build, and shrinking that set is the intended direction. The
  enumeration is also the honest price of the physical split — seven constraints to convert —
  and it is now countable rather than discovered mid-migration.

  This correction is recorded rather than edited away because the sequence is the point: the
  rule was written from reasoning, the check was written from the rule, and the code disagreed.
  The code was right about what exists.
Deliberately NOT done now:

- **`synchronous=FULL` for the money plane. Second correction, same day — and this one was a
  false claim, not an incomplete one.** This bullet originally sat under *Enforced now*. It was
  never implemented (`app/db/session.py:36` sets `PRAGMA synchronous=NORMAL`), and the owner
  asking "are we complying with the three-plane structure" is what surfaced it. An accepted ADR
  asserting wiring that does not exist is the same defect class this codebase is defined by, so
  it is corrected in place rather than quietly implemented.

  It is also **unimplementable as it was written.** `PRAGMA synchronous` is per *connection*, and
  all three planes share one SQLite file and one SQLAlchemy engine. There is no way to give
  money-plane commits `FULL` without giving the market plane's bulk backtest writes the same
  fsync-per-commit — which is exactly the coupling the plane split exists to remove. The
  original sentence ("the other planes keep `NORMAL`") described something the current topology
  cannot express.

  So F-2 stands open and its home is stated: it is fixed either by the physical split (separate
  files or a managed Postgres for the money plane) or by a deliberate global move to `FULL` with
  the write benchmark re-taken, which is the ordering
  `reference/2026-08-10-multi-user-failure-modes.md` §6 already gives it. **Under `NORMAL` with
  WAL a committed money transaction can still be lost to a host failure** — not to a process
  crash, which WAL does cover.

- Separate database files or servers. ADR 0014's trigger governs, and it has not fired: it is
  multi-host execution workers, not user count.
- Object storage for the market plane. Same reasoning; the seam is what matters today.

## 4. What this costs if the verdict is wrong

If credentials should have been user-plane, the correction is moving one table between planes
before the physical split — cheap, because the no-cross-plane-FK rule means it has no incoming
foreign keys to unwind. If the plane assignment mechanism itself is wrong, it is a test and a
table of names. **Neither cost grows with delay**, which is what makes accepting this now
correct rather than premature.

The cost that *does* grow with delay is the opposite one: every new table added without a plane
assignment is another thing to classify under pressure later, and the immutability triggers ADR
0014 counted grow the same way.

## 5. Invariants in the blast radius

- **Money — "paper and live are structurally separate books, failing closed to `live`."**
  Untouched: the book is a column and a resolution rule, orthogonal to which plane the row is in.
  A connection's plane does not decide whose money it is.
- **Authority — "exact execution attribution from scan to fill."** Strengthened, not weakened:
  keeping connections and intents in one plane is what keeps attribution a join rather than a
  hope.
- **Providers — "multiple provider connections per account must remain architecturally
  possible."** This ADR is what makes it *durable* as well as possible.
- **Delivery — "deploys go only through `scripts/deploy.sh`."** Untouched today; the day the
  money plane moves off-host, `deploy.sh`'s file-based backup and single-instance flock stop
  applying to it, and that is a named part of that future slice, not a surprise.

## 6. What would prove this wrong

- A measured lock-wait on the money plane caused by market-plane writes, *after* the pragma
  split. That would mean logical separation is insufficient and the physical split is due
  earlier than ADR 0014's trigger.
- A credential-rotation or revocation requirement that needs a write path faster than
  `synchronous=FULL` allows. Not expected — rotation is a human-frequency event.
- Regulatory advice that custody of another party's credential requires an isolated store by
  law rather than by design. That is **owner gate #6** and this ADR does not attempt it; it is
  noted because it changes the *physical* question, not the logical one decided here.

## 7. Scope — what this ADR does not do

It does not fix F-1 (durable exit intents), F-3 (backup in version control and a restore drill),
F-4 or F-5 (single process, unenforced active-passive). Those remain open in the failure-mode
review with the ordering that document gives them. This ADR only removes the block WS-02 §5
placed on durable connections, and states the plane rules the rest of that work must obey.
