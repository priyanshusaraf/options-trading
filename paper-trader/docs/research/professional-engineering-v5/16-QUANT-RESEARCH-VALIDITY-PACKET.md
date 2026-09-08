# Quant research-validity packet

## Verdict

The current research foundation contains useful methods and strong immutable inputs,
but the legacy experiment route cannot claim confirmatory OOS because qualification
uses the full history before later validation. DSR/PBO and optimizer reconstruction
also remain incomplete until the complete population and answer-changing inputs can
be reconstructed after restart and schema/code evolution.

## Claim-to-method matrix

| Method/claim | Required identity and assumptions | Current evidence | Verdict |
| --- | --- | --- | --- |
| Locked/untouched OOS | Split boundaries fixed before qualification/selection; OOS suffix cannot affect candidate set | Chat 1 RED records the same full rows in qualification and validation | `FAIL` for confirmatory label; result may be exploratory only |
| Walk-forward | Chronological train/select/evaluate windows; path-dependent warmup/state; overlap policy | Modules/tests exist; full preselection isolation and restart reconstruction not yet proved here | `PARTIAL` |
| DSR | Complete trial population; effective independent-trial count/correlation; Sharpe dispersion; length, skew, kurtosis; method version | Trial rows and some statistics persist; exact reconstructed inputs remain under-proved | `UNVERIFIED` |
| PBO/CSCV | Complete candidate performance matrix; fixed selection metric/order; symmetric partitions | PBO code exists; stored matrix/population reconstruction is incomplete | `UNVERIFIED` |
| Bootstrap confidence | Exact resampling unit and dependence assumption; seed/runs; method identity | Current implementation resamples individual trades IID without an explicit dependence test | `PARTIAL / ASSUMPTION MISSING` |
| Monte Carlo | Exact resampled object, dependencies preserved/lost, seed/runs and baseline | Required by product scope but not proved in the accepted path | `UNVERIFIED/ABSENT FROM GOLDEN PATH` |
| Parameter neighbourhood/sensitivity | Declared baseline, grid/neighbourhood, complete outcomes and selection history | Product scope requires it; no integrated evidence found in Chat 1 | `UNVERIFIED` |
| Costs/fills | Charge schedule, spread, slippage, timing, liquidity, partial fill and capital identity | Bounded equity path has charge identity; derivatives/depth/fills remain unsupported | `PARTIAL` |
| Reproduction | Graph/component/build/data/rulebook/cost/method/search/seed/trials reconstruct exactly | Strong ingredients; candidate order, resolved search population and some vectors omitted | `PARTIAL` |

## DSR and PBO evidence requirements

DSR and PBO must bind one immutable trial-family identity. Minimum evidence:

```text
experiment family and researcher session
graph/component/build versions
dataset/universe/provider/rulebook/correction cutoff
cost, fill and capital assumptions
search space, candidate order, budget, objective and stopping rule
every attempted, failed, cancelled and rejected trial
trial return series or sufficient exact statistics
IS/OOS partitions, purging/embargo policy and all OOS accesses
DSR/PBO method version, seeds and numerical implementation
selected candidate and baseline comparison
```

Old evidence lacking these facts remains readable but cannot be upgraded silently.

## Temporal and Indian-market truth

- NSE contract listings, expiries, strikes, tick sizes, lot sizes and quantity limits
  are effective-dated exchange facts.
- The September 2025 NSE circular changed stock-option tick rules from November
  2025 and made monthly review explicit. A present-day contract dump therefore
  cannot identify historical tick rules.
- Every option result must bind the actually listed contract, effective rulebook,
  provider mapping and available historical fields. The selector receipt does not
  replace exact held-contract identity for exits.
- Absent OI, bid/ask size or depth is unavailable, never numeric zero.
- Underlying-only or synthetic-premium research is a different authored graph and
  cannot validate an option-dependent graph.

## Costs and fills

For V0 equity research, retain exact charge-schedule and next-bar semantics. For
future options/execution evidence, add:

- bid/ask spread and side-aware execution;
- tick-size rounding under the effective rulebook;
- liquidity/quantity constraints and partial fills;
- order latency and ambiguous submission;
- expiry/exercise/settlement rules;
- conservative capacity estimates and adverse stress;
- no same-bar fill unless the authored clock makes it causal.

## Required RED-to-GREEN sequence

1. Mutate only the OOS suffix and prove qualification/candidate selection unchanged.
2. Persist and reopen exact search population/order and all trials.
3. Recompute DSR/PBO from stored evidence after restart and compare exact inputs.
4. Add dependent-trade fixtures before keeping the bootstrap “confidence” label.
5. Preserve old contaminated results with an exploratory/contaminated status.

No statistical threshold is chosen in this packet, and no performance or
profitability claim is accepted.
