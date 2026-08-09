# Durable Entry Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make every new live entry originate from a committed intent, record broker observations as idempotent immutable events, block uncertain resubmission, and expose measured latency and slippage without changing exit behavior.

**Architecture:** Add ExecutionIntent and ExecutionOrderEvent beside the legacy OrderJournal. A pure reducer derives state from append-only events. New entries use this lifecycle and mirror the old journal during cutover. Existing exits and legacy recovery rows remain on the current path.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2, Alembic, SQLite, pytest.

## Global Constraints

- Never call a real broker, deploy, touch the live database, or alter live flags.
- Use red-green TDD for every production behavior.
- Do not call OrderClient.place until the intent and SUBMIT_STARTED event commit.
- Duplicate or older observations cannot reduce fills, replace the broker order ID, reopen a terminal order, or book twice.
- Exit behavior remains unchanged. Entry persistence cannot block risk-reducing exits.
- Preserve legacy OrderJournal rows and do not invent intent IDs for old orders.
- Use compatibility scopes broker=kite, deployment account_id, and connection_scope=kite:legacy. Do not claim multi-account safety.
- New broker tags are exactly pti- plus the first 16 lowercase hexadecimal characters of the 32-character intent ID.
- Use runtime-supplied naive datetime values, matching current persistence.
- Canonical JSON uses sorted keys and compact separators.
- No authentication, customer tenancy, Upstox, PostgreSQL, queue, microservice, or frontend change belongs here.

---

### Task 1: Immutable execution lifecycle schema

**Files:**
- Create: paper-trader/backend/migrations/versions/20260809_0014_execution_lifecycle.py
- Modify: paper-trader/backend/app/db/models.py
- Modify: paper-trader/backend/tests/test_schema_migrations.py
- Create: paper-trader/backend/tests/test_execution_lifecycle_schema.py

**Produces:** ExecutionIntent, ExecutionOrderEvent, nullable entry_intent_id on Position and Trade, database constraints, indexes, and immutability triggers.

- [ ] **Step 1: Write failing schema tests**

Add these tests:

    test_execution_intent_and_events_survive_a_fresh_session
    test_execution_event_identity_is_unique_per_intent_and_source
    test_execution_events_are_append_only_in_the_database
    test_revision_0014_round_trips_without_rewriting_legacy_rows

The first inserts an intent and INTENT_CREATED, commits, reopens, and reads both. The second expects IntegrityError for duplicate intent/source/source_event_id. The third expects OperationalError for update and delete. The migration test upgrades 0013 to 0014, inspects exact objects, downgrades, and upgrades again while an old journal row stays unchanged.

- [ ] **Step 2: Verify RED**

Run:

    /Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/pytest -q tests/test_execution_lifecycle_schema.py tests/test_schema_migrations.py -k 'execution_lifecycle or revision_0014'

Expected: imports or inspection fail because revision 0014 and the models do not exist.

- [ ] **Step 3: Add the ORM models**

ExecutionIntent fields:

    client_intent_id String(32) primary key
    deployment_id Integer FK deployments.id, indexed, not null
    broker String(32), account_scope String(64), connection_scope String(64), not null
    broker_tag String(20), unique, not null
    intent String(8), CHECK intent = ENTRY
    instrument_key String(64), indexed; tradingsymbol String(64); exchange String(16)
    side String(8); product String(16) nullable; order_type String(12)
    requested_qty Integer CHECK > 0; limit_price Float nullable
    decision_price Float nullable; signal_at DateTime nullable
    strategy_key String(64) nullable; strategy_version String(64) nullable
    context_json Text default {}; created_at DateTime; both not null

ExecutionOrderEvent fields:

    id Integer primary key
    client_intent_id String(32) FK execution_intents.client_intent_id ON DELETE RESTRICT
    source String(24); source_event_id String(64); kind String(32), indexed
    broker_order_id String(32), indexed, nullable; broker_status String(32) default empty
    cumulative_filled_qty Integer CHECK >= 0 default 0
    avg_price Float CHECK >= 0 default 0; observed_at DateTime
    payload_json Text default {}; anomaly String(200) default empty

Create unique constraint uq_execution_event_source_identity on client_intent_id, source, source_event_id. Add indexed nullable entry_intent_id FKs to positions and trades with ON DELETE RESTRICT.

- [ ] **Step 4: Add revision 0014 and append-only triggers**

The migration creates update and delete triggers on execution_order_events. Each trigger aborts with the message execution_order_events are immutable. Downgrade drops the triggers and lifecycle tables, then the two nullable link columns. Follow the existing idempotent downgrade pattern.

- [ ] **Step 5: Verify GREEN**

Run the complete test_execution_lifecycle_schema.py and test_schema_migrations.py modules.

- [ ] **Step 6: Commit**

Commit message: feat(execution): add immutable entry lifecycle schema

---

### Task 2: Pure reducer and transactional store

**Files:**
- Create: paper-trader/backend/app/engine/execution_lifecycle.py
- Create: paper-trader/backend/tests/test_execution_lifecycle.py

**Consumes:** Task 1 models.

**Produces:** ExecutionState, ExecutionLifecycleStore, make_intent_id, make_broker_tag, broker_observation_id, and reduce_execution_events.

NewExecutionIntent is a frozen dataclass containing every ExecutionIntent field except client_intent_id, broker_tag, and context_json; it carries context as a dictionary. NewExecutionEvent is a frozen dataclass containing source, source_event_id, kind, broker_order_id, broker_status, cumulative_filled_qty, avg_price, payload, and anomaly. The store assigns IDs, canonicalizes JSON, and commits timestamps supplied by the caller.

- [ ] **Step 1: Write failing reducer tests**

Add:

    test_duplicate_source_event_is_idempotent
    test_out_of_order_lower_fill_cannot_reduce_quantity
    test_terminal_order_cannot_reopen
    test_broker_order_id_cannot_change_after_ack
    test_two_partial_observations_derive_vwap_remaining_and_new_fill_delta
    test_submit_started_without_ack_requires_reconciliation
    test_realised_slippage_uses_intent_decision_price
    test_latency_uses_persisted_event_times

Use cumulative observations 25 at 100 and then 75 at 102. Derived filled quantity is 75, current cumulative average is 102, and the second incremental fill is 50. Never average cumulative averages.

- [ ] **Step 2: Verify RED**

Run test_execution_lifecycle.py. Expected: module import fails.

- [ ] **Step 3: Implement identifiers**

Use these signatures:

    make_intent_id() -> str
    make_broker_tag(client_intent_id: str) -> str
    broker_observation_id(order_id: str, payload: dict) -> str

Intent IDs use uuid4 hex. The tag is pti- plus the first 16 characters. The observation ID is SHA-256 over canonical JSON containing order ID, uppercase status, integer cumulative fill, rounded average, and reason.

- [ ] **Step 4: Implement the reducer**

ExecutionState exposes client_intent_id, status, broker_order_id, filled_qty, avg_price, remaining_qty, terminal, reconciliation_required, anomalies, four latency measures, slippage_amount, and slippage_bps.

Use event insertion order. Ignore lower cumulative fill for derived state and add an anomaly. Preserve the first broker order ID and flag a later different ID. Terminal state is sticky. SUBMIT_STARTED without ACKNOWLEDGED requires reconciliation.

- [ ] **Step 5: Implement the transactional store**

Use:

    ExecutionLifecycleStore(session)
    create_intent(request: NewExecutionIntent, context: dict, now: datetime) -> ExecutionIntent
    append_event(client_intent_id: str, event: NewExecutionEvent, now: datetime) -> ExecutionOrderEvent
    state_for(client_intent_id) -> ExecutionState
    unresolved_entries(deployment_id, account_scope, connection_scope) -> list[ExecutionIntent]

Each write commits before returning. On a uniqueness collision, append_event rolls back and returns the existing row only if canonical contents match. It raises if the same identity carries different content.

- [ ] **Step 6: Verify GREEN and commit**

Run test_execution_lifecycle.py and test_execution_lifecycle_schema.py.

Commit message: feat(execution): reduce immutable order observations

---

### Task 3: Fail-closed live entry submission

**Files:**
- Modify: paper-trader/backend/app/engine/order_executor.py
- Modify: paper-trader/backend/app/engine/live_broker.py
- Modify: paper-trader/backend/app/engine/kite_order_client.py
- Modify: paper-trader/backend/app/engine/broker.py
- Modify: paper-trader/backend/tests/test_order_executor.py
- Create: paper-trader/backend/tests/test_live_entry_durability.py

**Produces:** An entry-only _execute_entry path. Existing _execute stays on exits.

- [ ] **Step 1: Write failing sequence tests**

Add:

    test_entry_does_not_call_place_when_intent_commit_fails
    test_entry_commits_intent_and_submit_started_before_place
    test_ack_callback_failure_returns_known_order_id_and_never_replaces
    test_new_entry_uses_unique_twenty_character_intent_tag
    test_legacy_and_intent_tags_are_both_recognised

The fake timeline must be intent_commit, submit_started_commit, place, ack_commit, status. Pre-submit failure contains no place. Ack failure calls place once and returns the known order ID with reconciliation required.

- [ ] **Step 2: Verify RED**

Run test_live_entry_durability.py and test_order_executor.py.

- [ ] **Step 3: Surface acknowledgement persistence failure**

Add reconciliation_required: bool = False to OrderResult. If on_placed raises, return ERROR with the known order ID, zero assumed fill, a typed reason, and reconciliation_required=True. Never retry place.

- [ ] **Step 4: Add _execute_entry**

It loads deployment account_id, commits intent, replaces the request tag, commits SUBMIT_STARTED, calls execute_order once, commits ACKNOWLEDGED in on_placed, appends final STATUS_OBSERVED, mirrors OrderJournal for compatibility, and returns result, filled, average, client_intent_id.

Options use decision mid-price when bid and ask are valid and LTP otherwise. Equity uses the passed decision price. Both use the passed runtime now.

- [ ] **Step 5: Expand tag recognition**

Define LEGACY_BOT_TAG=pt-bot and INTENT_TAG_PREFIX=pti-. is_strategy_os_tag accepts the legacy tag or a 20-character intent tag with 16 lowercase hexadecimal suffix characters. Recovery recognizes both. Protective stops keep pt-bot.

- [ ] **Step 6: Link positions and trades**

Set position.entry_intent_id before commit on a real entry. Copy it into every Trade created from that Position. Paper rows remain NULL.

- [ ] **Step 7: Verify GREEN and commit**

Run:

    tests/test_live_entry_durability.py
    tests/test_order_executor.py
    tests/test_order_journal.py
    tests/test_recover_tag_sweep.py
    tests/test_live_broker.py
    tests/test_safety.py
    tests/test_no_live_under_pytest.py

Commit message: fix(execution): persist live entry intent before submit

---

### Task 4: Recovery, fill deltas, and telemetry

**Files:**
- Modify: paper-trader/backend/app/engine/execution_lifecycle.py
- Modify: paper-trader/backend/app/engine/live_broker.py
- Modify: paper-trader/backend/app/engine/kite_order_client.py
- Create: paper-trader/backend/tests/test_execution_lifecycle_recovery.py
- Create: paper-trader/backend/tests/test_execution_telemetry.py

**Produces:** Unresolved-intent recovery and metrics derived only from persisted facts.

- [ ] **Step 1: Write failing recovery tests**

Add:

    test_restart_with_submit_started_and_no_ack_finds_exact_tag
    test_unresolved_intent_blocks_second_submit
    test_duplicate_complete_observation_books_once
    test_out_of_order_partial_never_shrinks_booked_quantity
    test_two_partial_observations_book_only_new_delta
    test_recovery_scopes_deployment_account_and_connection

- [ ] **Step 2: Verify RED**

Run test_execution_lifecycle_recovery.py.

- [ ] **Step 3: Expand normalized order reads**

KiteOrderClient.orders returns only normalized order_id, tradingsymbol, tag, status, filled_qty, avg_price, transaction_type, and exchange. It returns no SDK object or credential.

- [ ] **Step 4: Recover new intents first**

Acknowledged intents query by broker order ID. Submit-started intents search today's order book by exact tag. No match stays blocked. One match records acknowledgement and status. Multiple matches record an anomaly and alert. Book only the positive fill delta above quantity already linked to the intent. Run legacy recovery afterward only for rows without an execution intent.

- [ ] **Step 5: Write failing telemetry tests**

Add:

    test_slippage_uses_persisted_decision_reference_after_quote_changes
    test_buy_and_sell_adverse_slippage_are_positive
    test_latency_uses_persisted_signal_submit_ack_and_fill_times

BUY 100 to 101 and SELL 100 to 99 both produce adverse slippage +1 and +100 basis points.

- [ ] **Step 6: Implement and verify telemetry**

Add execution_metrics(intent, state) -> dict. It reads no provider quote.

Run recovery, telemetry, journal, tag-sweep, startup-reconcile, and reconcile tests.

- [ ] **Step 7: Commit**

Commit message: feat(execution): recover and measure durable entries

---

### Task 5: Compatibility proof and record

**Files:**
- Modify: paper-trader/docs/engineering/workstreams/WS-02-execution.md
- Modify: paper-trader/docs/CONTINUE.md
- Modify: this plan with evidence.

- [ ] **Step 1: Run mutation checks**

Prove named tests fail when separately bypassing pre-submit commit, acknowledgement propagation, event uniqueness, non-regressing fills, and exact-tag recovery. Restore after each mutation.

- [ ] **Step 2: Run full verification**

Run:

    /Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/pytest -q tests research_tests
    PT_PROVIDER=mock PT_EXECUTION=paper /Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python scripts/dryrun.py 700
    PT_PROVIDER=mock PT_EXECUTION=paper /Users/priyanshusaraf/dev/options-trading/paper-trader/backend/.venv/bin/python scripts/backtest_smoke.py
    git diff --check
    git status --short --branch

Expected: zero test failures, LEDGER OK, successful backtest smoke, and no whitespace errors.

- [ ] **Step 3: Update truth and commit**

Record exact guarantees, legacy exit limits, compatibility scopes, migration head 0014, commands and counts, mutation evidence, and the next causal-cache slice.

Commit message: docs(execution): record durable entry evidence

## Plan self-review

- Every production behavior starts with a named failing test.
- Schema, reducer, integration, recovery, telemetry, and verification have explicit interfaces.
- No task changes protective exits or claims multi-account safety.
- Legacy rows remain intact and unbackfilled.
- Tag and compatibility formats are exact.
- Final gates include full suites, smoke scripts, migration proof, mutation checks, and independent review.
