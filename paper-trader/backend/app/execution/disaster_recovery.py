"""Restore-specific entry into the existing execution lease authority."""
from __future__ import annotations

import re

from app.execution.leases import LeaseRepository, LeaseToken

_ADDRESS = re.compile(r"^sha256:[0-9a-f]{64}$")


class RestoreTakeoverRefused(RuntimeError):
    pass


def claim_restored_execution_lease(
    repository: LeaseRepository, *, owner_id: str, broker_account_id: str,
    cell_id: str, worker_id: str, verification_address: str,
    old_primary_isolated: bool, ttl_seconds: int = 30,
) -> LeaseToken:
    if not old_primary_isolated:
        raise RestoreTakeoverRefused("old primary isolation must be proven before execution recovery")
    if not _ADDRESS.fullmatch(verification_address):
        raise RestoreTakeoverRefused("restore verification report content address is required")
    return repository.claim_after_restore(
        owner_id=owner_id, broker_account_id=broker_account_id,
        cell_id=cell_id, worker_id=worker_id, ttl_seconds=ttl_seconds,
        restore_evidence=verification_address)
