from __future__ import annotations

import pytest

from app.core.config import BootConfigError, Settings, assert_boot_config


def _production(**updates):
    values = {
        "service_role": "api", "auth_disabled": False,
        "event_cursor_secret": "x" * 32,
        "database_url": "postgresql+psycopg://u@db/app",
        "execution_worker": "api",
    }
    values.update(updates)
    return Settings(**values)


def test_production_refuses_a_quarantined_restore_target():
    with pytest.raises(BootConfigError, match="quarantined"):
        assert_boot_config(_production(restore_safety_state="quarantined"),
                           env_file=None, under_test=True)


def test_verified_restore_requires_durable_deployment_evidence_identity():
    with pytest.raises(BootConfigError, match="restore generation"):
        assert_boot_config(_production(restore_safety_state="verified"),
                           env_file=None, under_test=True)
    assert_boot_config(_production(
        restore_safety_state="verified",
        restore_generation_id="restore-20260813-a",
        restore_verification_address="sha256:" + "a" * 64,
        restore_old_primary_isolated=True,
    ), env_file=None, under_test=True)


def test_verified_restore_requires_old_primary_isolation():
    with pytest.raises(BootConfigError, match="OLD_PRIMARY_ISOLATED"):
        assert_boot_config(_production(
            restore_safety_state="verified",
            restore_generation_id="restore-20260813-a",
            restore_verification_address="sha256:" + "a" * 64,
        ), env_file=None, under_test=True)


def test_main_boot_routes_verified_restore_through_restore_takeover():
    import inspect
    from app import main

    source = inspect.getsource(main.lifespan)
    assert "claim_restored_execution_lease" in source
    assert "restore_safety_state" in source


def test_unknown_restore_safety_state_is_refused():
    with pytest.raises(BootConfigError, match="RESTORE_SAFETY_STATE"):
        assert_boot_config(_production(restore_safety_state="green-ish"),
                           env_file=None, under_test=True)
