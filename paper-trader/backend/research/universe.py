"""Research eligibility — which instruments the research plane may develop strategies on.

The rule (owner's directive, 2026-07): once an instrument is committed to a live
watchlist it is OFF-LIMITS for strategy development — we don't re-litigate an instrument
that's already earning. The sole exception is a fixed commodity sandbox that stays open
to research forever, so there is always somewhere to try new ideas even after everything
liquid has been deployed.

Isolation: the research plane never opens the execution DB to learn what's committed. It
reads a read-only JSON SNAPSHOT that the execution side exports (see
app.core.watchlists.write_research_snapshot). A missing snapshot means 'nothing known to
be committed' → nothing blacklisted, so an unconfigured run is safe (and visibly so).
"""
from __future__ import annotations

import json

# The permanent research sandbox — always eligible, even when deployed live.
ALWAYS_ALLOWED = frozenset({"GOLDM", "SILVERM", "CRUDEOIL", "NATURALGAS", "COPPERM"})


def eligible_for_research(all_instruments, in_watchlists) -> set:
    """Instruments the research plane may develop on: everything NOT committed to a
    watchlist, plus the always-allowed sandbox regardless of commitment."""
    committed = set(in_watchlists)
    return {k for k in all_instruments if k in ALWAYS_ALLOWED or k not in committed}


def read_watchlist_snapshot(path: str) -> set:
    """The set of instrument keys committed to a watchlist, per the execution side's
    exported snapshot. Missing/unreadable snapshot -> empty set (nothing blacklisted)."""
    try:
        with open(path) as f:
            return set(json.load(f).get("in_watchlists", []))
    except (FileNotFoundError, ValueError, OSError):
        return set()
