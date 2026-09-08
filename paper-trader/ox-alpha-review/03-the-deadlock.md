# 03 — The Deadlock: Mechanism Analysis and the Exit

**Question:** why have nine evidence-harness recoveries failed, what is actually going wrong
right now, and how do we get Phase 5 unblocked without a tenth recovery in the same form?

## 1. What the deadlock is (facts on disk)

- Stage `phase1-4-foundation-critical-closure` has been the programme's current stage across many
  controller cycles. Its parent audit verdict: `FOUNDATION_RISK: BLOCKED`,
  `EVIDENCE_CURRENTNESS: STALE/REQUIRES RECHECK`.
- The blocking work collapsed into one artefact class: the **PostgreSQL16 semantic trigger-fixture
  evidence harness** — the machinery meant to prove that supported-old research databases upgrade
  cleanly (audit A-01/A-03/A-04/A-05).
- Nine recoveries of that harness were rejected. Rejection causes (from the frozen preaudit and
  CURRENT.md scope decisions):
  1. Manifest measured an intermediate package while final closure grew it — *evidence changed
     while measuring itself*.
  2. Unmanifested bytecode / nested unowned deps / duplicate JSON keys / incomplete restoration.
  3. Dynamic imports and aliased subprocess calls bypassed static checks.
  4. Embedded candidate data substituted for accepted authority; interpreter drift caused
     unrelated rejection.
  5. Validator compared a 19-file package against an 18-file expectation — *rejected itself*.
  6. Observer rejected a legitimate row that accepted authority permitted — *over-strict oracle*.
  7. Receipts measured 17 of 21 assignment files — *incomplete enumeration*.
  8. FINAL validation required mutation evidence only obtainable by invoking FINAL validation —
     *circular dependency*.
  9. Current state: 7 consolidated findings (`R9-PRE-001..007`), one comprehensive repair
     authorized, third patch forbidden.
- Meanwhile the actual product defects are small and fully specified: A-01 is "the staged
  table-copy path creates table shape but doesn't install triggers before advancing the marker";
  A-02 is "float() accepts bool".

## 2. Root cause — five mechanisms, not bad luck

**(a) Self-reference.** The harness validates a package whose contents include evidence about
the validator. Any growth in the package invalidates earlier manifests (rejections 1, 5, 7, 8).
This is a fixed-point problem: the system demands `validate(proof) ∧ proof ⊨ validate`. Each
repair adds surface area, which invalidates the proof, which requires another repair. **No amount
of effort converges here; the design cannot converge.**

**(b) Completeness demanded over an ill-bounded universe.** "Prove every supported-old upgrade"
requires defining: which historical states exist (all prefixes × both dialects), what "genuine
populated" means for user data, and what happens to states outside support. The programme kept
discovering the universe was bigger than the oracle (rejections 2, 4; the native-oracle and
native-state owner chains each stopped BLOCKED on exactly this). The defect-pattern register's own
critical-boundary rule ("enumerate the complete claimed universe") is correct — but you cannot
enumerate a universe nobody has bounded.

**(c) Static analysis mistaken for authority.** Dynamic imports and aliased subprocess defeated
the static checks (rejection 3). A checker that greps can always be defeated by indirection; the
register knows this (DP-002) but the harness re-committed the sin.

**(d) Oracle/authority confusion.** The observer rejected rows the accepted authority explicitly
permitted (rejection 6) — the mirror image of DP-002. An oracle stricter than the contract fails
legal states.

**(e) Sequencing inversion.** The programme is demanding a perfect evidence machine *before*
fixing the product defect the evidence is about (A-01). Every time the migration fix design moved,
the harness target moved with it. Evidence work downstream of an unfixed defect churns forever.

## 3. Why this matters beyond the deadlock

The same five mechanisms will regenerate wherever the governance asks an agent to produce
*self-certifying meta-evidence*. The register's DP-003/DP-008 already encode the healthy
direction: name the furthest real boundary exercised; independent consumers over self-attestation.
The harness violates its own register. That is the diagnosis in one sentence:

> **The project built a second, informal evidence system outside git and CI, gave it authority
> over acceptance, and that system has properties (self-reference, unbounded universes) that make
> it unfalsifiable-by-construction. The repo's own rules (evidence = reproducible command + output;
> guards proven red by mutation) were the right ones all along.**

## 4. The exit — six steps, no Recovery 10

**Step 1 — Owner decision: narrow the supported migration contract.** The audit explicitly offers
this ("The owner must either prove an independently projected supported old database or explicitly
narrow the supported contract with safe operational handling"). Recommended contract:
- Supported: fresh install at current head; forward replay from empty through every prefix
  (replaying IS genuine history for catalog objects); upgrade from exact N−1 schema state with a
  seeded corpus defined as the state-contract recovery already specified (immutable catalog
  authority + parameterized contract-valid user rows + deterministic witnesses).
- Everything older: restore-based, not migrate-based — documented, refused loudly, never silent.
This converts "prove every historical path" into "prove two paths", which is provable.

**Step 2 — Fix A-01 as an ordinary bounded product slice.** Prevention invariant is already
written by the audit: *every migration stage installs and validates its complete target contract
(table, index, constraint, trigger, marker) before advancing.* Permanent regression: exact seeded
0005→0010 upgrade, one stage per fresh connection, trigger inventory asserted, direct-SQL mutation
refusal, interruption/restart, killed trigger-installer mutation. This is a normal capsule with
normal review — days, not weeks.

**Step 3 — Fix A-02 as an ordinary bounded slice.** Reject `bool` before coercion at every raw
numeric ingress (provider prep, dataframe conversion, dataset encoder); one authoritative
validation helper imported everywhere; regression injects True/False into every OHLCV field across
the full chain and proves refusal end-to-end; mutation-kill the guard.

**Step 4 — Replace the sealed-package lifecycle with repo-native evidence.**
- Permanent regressions live in `tests/`, executed by CI, mutation-proven red like every other
  guard in this repo's history.
- The independent validator becomes a script that validates the *repository state*, never a
  package containing its own evidence. No self-measuring manifests.
- Adopt Codex's own fallback now rather than after Recovery 9 fails: if any residual harness need
  survives, split it into small independently specified components with disjoint ownership.
- The eight historical rejections stay exactly where they are — immutable counterexample corpus —
  and become CI replay cases (each rejection class gets one test that fails if that class regresses).

**Step 5 — Restore collectability first.** Before or alongside Step 2: finish or quarantine the
in-flight edits that break collection (`DeclaredNativeAdapter` import; slow-shard drift guard).
A tree that cannot collect cannot accept evidence.

**Step 6 — Re-run the invalidated checks, then open Phase 5.** FND-05/FND-06/FND-12 recheck plus
the transitive map from the audit against the fixed tree. With SPEC+QUALITY PASS on that narrow
scope, the Phase 5 gate condition ("route the correction and independent review chain through
critical-closure") is satisfiable honestly.

## 5. Expected cost/benefit

Continuing Recovery 9: unknown convergence (nine failures so far; the preaudit authorizes exactly
one more attempt, then forbids a tenth in-form). Steps 1–6: bounded, mostly mechanical, and they
produce permanent value (two real fixes, a CI-enforced migration contract, a counterexample corpus
in CI). The governance system stays intact for everything else — phases, reviews, owner gates,
capsules — because for product slices it demonstrably works (Phase 3 task 12, IR v2, and Phase 4
final-review-5 all converged through it).

## 6. One caution

Do not swing to the opposite extreme. The rejection discipline caught real things — forged
capability assessments (DP-002), the 4-of-24-tables false green, savepoints mistaken for physical
transactions (DP-009). The fix is to point that discipline at *repo-native* evidence under CI,
not to relax it.
