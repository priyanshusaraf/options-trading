Reference: [section index](../backend-hardening-2026-08-08.md). Read with its scope; this is not a new assignment.

## 14. Moving the pinned store read into the workers (2026-08-10)

The lever sized at the end of §12, executed and measured on the same machine and the same
benchmark shape: pinned/warm run, 500 cells x 5,000 bars, one strategy, mock-free full-mantissa
synthetic candles, benchmark in the session scratchpad. Two independent runs of each build,
interleaved, because the serial baseline moves ~10% run to run on this box.

**The change.** On a pinned run the parent no longer decodes anything. It resolves the pinned
address (no I/O), reads the ~550-byte manifest sidecar for the one planning value it cannot
get otherwise — the effective window's last timestamp, which discriminates the result cache —
and sends the worker the *address*. The worker calls `DatasetStore.get`, which is where
decompress + re-address + manifest comparison now happen, in parallel.

### Before / after

| workers | before s | before ms/cell | before speedup | after s | after ms/cell | after speedup |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 52.9 / 60.3 | 105.7 / 120.5 | 1.00x | 54.8 / 57.9 | 109.5 / 115.8 | 1.00x |
| 2 | 25.3 / 33.0 | 50.5 / 65.9 | 2.09x / 1.83x | 29.0 / 29.6 | 58.0 / 59.1 | 1.89x / 1.96x |
| 4 | 24.8 / 32.5 | 49.5 / 65.0 | **2.13x / 1.86x** | 18.9 / 20.6 | 37.9 / 41.2 | **2.89x / 2.81x** |
| 8 | 32.9 / 36.4 | 65.7 / 72.8 | 1.61x / 1.66x | 18.2 / 20.2 | 36.3 / 40.5 | **3.19x / 2.71x** |

**The 8-worker regression is gone.** Before, eight workers were *slower* than four, because the
parent was also pickling candles it had just decoded. After, eight is at worst equal to four
and at best the fastest configuration.

### The parent is no longer the bottleneck

Parent-thread wall time during a 4-worker pinned run:

| stage | before ms/cell | after ms/cell |
|---|---:|---:|
| dataset preparation (store read, or the manifest read that replaced it) | 49.15 / 46.46 | **0.43 / 0.39** |
| `_plan_dataset` (execution address + result-cache lookup + pickle) | 3.21 / 2.75 | 1.88 / 1.64 |
| submit + waiting on workers | 6.82 / 6.32 | 34.71 / 33.03 |
| parent wall, total | 59.2 / 55.5 | 37.0 / 35.1 |

Parent *active* work fell **~52 -> ~2.0 ms/cell**, better than the ~3.5 ms the §12 note
predicted, and 94% of parent wall is now waiting on workers rather than working.

### What this does and does not buy

At ~38 ms/cell on 8 workers the 16,000-cell NSE warm pass is **~10 minutes**, against ~17
minutes before. That is a real gain and it is **still not the owner's 1.4-minute target**. The
remaining ceiling is the machine, not the parent: this box reaches 3.78x at 4 workers on a pure
CPU fan-out and the pinned sweep now reaches 2.89x, so the next honest lever is the per-cell
cost itself (§6 of the design note: hoist `to_dict` and `ist_epoch` across the two simulators),
not more cores and not more parallelism plumbing.

### Reproducing the refusals worker-side was the whole risk, and it cost one design decision

`_pinned_dataset` refuses five ways: nothing pinned for the cell, the store raising, the blob
missing or no longer recomputing to its address, a manifest that describes another series or
another window, and a dataset thinner than `MIN_BARS`. Only the first is a property of the pin
map; the rest are properties of stored bytes. So exactly one of them stayed in the parent and
the other four moved, unchanged, by calling the same function (`_pinned_dataset_from_store`)
from both sides. Refusal ORDER is preserved because the parent now checks nothing else.

The decision that is not obvious: **a pinned dataset is submitted to a worker even when every
one of its cells was served from the result cache.** The parent's plan came from an unverified
manifest, so without that submission a cell whose bytes no longer verify would be served a
cached row while the serial path refuses it — faster, silently divergent, and exactly the class
of difference the bit-identity gate exists to forbid. A worker's refusal overrides the parent's
cache hits for that whole dataset.

Non-pinned refresh runs are untouched: the throttled provider read cannot move to a worker, so
those still fetch in the parent and still cost one read per dataset.

### Suppressions, both proven able to redden

- **Skip the address recomputation worker-side** (serve the blob straight from disk):
  `test_revised_content_fails_closed_in_a_worker` and
  `test_a_refused_dataset_beats_a_reusable_result_row` both go red.
- **Submit only datasets with work to do** (`if pinned_address and cells:`):
  `test_a_refused_dataset_beats_a_reusable_result_row` goes red on its own — a corrupt dataset
  is served from the result cache with an empty `error`.
