"""Derivative history remains authorable but unavailable without exact capture."""
import datetime as dt

from app.market_data.eligibility import EligibilityCode, compile_graph_data_eligibility
from app.market_truth.identity import CanonicalPhysicalInstrument
from tests.test_v0_graph_data_eligibility import T0, _case


def _option():
    return CanonicalPhysicalInstrument("fixture", "1", "XNFO", "OPTION", "WEEKLY_OPTION",
        "INR", "sha256:" + "7" * 64, T0 + dt.timedelta(days=7), "22000", "CALL", "50")


def test_expired_options_history_refuses_without_underlying_substitution():
    case = _case(instrument=_option())
    result = compile_graph_data_eligibility(**case)
    assert result.status == "REFUSED"
    assert EligibilityCode.EXPIRED_OPTIONS_HISTORY_UNAVAILABLE in {item.code for item in result.refusals}


def test_historical_depth_and_order_flow_refuse_even_when_declared_offer_claims_depth():
    depth = {"kind": "BOOK", "levels": 5}
    case = _case(field="BID_SIZE", depth=depth, instrument=_option())
    result = compile_graph_data_eligibility(**case)
    codes = {item.code for item in result.refusals}
    assert EligibilityCode.HISTORICAL_DEPTH_UNAVAILABLE in codes


def test_underlying_only_counterfactual_requires_a_distinct_graph_version():
    option_case = _case(instrument=_option())
    cash_case = _case()
    # Reuse the option graph/input binding with cash data: the compiler must not
    # treat the underlying as a provider fallback for the authored graph version.
    result = compile_graph_data_eligibility(**{**option_case, "datasets": cash_case["datasets"]})
    assert EligibilityCode.UNDERLYING_SUBSTITUTION_REQUIRES_GRAPH_VERSION in {
        item.code for item in result.refusals}


def test_replacing_binding_dataset_and_capability_still_requires_new_graph_version():
    from tests.test_v0_graph_data_eligibility import _replace_binding

    option_case = _case(instrument=_option())
    cash_case = _case()
    cash_dataset = cash_case["datasets"][0]
    binding = next(iter(cash_case["input_bindings"].document["inputs"].values()))[
        "binding"]
    replaced = _replace_binding(option_case,
        dataset_manifest_address=cash_dataset.manifest.manifest_address,
        market_truth_address=binding["market_truth_address"],
        provider_product_address=binding["provider_product_address"],
        provider_contract_address=binding["provider_contract_address"],
        canonical_instrument_address=cash_dataset.instrument.address,
        instrument={"role": "primary", "type": "PHYSICAL"})
    result = compile_graph_data_eligibility(**{
        **replaced,
        "datasets": cash_case["datasets"],
        "profile": cash_case["profile"],
        "conformance": cash_case["conformance"],
        "provider_contract": cash_case["provider_contract"],
    })
    assert EligibilityCode.UNDERLYING_SUBSTITUTION_REQUIRES_GRAPH_VERSION in {
        item.code for item in result.refusals}
