"""Research plane — an autonomous quantitative-research layer that coexists beside
the execution engine and is structurally unable to move capital.

This package is imported by the research process only; the execution engine
(`app/`) never imports `research`. See `docs/research/ARCHITECTURE.md`. The
capital-safety boundary is enforced by `research.guards`.
"""
