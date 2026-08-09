# Scalable Backtest Sweep Design

## Objective

Scale the exact backtest pipeline beyond the 100 instruments × 5 intervals example without
trading accuracy for throughput. The measured tiers are 100 × 5, 500 × 5, and 1,000 × 5;
the first tier is a baseline, not a product limit.

## Truthful warm modes

A normal refresh must read each requested instrument/interval dataset once. The provider APIs do
not expose revision tokens, conditional reads, or pushed invalidation, so request metadata cannot
prove that historical bytes are unchanged. Claiming zero provider reads on a refreshed trailing
window would reintroduce the stale-history defect fixed by cache schema v8.

Two modes are distinct:

- **Refresh warm:** acquire each dataset once, recompute its exact address, then skip every
  strategy simulation whose execution address matches. Budget: `instruments × intervals` reads.
- **Pinned warm:** explicitly clone an immutable prior run or evaluate against a persisted dataset
  address. This may make zero provider reads truthful. It must never be an implicit interpretation
  of “run this window again.”

## Staged architecture

1. Acquire and validate one immutable candle snapshot per instrument/interval/window, outside the
   strategy loop. Fan acquisition errors out to one result per requested strategy.
2. Prepare the canonical frame once per dataset and evaluate each strategy once. Spot and premium
   replay consume the same signal output; exact trade, metric, and serialized-artifact parity is a
   hard gate.
3. Persist results and progress in atomic batches of at most ten cells. Provider reads and
   simulation remain outside write transactions. Durable result count is progress authority.
4. Add an explicit pinned-run clone, then a content-addressed local candle store if new parameters
   must be evaluated without a provider refresh.
5. Measure stage timings and operation counts at 500, 2,500, and 5,000 datasets. Concurrency is
   considered only after provider throttles and database write limits are measured.

## Operation budgets

For `D = instruments × 5 intervals` and `S` strategies:

| Tier | Datasets | Refresh reads | Pinned reads | Frame preparations | Signal evaluations | Write transactions, batch 10 |
|---:|---:|---:|---:|---:|---:|---:|
| 100 × 5 | 500 | ≤500 | 0 | ≤500 | ≤500 × S | ≤51 including run creation |
| 500 × 5 | 2,500 | ≤2,500 | 0 | ≤2,500 | ≤2,500 × S | ≤251 including run creation |
| 1,000 × 5 | 5,000 | ≤5,000 | 0 | ≤5,000 | ≤5,000 × S | ≤501 including run creation |

Wall-clock targets require measurements against the real data service. Offline mock numbers must
report provider, identity, simulation, and persistence time separately.

## Invariants

- A revised older candle with the same final timestamp remains cold.
- One strategy cannot mutate the candle snapshot observed by another strategy.
- Shared preparation is byte-for-byte equal to independent cold evaluation for every stored
  result field except row/run identity and computation time.
- A batch transaction changes result rows and progress together or neither.
- No result is marked complete before its row is durable.
- SQLite stays the current single-writer authority; batching does not claim distributed workers.

