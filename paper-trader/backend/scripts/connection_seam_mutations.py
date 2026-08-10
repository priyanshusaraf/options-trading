#!/usr/bin/env python
"""Prove each connection-seam guard can go red, then restore the file byte-for-byte.

A green test proves nothing until a wrong change reddens it. Six shapes of vacuous test have
been caught in this repo by exactly this sweep; the connection seam is worth the same
treatment because its failure mode is silent and it is money.

Each mutation restores the *original bytes* whether the run passes, fails or raises, and the
script verifies the restoration by hash before exiting.

    .venv/bin/python scripts/connection_seam_mutations.py
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
FACTORY = BACKEND / "app" / "engine" / "broker_factory.py"
LIVE_BROKER = BACKEND / "app" / "engine" / "live_broker.py"
CONNECTION = BACKEND / "app" / "providers" / "connection.py"
PROVIDER_FACTORY = BACKEND / "app" / "providers" / "factory.py"

# (label, file, find, replace, the test that must fail)
MUTATIONS = [
    (
        "the order credential falls back to the data provider",
        FACTORY,
        "client = KiteOrderClient(kite, token_source=conn.token_source,",
        "client = KiteOrderClient(kite, token_source=lambda: getattr(provider, 'access_token', None),",
        "tests/test_execution_connection.py::"
        "test_the_order_credential_comes_from_the_execution_connection_not_the_data_provider",
    ),
    (
        "a named data-only connection silently falls back to paper",
        FACTORY,
        "        if named:\n            raise ConnectionCannotExecute(",
        "        if False:\n            raise ConnectionCannotExecute(",
        "tests/test_execution_connection.py::"
        "test_a_named_data_only_connection_refuses_instead_of_silently_paper_trading",
    ),
    (
        "the intent row re-hardcodes the legacy scope",
        LIVE_BROKER,
        "                connection_scope=self.connection.scope,",
        "                connection_scope=KITE_LEGACY_CONNECTION_SCOPE,",
        "tests/test_execution_lifecycle_recovery.py::"
        "test_the_money_record_carries_the_connection_that_actually_placed_the_order",
    ),
    (
        "the intent row re-hardcodes the broker name",
        LIVE_BROKER,
        "                broker=self.connection.broker,",
        '                broker="kite",',
        "tests/test_execution_lifecycle_recovery.py::"
        "test_the_money_record_carries_the_connection_that_actually_placed_the_order",
    ),
    (
        "the credential is snapshotted instead of late-bound",
        FACTORY,
        "client = KiteOrderClient(kite, token_source=conn.token_source,",
        "client = KiteOrderClient(kite, token_source=(lambda _t=conn.token_source(): _t),",
        "tests/test_execution_connection.py::"
        "test_the_credential_stays_late_bound_so_a_daily_relogin_still_propagates",
    ),
    (
        "restart recovery matches the legacy scope rather than this connection's",
        LIVE_BROKER,
        "                self.connection.scope,\n            )",
        "                KITE_LEGACY_CONNECTION_SCOPE,\n            )",
        "tests/test_execution_lifecycle_recovery.py::"
        "test_restart_recovers_this_connections_entries_and_not_another_connections",
    ),
    # ── the composition-root binding ─────────────────────────────────────────
    (
        "a split-role connection reuses the legacy scope",
        CONNECTION,
        'return connection_for(executor, scope=f"{chosen}:execution")',
        "return connection_for(executor)",
        "tests/test_execution_connection.py::"
        "test_split_roles_resolve_to_the_execution_provider_under_its_own_scope",
    ),
    (
        "the resolver reads prices' provider for execution too",
        CONNECTION,
        "    executor = provider_named(chosen)",
        "    executor = data_provider",
        "tests/test_execution_connection.py::"
        "test_split_roles_resolve_to_the_execution_provider_under_its_own_scope",
    ),
    (
        "naming the same provider twice mints a second scope",
        CONNECTION,
        'if not chosen or chosen == (s.provider or "").strip().lower():',
        "if not chosen:",
        "tests/test_execution_connection.py::"
        "test_naming_the_same_provider_for_both_roles_is_still_the_legacy_path",
    ),
    (
        "an unknown execution provider falls through to the mock",
        PROVIDER_FACTORY,
        "    raise UnknownProvider(",
        "    from app.providers.mock import MockProvider\n    return MockProvider()\n    raise UnknownProvider(",
        "tests/test_execution_connection.py::"
        "test_an_unknown_execution_provider_refuses_instead_of_defaulting_to_the_mock",
    ),
    (
        "a broker with no order client is handed to Kite's endpoint",
        FACTORY,
        '    if conn.broker != "kite":',
        "    if False:",
        "tests/test_execution_connection.py::"
        "test_a_broker_with_no_order_client_refuses_even_when_it_declares_execution",
    ),
]


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()



import fcntl
# See tenancy_mutations.py: two concurrent sweeps restore one's mutant over the other's baseline,
# permanently. On 2026-08-10 that silently removed credential destruction from
# `OwnedConnectionStore.revoke`, and only a stale-anchor SKIP revealed it.
_LOCK_FD = open(pathlib.Path(__file__).resolve().parent / ".mutation-sweep.lock", "w")
try:
    fcntl.flock(_LOCK_FD, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print("REFUSED: another mutation sweep is already running in this tree.")
    raise SystemExit(2)


def main() -> int:
    baselines = {p: p.read_bytes() for p in {m[1] for m in MUTATIONS}}
    reddened, unguarded, wrong = 0, [], []

    for label, path, find, replace, test in MUTATIONS:
        original = baselines[path]
        source = original.decode()
        if find not in source:
            print(f"SKIP  {label}: anchor not found — the code moved, fix this script")
            wrong.append(label)
            continue
        if test is None:
            print(f"OPEN  {label}: no guard exists; not proven")
            unguarded.append(label)
            continue
        try:
            path.write_text(source.replace(find, replace, 1))
            result = subprocess.run(
                [sys.executable, "-m", "pytest", test, "-x", "-q"],
                cwd=BACKEND, capture_output=True, text=True)
        finally:
            path.write_bytes(original)
        if result.returncode == 0:
            print(f"VACUOUS  {label}: the guard stayed green under its own defect")
            wrong.append(label)
        else:
            print(f"RED   {label}")
            reddened += 1

    for path, original in baselines.items():
        if _digest(path) != hashlib.sha256(original).hexdigest():
            print(f"FATAL: {path} was not restored")
            return 2

    print(f"\n{reddened}/{len([m for m in MUTATIONS if m[4]])} guarded mutations reddened; "
          f"{len(unguarded)} unguarded and named; all files restored")
    for label in unguarded:
        print(f"  open: {label}")
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())
