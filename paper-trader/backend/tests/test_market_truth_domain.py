from datetime import datetime, timedelta, timezone
import json

import pytest

from app.ir.hashing import canonical_json
from app.market_truth import (
    CanonicalInstrumentId, ContinuousFutureDefinition, InstrumentSelector,
    MarketTruthError, MarketTruthSnapshot, ProviderInstrumentMapping, Quality,
    Reconstruction, RulebookRecord, canonical_decimal, preserve_held_identity,
    validate_provider_mappings,
)

UTC = timezone.utc
T0 = datetime(2026, 1, 1, tzinfo=UTC)
LEGACY_V2_SNAPSHOT_BYTES = (
    b'{"fact":{"authority_scope":"RESEARCH","effective_from":"2026-01-01T00:00:00+00:00",'
    b'"effective_to":null,"instrument_addresses":[],"knowledge_cutoff":'
    b'"2026-01-01T02:00:00+00:00","quality":"OBSERVED","reconstruction":null,'
    b'"records":[{"effective_from":"2026-01-01T00:00:00+00:00","effective_to":'
    b'"2026-01-02T00:00:00+00:00","natural_key":[["instrument","NIFTY"]],'
    b'"record_kind":"contract","recorded_at":"2026-01-01T00:00:00+00:00",'
    b'"terms":[["tick","0.05"]]}],"source_evidence":['
    b'"sha256:1111111111111111111111111111111111111111111111111111111111111111"]},'
    b'"schema":"market-truth-snapshot/2"}'
)
LEGACY_V2_SNAPSHOT_ADDRESS = (
    "sha256:d1202aadf66edcf71502d6711ee6e8e3604a87b6c94a324a2c5db944ab554fa0"
)


def option(*, strike="22000", expiry=T0 + timedelta(days=7), multiplier="50"):
    return CanonicalInstrumentId("NSE", "OPTION", "NIFTY", "WEEKLY_OPTION", "INR", expiry, strike, "CALL", multiplier)


def rule(start=T0, end=T0 + timedelta(days=1), terms=(("tick", "0.05"),), recorded_at=T0):
    return RulebookRecord("contract", (("instrument", "NIFTY"),), terms, start, end, recorded_at)


def test_physical_identity_is_decimal_canonical_and_provider_free():
    assert option().address == option().address
    assert option(strike="22100").address != option().address
    assert option(expiry=T0 + timedelta(days=14)).address != option().address
    assert canonical_decimal("0") == "0"
    with pytest.raises(MarketTruthError, match="canonical"):
        option(strike="22000.0")
    with pytest.raises(MarketTruthError):
        canonical_decimal("nan")


@pytest.mark.parametrize(
    ("asset_class", "contract_kind", "terms"),
    [
        ("EQUITY", "SPOT", {}),
        ("INDEX", "SPOT", {}),
        ("FUTURE", "FUTURE", {"expiry": T0 + timedelta(days=30), "multiplier": "50"}),
        (
            "OPTION",
            "WEEKLY_OPTION",
            {
                "expiry": T0 + timedelta(days=7),
                "strike": "22000",
                "option_right": "CALL",
                "multiplier": "50",
            },
        ),
        (
            "OPTION",
            "MONTHLY_OPTION",
            {
                "expiry": T0 + timedelta(days=30),
                "strike": "22000",
                "option_right": "PUT",
                "multiplier": "50",
            },
        ),
    ],
)
def test_p4_spec_002_accepts_only_the_closed_canonical_contract_matrix(
    asset_class, contract_kind, terms
):
    instrument = CanonicalInstrumentId(
        "NSE", asset_class, "NIFTY", contract_kind, "INR", **terms
    )
    assert instrument.asset_class == asset_class
    assert instrument.contract_kind == contract_kind


@pytest.mark.parametrize(
    "fields",
    [
        {"asset_class": "OPTION", "contract_kind": "WEEKLY_OPTION"},
        {
            "asset_class": "FUTURE",
            "contract_kind": "FUTURE",
            "expiry": T0 + timedelta(days=30),
        },
        {"asset_class": "FUTURE", "contract_kind": "FUTURE", "multiplier": "50"},
        {"asset_class": "EQUITY", "contract_kind": "SPOT", "expiry": T0},
        {"asset_class": "INDEX", "contract_kind": "SPOT", "multiplier": "1"},
        {
            "asset_class": "OPTION",
            "contract_kind": "WEEKLY_OPTION",
            "expiry": T0 + timedelta(days=7),
            "strike": "22000",
            "option_right": "CALL",
            "multiplier": "50",
            "series_terms": (("settlement", "cash"),),
        },
        {"asset_class": "EQUITY", "contract_kind": "FUTURE"},
        {"asset_class": "OPTION", "contract_kind": "SPOT"},
        {"asset_class": "equity", "contract_kind": "SPOT"},
    ],
)
def test_p4_spec_002_refuses_incomplete_or_undeclared_contract_terms(fields):
    asset_class = fields["asset_class"]
    contract_kind = fields["contract_kind"]
    terms = {key: value for key, value in fields.items() if key not in {"asset_class", "contract_kind"}}
    with pytest.raises(MarketTruthError):
        CanonicalInstrumentId("NSE", asset_class, "NIFTY", contract_kind, "INR", **terms)


def test_selector_and_held_identity_cannot_rewrite_physical_contract():
    held = option()
    selector = InstrumentSelector("nearest_eligible_weekly_call", (("delta_band", "0.25"),))
    assert preserve_held_identity(held, selector) is held
    with pytest.raises(MarketTruthError):
        InstrumentSelector("weekly", (("token", "123"),))


@pytest.mark.parametrize(
    "selector_kind, parameters",
    [
        ("weekly", (("delta_band", "0.25"),)),
        ("nearest_eligible_weekly_call", ()),
        ("nearest_eligible_weekly_call", (("delta_band", "0.25"), ("extra", "1"))),
        ("nearest_eligible_weekly_call", (("delta_band", "0.250"),)),
        ("nearest_eligible_weekly_call", (("provider_symbol", "NFO:NIFTY26JAN22000CE"),)),
        ("nearest_eligible_weekly_call", (("provider_token", "123"),)),
        ("nearest_eligible_weekly_call", (("broker_symbol", "NIFTY26JAN22000CE"),)),
        ("nearest_eligible_weekly_call", (("broker_token", "123"),)),
        ("nearest_eligible_weekly_call", (("payload", '{"provider_symbol":"NFO:NIFTY26JAN22000CE"}'),)),
        ("nearest_eligible_weekly_call", (("delta_band.value", "0.25"),)),
        # A nested object is not an economic selector parameter encoding.
        ("nearest_eligible_weekly_call", (("delta_band", {"min": "0.20", "max": "0.30"}),)),
    ],
)
def test_p4_spec_003_selector_schema_rejects_undeclared_and_encoded_aliases(
    selector_kind, parameters
):
    with pytest.raises(MarketTruthError):
        InstrumentSelector(selector_kind, parameters)


def test_provider_temporal_intervals_reject_overlap_and_token_reuse():
    physical = option()
    later = option(strike="22100")
    first = ProviderInstrumentMapping(physical, "kite", "123", "1", T0, T0 + timedelta(days=1))
    reused_later = ProviderInstrumentMapping(later, "kite", "123", "1", T0 + timedelta(days=1), None)
    validate_provider_mappings((first, reused_later))
    overlap = ProviderInstrumentMapping(later, "kite", "123", "1", T0 + timedelta(hours=12), None)
    with pytest.raises(MarketTruthError, match="ambiguous"):
        validate_provider_mappings((first, overlap))
    remapped = ProviderInstrumentMapping(physical, "kite", "456", "1", T0 + timedelta(hours=12), None)
    with pytest.raises(MarketTruthError, match="overlaps"):
        validate_provider_mappings((first, remapped))


def test_rulebook_resolves_half_open_history_and_refuses_gap_or_current_substitution():
    snapshot = MarketTruthSnapshot((rule(),), T0, T0 + timedelta(days=2), T0, Quality.OBSERVED)
    assert snapshot.record_at("contract", (("instrument", "NIFTY"),), T0).terms == (("tick", "0.05"),)
    with pytest.raises(MarketTruthError, match="forbidden"):
        snapshot.record_at("contract", (("instrument", "NIFTY"),), T0 + timedelta(days=1))
    with pytest.raises(MarketTruthError, match="overlap"):
        MarketTruthSnapshot((rule(), rule(T0 + timedelta(hours=12))), T0, None, T0, Quality.OBSERVED)


def test_p4_spec_004_snapshot_defensively_owns_records_and_digest():
    records = [rule()]
    snapshot = MarketTruthSnapshot(records, T0, None, T0, Quality.OBSERVED)
    digest = snapshot.digest

    assert snapshot.records == tuple(records)
    records.clear()

    assert snapshot.records == (rule(),)
    assert snapshot.digest == digest
    assert snapshot.record_at("contract", (("instrument", "NIFTY"),), T0).terms == (("tick", "0.05"),)


def test_p4_spec_005_snapshot_rejects_future_record_and_resolves_at_cutoff():
    future_record = rule(recorded_at=T0 + timedelta(days=1))
    with pytest.raises(MarketTruthError):
        MarketTruthSnapshot((future_record,), T0, None, T0, Quality.OBSERVED)

    at_cutoff = MarketTruthSnapshot((rule(recorded_at=T0),), T0, None, T0, Quality.OBSERVED)
    assert at_cutoff.record_at("contract", (("instrument", "NIFTY"),), T0).recorded_at == T0


def test_snapshot_digest_quality_and_reconstruction_are_identity_bearing():
    observed = MarketTruthSnapshot((rule(),), T0, None, T0, Quality.OBSERVED)
    rebuilt = MarketTruthSnapshot((rule(),), T0, None, T0, Quality.RECONSTRUCTED, Reconstruction("rules", "1", ("oi",)))
    assert observed.digest != rebuilt.digest
    with pytest.raises(MarketTruthError, match="only OBSERVED"):
        rebuilt.require_observed_ground_truth()
    with pytest.raises(MarketTruthError, match="requires"):
        MarketTruthSnapshot((rule(),), T0, None, T0, Quality.RECONSTRUCTED)
    unknown = MarketTruthSnapshot((rule(),), T0, None, T0, Quality.UNKNOWN)
    with pytest.raises(MarketTruthError, match="only OBSERVED"):
        unknown.require_observed_ground_truth()


def test_nmt_001_snapshot_recorded_at_is_identity_bearing_and_round_trips():
    knowledge_cutoff = T0 + timedelta(hours=2)
    recorded_first = T0 + timedelta(hours=1)
    recorded_second = knowledge_cutoff
    first = MarketTruthSnapshot(
        (rule(),), T0, None, recorded_first, Quality.OBSERVED,
        knowledge_cutoff=knowledge_cutoff,
    )
    second = MarketTruthSnapshot(
        (rule(),), T0, None, recorded_second, Quality.OBSERVED,
        knowledge_cutoff=knowledge_cutoff,
    )

    assert first.canonical_bytes != second.canonical_bytes
    assert first.address != second.address
    assert MarketTruthSnapshot.from_bytes(first.canonical_bytes).recorded_at == recorded_first
    assert MarketTruthSnapshot.from_bytes(second.canonical_bytes).recorded_at == recorded_second


def test_nmt_001_utc_offsets_canonicalize_to_one_v3_identity():
    india = timezone(timedelta(hours=5, minutes=30))
    utc_snapshot = MarketTruthSnapshot(
        (rule(),), T0, None, T0 + timedelta(hours=1), Quality.OBSERVED,
        knowledge_cutoff=T0 + timedelta(hours=2),
    )
    offset_snapshot = MarketTruthSnapshot(
        (rule(),), T0.astimezone(india), None,
        (T0 + timedelta(hours=1)).astimezone(india), Quality.OBSERVED,
        knowledge_cutoff=(T0 + timedelta(hours=2)).astimezone(india),
    )

    assert offset_snapshot.recorded_at == utc_snapshot.recorded_at
    assert offset_snapshot.canonical_bytes == utc_snapshot.canonical_bytes
    assert offset_snapshot.address == utc_snapshot.address


def test_nmt_cr_001_frozen_actual_v2_bytes_and_address_reconstruct_read_only():
    legacy = MarketTruthSnapshot.from_legacy_v2_bytes(LEGACY_V2_SNAPSHOT_BYTES)

    assert legacy.schema == MarketTruthSnapshot.LEGACY_SCHEMA == "market-truth-snapshot/2"
    assert legacy.recorded_at == legacy.knowledge_cutoff
    assert legacy.canonical_bytes == LEGACY_V2_SNAPSHOT_BYTES
    assert legacy.address == LEGACY_V2_SNAPSHOT_ADDRESS
    assert MarketTruthSnapshot.from_bytes(LEGACY_V2_SNAPSHOT_BYTES) == legacy
    with pytest.raises(MarketTruthError, match="reconstruction-only"):
        legacy.require_authority_complete()


def test_nmt_cr_001_new_v3_and_unsupported_or_ambiguous_shapes_are_closed():
    current = MarketTruthSnapshot(
        (rule(),), T0, None, T0 + timedelta(hours=1), Quality.OBSERVED,
        knowledge_cutoff=T0 + timedelta(hours=2),
    )
    assert current.schema == MarketTruthSnapshot.SCHEMA == "market-truth-snapshot/3"
    assert json.loads(current.canonical_bytes)["schema"] == MarketTruthSnapshot.SCHEMA
    assert MarketTruthSnapshot.from_bytes(current.canonical_bytes) == current

    ambiguous_document = json.loads(LEGACY_V2_SNAPSHOT_BYTES)
    ambiguous_document["fact"]["recorded_at"] = ambiguous_document[
        "fact"
    ]["knowledge_cutoff"]
    ambiguous_v2 = canonical_json(ambiguous_document).encode("utf-8")
    with pytest.raises(MarketTruthError, match="not closed"):
        MarketTruthSnapshot.from_bytes(ambiguous_v2)
    unsupported = canonical_json({
        "schema": "market-truth-snapshot/1",
        "fact": current.fact(),
    }).encode("utf-8")
    with pytest.raises(MarketTruthError, match="unsupported"):
        MarketTruthSnapshot.from_bytes(unsupported)


def test_nmt_001_recorded_at_and_knowledge_cutoff_remain_causally_distinct():
    cutoff = T0 + timedelta(hours=2)
    learned_after_snapshot_recording = rule(recorded_at=T0 + timedelta(hours=1, minutes=30))
    snapshot = MarketTruthSnapshot(
        (learned_after_snapshot_recording,), T0, None,
        T0 + timedelta(hours=1), Quality.OBSERVED,
        knowledge_cutoff=cutoff,
    )

    assert snapshot.record_at(
        "contract", (("instrument", "NIFTY"),), T0
    ).recorded_at == learned_after_snapshot_recording.recorded_at

    with pytest.raises(MarketTruthError, match="learned after"):
        MarketTruthSnapshot(
            (rule(recorded_at=cutoff + timedelta(seconds=1)),), T0, None,
            T0 + timedelta(hours=1), Quality.OBSERVED,
            knowledge_cutoff=cutoff,
        )


def test_continuous_future_keeps_signal_roll_adjustment_and_contracts_distinct():
    future = CanonicalInstrumentId("NSE", "FUTURE", "NIFTY", "FUTURE", "INR", T0 + timedelta(days=30), multiplier="50")
    continuous = ContinuousFutureDefinition("NIFTY-front", "calendar", "1", "back_adjusted", "2", (future,))
    assert continuous.address.startswith("sha256:")
    with pytest.raises(MarketTruthError):
        ContinuousFutureDefinition("NIFTY-front", "", "1", "none", "1", (future,))


# Explicit source declarations are separate from observed market truth.
def _dated_document():
    return {
        "schema": "dated-trading-sessions/1",
        "instrument_address": "sha256:" + "a" * 64,
        "venue_code": "XNSE", "timezone": "Asia/Kolkata",
        "provenance": "SOURCE_DECLARED", "source_reference": "calendar declaration v1",
        "recorded_at": "2026-01-01T00:00:00Z",
        "rows": [{"date": "2026-01-01", "status": "OPEN",
                  "opens_at": "2026-01-01T04:00:00Z", "closes_at": "2026-01-01T05:10:00Z"}],
    }


def _parse_dated(document=None, **options):
    from app.market_truth.dated_sessions import parse_dated_sessions
    document = _dated_document() if document is None else document
    arguments = dict(instrument_address="sha256:" + "a" * 64, venue_code="XNSE",
                     timezone="Asia/Kolkata", as_of=T0)
    arguments.update(options)
    return parse_dated_sessions(json.dumps(document).encode(), **arguments)


def test_dated_sessions_are_content_addressed_frozen_source_declarations():
    from dataclasses import FrozenInstanceError
    from app.ir.hashing import content_address
    document = _dated_document()
    calendar = _parse_dated(document)
    assert calendar.address == content_address(document)
    assert calendar.provenance == "SOURCE_DECLARED"
    assert calendar.instrument_address == document["instrument_address"]
    assert calendar.venue_code == "XNSE"
    assert calendar.timezone == "Asia/Kolkata"
    assert calendar.source_reference == "calendar declaration v1"
    assert calendar.recorded_at == T0
    assert type(calendar.dates) is tuple
    document["rows"][0]["opens_at"] = "2026-01-01T05:00:00Z"
    assert calendar.dates[0].opens_at == T0 + timedelta(hours=4)
    assert calendar.address != content_address(document)
    with pytest.raises(FrozenInstanceError):
        calendar.provenance = "OBSERVED"
    with pytest.raises(FrozenInstanceError):
        calendar.dates[0].local_date = "2026-01-02"


@pytest.mark.parametrize("resolution,count", [(900, 5), (1800, 3), (3600, 2)])
def test_dated_sessions_anchor_bars_and_complete_the_short_terminal_bar(resolution, count):
    from app.market_truth.dated_sessions import expected_bars, completion_for
    calendar = _parse_dated()
    start, close = T0 + timedelta(hours=4), T0 + timedelta(hours=5, minutes=10)
    bars = expected_bars(calendar, requested_start=start, requested_end=close,
                         resolution_seconds=resolution, cutoff_at=close)
    assert len(bars) == count
    assert bars[0] == (start, start + timedelta(seconds=resolution))
    assert bars[-1] == (T0 + timedelta(hours=5), close)
    assert all(completion_for(calendar, event, resolution) == completion
               for event, completion in bars)
    assert all(completion <= close for _, completion in bars)


def test_dated_sessions_request_is_inclusive_by_open_and_excludes_forming_bars():
    from app.market_truth.dated_sessions import expected_bars
    calendar = _parse_dated()
    event, close = T0 + timedelta(hours=5), T0 + timedelta(hours=5, minutes=10)
    arguments = dict(requested_start=event, requested_end=event, resolution_seconds=3600)
    assert expected_bars(calendar, **arguments, cutoff_at=close) == ((event, close),)
    assert expected_bars(calendar, **arguments, cutoff_at=close - timedelta(microseconds=1)) == ()
    assert expected_bars(calendar, requested_start=event + timedelta(seconds=1),
                         requested_end=close, resolution_seconds=3600, cutoff_at=close) == ()
    assert expected_bars(calendar, requested_start=T0, requested_end=T0 + timedelta(hours=1),
                         resolution_seconds=3600, cutoff_at=close) == ()


def test_dated_sessions_require_every_date_and_honor_explicit_closures():
    from app.market_truth.dated_sessions import expected_bars, completion_for
    document = _dated_document()
    document["rows"].append({"date": "2026-01-02", "status": "CLOSED",
                             "opens_at": None, "closes_at": None})
    calendar = _parse_dated(document)
    closed_event = T0 + timedelta(days=1, hours=4)
    assert expected_bars(calendar, requested_start=closed_event, requested_end=closed_event,
                         resolution_seconds=900, cutoff_at=closed_event) == ()
    with pytest.raises(MarketTruthError, match="explicitly closed"):
        completion_for(calendar, closed_event, 900)
    for start, end in [(T0 - timedelta(days=1), T0), (T0, T0 + timedelta(days=2))]:
        with pytest.raises(MarketTruthError, match="COVERAGE_MISSING"):
            expected_bars(calendar, requested_start=start, requested_end=end,
                          resolution_seconds=900, cutoff_at=T0 + timedelta(days=10))
    with pytest.raises(MarketTruthError, match="COVERAGE_MISSING"):
        completion_for(calendar, T0 + timedelta(days=2), 900)


@pytest.mark.parametrize("close", ["2026-01-02T04:00:00Z", "2026-01-02T05:00:00Z"])
def test_dated_sessions_allow_utc_overnight_within_local_date_or_next_midnight(close):
    from app.market_truth.dated_sessions import expected_bars
    document = _dated_document()
    document["timezone"] = "America/New_York"
    document["rows"][0].update(opens_at="2026-01-01T22:00:00Z", closes_at=close)
    calendar = _parse_dated(document, timezone="America/New_York")
    finish = datetime.fromisoformat(close.replace("Z", "+00:00"))
    bars = expected_bars(calendar, requested_start=T0 + timedelta(hours=22),
                         requested_end=finish - timedelta(seconds=1),
                         resolution_seconds=3600, cutoff_at=finish)
    assert bars[-1][1] == finish
    assert bars[-1][0].date().isoformat() == "2026-01-02"
    if finish.hour == 5:
        with pytest.raises(MarketTruthError, match="COVERAGE_MISSING"):
            expected_bars(calendar, requested_start=T0 + timedelta(hours=22),
                          requested_end=finish, resolution_seconds=3600, cutoff_at=finish)


@pytest.mark.parametrize("patch", [
    {"date": "20260101"}, {"date": "2026-02-30"}, {"date": 20260101},
    {"status": "UNKNOWN"}, {"status": "CLOSED"}, {"extra": True},
    {"opens_at": None}, {"opens_at": "2026-01-01T04:00:00.001Z"},
    {"opens_at": "2026-01-01T09:30:00+05:30"},
    {"opens_at": "2026-01-01T04:00:00"}, {"opens_at": "2026-01-01T24:00:00Z"},
    {"opens_at": "2025-12-31T04:00:00Z"},
    {"closes_at": "2026-01-01T04:00:00Z"},
    {"closes_at": "2026-01-02T04:00:00Z"},
    {"closes_at": "2026-01-01T18:30:01Z"},
])
def test_dated_sessions_refuse_invalid_or_local_overnight_rows(patch):
    document = _dated_document()
    document["rows"][0].update(patch)
    with pytest.raises(MarketTruthError):
        _parse_dated(document)


@pytest.mark.parametrize("patch", [
    {"schema": "dated-trading-sessions/2"}, {"extra": 1},
    {"instrument_address": "sha256:" + "b" * 64}, {"instrument_address": "invalid"},
    {"venue_code": "XNAS"}, {"timezone": "UTC"},
    {"provenance": "OBSERVED"}, {"provenance": "SYNTHETIC"},
    {"source_reference": ""}, {"source_reference": " "},
    {"source_reference": "a" * 2049}, {"source_reference": "bad\x00reference"},
    {"source_reference": "\ud800"}, {"source_reference": float("nan")},
    {"recorded_at": "2026-01-01T00:00:01Z"},
    {"recorded_at": "2026-01-01T00:00:00+01:00"}, {"rows": []}, {"rows": {}},
])
def test_dated_sessions_refuse_foreign_future_undeclared_or_malformed_documents(patch):
    document = _dated_document()
    document.update(patch)
    with pytest.raises(MarketTruthError):
        _parse_dated(document)


def test_dated_sessions_synthetic_is_explicit_opt_in_and_never_upgraded():
    document = _dated_document()
    document["provenance"] = "SYNTHETIC"
    assert _parse_dated(document, allow_synthetic=True).provenance == "SYNTHETIC"
    with pytest.raises(MarketTruthError):
        _parse_dated(document, allow_synthetic=1)


@pytest.mark.parametrize("options", [
    {"as_of": T0.replace(tzinfo=None)},
    {"as_of": T0.astimezone(timezone(timedelta(hours=1)))},
    {"instrument_address": "bad"}, {"venue_code": "nse"},
])
def test_dated_sessions_validate_caller_identity_and_utc_cutoff(options):
    with pytest.raises(MarketTruthError):
        _parse_dated(**options)


@pytest.mark.parametrize("zone", ["No/Such_Zone", "/etc/localtime", "", 1])
def test_dated_sessions_refuse_invalid_iana_timezone(zone):
    document = _dated_document()
    document["timezone"] = zone
    with pytest.raises(MarketTruthError):
        _parse_dated(document, timezone=zone)


@pytest.mark.parametrize("date", ["2026-01-01", "2026-01-03", "2025-12-31"])
def test_dated_sessions_refuse_duplicate_missing_or_out_of_order_dates(date):
    document = _dated_document()
    document["rows"].append({"date": date, "status": "CLOSED", "opens_at": None, "closes_at": None})
    with pytest.raises(MarketTruthError, match="consecutive"):
        _parse_dated(document)


def test_dated_sessions_reject_duplicate_json_keys_at_any_depth_and_payload_bounds():
    from app.market_truth.dated_sessions import parse_dated_sessions
    payload = json.dumps(_dated_document()).encode()
    duplicate_root = payload.replace(b'"schema":', b'"schema":"substituted","schema":', 1)
    duplicate_row = payload.replace(b'"date":', b'"date":"2026-01-02","date":', 1)
    options = dict(instrument_address="sha256:" + "a" * 64, venue_code="XNSE",
                   timezone="Asia/Kolkata", as_of=T0)
    for invalid in (duplicate_root, duplicate_row, b"", b" " * 1_048_577, b"\xff", b"[]"):
        with pytest.raises(MarketTruthError):
            parse_dated_sessions(invalid, **options)
    assert parse_dated_sessions(payload.ljust(1_048_576), **options).address == _parse_dated().address


def test_dated_sessions_enforce_calendar_and_bar_count_bounds_without_inferring_closures():
    from app.market_truth.dated_sessions import expected_bars
    document = _dated_document()
    document["timezone"] = "UTC"
    document["rows"] = [
        {"date": (T0 + timedelta(days=index)).date().isoformat(), "status": "OPEN",
         "opens_at": (T0 + timedelta(days=index)).isoformat(),
         "closes_at": (T0 + timedelta(days=index + 1)).isoformat()}
        for index in range(21)
    ]
    calendar = _parse_dated(document, timezone="UTC")
    args = dict(requested_start=T0, resolution_seconds=900, cutoff_at=T0 + timedelta(days=21))
    assert len(expected_bars(calendar, **args, requested_end=T0 + timedelta(days=20, seconds=-1))) == 1920
    with pytest.raises(MarketTruthError, match="2000"):
        expected_bars(calendar, **args, requested_end=T0 + timedelta(days=21, seconds=-1))
    document["rows"] = [{"date": (T0 + timedelta(days=index)).date().isoformat(),
                         "status": "CLOSED", "opens_at": None, "closes_at": None}
                        for index in range(367)]
    with pytest.raises(MarketTruthError, match="366"):
        _parse_dated(document, timezone="UTC")
    calendar = _parse_dated({**document, "rows": document["rows"][:366]}, timezone="UTC")
    assert len(calendar.dates) == 366
    with pytest.raises(MarketTruthError, match="bound"):
        expected_bars(calendar, requested_start=T0, requested_end=T0 + timedelta(days=366),
                      resolution_seconds=900, cutoff_at=T0)


@pytest.mark.parametrize("event,resolution", [
    (T0 + timedelta(hours=4, seconds=1), 900),
    (T0 + timedelta(hours=4, microseconds=1), 900),
    (T0 + timedelta(hours=3), 900), (T0 + timedelta(hours=5, minutes=10), 900),
    (T0 + timedelta(hours=4), 60), (T0 + timedelta(hours=4), True),
    (T0.replace(tzinfo=None), 900),
])
def test_dated_sessions_completion_refuses_unaligned_outside_or_unsupported_bars(event, resolution):
    from app.market_truth.dated_sessions import completion_for
    with pytest.raises(MarketTruthError):
        completion_for(_parse_dated(), event, resolution)


def test_dated_sessions_request_rejects_reversed_or_naive_clocks():
    from app.market_truth.dated_sessions import expected_bars
    for start, end, cutoff in [(T0, T0 - timedelta(seconds=1), T0),
                               (T0, T0, T0.replace(tzinfo=None))]:
        with pytest.raises(MarketTruthError):
            expected_bars(_parse_dated(), requested_start=start, requested_end=end,
                          resolution_seconds=900, cutoff_at=cutoff)
