---
description: Execution, authority, orders, fills, positions, accounting, paper/live separation
paths:
  - "paper-trader/backend/app/engine/**"
  - "paper-trader/backend/app/core/execution_*.py"
  - "paper-trader/backend/app/core/paper_authority.py"
  - "paper-trader/backend/app/core/shadow_deployments.py"
  - "paper-trader/backend/app/strategy/**"
  - "paper-trader/backend/scripts/deploy.sh"
---

# Execution safety

You are in the part of the system that moves real money. Read
`docs/engineering/decisions/0011`, `0012` and `0013` before changing authority, binding or
approval semantics — those questions are settled, not open.

## Invariants that must survive your change

1. **The ledger reconciles to the paisa**: `cash == initial + realized − Σ(open entry_cost)`.
   `scripts/dryrun.py 700` asserts it.
2. **ARM gates entries only — never exits.** `mark_and_exit_positions` marks and fires SL/TP/
   square-off regardless of arm state; the gate lives in `process_entries`. Not getting out is
   worse than any other failure. Consequence: the persisted book must contain only positions
   the real account actually holds.
3. **Paper-by-default is structural.** `SafePaperKite` hard-disables every order/GTT/MF/convert
   endpoint with a fail-closed route allowlist. Live requires `PT_EXECUTION=live` ∧
   `PT_LIVE_ACK=I_UNDERSTAND_REAL_MONEY` ∧ `PT_PROVIDER=kite`, then a per-session ARM that
   resets on every process start. The shipped `.env` satisfies all three — the fallback is
   paper, the configuration is live.
4. **Books are separate.** `app/core/execution_book.py` answers "whose money is this" and the
   answer is the execution mode. Resolution **fails closed to `live`**. `foreign_book_positions`
   reports the other book's open rows loudly rather than adopting them.
5. **Authority is granted at one reviewed line** — `GRANTS` in `app/core/execution_binding.py`.
   Source *and* mode are recomputed at the point of use, so a hand-built binding cannot launder
   itself past the gate. `(ir_graph, paper, authoritative)` is granted;
   **`(ir_graph, live, authoritative)` is ABSENT and is an owner gate.**
6. **Attribution follows selection.** The binding that produced a signal is carried from scan to
   fill. A state entry with no binding is a signal whose author is unknown, and entry paths
   refuse to open on one.
7. **Withdrawing authority withdraws the signal it authored.** `_withdraw_superseded_signals`,
   scoped per instrument to the binding that actually authored the state.
8. **Execution is provenance-blind (C13).** Nothing under `app/engine/` may branch on where a
   component came from. Capability and authority checks live in `app/core/`; the engine consumes
   only the verdict.

## The signal → intent → order boundary

Today several stages are collapsed and that is acceptable. What must not deepen (WS-02 §3):

| Assumption | Why it must not harden |
|---|---|
| one signal ≡ one order | a spread is one decision and several orders |
| one strategy action ≡ one `Position` | a two-leg intent is two rows, one economic result |
| all order-lifecycle state belongs to `Position` | it belongs to the order/fill stage — `order_journal` exists for it |
| an intent can only hold one leg | ratios, hedges and rolls are leg *sets* |

## Sizing and exits — read the box, not the code

`runtime_config` rows shadow code defaults and **ten differ deliberately**. They are the owner's
hand-set decisions from live trading. Reasoning about position size from `config.py` alone will
be wrong. Read `/api/settings`. Never clear an override to make a shipped default take effect
without the owner naming that key.

`intraday_leverage` was removed as a binding cap on 2026-07-22 — do not reintroduce it. Sizing
fails closed to ₹0 if funds cannot be read. Across 72 live trades `TARGET` has fired **zero**
times; read `docs/reports/2026-08-01-exit-sweep.md` before changing an exit.

## Before you claim done

Invoke `.claude/skills/execution-safety-review`, and have `execution-safety-reviewer` review the
diff rather than reviewing it yourself.
