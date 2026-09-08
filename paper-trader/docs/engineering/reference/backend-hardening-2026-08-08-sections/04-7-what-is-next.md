Reference: [section index](../backend-hardening-2026-08-08.md). Read with its scope; this is not a new assignment.

## 7. What is next

1. **Adapter #2 (recommend Upstox).** The abstraction is now testable rather than theoretical:
   capabilities, an instrument-resolver seam, and a second-broker reachability suite exist. The
   adapter is what proves them, and it carries the `spot_symbol`/`option_name` relocation with it.
2. **A conformance suite both adapters pass** — and that fails an adapter which lies about a
   capability. Today's tests prove the seam; they do not yet hold two adapters to one contract.
3. **Pool sizing + saturation telemetry.** Make the pool explicitly configured rather than
   an accidental default, and report utilisation on `/api/health` so saturation is visible
   before it is total. The sizing value itself is the owner decision above.
4. **Connection objects.** Capabilities now exist per provider; the remaining piece is a
   `Connection` record (a user's credentialed link) so one account can hold several, and a
   deployment can validate its required capabilities before activation.
5. **Finish the leakage audit** — §5.3, starting with cache key dimensionality and the DSR
   deflation claim, which is the one with a known prior defect.
6. **Ownership columns and identifier namespacing** — §2.1.

## 8. Method notes worth keeping

- **Mutation-prove every guard, including the ones that pass before and after.** A test
  that is green on both sides of a change proves nothing until a wrong change is shown to
  redden it. That is what caught the vacuous seed in §3.2.
- **Settle "did I break this" with a worktree at HEAD.** Used here to separate a
  pre-existing red from a new one; both the isolated run and the full-suite run at HEAD
  were needed, because the failure only existed in the second.
- **An oracle written in the implementation's own idiom agrees with a wrong
  implementation.** Compute expected values by a different route.


---

## 9. The provider conformance contract, and what it found (2026-08-09)

`b47e8f5..ca6f231` is published and its **exact-head CI run `31303084479` is green** across
backend, frontend and deterministic smoke. That closes the verification gap this phase carried.

### 9.1 Why a second contract was needed

`test_provider_capabilities.py` checks that a declared capability has a method behind it which
is not the base class's default. That is structural, and three adapters written to lie in the
three ways that cost money pass it clean — measured, not assumed:

```
liar-stub        honesty-check offenders: NONE — the guard passes it
liar-candles     honesty-check offenders: NONE — the guard passes it
liar-futures     honesty-check offenders: NONE — the guard passes it
```

`tests/provider_conformance.py` is the semantic contract; `tests/test_provider_conformance.py`
runs every adapter through it and proves it can fail one. It lives under `tests/` deliberately:
its only consumer is CI, `conform()` places live reads, and `break_transport` is destructive to
the connection — so an activation-time capability precondition is a *different* mechanism, not a
relocation of this one. Shipping it under `app/` would have been a mechanism wired to nothing.

### 9.2 Four defects, all found by the contract on its first runs

1. **`ReplayProvider.option_ltp` took one argument; `MarketDataProvider.live_snapshot` calls it
   with five.** Any open option position in a replayed session raised `TypeError` inside the
   provider; `mark_and_exit_positions` caught it, recorded a `quote` health failure and marked
   nothing. The position stayed unmarked for the whole run — no trail, no staleness, no exit.
   A forensic tool had quietly stopped reproducing the day it was replaying.
2. **`MockProvider` implemented futures pricing and never declared `FUTURES_QUOTES`.** The
   capability gate then fenced the index-futures segment off from the only connection on which
   it could be exercised before going live. Under-declaration is the quiet mirror of a lie.
3. **`KiteProvider` searched `spot_exchange` for `FUT` rows.** NSE index futures live in the
   **NFO** dump, so `get_futures_ltp` resolved to nothing for every index future. Invisible on
   MCX, where `segment == spot_exchange` — which is why the commodity tests passed. `a23157a`
   therefore closed the dated-futures feed **for commodities only**; the earlier wording in this
   record overstated it and is corrected here.
4. **`_process_futures_entries` invented the contract expiry** — found by independent review,
   not by the contract, and the most serious of the four. It read
   `getattr(inst, "expiry", None) or now.date()`; `Instrument` is a frozen dataclass describing
   the economic *underlying* and has no `expiry`, so the entry expiry was always **today**.
   With (2) fixed, the gate opened and a NIFTY futures position booked at **exactly spot**
   (24101.45), because at zero days to run the mock's basis has converged — the underlying
   substituted for the contract, arriving through a working provider. From the next simulated
   day the held expiry no longer priced, `_mark_exit_futures` marked nothing, and
   `handle_overnight` no-ops on the mock, so the position could never exit.

Fix for (4): `MarketDataProvider.front_month_expiry` — concrete, defaulting to `None`, the same
pattern `get_futures_ltp` established. The connection is the only thing that knows its own
listed series. Kite answers from the near-future row (and `_near_future` now reads `inst.segment`
too, so the two sibling lookups no longer disagree); the mock answers from the expiries its own
option chain uses; replay inherits the refusal. The runner honours `None` with
`FUTURES_NO_CONTRACT` and opens nothing.

### 9.3 Evidence

```
$ .venv/bin/python -m pytest tests/test_provider_conformance.py
30 passed

$ .venv/bin/python scripts/provider_conformance_mutations.py
8/8 mutations reddened their own guard and were restored · suite green · EXIT 0
```

The contract's first draft was hardened after two independent reviews demonstrated it did not
hold a *data-only* adapter to anything: a deliberately wrong Upstox stub — daily bars for a
15-minute request, three bars for thirty days, the still-forming bar included, tz-aware stamps,
and a dead transport serving cache — produced **zero** violations. It now produces five. Added:
bar completeness against a real clock, modal interval spacing, the requested window, naive-IST
timestamps, front-month resolution priced at a real basis, instrument-identity provenance, and
market-data behaviour under a broken transport. Two of the contract's own checks could not fail
at all (the broken-transport clause allowed every success type; a permanently stuck clock passed)
and were fixed.

### 9.4 Still open — named, not solved

1. ~~**`get_candles` has no failure channel**~~ — **DONE 2026-08-09.** `ProviderReadError` is
   the typed refusal; `KiteProvider.get_candles` raises it (carrying the SDK's message, which
   `_is_auth_error` reads) instead of returning `[]`, and `[]` now means only "no bars". The
   engine's `candle` health failure and `_mark_token_bad` auth latch are reachable for the first
   time — pinned by `tests/test_provider_read_failures.py`, which drives `scan_signals` against a
   failing transport and asserts the latch engages and `last_scan_ok` is *not* refreshed. Two
   mutations prove it: swallowing the failure again, and dropping the message from the wrapper.
   The conformance contract now requires the typed refusal, so Upstox inherits the obligation.
   **This is a live-path change**, in the safe direction: the live candle read now raises where
   it returned `[]`. It alters no order routing, sizing or exit logic, but describing the phase
   as "no live-money path changed" was wrong and is corrected here.
   The three other call sites improve without change — `sweep.py` already records the error on
   the run, `research/data/store.py` no longer content-hashes a Dataset built from an API error,
   and the one unguarded chart route now degrades to an empty panel rather than a 500.

   The original entry is kept below because the *reasoning* is the reusable part.

   **`get_candles` had no failure channel — and the engine's own failure handling was
   consequently unreachable for Kite.**

   `kite.py` catches every exception around `_historical` and returns `[]`, so "the API 500'd",
   "the token expired" and "this instrument has no history" are one answer. But
   `runner.py:725` is written on the opposite assumption — it wraps the call in `try/except`
   and, on an exception, records a `candle` health failure, latches `_mark_token_bad` for an
   auth error so the remaining instruments are skipped rather than re-failing, and breaks the
   scan.

   None of that can fire. The adapter never raises, so on a live token expiry the engine calls
   `health.record_ok("candle")` and refreshes `last_scan_ok[key]` on every tick, then falls to
   `if len(candles) < ema_length + 5: continue` and skips the instrument silently. The operator's
   health surface reports a healthy feed while the connection is returning nothing, and the
   token-bad latch built for exactly this case never engages.

   It degrades toward *no new entries*, which is the safe direction, so this is not an
   emergency — but it means the data-health signal is not measuring what it claims. Settle it
   before Upstox: a second provider doubles the ways a read can fail, and the conformance
   contract's `check_market_data_under_failure` currently has to accept `[]` as a refusal
   because that is the only vocabulary available.
2. **A stale futures position skips its exit check entirely.** `_mark_exit_futures` sets
   `pos_stale` and returns without evaluating the exit, so a position that cannot be marked
   cannot leave. Unreachable today — no futures entry can open — but it is the "nothing may
   block an exit" invariant and it should not stay latent.
3. **The under-declaration check reaches only the capabilities in `_ANSWERED`.** Behavioural
   judgement needs a way to ask "did it answer"; capabilities without one are listed, not
   silently skipped.
4. **The Kite double bypasses `SafePaperKite`**, the wrapper that actually ships between the
   adapter and `KiteConnect`, so the order-endpoint allowlist is not exercised by this suite.
5. **Rate limiting is stubbed out** (`_NoThrottle`), so the suite cannot observe throttling.
   Upstox's limits are not Kite's per-category ones.
