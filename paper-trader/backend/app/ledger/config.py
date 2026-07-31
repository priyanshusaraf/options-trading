"""Path resolution for the ledger DB.

Deliberately does NOT import app.core.config, so importing the ledger never
implicitly binds the execution DB engine. Mirrors the isolation the deleted
journal package had, which was the one thing about it worth keeping."""
from __future__ import annotations

import os
from collections.abc import Mapping

# Absolute by construction. A bare relative default resolves against the process
# cwd, so a systemd restart with a different WorkingDirectory would silently
# create a second, empty journal. See the design spec §9.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_LEDGER_DB = os.path.join(_BACKEND_DIR, "ledger.db")


def ledger_db_path(env: Mapping[str, str] | None = None) -> str:
    e = os.environ if env is None else env
    return e.get("PT_LEDGER_DB_PATH") or DEFAULT_LEDGER_DB
