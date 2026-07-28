"""Test isolation lives in the ROOTDIR conftest (`backend/conftest.py`), not here.

This file used to force PT_PROVIDER / PT_EXECUTION / PT_LIVE_ACK / PT_DB_PATH. That
was one directory too deep: it left `pytest research_tests` resolving to the live
Kite provider, real-money execution and the production ledger. Moving it up one level
makes the guarantee unconditional instead of dependent on which paths pytest was
handed. See `backend/conftest.py` for the incident and the reasoning.

Do NOT reintroduce env forcing here. A second writer would silently win or lose by
import order — which is the exact class of bug that made the hole invisible.
"""
