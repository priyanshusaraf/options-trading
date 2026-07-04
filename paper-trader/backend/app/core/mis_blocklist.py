"""Intraday (MIS) ineligibility blocklist — names the bot must NOT add to the
equity_intraday portfolio because their MIS leverage can't support the bot's intraday
sizing. The list is generated from the owner's sheet by scripts/fetch_mis_blocklist.py;
this module just loads it and answers membership, normalizing the engine's
exchange-prefixed keys (e.g. 'NSE:IRCON', 'BSE:MTARTECH') to the bare symbol the
sheet uses."""
from __future__ import annotations

import json
import os
from functools import lru_cache

_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "mis_blocklist.json")


@lru_cache(maxsize=1)
def _blocked() -> frozenset[str]:
    try:
        with open(_PATH) as f:
            data = json.load(f)
        return frozenset(s.strip().upper() for s in data.get("blocked", []))
    except (OSError, ValueError):
        return frozenset()


def _bare(key: str) -> str:
    """The engine's instrument key may carry an exchange prefix ('NSE:IRCON'); the
    sheet lists the bare NSE symbol."""
    k = (key or "").strip().upper()
    return k.split(":", 1)[1] if ":" in k else k


def is_mis_blocked(key: str) -> bool:
    """True if `key` is NOT MIS-eligible (per the sheet) and so must not be assigned to
    the intraday segment. An empty/missing blocklist blocks nothing."""
    return _bare(key) in _blocked()


def reload_blocklist() -> None:
    """Drop the cache so a freshly-fetched list is picked up without a restart."""
    _blocked.cache_clear()
