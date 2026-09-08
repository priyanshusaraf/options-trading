Reference: [section index](../backend-hardening-2026-08-08.md). Read with its scope; this is not a new assignment.

## 6a. Provider architecture — 2026-08-09

### Done: capabilities replace provider-name branching (`553d871`, `7442e69`)

**The finding.** Ten sites in shared engine/backtest/analytics code branched on
`provider.name == "kite"` or `== "mock"`. Each is really a capability question, and each would
have answered False for a second broker — silently, on the safe-looking branch:

| Site | Consequence for a non-Kite connection |
|---|---|
| `broker_factory.py` | no live order client is ever constructed |
| `runner.py` deployable capital | no account funds read → sizing fails closed to ₹0 |
| `runner.py` futures margin | no real margin quote → sizing refuses |
| `runner.py` cockpit payload | account funds never surfaced |
| `analytics.py` | account equity reported as unavailable |
| `universe.py` (×2) | refuses to build a real instrument universe |

None of them raises. `app/providers/capabilities.py` now carries a role-separated vocabulary
(market data / account / execution / instrument identity / determinism), every provider declares
its set, and all seven kite-gated sites ask the capability instead.

Migration safety was proven **before** the migration: an equivalence table asserts the capability
answer is identical to the name answer, for every provider that exists, at every migrated site —
and a deliberately wrong mapping is shown to fail it. `test_second_broker_is_reachable.py` then
proves what equivalence cannot: a connection named `"upstox"` declaring Kite's capabilities now
passes every gate, while a **data-only** connection is still refused the account and execution
questions. That is the Upstox-data/Zerodha-execution split, asserted.

Deliberately **not** migrated: the three `name == "mock"` sites. `SIMULATED_CLOCK` is broader —
`ReplayProvider` also has an advanceable clock — so migrating them is a behaviour change for
replay, not a refactor. Guarded rather than done quietly.

### Found AND fixed: the index-futures segment had no price feed (latent P1)

The capability honesty check rejected Kite's `FUTURES_QUOTES` declaration on its first run:
**no provider implements `get_futures_ltp`** — not Kite, not mock, not replay. Meanwhile
`runner.py` calls it at three sites to mark futures positions, decide staleness, and price the
delivery-window force close. With the feed unimplemented, `fut` is always `None`, so a position
would never mark on a real price, would read permanently stale, and would be force-closed at
`pos.last_premium` — the **entry** price.

`index_futures_enabled` defaults False and the segment is documented as "fully built and switched
OFF", so this was latent. It stops being latent the moment that flag is flipped, and nothing
would have raised.

Two-part fix. `_process_futures_entries` refuses to open without the capability (`553d871`), and
`KiteProvider.get_futures_ltp` is now implemented (`a23157a`), so Kite declares the capability
honestly and the guard opens for it. The load-bearing behaviour is **exact expiry matching**:
`_near_future` returns the front month, and marking a September position against the August
contract prices a different instrument at a different basis — silently, and flatteringly. Mock and
replay still cannot price futures, so the guard still has something to protect against; a test
asserts it would be dead code if it ever did not.

`index_futures_enabled` remains False. **Live verification against a real Kite session is
outstanding** — the tests stub the dump and the quote call, so they prove the mapping and the
refusals, not the feed.

### Done: instrument identity has a seam, and Kite is behind it (`0a55b3a`)

**Strategy OS does not own instrument identity today; the canonical `Instrument` carries one
provider's symbology inline.** Measured:

- `app/core/instruments.py` — `spot_symbol` is a Kite tradingsymbol; `option_name` is documented
  as "`name` used to find option contracts in **the instruments dump**", a Kite concept;
  `lot_size`/`strike_step` are "re-resolved from the instruments dump each day".
- `app/providers/kite.py:352` builds a Kite quote key directly out of canonical fields:
  `f"{inst.spot_exchange}:{inst.spot_symbol}"`.
- `kite.py:310` tries `(inst.option_name, inst.spot_symbol, inst.key)` as Kite dump lookups.
- `kite.py:297` matches the dump on `row["tradingsymbol"] == inst.spot_symbol`.

So a second provider with different symbology has **nowhere to put its mapping**. It would either
reuse Kite's strings (wrong instrument) or fork the `Instrument` model (breaks "one of anything").
This blocks provider switching, data/execution separation and cross-instrument strategies at once.

`app/providers/instrument_resolver.py` is that somewhere. `ResolvedInstrument` carries the
canonical key as the **only** cross-provider identifier, plus provider-scoped symbol, exchange and
token, plus the connection that produced them — provenance, because a mapping applied against the
wrong broker resolves to a different contract while looking entirely valid.

It shipped with a consumer rather than as a mechanism wired to nothing: `KiteProvider` implements
`resolve_underlying`, and **both** `_underlying_token` and `_underlying_quote_key` now derive from
it. They previously duplicated the index-vs-future branch, which is the `candles.py` shape (two
hand-written implementations of one idea) this project has already paid for once.

Observable success: a fake Upstox resolver maps the same canonical instrument to a different
symbol, exchange and token space — reading only `inst.key` — with no change to `Instrument`.
Proven non-tautological by poisoning the Kite-specific fields; a resolver that read them would
surface the poison.

**What is still outstanding, stated plainly.** `spot_symbol` and `option_name` still live on
`Instrument`. Relocating them is a schema and seed change on the live symbol-resolution path, and
it needs a second real mapping to hold plus a way to prove Kite's resolution is preserved exactly.
Until then `KiteInstrumentResolver` is the only thing permitted to read those fields as symbology,
and a test enforces that a non-Kite resolver does not. **That relocation lands with adapter #2.**
