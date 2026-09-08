from __future__ import annotations

import copy
import datetime as dt

import pytest

from app.ir.hashing import content_address
from app.market_data.capability import ProviderConformance
from app.market_data.provider_evidence import ProviderEvidenceRefusal, map_provider_evidence


NOW = dt.datetime(2026, 8, 26, 12, tzinfo=dt.UTC)


def _address(name: str) -> str:
    return content_address({"fixture": name})


def _fixture() -> dict:
    return {
        "schema": "provider-evidence-fixture/1",
        "owner_id": "owner-a",
        "mode": "RESEARCH",
        "at_time": NOW.isoformat(),
        "entity": {
            "authority_namespace": "strategy-os",
            "entity_code": "fixture-provider",
            "legal_name": "Fixture Provider Ltd",
        },
        "product": {
            "product_code": "historical-candles",
            "observation_namespace": "fixture-candles",
            "product_version": "1",
        },
        "contract": {
            "permitted_uses": ["RESEARCH"],
            "effective_from": (NOW - dt.timedelta(days=10)).isoformat(),
            "effective_to": (NOW + dt.timedelta(days=10)).isoformat(),
            "evidence_address": _address("contract-evidence"),
        },
        "aliases": [{
            "provider_token": "token-101",
            "provider_symbol": "FIXTURE:ABC",
            "canonical_instrument_address": _address("instrument"),
            "adapter_schema_version": "fixture/1",
            "effective_from": (NOW - dt.timedelta(days=10)).isoformat(),
            "effective_to": (NOW + dt.timedelta(days=10)).isoformat(),
            "observation_namespace": "fixture-candles",
            "source_evidence_address": _address("alias-evidence"),
        }],
        "conformance": {
            "tested_fields": ["CLOSE"],
            "tested_resolutions": [60],
            "test_method": "fixture-vector",
            "test_version": "1",
            "observed_from": (NOW - dt.timedelta(days=1)).isoformat(),
            "observed_to": (NOW + dt.timedelta(days=1)).isoformat(),
            "evidence_artifacts": [_address("conformance-artifact")],
            "result": "PASS",
            "coverage": [{
                "instrument": {"role": "primary", "type": "PHYSICAL"},
                "field": "CLOSE",
                "resolution_seconds": 60,
                "history": {
                    "from": (NOW - dt.timedelta(days=2)).isoformat(),
                    "to": (NOW - dt.timedelta(minutes=2)).isoformat(),
                    "bars": 1000,
                },
                "maximum_freshness_seconds": 120,
                "depth": {"kind": "NONE", "levels": None},
                "session": "INSTRUMENT_CALENDAR",
                "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
                "derived_local": False,
                "entitlement": "VERIFIED",
            }],
        },
        "capability_profile": {
            "profile_version": 1,
            "observed_at": (NOW - dt.timedelta(hours=1)).isoformat(),
            "expires_at": (NOW + dt.timedelta(hours=1)).isoformat(),
            "offers": [{
                "instrument": {"role": "primary", "type": "PHYSICAL"},
                "field": "CLOSE",
                "timeframes": [60],
                "maximum_history_bars": 1000,
                "available_from": (NOW - dt.timedelta(days=2)).isoformat(),
                "available_to": (NOW - dt.timedelta(minutes=2)).isoformat(),
                "maximum_freshness_seconds": 120,
                "depth": {"kind": "NONE", "levels": None},
                "session": "INSTRUMENT_CALENDAR",
                "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
                "derived_local": False,
                "entitled": True,
                "known": True,
            }],
            "change_level": 0,
        },
        "raw_observation": {
            "alias_index": 0,
            "media_type": "application/json",
            "raw_schema": "fixture-candle/1",
            "payload_text": '{"close":"100.00"}',
            "field": "CLOSE",
            "resolution_seconds": 60,
            "event_time": (NOW - dt.timedelta(minutes=2)).isoformat(),
            "completed_at": (NOW - dt.timedelta(minutes=1)).isoformat(),
            "available_at": (NOW - dt.timedelta(seconds=50)).isoformat(),
            "recorded_at": (NOW - dt.timedelta(seconds=40)).isoformat(),
            "sequence_id": "seq-1",
            "correction_id": "original",
        },
    }


def test_fixture_maps_exact_existing_provider_authority_chain():
    bundle = map_provider_evidence(_fixture())
    assert bundle.product.entity_address == bundle.entity.address
    assert bundle.contract.product_address == bundle.product.address
    assert bundle.aliases[0].product_address == bundle.product.address
    assert bundle.capability_profile.provider_contract_address == bundle.contract.address
    assert bundle.raw_observation.raw_segment_address == bundle.raw_segment.address
    assert not hasattr(bundle, "normalized_observation")


@pytest.mark.parametrize(
    "mutation",
    (
        lambda row: row["capability_profile"]["offers"][0]["instrument"].update(role="secondary"),
        lambda row: row["capability_profile"]["offers"][0].update(field="BID"),
        lambda row: row["capability_profile"]["offers"][0].update(timeframes=[120]),
        lambda row: row["capability_profile"]["offers"][0].update(maximum_history_bars=1001),
        lambda row: row["capability_profile"]["offers"][0].update(
            available_from=(NOW - dt.timedelta(days=3)).isoformat()),
        lambda row: row["capability_profile"]["offers"][0].update(
            available_to=NOW.isoformat()),
        lambda row: row["capability_profile"]["offers"][0].update(maximum_freshness_seconds=119),
        lambda row: row["capability_profile"]["offers"][0].update(
            depth={"kind": "TOP_OF_BOOK", "levels": None}),
        lambda row: row["capability_profile"]["offers"][0].update(session="CONTINUOUS"),
        lambda row: row["conformance"]["coverage"][0]["alignment"].update(
            maximum_skew_seconds=1),
        lambda row: row["capability_profile"]["offers"][0].update(derived_local=True),
        lambda row: row["conformance"]["coverage"][0].update(entitlement="UNVERIFIED"),
    ),
)
def test_profile_cannot_claim_more_than_one_complete_coverage_row(mutation):
    fixture = copy.deepcopy(_fixture())
    mutation(fixture)
    with pytest.raises(ProviderEvidenceRefusal, match="exceeds conformance evidence"):
        map_provider_evidence(fixture)


def test_unverified_entitlement_remains_an_explicit_unavailable_offer():
    fixture = _fixture()
    fixture["conformance"]["coverage"][0]["entitlement"] = "UNVERIFIED"
    fixture["capability_profile"]["offers"][0]["entitled"] = False
    bundle = map_provider_evidence(fixture)
    assert bundle.conformance.coverage[0]["entitlement"] == "UNVERIFIED"
    assert bundle.capability_profile.offers[0]["entitled"] is False


def test_v2_coverage_is_canonical_and_answer_changing():
    fixture = _fixture()
    first = map_provider_evidence(fixture).conformance
    reordered = copy.deepcopy(fixture)
    reordered["conformance"]["coverage"] = list(reversed(
        reordered["conformance"]["coverage"]
    ))
    second = map_provider_evidence(reordered).conformance
    assert first.schema == "provider-conformance/2"
    assert first.address == second.address
    assert first.canonical_bytes == second.canonical_bytes

    changed = copy.deepcopy(fixture)
    changed["conformance"]["coverage"][0]["history"]["from"] = (
        NOW - dt.timedelta(days=3)
    ).isoformat()
    assert map_provider_evidence(changed).conformance.address != first.address


@pytest.mark.parametrize("mutation", (
    lambda row: row["instrument"].update(role="secondary"),
    lambda row: row.update(field="BID"),
    lambda row: row.update(resolution_seconds=120),
    lambda row: row["history"].update(**{"from": NOW - dt.timedelta(days=3)}),
    lambda row: row["history"].update(bars=1001),
    lambda row: row.update(maximum_freshness_seconds=121),
    lambda row: row.update(depth={"kind": "TOP_OF_BOOK", "levels": None}),
    lambda row: row.update(session="CONTINUOUS"),
    lambda row: row.update(alignment={"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 1}),
    lambda row: row.update(derived_local=True),
    lambda row: row.update(entitlement="UNVERIFIED"),
))
def test_each_v2_coverage_dimension_changes_identity(mutation):
    coverage = {
        "instrument": {"role": "primary", "type": "PHYSICAL"},
        "field": "CLOSE", "resolution_seconds": 60,
        "history": {"from": NOW - dt.timedelta(days=2),
            "to": NOW - dt.timedelta(minutes=2), "bars": 1000},
        "maximum_freshness_seconds": 120,
        "depth": {"kind": "NONE", "levels": None},
        "session": "INSTRUMENT_CALENDAR",
        "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
        "derived_local": False, "entitlement": "VERIFIED",
    }
    baseline = ProviderConformance(
        _address("product"), ("BID", "CLOSE"), (60, 120), "fixture", "2",
        NOW - dt.timedelta(days=1), NOW + dt.timedelta(days=1),
        (_address("evidence"),), "PASS", (coverage,),
    )
    changed = copy.deepcopy(coverage)
    mutation(changed)
    candidate = ProviderConformance(
        baseline.product_address, baseline.tested_fields, baseline.tested_resolutions,
        baseline.test_method, baseline.test_version, baseline.observed_from,
        baseline.observed_to, baseline.evidence_artifacts, baseline.result, (changed,),
    )
    assert candidate.address != baseline.address


@pytest.mark.parametrize(
    ("mutation", "match"),
    (
        (lambda row: row.update(other=True), "open or incomplete"),
        (lambda row: row["contract"].pop("evidence_address"), "open or incomplete"),
        (lambda row: row.update(at_time=(NOW + dt.timedelta(days=20)).isoformat()), "not effective"),
        (lambda row: row["capability_profile"].update(expires_at=(NOW - dt.timedelta(seconds=1)).isoformat()), "not current"),
        (lambda row: row["conformance"].update(result="FAIL"), "failed or stale"),
        (lambda row: row["aliases"][0].update(observation_namespace="other"), "namespace conflicts"),
        (lambda row: row["capability_profile"].update(api_secret="never"), "secret-bearing"),
        (lambda row: row["capability_profile"]["offers"][0].update(field="BID"), "exceeds conformance"),
    ),
)
def test_unknown_incomplete_stale_conflicting_and_secret_evidence_refuses(mutation, match):
    fixture = copy.deepcopy(_fixture())
    mutation(fixture)
    with pytest.raises(ProviderEvidenceRefusal, match=match):
        map_provider_evidence(fixture)


def test_mapping_is_deterministic_and_contains_no_network_or_credential_value():
    first = map_provider_evidence(_fixture())
    second = map_provider_evidence(_fixture())
    assert first == second
    assert first.entity.address == second.entity.address
    assert first.capability_profile.capability_profile_address \
        == second.capability_profile.capability_profile_address
