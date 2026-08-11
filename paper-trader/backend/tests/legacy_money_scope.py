"""Explicit trusted-composition adapter for pre-tenancy behavior tests.

These tests exercise the legacy single-account runtime. Production repositories keep owner
and account arguments mandatory; this proxy stamps the known migration root at the test
composition boundary so the older behavioral assertions remain about behavior, not tenancy.
Two-tenant isolation is tested directly in ``test_money_repository_isolation.py``.
"""
from __future__ import annotations

from app.db.models import LEGACY_BROKER_ACCOUNT_ID, LEGACY_OWNER_ID


class LegacyMoneyScope:
    def __init__(self, module, *scoped_names: str):
        object.__setattr__(self, "_module", module)
        object.__setattr__(self, "_scoped_names", frozenset(scoped_names))

    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            setattr(self._module, name, value)

    def __getattr__(self, name):
        value = getattr(self._module, name)
        if name not in self._scoped_names or not callable(value):
            return value

        def call(*args, **kwargs):
            kwargs.setdefault("owner_id", LEGACY_OWNER_ID)
            kwargs.setdefault("broker_account_id", LEGACY_BROKER_ACCOUNT_ID)
            return value(*args, **kwargs)

        return call


LEGACY_SCOPE = {
    "owner_id": LEGACY_OWNER_ID,
    "broker_account_id": LEGACY_BROKER_ACCOUNT_ID,
}
