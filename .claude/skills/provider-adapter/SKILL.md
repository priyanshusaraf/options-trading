---
name: provider-adapter
description: Required for broker or market-data provider work in Strategy OS — adding a broker, changing an adapter, connection/capability modelling, or instrument resolution. Enforces the reuse-and-licence sequence and conformance evidence before closure.
---

# Provider adapter

Follow the sequence. Skipping to implementation is how symbol handling forks per adapter.

## 1. Inspect Strategy OS first

`app/providers/base.py::MarketDataProvider` (data) and `app/engine/broker_protocol.py::Broker` /
`ExecutionVenue` (execution) are separate protocol seams. Inspect the composition root too:
`providers/factory.py` currently returns one singleton and `broker_factory.make_broker(provider)`
still derives execution from it. Protocol separation without role selection is not split routing.

`kite_venue.py` is the target home for `MIS`/`NRML`/GTT/SL-M, but verify the claim from imports:
`live_broker.py` currently reaches Kite product/exchange helpers through `kite_order_client.py`.

## 2. Inspect OpenAlgo — for behaviour, never code

`~/dev/openalgo`, **AGPL-3.0**, 35 Indian broker adapters. Worth learning:

- the adapter directory contract (auth · orders · data · funds · margin · GTT · symbol master ·
  streaming), which is why "add a broker" is a known-shape task for them;
- the canonical symbol vocabulary sitting **above** the adapters, built before them;
- market-data fan-out invariants: the **SUB binds and every PUB connects**; multi-device login
  must not tear down the shared feed;
- error normalisation and rejection taxonomies.

**Re-derive, never transcribe.** Copyright does not cover architecture; it does cover files.

## 3. Inspect `~/dev/multiverse-of-ideas`

Start at `docs/engineering/reference/multiverse-index.md`. Only `reviews/` prose may cross.

## 4. Classify reuse and licence

DIRECT REUSE / ADAPT-WRAP / REFERENCE ONLY / REJECT, with the licence file's first lines read —
never a grep. If actual code reuse starts to look necessary, **stop and raise an owner/legal
gate**; do not proceed on your own judgement.

## 5. Define capabilities explicitly

Which of these does this connection serve: execution · market/limit/stop orders · GTT · slicing ·
positions · funds · historical data · streaming · option chains · depth · postbacks? Do not
pretend parity. Capability resolution lives in `app/core/`, never `app/engine/` (C13).

Before adapter #2, prove the runtime can bind market data, execution, account/portfolio and
instrument resolution independently. A test must select data connection A and execution
connection B. Adding another value to the process-global provider factory is not that proof.

## 6. Preserve canonical instrument identity

Provider token/symbol/security-id maps **onto** the Strategy OS canonical instrument. A strategy
definition never holds a provider identifier.

## 7. Implement a thin adapter

Quirks at the edge. No second symbol table, charge model, frame converter or order path.

## 8. Conformance tests

One suite both adapters pass, and it must **fail an adapter that lies about a capability**. Add a
runtime proof for concrete adapter failure semantics when health or recovery depends on them; a
test double must not raise when the real adapter returns `None` for the same failure.

## 9. Failure and recovery verification

`HTTP 200` is not evidence. Exercise: rejection · partial fill · duplicate suppression /
idempotency · order-status polling · token expiry mid-flight · reconnect · postback ordering ·
restart recovery. Verify the expected adapter was selected, the request mapping is right, the
normalized response is right, and provenance is recorded.
