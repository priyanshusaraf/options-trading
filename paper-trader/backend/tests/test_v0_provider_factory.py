"""V0 process provider configuration must fail closed to synthetic data."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.providers import factory
from app.providers import mock as mock_module


def _settings(provider: str):
    return SimpleNamespace(provider=provider, replay_path="unused-replay.json")


@pytest.mark.parametrize("configured", ["", "   ", "unknown-provider", "dhan"])
def test_unknown_empty_and_v0_unopened_configuration_never_falls_through_to_mock(
    monkeypatch, configured,
):
    constructed: list[str] = []

    class ForbiddenMock:
        def __init__(self):
            constructed.append("mock")

    monkeypatch.setattr(factory, "_provider", None)
    monkeypatch.setattr(factory, "get_settings", lambda: _settings(configured))
    monkeypatch.setattr(mock_module, "MockProvider", ForbiddenMock)

    with pytest.raises(factory.UnknownProvider, match="configured provider"):
        factory.get_provider()
    assert constructed == []

    with pytest.raises(factory.UnknownProvider, match="configured provider"):
        factory.provider_named(configured)
    assert constructed == []


def test_explicit_mock_is_normalized_and_reused_without_a_second_constructor(monkeypatch):
    constructed: list[object] = []

    class ExplicitMock:
        def __init__(self):
            constructed.append(self)

    monkeypatch.setattr(factory, "_provider", None)
    monkeypatch.setattr(factory, "get_settings", lambda: _settings("  MOCK  "))
    monkeypatch.setattr(mock_module, "MockProvider", ExplicitMock)

    first = factory.get_provider()
    assert first is constructed[0]
    assert factory.get_provider() is first
    assert factory.provider_named("mock") is first
    assert len(constructed) == 1


@pytest.mark.parametrize("configured", ["unknown-provider", "dhan"])
def test_warm_singleton_cannot_bypass_configured_provider_refusal(monkeypatch, configured):
    existing = object()
    monkeypatch.setattr(factory, "_provider", existing)
    monkeypatch.setattr(factory, "get_settings", lambda: _settings(configured))

    with pytest.raises(factory.UnknownProvider, match="configured provider"):
        factory.get_provider()
    assert factory._provider is existing

    with pytest.raises(factory.UnknownProvider, match="configured provider"):
        factory.provider_named(configured)
    assert factory._provider is existing
