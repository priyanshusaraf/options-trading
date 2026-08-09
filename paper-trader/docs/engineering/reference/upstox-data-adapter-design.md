# Upstox, data-only — the design the adapter is built from

**Status: corrected design, implementation to follow in the same phase.** Revised 2026-08-09
after independent review found five errors in the first draft, the most consequential being a
**scope error on my part**: it treated Upstox credentials as blocking *implementation*. They do
not. Credentials gate **live acceptance**. The adapter is built and proven against transport-level
fixtures and documented doubles first, and credentials are requested only for a bounded
read-only acceptance run at the end.

**Scope: `HISTORICAL_DATA` and `LIVE_QUOTES`. Nothing else.** No execution, no option chain, no
streaming, no account reads. Zerodha keeps every order path.

The three sections below are deliberately separated, because conflating them is how a design
document starts asserting things nobody checked.

---

## 1. Established from the official V3 documentation

Sources: [historical candle
V3](https://upstox.com/developer/api-documentation/v3/get-historical-candle-data/) ·
[intraday candle
V3](https://upstox.com/developer/api-documentation/v3/get-intra-day-candle-data/)

### 1.1 Two endpoints, not one

```
GET /v3/historical-candle/{instrument_key}/{unit}/{interval}/{to_date}/{from_date}
GET /v3/historical-candle/intraday/{instrument_key}/{unit}/{interval}
```

**The path order is `{to_date}` then `{from_date}`** — pinned, not a guess. Reversing it is the
silent-wrong-answer risk in this adapter: it returns an empty window rather than an error.

**The current trading day is served by the separate `intraday` endpoint.** Upstox directs clients
there explicitly. This is the single most important structural difference from Kite, where one
call covers both. A live 15-minute scan therefore needs a **deliberate merge** of the historical
range and the intraday tail — see §1.4.

### 1.2 Interval vocabulary — `unit` and `interval` are separate path segments

Our live 15-minute bar is **`minutes/15`**. It is not `15minute`, and on v2 it did not exist at
all. The mapping from this repository's vocabulary to Upstox's is explicit and total, and an
interval that does not map is **refused**. Never round, never substitute a nearby interval: a
`15minute` request answered with 1-minute or 30-minute bars changes every indicator's horizon
and raises nothing.

### 1.3 Candles are arrays, and the response carries open interest

```json
{"status":"success","data":{"candles":[
  ["2022-11-30T00:00:00+05:30", 125.35, 126.8, 122.1, 123.45, 1542678, 184632]
]}}
```

Index order is `[timestamp, open, high, low, close, volume, open_interest]`. Timestamps are
**`+05:30`-aware** and must be normalised to naive IST, exactly as `kite.py` does — this
codebase's candle epoch is naive IST throughout and the frontend re-anchors offset-less times.

### 1.4 The merge, stated as behaviour

Historical and intraday overlap, and neither ordering may be trusted (§2.1). The adapter must,
deterministically:

1. normalise every timestamp `+05:30` → naive IST;
2. concatenate historical and intraday;
3. **deduplicate by timestamp**, preferring the intraday copy for a shared bar — it is the fresher
   observation of the same interval;
4. **sort ascending**;
5. remove **only** the still-forming bar, decided by the provider clock and the requested
   interval (`ts + interval > now`), never by position in the array.

Step 5 is the one that repaints live signals if it is wrong, and "drop the last element" is not
an implementation of it — that is Kite's shortcut and it is only correct because Kite's ordering
happens to be stable.

### 1.5 Instrument identity is ISIN-based

```
NSE_EQ|INE848E01016      cash equity, addressed by ISIN
NSE_INDEX|Nifty 50       index, addressed by name
```

**There is no transformation from a Kite tradingsymbol to an Upstox instrument key.** It is a
lookup against Upstox's own instrument master (official daily JSON). This is what makes the
`InstrumentResolver` seam load-bearing rather than decorative: Upstox literally cannot read
`Instrument.spot_symbol` or `option_name`, and `test_instrument_resolution.py` already forbids a
non-Kite resolver from doing so.

The mapping is provider-owned data — the official daily JSON master, or a clearly isolated seeded
fixture for the existing universe. **It does not live as mapping logic inside the provider.**

### 1.6 Errors are coded

| Code | Meaning | Adapter behaviour |
|---|---|---|
| `UDAPI1021` | instrument key malformed | our bug — refuse, never retry |
| `UDAPI100011` | unknown instrument key | resolver returns `None` |
| `UDAPI1020` | unsupported interval | refuse loudly |
| `UDAPI1149` | endpoint needs a paid plan | a capability this connection lacks |

Transport failures raise `ProviderReadError` with the API/transport context preserved. `[]` is
reserved **exclusively** for a successful read that contained no bars.

### 1.7 LTP

`GET /v3/market-quote/ltp`, batched, up to 500 instruments per call, keyed by instrument key in
the response. Satisfies the existing `LIVE_QUOTES` contract.

---

## 2. Requires a recorded or live response — do NOT assume

### 2.1 Response ordering

The v2 example is newest-first. **Do not trust the ordering either way.** The adapter sorts, and
the conformance obligation proves the sort is real. This is recorded as a permanent rule, not as
a question awaiting an answer: an adapter that depends on the provider's ordering is one API
revision away from silently reversing every series.

### 2.2 Still open until a real response is seen

- Whether the intraday endpoint's newest bar is the forming one (the merge in §1.4 handles either,
  but the behaviour should be observed rather than inferred).
- Exact error envelope shape for 5xx versus coded application errors.
- Rate limits, and whether they are per-endpoint like Kite's.
- Whether the historical endpoint's `from_date`/`to_date` are inclusive at both ends.

None of these block implementation. All of them are asserted against fixtures now and re-checked
at live acceptance.

---

## 3. Deliberately deferred architecture

### 3.1 A data-only Upstox adapter does NOT yet prove "Upstox data, Zerodha execution"

This is the correction that matters most, and it must not be quietly skipped.

`app/engine/broker_factory.py::make_broker(provider, …)` takes **one** provider object. It builds
the real Zerodha broker only when *that same object* declares `LIVE_EXECUTION`, and it reads
`provider.access_token` and `provider.tick_size` off it for the order client's token and tick
resolution. So selecting Upstox as `PT_PROVIDER` yields a connection that declares no
`LIVE_EXECUTION`, no live broker is constructed, and execution silently falls to paper.

The seam required before the mixed-provider claim is true: **the data provider and the execution
connection must be separately selected and separately held**, rather than being one injected
object that must serve both roles. `app/providers/base.py::MarketDataProvider` and
`app/engine/broker_protocol.py::Broker`/`ExecutionVenue` are already distinct *protocols*; what
does not exist is a place for a user to hold two connections and route the roles independently.

**That work is not in this slice.** The adapter lands as a bounded capability slice, is **left
unselected in production**, and this gap is recorded rather than papered over. Anyone reading a
future claim of "Upstox data with Zerodha execution" should check this section first.

### 3.2 Not in scope

Streaming (the live feed is protobuf over WebSocket — a different problem, not a variation on
Kite's tick format), option chain, account reads, execution, and the
`spot_symbol`/`option_name` relocation. **The relocation waits until this second mapping is
proven**, which is the whole reason it is the second provider rather than a refactor.

---

## 4. Credentials — a live-acceptance gate, not an implementation gate

The adapter is built now and held to the entire conformance contract through transport-level
fixtures, exactly as Kite is. What fixtures **cannot** establish:

- that the pinned path order returns the expected window against the real service;
- the true ordering, forming-bar behaviour and inclusivity of the real endpoints;
- real error envelopes and rate-limit behaviour;
- that our instrument-master mapping resolves to the contracts we think it does.

Those are the assertions that need a **bounded, read-only acceptance run**. Credentials are
requested at that point and never before — and never pasted into chat, committed, or written into
documentation.

Until that run, the honest claim is **"conformant against documented doubles"**, never "working".

---

## 5. Implementation sequence

1. Transport boundary with explicit timeouts; bearer token never logged or persisted.
2. Instrument-master mapping as provider-owned data (official daily JSON or an isolated seeded
   fixture for the existing universe).
3. `UpstoxInstrumentResolver` reading only `inst.key`, stamping `provider="upstox"`.
4. `UpstoxProvider` declaring **only** `HISTORICAL_DATA` and `LIVE_QUOTES`: explicit total
   interval mapping with refusal, array→`Candle` normalisation, historical + intraday merge per
   §1.4, V3 LTP.
5. A `ConformanceCase` at the HTTP/transport boundary — the suite refuses to let a
   `MarketDataProvider` subclass exist without one, so this is not optional.
6. Only then, and only after live acceptance: the `spot_symbol` / `option_name` relocation.
