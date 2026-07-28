"""Boot-time positive assertion on the resolved configuration.

The hole this closes: `Settings.model_config["env_file"]` is None whenever
`"pytest" in sys.modules` (`config.py:_env_file_for_this_process`). That is the
right isolation control, but pytest lives in the SAME venv production runs from.
Anything that imports it — a debug shell, a stray `import pytest` in a module, a
dependency that pulls it in — detaches `.env` from a real process. The app then
boots with NO configuration: `PT_PROVIDER` falls back to its default "mock", and
a live engine runs against a synthetic market while every health check stays
green.

`"pytest" in sys.modules` cannot be the discriminator here — it is the very
signal under suspicion. `PYTEST_CURRENT_TEST` is set by pytest only while a test
is actually executing; merely importing pytest does not set it. That is the
independent signal.
"""
from __future__ import annotations

import os

import pytest

from app.core.config import BootConfigError, Settings, assert_boot_config


def _settings(*, provider="mock", kite_api_key=None, kite_api_secret=None) -> Settings:
    """Build a Settings by ALIAS, not field name.

    `kite_api_key`/`kite_api_secret` carry `validation_alias="KITE_API_KEY"` etc.
    (they are deliberately not PT_-prefixed), and pydantic does not set
    `populate_by_name`, so `Settings(kite_api_key="k")` is silently DISCARDED and
    the field stays "". Constructing by field name here would have made every
    credential test pass for the wrong reason.
    """
    kw = {"provider": provider}
    if kite_api_key is not None:
        kw["KITE_API_KEY"] = kite_api_key
    if kite_api_secret is not None:
        kw["KITE_API_SECRET"] = kite_api_secret
    return Settings(**kw)


def test_settings_helper_really_populates_the_aliased_credentials():
    """Pins the footgun above: if this breaks, the cred tests below go green
    vacuously."""
    s = _settings(provider="kite", kite_api_key="k", kite_api_secret="s")
    assert s.kite_api_key == "k"
    assert s.kite_api_secret == "s"


# ---------------------------------------------------------------- env_file ----

def test_detached_env_file_outside_a_test_run_refuses_to_boot():
    """The exact production scenario: pytest got imported, `.env` detached."""
    s = _settings(provider="mock")
    with pytest.raises(BootConfigError) as e:
        assert_boot_config(s, env_file=None, under_test=False)
    msg = str(e.value)
    assert "env_file" in msg
    # Must name the actual mechanism, not just "bad config".
    assert "pytest" in msg


def test_detached_env_file_under_a_real_test_run_is_fine():
    s = _settings(provider="mock")
    assert_boot_config(s, env_file=None, under_test=True)  # must not raise


def test_attached_env_file_outside_a_test_run_is_fine():
    s = _settings(provider="mock")
    assert_boot_config(s, env_file=".env", under_test=False)


def test_explicit_dotenv_opt_out_is_allowed_but_only_when_explicit(monkeypatch):
    """PT_DISABLE_DOTENV=1 is a deliberate, operator-typed opt-out — a different
    path from the heuristic misfiring, and it must print differently."""
    monkeypatch.setenv("PT_DISABLE_DOTENV", "1")
    s = _settings(provider="mock")
    assert_boot_config(s, env_file=None, under_test=False)  # must not raise


def test_boot_assert_reads_the_live_settings_class_by_default(monkeypatch):
    """With no explicit args it must consult the REAL resolved config, not a
    default that quietly passes."""
    monkeypatch.delenv("PT_DISABLE_DOTENV", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    # Under pytest the class-level env_file is None, and PYTEST_CURRENT_TEST is
    # now unset — so the default-argument path must detect the misfire and raise.
    with pytest.raises(BootConfigError):
        assert_boot_config(_settings(provider="mock"))


def test_pytest_current_test_is_what_marks_a_real_test_run(monkeypatch):
    monkeypatch.delenv("PT_DISABLE_DOTENV", raising=False)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/x.py::test_y (call)")
    assert_boot_config(_settings(provider="mock"))  # must not raise


# ------------------------------------------------------------ kite creds ----

def test_kite_provider_with_empty_api_key_refuses_to_boot():
    s = _settings(provider="kite", kite_api_key="", kite_api_secret="sekret")
    with pytest.raises(BootConfigError) as e:
        assert_boot_config(s, env_file=".env", under_test=False)
    assert "KITE_API_KEY" in str(e.value)


def test_kite_provider_with_empty_api_secret_refuses_to_boot():
    s = _settings(provider="kite", kite_api_key="k", kite_api_secret="")
    with pytest.raises(BootConfigError) as e:
        assert_boot_config(s, env_file=".env", under_test=False)
    assert "KITE_API_SECRET" in str(e.value)


def test_kite_provider_with_both_creds_is_fine():
    s = _settings(provider="kite", kite_api_key="k", kite_api_secret="s")
    assert_boot_config(s, env_file=".env", under_test=False)


def test_kite_cred_check_is_enforced_even_under_test_when_provider_is_kite():
    """A test that deliberately selects the kite provider still must not resolve
    half a credential set — that is how a suite reaches the real account."""
    s = _settings(provider="kite", kite_api_key="", kite_api_secret="")
    with pytest.raises(BootConfigError):
        assert_boot_config(s, env_file=None, under_test=True)


def test_mock_provider_never_needs_kite_creds():
    s = _settings(provider="mock", kite_api_key="", kite_api_secret="")
    assert_boot_config(s, env_file=".env", under_test=False)


# ------------------------------------------------- synthetic-market warning ----

def test_mock_provider_outside_a_test_run_is_reported_not_silent(caplog):
    """dryrun.py/backtest_smoke.py legitimately run mock outside pytest, so this
    is not fatal — but a real process on a synthetic market must never be quiet
    about it."""
    s = _settings(provider="mock")
    warnings: list[str] = []
    assert_boot_config(s, env_file=".env", under_test=False, warn=warnings.append)
    assert warnings, "mock provider outside a test run produced no warning"
    assert "synthetic" in " ".join(warnings).lower()


def test_kite_provider_outside_a_test_run_warns_about_nothing():
    s = _settings(provider="kite", kite_api_key="k", kite_api_secret="s")
    warnings: list[str] = []
    assert_boot_config(s, env_file=".env", under_test=False, warn=warnings.append)
    assert warnings == []


# ------------------------------------------------------------ wiring ----

def test_the_app_boot_path_actually_calls_the_assertion():
    """A guard nobody calls is prose. Pin the call site."""
    import inspect

    from app import main

    src = inspect.getsource(main.lifespan)
    assert "assert_boot_config" in src, "lifespan does not call assert_boot_config"
