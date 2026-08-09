# Upstox, data-only — what the API actually is, before writing the adapter

**Status: design, not code.** Written 2026-08-09 from the Upstox Developer API documentation.
Nothing here is verified against a live Upstox session, because that needs credentials the owner
has not issued — see §6. The point of this document is that the next session writes the adapter
against *these* facts instead of against the shape Kite trained us to expect.

**Scope when it lands: `HISTORICAL_DATA` and `LIVE_QUOTES`. Nothing else.** No execution, no
option chain, no streaming. Zerodha keeps every order path; this is the connection that proves
"Upstox data, Zerodha execution" is real rather than architectural.

---

## 1. The headline: Upstox breaks four assumptions Kite quietly installed

Each one already has an obligation in `tests/provider_conformance.py`. That is the return on
having built the contract first — these are not hypotheticals, they are documented differences,
and every one of them would otherwise have been discovered as a wrong number.

| Upstox behaviour | Kite's behaviour | Obligation that catches it |
|---|---|---|
| Candles are **arrays** `[ts, o, h, l, c, volume, oi]` | dicts keyed `date/open/…` | `Candle` type check |
| Documented example is **newest-first** | oldest-first | strictly-increasing `ts` |
| Interval vocabulary is **not** Kite's (below) | `15minute` &c. | modal `ts` delta == requested interval |
| Timestamps are `+05:30`-**aware** | aware, stripped at the adapter | naive-IST timestamps |

The interval difference is the dangerous one, because it fails silently in both directions.
Upstox v2 historical accepts only `1minute, 30minute, day, week, month` — error `UDAPI1020`
enumerates exactly that set. **Our live interval is `15minute`, which is not in it.** A naive
adapter that passes our interval through gets an error; a *helpful* adapter that "rounds" to
`30minute` or `1minute` returns bars at the wrong horizon, and every `z_length` / `ema_length`
computed on them is wrong with nothing raising. The v3 historical API adds a unit + interval
split for finer control, and is the version to use — but see §5, the ordering is unpinned.

## 2. Instrument identity — this is the interesting part

An Upstox instrument key is `SEGMENT|ISIN`:

```
NSE_EQ|INE848E01016          a cash equity, addressed by ISIN
NSE_INDEX|Nifty 50           an index, addressed by name
```

**It is not a tradingsymbol, and it cannot be derived from one.** There is no transformation
from Kite's `NIFTY 50` / `RELIANCE` to `INE848E01016`; it is a lookup against Upstox's own
instrument master.

That settles a question this repo has been circling. `Instrument.spot_symbol` is a Kite
tradingsymbol and `option_name` is a Kite instruments-dump concept, both sitting on the canonical
object. Upstox cannot use either. So the `InstrumentResolver` seam is not a nicety — it is the
only place an Upstox mapping can exist, and this adapter is the second real mapping that makes
the relocation provable rather than theoretical. `UpstoxInstrumentResolver` must read **only**
`inst.key`; `test_instrument_resolution.py` already enforces that for non-Kite resolvers, and
`check_instrument_identity` requires the mapping to carry `provider == "upstox"` so it can never
be applied against a Zerodha connection.

The instrument master is its own component in every mature implementation (OpenAlgo gives each
broker a `database/master_contract_db.py`; see `multiverse-index.md` §7). Ours should be a
seeded mapping table, refreshed like Kite's daily dump, not a hard-coded dict.

## 3. Endpoints the first slice needs

| Need | Endpoint | Notes |
|---|---|---|
| History | `GET /v3/historical-candle/…` | v3 for the interval flexibility; **parameter order unpinned, §5** |
| LTP | `GET /v3/market-quote/ltp` | batch, up to 500 instruments per call |
| OHLC quote | `GET /v3/market-quote/ohlc?instrument_key=…&interval=1d` | keyed by instrument key in the response |

Auth is `Authorization: Bearer <access_token>`. The batch LTP is a genuine advantage over the
per-key round trips the mock's default `live_snapshot` makes, and is the natural place to
override `live_snapshot` — but not in the first slice.

## 4. Errors map cleanly onto the failure channel

Upstox returns coded errors, which is more than Kite gives us:

| Code | Meaning | Adapter behaviour |
|---|---|---|
| `UDAPI1021` | instrument key malformed | resolution bug — refuse, do not retry |
| `UDAPI100011` | unknown instrument key | `None` from the resolver |
| `UDAPI1020` | unsupported interval | **refuse loudly**; never substitute a nearby interval |
| `UDAPI1149` | endpoint needs a paid plan | a capability this connection does not have |

`ProviderReadError` (added 2026-08-09) is the channel for the transport-level failures. Note the
distinction the codes let us make and Kite does not: a malformed key is *our* bug and must not be
retried, whereas a 5xx or an expired token is an outage. `UDAPI1149` is the more interesting one
— a plan-gated endpoint is a connection that genuinely lacks a capability, which is the first
real case for validating a deployment's required capabilities before activation.

## 5. What is NOT pinned, and must be before the adapter ships

1. **Historical path parameter order.** The documentation shows both
   `/{interval}/{from_date}/{to_date}` and a to-then-from ordering in different places. Getting
   this backwards returns an empty window, not an error — a silent wrong answer. Pin it against
   the live API, or against a recorded response, before trusting it.
2. **The exact v3 unit/interval spelling** (`unit=minutes&interval=15` vs a path segment).
3. **Whether v3 candles are ascending or descending.** The v2 example is descending. Do not
   assume; sort, and let the conformance obligation prove the sort is real.
4. **Whether the newest candle is still forming.** Kite's is, and `kite.py` drops it. If Upstox's
   is too and we do not drop it, every live signal repaints — the conformance contract checks
   this against a real clock, so an adapter that gets it wrong fails rather than trades.

## 6. Owner gate — credentials

The adapter can be written and held to the whole conformance contract through a faithful double,
exactly as Kite is. It **cannot** be verified against the live Upstox API without an API key and
access token, and issuing those is the owner's call. Until then the honest claim is "conformant
against a documented double", never "working".

Nothing in this slice touches execution, so it crosses no other gate.

## 7. The sequence when it lands

1. Seed the Upstox instrument-master mapping for the existing universe (ISIN per canonical key).
2. `UpstoxInstrumentResolver` reading only `inst.key`, stamping `provider="upstox"`.
3. `UpstoxProvider(MarketDataProvider)` declaring **only** `HISTORICAL_DATA` and `LIVE_QUOTES`,
   normalising: array candles → `Candle`, `+05:30` → naive IST, sort ascending, drop the forming
   bar, map our interval vocabulary → theirs and **refuse** what does not map.
4. A `ConformanceCase` for it in `CASE_FIXTURES`, with `break_transport` — the suite refuses to
   let a `MarketDataProvider` subclass exist without one, so this is not optional.
5. Only then: the `spot_symbol` / `option_name` relocation, with Kite's resolution proven
   byte-identical across the move.
