# Configurable Entry Order Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an operator explicitly choose automatic, market, or limit entry routing while preserving durable recovery and existing safety vetoes.

**Architecture:** A pure entry-order planner separates purpose from side and returns the complete requested order instruction. Runtime and scoped configuration validate a closed three-value mode. Options use book-aware planning; equities preserve legacy automatic market routing but support explicit side-aware limits from their reference price. `LiveBroker` freezes the resulting request into the existing durable lifecycle.

**Tech Stack:** Python 3.12, Pydantic Settings, SQLAlchemy, pytest, React 18, TypeScript, Vitest.

## Global Constraints

- Default `AUTO` behavior must remain backward compatible.
- No broker call may occur before the effective order instruction is committed as an execution intent.
- No timeout path may automatically resubmit or reprice an unresolved order.
- Exit behavior remains market-only in this slice.
- Tests must fail for the missing behavior before production code changes.

---

### Task 1: Closed runtime setting

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/core/runtime_config.py`
- Modify: `backend/app/core/scoped_config.py`
- Test: `backend/tests/test_runtime_sltp.py`
- Test: `backend/tests/test_scoped_config.py`

**Interfaces:**
- Produces: `Settings.entry_order_mode: str` with canonical values `AUTO | MARKET | LIMIT`.
- Produces: runtime and scoped overrides that reject all other values and normalize accepted case to uppercase.

- [ ] **Step 1: Write failing tests**

```python
def test_entry_order_mode_accepts_closed_case_insensitive_values():
    assert "error" not in set_override("entry_order_mode", "limit")
    assert effective()["entry_order_mode"] == "LIMIT"

def test_entry_order_mode_rejects_unknown_value():
    assert "error" in set_override("entry_order_mode", "iceberg")
```

- [ ] **Step 2: Run tests and verify they fail because the setting is absent**

Run: `pytest -q tests/test_runtime_sltp.py tests/test_scoped_config.py`

- [ ] **Step 3: Add the setting and one shared key-aware coercion path**

Add `entry_order_mode = "AUTO"`, add it to `OVERRIDABLE`, define the three allowed values, and make runtime plus scoped resolution use the same canonical coercion.

- [ ] **Step 4: Run the focused tests**

Run: `pytest -q tests/test_runtime_sltp.py tests/test_scoped_config.py tests/test_runtime_config_schema.py`

### Task 2: Purpose-aware pure planner

**Files:**
- Modify: `backend/app/engine/execution_policy.py`
- Test: `backend/tests/test_execution_policy.py`

**Interfaces:**
- Produces: `plan_order(purpose, side, bid, ask, ltp, top_qty, lot_qty, params) -> OrderPlan`.
- Produces: `plan_reference_entry(side, reference_price, params) -> OrderPlan` for paths without a book snapshot.

- [ ] **Step 1: Write failing planner tests**

```python
def test_forced_limit_prices_buy_and_short_entry_in_opposite_directions():
    buy = plan_order("ENTRY", "BUY", 99, 101, 100, 1000, 10, {**P, "entry_order_mode": "LIMIT"})
    sell = plan_order("ENTRY", "SELL", 99, 101, 100, 1000, 10, {**P, "entry_order_mode": "LIMIT"})
    assert buy.limit_price > 100
    assert sell.limit_price < 100

def test_short_entry_is_not_misclassified_as_exit():
    plan = plan_order("ENTRY", "SELL", 99, 101, 100, 1000, 10, {**P, "entry_order_mode": "LIMIT"})
    assert plan.action == "LIMIT"
```

- [ ] **Step 2: Run tests and verify the old side-only API fails**

Run: `pytest -q tests/test_execution_policy.py`

- [ ] **Step 3: Implement purpose-aware planning with the existing hard veto**

Keep exit market behavior, preserve `AUTO`, make forced `MARKET` skip known thin or over-wide books, and compute side-aware `LIMIT` caps.

- [ ] **Step 4: Run the planner tests**

Run: `pytest -q tests/test_execution_policy.py`

### Task 3: Options and equity live-entry integration

**Files:**
- Modify: `backend/app/engine/runner.py`
- Modify: `backend/app/engine/broker.py`
- Modify: `backend/app/engine/live_broker.py`
- Test: `backend/tests/test_execution_routing_engine.py`
- Test: `backend/tests/test_live_broker.py`
- Test: `backend/tests/test_live_entry_durability.py`

**Interfaces:**
- `PaperBroker.open_equity_position(..., plan: OrderPlan | None = None)` accepts but does not fabricate live fills.
- `LiveBroker.open_equity_position(..., plan: OrderPlan | None = None)` submits the planned request.
- Every live entry intent persists the effective order type and limit price.
- `OptionQuote` preserves top bid/ask quantities so a forced market request cannot bypass the known-thin-book veto merely because the provider discarded depth.
- Venue tick normalization happens before durable intent creation, so the persisted request and submitted request are identical.

- [ ] **Step 1: Write failing integration tests**

Add one option test and long/short equity tests that inspect `FakeClient.placed[0]`. Add a lifecycle assertion that reads `ExecutionIntent.order_type` and `limit_price` after submission. Add provider and live-broker tests for top-of-book quantity and pre-intent venue-tick normalization.

- [ ] **Step 2: Run the focused tests and verify equity still hardcodes market**

Run: `pytest -q tests/test_execution_routing_engine.py tests/test_live_broker.py tests/test_live_entry_durability.py`

- [ ] **Step 3: Thread the plan through the runner and broker boundary**

Options call the purpose-aware book planner with the entry-side top quantity. Equity calls `plan_reference_entry` and passes the plan to both paper and live broker implementations. `LiveBroker` refuses `SKIP`, resolves the venue tick, constructs the final `OrderRequest`, and lets `_execute_entry` persist that exact request before placement.

- [ ] **Step 4: Run focused execution tests**

Run: `pytest -q tests/test_execution_policy.py tests/test_execution_routing_engine.py tests/test_live_broker.py tests/test_live_entry_durability.py tests/test_execution_lifecycle.py`

### Task 4: Operator UI control

**Files:**
- Modify: `frontend/src/views/overridable.ts`
- Modify: `frontend/src/views/settingsMeta.ts`
- Modify: `frontend/src/views/SettingsView.tsx`
- Test: `frontend/src/views/settingsMeta.test.ts`
- Test: create `frontend/src/views/SettingsView.test.tsx` only if the existing test harness supports component rendering without new dependencies.

**Interfaces:**
- The Settings UI renders `entry_order_mode` as a select with `Automatic`, `Market`, and `Limit` choices.
- The backend schema is the source of truth for closed choices; the frontend does not duplicate the accepted value list.

- [ ] **Step 1: Write a failing metadata/control test**

Assert the frontend whitelist includes `entry_order_mode`, the metadata explains all three modes, and backend choice metadata drives a select rather than free text.

- [ ] **Step 2: Run the frontend test and verify it fails**

Run: `npm test -- --run src/views/settingsMeta.test.ts`

- [ ] **Step 3: Add closed choice metadata and select rendering**

Publish canonical values `AUTO`, `MARKET`, and `LIMIT` from the backend runtime schema; render those choices as a native select and keep the API payload unchanged.

- [ ] **Step 4: Run frontend tests and build**

Run: `npm test -- --run src/views/settingsMeta.test.ts`

Run: `npm run build`

### Task 5: Verification and roadmap evidence

**Files:**
- Modify: `docs/engineering/workstreams/WS-02-execution.md`
- Modify: supervisor checkpoint document selected by the roadmap audit.

**Interfaces:**
- Produces: exact evidence for explicit order modes and a declared remaining fill-model gap.

- [ ] **Step 1: Run backend suites**

Run: `pytest -q tests research_tests`

- [ ] **Step 2: Run deterministic smoke checks**

Run: `python dryrun.py 700`

Run: `python backtest_smoke.py`

- [ ] **Step 3: Record only verified claims**

Mark configurable live entry order selection complete only if all focused and branch-wide tests pass. Keep backtest limit-fill parity open until the separate versioned fill-model slice lands.
