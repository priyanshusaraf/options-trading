"""Evaluation layer — the research plane's use of the pure execution kernels.

`kernels` is the explicit reuse boundary (simulate / metrics / registry). Later
modules here add the research-owned pieces the kernels deliberately do NOT provide:
a capital-aware SizingModel, a per-segment return numeraire, and a windowed
walk-forward evaluator. We reuse the simulation math; we never duplicate it.
"""
