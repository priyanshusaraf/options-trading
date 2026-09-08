Reference: [section index](../0011-l1-ir-runtime-adoption.md). Read with its scope; this is not a new assignment.

**Exit criterion:** a paper session whose ledger reconciles to the paisa, with shadow divergence
from Stage 1 explaining every difference.

### Stage 3 — live adoption **(OWNER-GATED, one instrument, reversible in one command)**

Bind one IR graph to **one** instrument via the existing per-instrument `strategy_key`, which is
DB-persisted and live-applied. Rollback is reassigning that key — no deploy, no restart.

**Preconditions, all required:** Stage 1 divergence at zero on that instrument for the agreed
window; Stage 2 ledger clean; a measured `/api/health` and `/` check; the deployed commit
recorded; and the owner's explicit approval **at this stage specifically**, separate from
approving this ADR.

---

## 6. What stays authoritative at each stage

| Stage | Signals authoritative | Orders | Ledger | Rollback |
|---|---|---|---|---|
| 0 | hand-written | hand-written | untouched | n/a — nothing live changed |
| 1 | **hand-written** (shadow is recorded only) | hand-written | untouched | disable shadow config |
| 2 | IR **in paper only**; hand-written in live | paper broker only | paper | flip the selector |
| 3 | IR on one named instrument | live, that instrument only | live | reassign `strategy_key` |

Hard invariants 1–6 hold unchanged throughout. In particular **invariant 2** (ARM gates entries,
never exits) and **invariant 4** (live/backtest parity) are the two most at risk — #4 above is
already a latent invariant-4 violation, and it is fixed in Stage 0 before anything else proceeds.

---

## 7. Non-vacuous safety proofs required

Each must be proven able to fail, restored, and recorded — the eight-mutation discipline used in
S4.6d:

1. a frame shorter than resolved warmup **cannot** silently produce all-False;
2. an unregistered or drifted `ir.*` key **cannot** silently trade v3 — it must refuse or alarm;
3. an IR strategy without a carried `risk_model` **cannot** silently disable the ATR ratchet;
4. live and backtest agree on the warmup-trimmed bar set for the same graph and frame;
5. the shadow lane **cannot** reach `open_position`, `open_equity_position`, or any order seam
   (patch the broker; the test fails if touched);
6. the paper gate **cannot** bind an IR strategy while `PT_EXECUTION=live`;
7. evaluation cost per scan stays inside the signal-loop budget on a 1 GB box;
8. parity holds through `IRGraphStrategy` on real candles across a parameter sweep, gaps and
   session boundaries — not just through `evaluate()` on a sine wave.

---

## 8. Honest scope and risk

**Scope.** Stage 0 is the largest piece: roughly the size of a full slice band (comparable to
S4.1–S4.3 combined), because it is where six real defects get fixed and where the parity claim is
rebuilt from scratch. Stages 1 and 2 are each about one slice. Stage 3 is hours of work and weeks
of patience.

**Risk, stated plainly.** The severe risks are all *silent-degradation* risks, not crashes:
all-False signals from warmup (#2), a disabled ratchet (#3), and a silent fallback to v3 (#5, #6).
Each fails in the direction of "the bot quietly stops doing what you think it does" — the same
shape as the E0.2 re-anchor bug that reported ₹49,833 against a much smaller real account for
three weeks. That is why Stage 0 fixes them before any shadow data is collected, and why every
proof above is phrased as "cannot silently…".

**The honest counterpoint the owner should weigh.** Adoption makes the research plane pay rent,
but it does not by itself improve trading outcomes. The book says the problem is entry quality:
across 72 trades `TARGET` has fired **zero** times, the largest favourable excursion ever recorded
(1.216%) is below the target it must hit, and the median trade travels further against you
(0.427%) than for you (0.286%). Running the same strategy through a different runtime changes none
of that. **The value of L1 is that it makes the research plane able to change the strategy at
all** — it is the bridge, not the destination.

---

## 9. Boundary

This ADR authorises **design only**. No implementation begins before owner approval. Stage 3 —
live adoption — requires a **second, separate** approval at that stage, and remains subject to the
standing owner gates on the architecture migration and on any sizing, exit, or routing change.
