"""Orchestrator — the research plane's brain: a worklist driven by
Hypothesis.retest_priority, a single global process pool sized to the host
(cores-1, not a per-experiment knob), a compute budget in bar-count/CPU-seconds,
idempotent resume via the content-addressed evaluation cache (no bespoke
Checkpoint blob), a cross-process Kite token bucket, and morning report
generation. Invoked by `research.nightly`. (M1+.)
"""
