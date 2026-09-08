"""Chat 1 characterization of claimed OOS separation; no product edit."""

from research.orchestrator import run as run_module
from research_tests.test_orchestrator import _run


def test_qualification_cannot_observe_later_oos_rows(
        research_session, inst_factory, uptrend_factory, monkeypatch):
    qualification_lengths = []
    validation_lengths = []
    real_qualify = run_module.qualify_instrument
    real_validate = run_module.validate

    def observe_qualification(candles, *args, **kwargs):
        qualification_lengths.append(len(candles))
        return real_qualify(candles, *args, **kwargs)

    def observe_validation(candles, *args, **kwargs):
        validation_lengths.append(len(candles))
        return real_validate(candles, *args, **kwargs)

    monkeypatch.setattr(run_module, "qualify_instrument", observe_qualification)
    monkeypatch.setattr(run_module, "validate", observe_validation)

    _run(research_session, inst_factory, uptrend_factory)

    assert qualification_lengths and validation_lengths
    assert all(q < v for q, v in zip(qualification_lengths, validation_lengths)), (
        "qualification inspected the same full history whose later rows are labelled OOS: "
        f"qualification={qualification_lengths}, validation={validation_lengths}"
    )
