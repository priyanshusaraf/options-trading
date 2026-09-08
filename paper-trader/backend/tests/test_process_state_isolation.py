"""Paired proofs for pytest's case-blind process-state restoration."""
from __future__ import annotations

import datetime as dt

from app.main import app
from app.providers.factory import get_provider
from app.strategy import registry as strategy_registry


_APP_BASELINE = None
_PROVIDER_BASELINE = None
_REGISTRY_BASELINE = None
_SETTINGS_BASELINE = None


def _assert_shallow_exact(mapping, expected):
    assert mapping.keys() == expected.keys()
    for key, value in expected.items():
        assert mapping[key] is value, key


def _dependency_key():
    return "original"


def _dependency_override():
    return "override"


def test_01_app_state_and_overrides_change_within_the_predecessor():
    global _APP_BASELINE
    state = app.state._state
    overrides = app.dependency_overrides
    _APP_BASELINE = (state, dict(state), overrides, dict(overrides))

    marker = object()
    app.state.process_state_isolation_marker = marker
    app.dependency_overrides[_dependency_key] = _dependency_override

    assert app.state.process_state_isolation_marker is marker
    assert app.dependency_overrides[_dependency_key] is _dependency_override


def test_02_app_state_and_overrides_start_at_the_predecessor_snapshot():
    state, expected_state, overrides, expected_overrides = _APP_BASELINE
    assert app.state._state is state
    assert app.dependency_overrides is overrides
    _assert_shallow_exact(state, expected_state)
    _assert_shallow_exact(overrides, expected_overrides)


def test_03_provider_attributes_change_within_the_predecessor():
    global _PROVIDER_BASELINE
    provider = get_provider()
    attributes = provider.__dict__
    _PROVIDER_BASELINE = (attributes, dict(attributes))

    marker = object()
    provider.process_state_isolation_marker = marker
    provider._cursor = -1
    provider.now = lambda: dt.datetime(2035, 1, 1, 9, 45)

    assert provider.process_state_isolation_marker is marker
    assert provider._cursor == -1
    assert provider.now() == dt.datetime(2035, 1, 1, 9, 45)


def test_04_provider_attributes_start_at_the_predecessor_snapshot():
    attributes, expected = _PROVIDER_BASELINE
    provider = get_provider()
    assert provider.__dict__ is attributes
    _assert_shallow_exact(provider.__dict__, expected)


def test_05_both_strategy_registries_change_within_the_predecessor():
    global _REGISTRY_BASELINE
    handwritten = strategy_registry._REGISTRY
    generated = strategy_registry._GENERATED_REGISTRY
    _REGISTRY_BASELINE = (
        handwritten, dict(handwritten), generated, dict(generated),
    )

    handwritten_marker = object()
    generated_marker = object()
    strategy_registry._REGISTRY["process_state_isolation"] = handwritten_marker
    strategy_registry._GENERATED_REGISTRY = {
        **strategy_registry._GENERATED_REGISTRY,
        ("owner.process-state", "gen_process_state_isolation"): generated_marker,
    }

    assert strategy_registry._REGISTRY["process_state_isolation"] is handwritten_marker
    assert strategy_registry._GENERATED_REGISTRY[
        ("owner.process-state", "gen_process_state_isolation")
    ] is generated_marker


def test_06_both_strategy_registries_start_at_the_predecessor_snapshot():
    handwritten, expected_handwritten, generated, expected_generated = _REGISTRY_BASELINE
    assert strategy_registry._REGISTRY is handwritten
    assert strategy_registry._GENERATED_REGISTRY is generated
    _assert_shallow_exact(strategy_registry._REGISTRY, expected_handwritten)
    _assert_shallow_exact(strategy_registry._GENERATED_REGISTRY, expected_generated)


def test_07_settings_change_within_the_predecessor():
    global _SETTINGS_BASELINE
    from app.core.config import get_settings

    settings = get_settings()
    attributes = settings.__dict__
    _SETTINGS_BASELINE = (settings, attributes, dict(attributes))

    settings.owner_id = "owner.process-state-isolation"
    settings.research_enabled = not settings.research_enabled

    assert settings.owner_id == "owner.process-state-isolation"
    assert settings.research_enabled is not _SETTINGS_BASELINE[2]["research_enabled"]


def test_08_settings_start_at_the_predecessor_snapshot():
    from app.core.config import get_settings

    settings, attributes, expected = _SETTINGS_BASELINE
    assert get_settings() is settings
    assert settings.__dict__ is attributes
    _assert_shallow_exact(settings.__dict__, expected)
