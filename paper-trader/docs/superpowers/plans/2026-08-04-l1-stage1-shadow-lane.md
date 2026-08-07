# L1 Stage 1 — shadow-only IR lane in the live signal loop

**Owner approval:** granted 2026-08-04 as a **shadow-only integration**. The existing live
strategy remains the sole execution authority. Stage 2/3 (paper, staged, live adoption) are
**not** authorised by this plan and require a separate owner approval.

Reference: ADR 0011 §5 (Stage 1 and its acceptance criteria), §7 (non-vacuous safety proofs).

---

## 1. What is being built

One observer inside `EngineRunner.scan_signals`. For an instrument whose **authoritative**
strategy has a Component IR mirror, the mirror is evaluated on the *same* candle frame the
authoritative strategy just consumed, the two verdicts are compared on the newest completed
bar, and any disagreement is persisted with enough context to attribute it after the fact.

Nothing else changes. The authoritative `sig`/`latest` computation, `self.state[key]`,
`process_entries`, the risk lane, the broker, the ledger and the deploy model are untouched.

### Why pairing is by authoritative strategy key

The only IR graph that exists is `app/ir/strategies/expanding_z.py`, which mirrors the
hand-written `expanding_z_v4`. Evaluating it against an instrument running `trend_impulse_v3`
would compare two different strategies and produce meaningless "disagreement". So the lane
pairs on the authoritative key:

```
SHADOW_PAIRS = {"expanding_z_v4": <expanding_z graph + library>}
```

An instrument whose authoritative strategy has no mirror is skipped, and that skip is counted
rather than silent.

**Consequence the owner must know before reading any agreement number:** production's default
is `trend_impulse_v3`. Unless an instrument is deliberately assigned `expanding_z_v4`, the
shadow lane observes **nothing** in production. Assigning it would change authoritative
trading, which this plan may not do (constraint 16). Recorded in the Stage 1 report, not
worked around.

---

## 2. Constraint → mechanism

| # | Owner constraint | Mechanism | Proof |
|---|---|---|---|
| 1 | isolated observer only | `app/engine/ir_shadow.py`, called from `scan_signals` after the authoritative state is written | integration test |
| 2 | live strategy stays authoritative | shadow returns an observation object; nothing reads it back into `self.state`, `params` or entries | state-identity test |
| 3 | no broker/order/sizing/routing/reconciliation/square-off seam reachable | (a) AST transitive-import guard on the shadow module (b) dynamic test that patches every seam to raise and runs the lane | 2 tests + mutation |
| 4 | no mutation of shared state | frames copied; own DB session; deep-equality assertion over runner state before/after | mutation-detecting test |
| 5 | exceptions contained | every shadow entry point wrapped; injected raise at each layer; authoritative output asserted byte-identical | 4 injections |
| 6 | no persistent cross-frame IR cache | adapter builds a fresh `Cache` per `evaluate()`; shadow constructs no `Cache` at all | static + behavioural guard |
| 7 | disagreement record fields | `ir_shadow_divergence` table, migration `0010` | field-completeness test |
| 8 | fail-closed feature flag, no deploy/restart | `Settings.ir_shadow_enabled = False` + `runtime_config` override; unreadable/absent ⇒ disabled | flag tests |
| 9 | engine + deployment model unchanged | no change to loops, cadences, `deploy.sh`, health | diff review + suite |
| 10 | no frontend | backend + `GET /api/ir-shadow` only | — |
| 11 | measurements | `IrShadowMetrics` + replay harness | Stage 1 report |
| 13 | non-vacuous mutations | `docs/reports/2026-08-04-l1-stage1-shadow.md` records each mutation, the guard it reddens, and the restore | recorded run output |

## 3. Disagreement classification

Persisted `reason`, one of:

- `FLAG_DIVERGENCE` — both lanes produced flags on a settled bar and at least one of the four
  canonical columns differs. `detail` names the columns.
- `INSUFFICIENT_HISTORY` — the graph's resolved warmup exceeds the frame. This is ADR conflict
  #2 and criterion 8: zero of these in market hours, or the live admission guard and the graph
  warmup disagree.
- `MISSING_GRAPH_INPUT` — the frame omits a declared graph input.
- `ADAPTER_REFUSAL` — any other typed `IRAdapterError` (unmappable outputs, invalid risk model).
- `EVALUATION_ERROR` — the IR runtime or a kernel raised.
- `UNEXPECTED_ERROR` — anything else; always a defect, never expected.

Agreement is *not* persisted — it is counted. Evaluation-cost budget breaches are a metric,
not a disagreement class.

## 4. Order of work (each step test-first)

1. classification + frame identity + `observe()` — pure, no DB, no runner
2. metrics
3. model + migration `0010` + store (own session) + retention
4. flag
5. runner hook
6. isolation / containment / mutation proofs
7. `GET /api/ir-shadow`
8. replay measurement harness + report
9. full suite, dryrun, backtest smoke, CI, commit, push

## 5. Out of scope, explicitly

Paper adoption, staged authority, live adoption, per-instrument shadow assignment UI, any
frontend, any change to which strategy an instrument runs.

---

## 6. Closure and what followed (2026-08-04)

**Stage 1 is engineering-closed.** Steps 1–9 landed, plus the warmup/history admission
contract that closed conflict #2: required history comes from the resolved IR contract, not a
constant; available history from the configured interval and `history_days`; an impossible
pairing is rejected *before* evaluation with a reason naming both numbers, so it can never
emit a permanent all-False output or repeat an in-hours refusal. The graph warmup was not
shortened and the authoritative history window was not widened.

Two slices followed, both inside the shadow-only perimeter:

- **ADR 0012 — execution-state ownership.** One binding contract reconciling the six
  mechanisms that express "what runs where", plus one place authority is granted.
  `ir_graph → shadow`, so every ADR 0011 owner gate begins at one reviewed line.
- **The wiring.** `EngineRunner` now consults that contract for every strategy-selection
  decision, proven equivalent to the resolution it replaced. Without this the contract was a
  seventh mechanism: correct, tested, and consulted by nothing — the defect it was written to
  fix.

Section 5 still holds in full. Nothing here grants IR output any influence over orders,
positions, accounting, sizing, routing, exits, reconciliation, risk controls or deployment
authority; `AUTHORITY_BY_SOURCE` still reads `ir_graph → shadow`, and moving it is the
owner's decision, not an implementation detail of a later slice.

---

## 7. L1.3 — execution attribution (2026-08-04)

**L1.2 canonicalised execution selection authority. This slice canonicalises execution
attribution.**

### The defect, as it stood

Selection went through `execution_binding.bind`; the `strategy_key` stamped onto a position
came from `self.strategy_keys.get(key)` — the raw instrument assignment. Those disagree in
exactly the case the fail-safe fallback exists for. Recorded here because the test that
demonstrated it is not kept: a permanent test asserting wrong behaviour is a trap.

```
$ .venv/bin/python -m pytest tests/test_execution_attribution.py -q --tb=short
    assert position.strategy_key == DEFAULT_STRATEGY_KEY
E   AssertionError: assert 'a_strategy_that_was_withdrawn' == 'trend_impulse_v3'
E     - trend_impulse_v3
E     + a_strategy_that_was_withdrawn
```

An instrument assigned `a_strategy_that_was_withdrawn` traded `trend_impulse_v3` — correct,
deliberate, unchanged — and the position claimed the withdrawn key. Two mutations restore
this exact line (intraday and futures write sites) and both redden.

### What changed

- The binding that produced a signal is carried from scan to fill (`executed_binding`) and is
  the attribution at both write sites. The options path already used the resolved strategy.
- `publish_signal(key, execution, state)` is the only writer of a signal state, so the state
  and its binding cannot fall out of step. Nineteen test call sites moved to it.
- A refusal drops the instrument's previous signal state, so it cannot open on a signal
  produced while it was still authorised.
- No schema change, no migration, no repair tool — ADR 0012 §4.1b has the production
  measurement that justifies leaving history alone.

### Boundaries held

Which strategy executes, the signal, orders, fills, sizing, routing, exits, reconciliation,
risk controls and authority are all unchanged; `test_only_the_attribution_changed_the_economics_did_not`
compares a stale-assignment fill against a clean one field by field. Section 5 still holds in
full: `AUTHORITY_BY_SOURCE` still reads `ir_graph → shadow`.

### Two guards that had to be repaired before they were evidence

- **A vacuous mutation.** "Re-resolve the identity at the fill" stayed green against a test
  that flipped the assignment from inside `open_equity_position` — the attribution argument
  is evaluated before the call, so the window was never open. The test now drives the scan
  and the entry as separate halves of a tick.
- **A shared-state leak in the suite, not the slice.** Sixteen sites across five wiring files
  set `r.provider.now` on the process-wide provider singleton and never restore it, freezing
  the market clock for everything that follows. Ten attribution tests failed in the suite and
  passed alone. Fixed once, in the rootdir `conftest.py`.
