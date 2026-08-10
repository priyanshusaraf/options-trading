# How a user gets hurt by this software — failure-mode review, first pass

**Date:** 2026-08-10
**Scope:** order, funds and ledger integrity when things go wrong, for *other people's* money.
**Status:** first pass, inline, single reviewer. Not adversarially verified. §7 says what is missing.

The question this answers is not "is the code correct". It is **"what sequence of events leaves a
user unable to answer 'what do I hold and what am I owed', and which of those become legal rather
than operational problems."**

---

## 1. The single most important structural fact, stated first

**For what the account actually holds, we are not the source of truth and we do not try to be.**

- Funds come from `provider.account_funds()` (`runner.py:2558`), not from our arithmetic.
- Positions are re-derived and the ledger re-anchors to the broker (`ledger_reconcile.plan_reanchor`,
  `should_reanchor`).
- `can_bot_close` refuses to act on any position the live account does not back.
- `foreign_book_positions` reports rows belonging to the other book loudly instead of adopting them.

This is the strongest contingency property in the system and it should not be traded away. If our
database is destroyed entirely, a user's *broker* still knows their positions and funds, and the
system re-derives rather than reconstructs from our copy.

**What is genuinely ours, and therefore genuinely at risk:** realised P&L history, the trade
ledger, execution attribution, research evidence, and the audit trail of *why* an order was sent.
Those cannot be re-derived from Kite. That is the correct target for durability work — not
positions.

---

## 2. Findings, ordered by how badly they end

### F-1 — Exits have no durable intent. The path that must never fail is the least durable one.

**Evidence.** `ExecutionLifecycleStore.create_intent` is called at exactly one site:
`live_broker.py:160`, inside the entry path. `close_position` (`live_broker.py:1450`) creates no
intent and writes no immutable event stream; it relies on the older best-effort `order_journal`
plus reconciliation.

**Why this is the wrong asymmetry.** Hard invariant 2 says ARM gates entries only and never exits,
because *not getting out is worse than any other failure*. Phase 1–2 then gave the durable
lifecycle to entries and not to exits. The roadmap said so honestly ("integrates new live entries
**without changing exit behavior**") — this is a known boundary, not a hidden bug — but the net
effect is that the system's most safety-critical path has the weakest crash story.

**The sequence that hurts.** Bot sends closing SELL → process dies during the poll → on restart the
entry-side recovery finds nothing because no intent was ever written → the position is recovered
from `order_journal` if that commit landed, and from `reconcile_orphans` if it did not. Both are
best-effort. The user's position may be closed at the broker while our book still shows it open,
which means our P&L and their P&L disagree until someone looks.

**Mitigating.** The exit path is heavily hardened by incident: cancel-then-sell ordering (L6),
`can_bot_close` ownership guard, a second account re-check immediately before sending, and H4's
immediate persist of a cancelled trigger id. This is not naive code. But hardening is not durability.

### F-2 — `synchronous=NORMAL` under WAL. A committed money transaction can be lost to a host failure.

**Evidence.** `db/session.py:35-36` sets `journal_mode=WAL` and `synchronous=NORMAL`.

Under WAL, `NORMAL` means the WAL is **not fsynced on every commit**. A process crash is safe — the
WAL survives and replays. A **host-level failure — power loss, hypervisor reset, a hard DO droplet
reboot — can lose the most recent committed transactions.**

That is precisely the user's stated fear: the box blinks, and a fill that the exchange executed is
missing from our ledger. Note the danger is one-directional and bad: the *exchange* keeps the trade,
we lose the record of it, so we under-report what the user owns.

`synchronous=FULL` closes it at a write-throughput cost. ADR 0014 measured SQLite writes at 16,000
rows in 2.64 s, so there is headroom to spend — but that measurement was taken at `NORMAL` and must
be re-taken before claiming the cost is acceptable.

### F-3 — The backup script is not in version control and has never been restore-tested.

**Evidence.** `scripts/deploy.sh:58-59` excludes `backups` and `backup.sh` from the rsync, with the
comment "the cron script that creates them — **VPS-only**". Line 323 confirms it is "not in git".

Three separate problems in one:

1. **It is not reviewable.** Nobody has read it in a session. Its correctness is assumed.
2. **It has never been restored.** A backup you have not restored is a hypothesis, not a backup.
3. **It lives on the droplet it protects.** A host loss takes the database and its backups together.

For one owner trading their own money this is a tolerable risk they chose. For other people's money
it is not, and it is the cheapest of all these findings to fix.

### F-4 — One process, one droplet, no stated RPO or RTO.

There is no second host, no failover, and no written recovery objective anywhere in the docs. Phase
7's gate names "50-account soak and crash/fencing drills meet latency, RPO, and RTO targets" — that
work is not started, and the targets themselves have never been chosen.

The relevant question is not uptime. It is: **when the host is gone, how long until a user can see
their own trade history, and how much of it is missing?** Today the honest answer is "unknown, and
dependent on an unreviewed script."

### F-5 — Active-passive is asserted but not enforced.

The target architecture says "two workers must never submit for the same account at the same time."
Today that is true because there is exactly one process. There is **no lease, no fence, no lock**
that would make it true if a second one started — and the most likely way a second one starts is a
botched deploy or a partially-failed restart, which is exactly when nobody is watching.

Two engines on one Kite account double every order. This is currently prevented by luck and
operator discipline, and it is a phase-7 blocker rather than something to defer past it.

### F-6 — The blast radius of a shared plane, from our own history.

The 2026-07-23 outage was a dashboard poll running full-table ORM scans: +100 MB/min into a 1 GB
droplet, OOM, DB-pool collapse. One user's open browser tab took the trading engine down.

With 500 users, any shared read path has that property by default. This is the concrete argument for
your three-plane split and for making the market plane read-only and aggregate-shaped, not a
convenience others can query freely.

---

## 3. Where the three-plane split actually earns its cost

Your framing was right and the findings above sharpen *why*. The three planes have different
recovery requirements, and that — not performance — is the argument:

| Plane | If it is lost | Therefore |
|---|---|---|
| **Market data** | Re-fetchable. Costs money and Kite rate limit, not correctness | Cheap durability. Content-addressed blobs, ideally object storage, not an RDBMS. Never on the same failure domain as money |
| **User** | Gone. Graphs, research, notes are irreplaceable creative work | Real backups, point-in-time recovery, per-owner export |
| **Money** | Legally significant. Ledger, fills, attribution, the audit trail of *why* | Strictest durability (`synchronous=FULL` or a real RDBMS), append-only where possible, off-host replication, restore drills |

**The money plane is the one that must move off SQLite-on-the-app-droplet first**, and it is the
smallest of the three by volume. That ordering is the opposite of what a performance-driven
migration would pick, which is exactly why this should be decided on recovery grounds rather than
throughput grounds. ADR 0014 deferred Postgres pending a *topology* trigger — this is that trigger,
and it applies to one plane rather than all three.

Your point that the database need not live on the droplet is correct and makes this easier: a
managed Postgres with automated PITR removes F-2, F-3 and most of F-4 in one move, for the money
plane only, without touching the sweep's SQLite performance profile.

---

## 4. Sequences worth drilling before any user is onboarded

Written as drills because a claim about crash behaviour is worth nothing until it has been run.

1. **Kill -9 between order submit and fill observation.** Entry: covered, proven in
   `test_execution_lifecycle_recovery`. **Exit: not covered** (F-1).
2. **Kill -9 between the GTT cancel and the closing SELL.** H4 persists the cleared trigger id, so
   this is *designed* for. Never drilled.
3. **Host reset (not process kill) with an uncommitted-to-disk WAL.** Directly tests F-2. Never run.
4. **Token expiry mid-session.** Now reaches the health-failure latch via `ProviderReadError` —
   which itself is built and undeployed.
5. **Two engines on one account.** F-5. No mechanism prevents it; the drill would currently fail.
6. **Broker reports a fill we have no intent for.** Reconciliation adopts it — good — but under
   whose attribution, and does the user see a trade with no explanation?
7. **Restore from backup into a running system.** F-3. Never attempted.
8. **A user disputes a fill.** Can we produce the decision price, the signal, the binding and the
   graph version that authored it? For entries after L1.2b, yes. For exits, partially.

---

## 5. The regulatory line, named rather than answered

Running a bot on your own account is one legal category. Holding other people's execution
credentials, sending orders on their behalf and telling them what they own is a different one, and
it is **owner gate #6**. The technical findings above do not depend on how that resolves, but the
*deadline* for fixing them does. I am not the right party to judge SEBI/broker-authorisation
questions and this document does not attempt to.

---

## 6. Recommended order

1. **F-3 backup into git + a restore drill.** Hours, not days. Removes the worst
   unknown-unknown.
2. **F-2 `synchronous=FULL` for the money plane**, with the write benchmark re-taken.
3. **F-1 durable exit intents.** The largest of these and the most safety-relevant.
4. **Three-plane ADR**, deciding the money plane's home. Then F-4/F-5 fall out of it.
5. Phase 7 drills as acceptance, not as discovery.

None of this is a deployment. All of it is ahead of onboarding a single external user.

---

## 7. What this review is not

Single reviewer, one pass, no adversarial verification, and I wrote it — which by this repo's own
rule disqualifies me from being its reviewer. It reads the entry lifecycle, the exit path, the
durability pragmas, the deploy script and the funds path. It does **not** cover: partial fills and
average-price arithmetic under crash, the risk-loop's behaviour when the DB is unavailable mid-tick,
concurrent square-off versus manual close, notification loss, or anything in the research plane.

Treat the findings as leads that were checked against code, not as a completed audit.
