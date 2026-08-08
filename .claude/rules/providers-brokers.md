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

The seams already exist and are already separate: `app/providers/base.py::MarketDataProvider`
versus `app/engine/broker_protocol.py::Broker` / `ExecutionVenue`. Do not merge them into one
"connection interface". A connection *holds* capabilities; it is not a third protocol.

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
capabilities before activation. Capability resolution belongs in `app/core/`, never under
`app/engine/` (C13).

## Adapters stay thin

Provider quirks live at the edge. `kite_venue.py` is the only place `MIS`/`NRML`/GTT/SL-M are
spelled, and that is the pattern. A second broker must not grow its own symbol table, charge
model, frame converter or order path — that breaks "one of anything" and the second one is the
one nobody tests.

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
