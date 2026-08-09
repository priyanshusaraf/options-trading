---
description: Market-data providers, execution brokers, connections, canonical instruments
paths:
  - "paper-trader/backend/app/providers/**"
  - "paper-trader/backend/app/engine/broker*.py"
  - "paper-trader/backend/app/engine/kite_venue.py"
  - "paper-trader/backend/app/options/**"
  - "paper-trader/backend/app/core/instruments.py"
---

# Providers and brokers

Invoke `.claude/skills/provider-adapter` for any broker or provider work — it carries the
required reuse-and-licence sequence.

## The model that must not collapse

Do **not** assume `one user → one broker → broker owns data + execution + positions + funds +
instrument identity`. These are separate roles that may be served by different connections:

- **connection/account** — a credentialed link a user holds
- **MarketDataProvider** — quotes, candles, streaming, option chains, depth
- **ExecutionBroker** — orders, modification, cancellation
- **Account/PortfolioProvider** — positions, funds
- **InstrumentResolver** — provider symbol/token ↔ canonical instrument

The protocol seams exist: `app/providers/base.py::MarketDataProvider` versus
`app/engine/broker_protocol.py::Broker` / `ExecutionVenue`. **The current composition root does
not separate them end to end.** `providers/factory.py` returns one process-global provider and
`broker_factory.make_broker(provider)` derives execution credentials, token refresh and tick
lookup from that same object. A second data adapter does not prove split routing until a test
selects market data from one connection and execution from another.

Do not merge the protocols into one "connection interface". A connection *holds* credentials and
capabilities; role binding selects which connection serves each protocol.

Target examples that must stay expressible: Upstox data → Zerodha execution; Dhan for a
specialised capability → Zerodha positions/execution.

## Canonical instrument identity

**Strategy OS owns economic instrument identity.** Provider tokens, symbols and security IDs map
*onto* a canonical instrument, never the reverse. A strategy definition must never become tied to
a provider-specific identifier — that breaks provider switching, data/execution separation, and
cross-instrument strategies at once.

## Capabilities are explicit, not assumed

Do not pretend every provider has identical capabilities. A connection declares what it can do —
execution, market/limit/stop orders, GTT, slicing, positions, funds, historical data, streaming,
option chains, depth, postbacks — and a deployment should eventually validate its required
capabilities before activation. The vocabulary and the resolution both live in
`app/providers/capabilities.py`; shared code asks `provider.supports(...)` or
`caps.provider_supports(provider, ...)` and consumes the verdict.

**A capability check is not a C13 violation.** C13 forbids branching on *provenance* — where a
component came from — and is enforced subtractively: there is nothing under `app/engine/` to
branch on. Asking an injected connection what it can do is a property query on a dependency, not
a provenance branch, and the engine is where several of those decisions must be made (whether to
size against real funds, whether a futures position can be marked). What must NOT appear under
`app/engine/` is a branch on a provider's *identity* — `name == "kite"` — which is what the
capability model exists to remove.

## Adapters stay thin

Provider quirks belong at the edge. `kite_venue.py` is the intended home for `MIS`/`NRML`/GTT/
SL-M. There is known debt: `live_broker.py` still imports Kite product/exchange helpers through
`kite_order_client.py`. Do not describe the boundary as complete until shared live-broker code
consumes neutral product intent and the concrete venue translates it. A second broker must not
grow its own canonical symbol table, charge model, frame converter or order lifecycle.

New optional provider methods must be **concrete with a safe default** (`get_futures_ltp`
returns `None`), never abstract — an accidental abstract method once broke provider construction
in nine tests at once. `None` means "I cannot price this"; the caller must refuse, never fall
back to spot.

## Licence discipline

`~/dev/openalgo` is **AGPL-3.0** with 35 Indian broker adapters. §13's network clause triggers on
merely serving users, which is fatal to a hosted product. It is a **behaviour reference and a
catalogue of solved problems** — adapter directory shape, canonical symbol vocabulary, market-data
fan-out invariants, error normalisation. **Re-derive, never transcribe.** If real code reuse
starts to look necessary, stop and raise it as an owner/legal gate.

## Evidence for adapter work

`HTTP 200` is not evidence. Verify: the expected adapter was selected · canonical instrument
mapping is correct · the provider-specific request mapping is correct · the normalized response is
correct · provider provenance is recorded · the relevant failure behaviour (rejection, partial
fill, timeout, token expiry, reconnect) actually does what it claims.

For health and recovery tests, exercise the concrete adapter's public semantics. A fake that
raises is not evidence for a real adapter that catches the same exception and returns `None`.
