"""Fail-closed human help for the immutable V0 verified-language catalogue.

Help is a presentation projection of existing component specifications and
evaluators.  It is not an executable component, formula source, or authority
record.  Every row is bound to the implementation identity already carried by
the catalogue so a semantic implementation change requires a help review.
"""
from __future__ import annotations

import re
from collections import Counter
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from app.ir.first_party import derivatives, logic_state, monitoring_intent_v2
from app.ir.first_party.analytical_v2 import (
    core_math,
    multi_output,
    recursive_state,
    remaining_oracles,
    session_data,
)
from app.ir.schema import is_content_address


SEMANTIC_KINDS = frozenset({
    "MATHEMATICAL_FORMULA",
    "FIELD_SELECTION",
    "FIELD_SPLITTER",
    "LOGICAL_OPERATION",
    "INTENT_BEHAVIOR",
})
EXPECTED_KIND_COUNTS = MappingProxyType({
    "MATHEMATICAL_FORMULA": 181,
    "FIELD_SELECTION": 29,
    "FIELD_SPLITTER": 1,
    "LOGICAL_OPERATION": 47,
    "INTENT_BEHAVIOR": 12,
})
RAW_ADDRESS_PATTERN = re.compile(r"(?:sha256:)?[0-9a-f]{64}", re.IGNORECASE)
IMMUTABLE_BOUNDARY = (
    "This is an immutable built-in. You can change only the listed parameters; "
    "you cannot edit its code here."
)
NO_PARAMETERS = "This built-in has no parameters."


class CatalogueHelpError(ValueError):
    """Help cannot close the exact published catalogue identity set."""


_ANALYTICAL_MODULES = (
    core_math,
    recursive_state,
    multi_output,
    session_data,
    remaining_oracles,
)

_FIELD_SELECTIONS = frozenset({
    "analytical.close", "analytical.high", "analytical.low", "analytical.open",
    "derivative.atm", "derivative.atm_plus_minus_n", "derivative.call_put_selector",
    "derivative.continuous_research_series", "derivative.delta_target_selector",
    "derivative.depth_level_n", "derivative.dte_selector", "derivative.expiry_list",
    "derivative.far_contract", "derivative.far_expiry", "derivative.front_contract",
    "derivative.moneyness_selector", "derivative.nearest_expiry",
    "derivative.next_contract", "derivative.next_expiry", "derivative.option_chain_slice",
    "derivative.peer_basket", "derivative.roll_selector",
    "derivative.secondary_instrument_input", "derivative.straddle_selector",
    "derivative.strangle_selector", "derivative.tradable_mapped_contract",
})

_LOGICAL_OPERATIONS = frozenset({
    "logic.a_then_b", "logic.a_within_n_bars_of_b", "logic.all", "logic.and",
    "logic.any", "logic.bars_since", "logic.cooldown", "logic.counter",
    "logic.date_range", "logic.debounce", "logic.dte_gate", "logic.explicit_fallback",
    "logic.falling_n", "logic.hysteresis", "logic.if_missing", "logic.is_missing",
    "logic.is_stale", "logic.is_undefined", "logic.is_valid", "logic.lag_n",
    "logic.latch", "logic.minutes_from_open", "logic.minutes_to_close",
    "logic.n_consecutive", "logic.n_of_last_m", "logic.not", "logic.or",
    "logic.previous_value", "logic.resettable_latch", "logic.rising_n",
    "logic.session_gate", "logic.state_machine", "logic.time_range", "logic.time_since",
    "logic.toggle", "logic.weekday_gate", "logic.xor",
})


# These texts follow the closed branches in logic_state._derivative_result,
# _order_book_result, and _trade_flow_result. There is deliberately no fallback
# based on the component's display name.
_TYPE_3_SEMANTICS = MappingProxyType({
    "AGGRESSOR_BUY_SELL_FLOW": "Return (sum(aggressor_buy_volume), sum(aggressor_sell_volume)) over the accepted point-in-time members.",
    "ANNUALIZED_BASIS": "Return (future - spot) / year_fraction.",
    "ASK_QUANTITY": "Return the primary member's best-ask quantity.",
    "ATM": "Return the strike with the smallest absolute distance from spot; break a tie with the lower strike.",
    "ATM_PLUS_MINUS_N": "Sort distinct strikes, locate ATM by absolute distance from spot then lower strike, and return the bounded slice from N strikes below through N strikes above.",
    "BASIS": "Return future - spot.",
    "BEST_ASK": "Return the primary member's best ask.",
    "BEST_BID": "Return the primary member's best bid.",
    "BID_QUANTITY": "Return the primary member's best-bid quantity.",
    "BOOK_SLOPE": "Across the selected depth prefix, return ((last ask - first ask) + (first bid - last bid)) / 2.",
    "CALENDAR_SPREAD": "Sort members by contract_rank then instrument address and return front price - next price.",
    "CALL_PUT_SELECTOR": "Return the instrument addresses whose option right equals the requested CALL or PUT value.",
    "CHAIN_OPEN_INTEREST": "Return the sum of open_interest over the accepted members.",
    "CHANGE_IN_OPEN_INTEREST": "Return the sum of change_in_open_interest over the accepted members.",
    "CONTINUOUS_RESEARCH_SERIES": "Sort members by contract_rank then instrument address and return their price series in that order.",
    "CUMULATIVE_DELTA": "Return each accepted member's cumulative_delta in member order.",
    "CUMULATIVE_N_LEVEL_DEPTH": "Return the summed bid quantity and summed ask quantity across the selected depth prefix.",
    "DAYS_TO_EXPIRY": "Return the minimum dte across the accepted members.",
    "DELTA": "Return the provider-supplied delta for each accepted member.",
    "DELTA_TARGET_SELECTOR": "Return the member whose delta is closest to target_delta; break a tie with instrument address.",
    "DEPTH_IMBALANCE": "Return (bid_quantity - ask_quantity) / (bid_quantity + ask_quantity) for the primary member.",
    "DEPTH_LEVEL_N": "Return (bid, ask, bid_quantity, ask_quantity) from the last level in the selected depth prefix.",
    "DEPTH_WEIGHTED_SPREAD": "Return quantity-weighted ask - quantity-weighted bid across the selected depth prefix.",
    "DTE_SELECTOR": "Return the member whose dte is closest to target_dte; break a tie with instrument address.",
    "EXPIRY_LIST": "Return the sorted distinct expiry values from the accepted members.",
    "FAR_CONTRACT": "Sort members by contract_rank then instrument address and return the last member's instrument address.",
    "FAR_EXPIRY": "Return the last value in the sorted distinct expiry list.",
    "FRONT_CONTRACT": "Sort members by contract_rank then instrument address and return the first member's instrument address.",
    "GAMMA": "Return the provider-supplied gamma for each accepted member.",
    "IMPLIED_VOLATILITY": "Return the provider-supplied implied_volatility for each accepted member.",
    "IV_PERCENTILE": "Return the provider-supplied iv_percentile for each accepted member.",
    "IV_RANK": "Return the provider-supplied iv_rank for each accepted member.",
    "LIQUIDITY_CONCENTRATION": "Return the largest bid-or-ask level quantity divided by the sum of all bid and ask quantities in the selected depth prefix.",
    "MICROPRICE": "Return (ask * bid_quantity + bid * ask_quantity) / (bid_quantity + ask_quantity) for the primary member.",
    "MONEYNESS_SELECTOR": "Return the member whose strike / spot ratio is closest to target_moneyness_ratio; break a tie with instrument address.",
    "NEAREST_EXPIRY": "Return the first value in the sorted distinct expiry list.",
    "NEXT_CONTRACT": "Sort members by contract_rank then instrument address and return the second member's instrument address.",
    "NEXT_EXPIRY": "Return the second value in the sorted distinct expiry list.",
    "OPEN_INTEREST_CONCENTRATION": "Return max(open_interest) / sum(open_interest) over the accepted members.",
    "OPTION_CHAIN_SLICE": "Return instrument addresses whose strike lies within the inclusive requested range and whose expiry equals selected_expiry.",
    "PCR_OPEN_INTEREST": "Return total PUT open_interest / total CALL open_interest.",
    "PCR_VOLUME": "Return total PUT volume / total CALL volume.",
    "PEER_BASKET": "Return all accepted member instrument addresses in canonical member order.",
    "PROVIDER_TOTAL_BUY_SELL_QUANTITY": "Return the provider's total_buy_quantity and total_sell_quantity for the primary member.",
    "PUT_CALL_PARITY_DEVIATION": "Return call price - put price - (spot - strike).",
    "RELATIVE_VALUE_STRUCTURE": "Return primary price - secondary price.",
    "RHO": "Return the provider-supplied rho for each accepted member.",
    "ROLL_SELECTOR": "Among members with dte at least minimum_roll_dte, return the lowest-dte member; break a tie with instrument address.",
    "SECONDARY_INSTRUMENT_INPUT": "Return the instrument address of the single member with structure_role SECONDARY.",
    "SKEW": "Return the provider-supplied skew for each accepted member.",
    "SPREAD": "Return best ask - best bid for the primary member.",
    "STRADDLE_PRICE": "Select the nearest common call/put strike to spot and return call price + put price.",
    "STRADDLE_SELECTOR": "Select the nearest common call/put strike to spot and return the call and put instrument addresses.",
    "STRANGLE_SELECTOR": "Return the nearest out-of-the-money call above spot and put below spot, with instrument address as the tie-break.",
    "STRIKE_VOLUME_OI_RATIO": "For each accepted member, return volume / open_interest.",
    "SYNTHETIC_FUTURE": "Return call price - put price + strike.",
    "TERM_STRUCTURE": "Return the provider-supplied term_structure for each accepted member.",
    "THETA": "Return the provider-supplied theta for each accepted member.",
    "TRADABLE_MAPPED_CONTRACT": "Return mapped_contract_address only when it names one of the accepted members.",
    "TRADE_IMBALANCE": "Return (sum(aggressor_buy_volume) - sum(aggressor_sell_volume)) / (sum(aggressor_buy_volume) + sum(aggressor_sell_volume)).",
    "VEGA": "Return the provider-supplied vega for each accepted member.",
    "VOLUME_DELTA": "Return sum(aggressor_buy_volume) - sum(aggressor_sell_volume).",
    "WEIGHTED_DEPTH_IMBALANCE": "Weight each selected depth level by 1 / level_number and return (weighted bid quantity - weighted ask quantity) / (weighted bid quantity + weighted ask quantity).",
})


# These texts follow evaluate_logic_state and _stateful_evaluation. Invalid
# inputs retain the evaluator's explicit validity state rather than becoming a
# boolean or numeric fallback.
_TYPE_5_SEMANTICS = MappingProxyType({
    "ABS": "Return abs(left).",
    "ADD": "Return left + right.",
    "ALL": "Return true only when every value in series is true.",
    "AND": "Return left and right.",
    "ANY": "Return true when any value in series is true.",
    "AVERAGE": "Return sum(series) / count(series).",
    "A_THEN_B": "For each event, return true when B is true after A has previously been observed; once A is observed, retain that state.",
    "A_WITHIN_N_BARS_OF_B": "For each B event, return true when A occurred in the preceding window events; retain only that bounded A history.",
    "BARS_SINCE": "Return 0 on a true trigger, the number of later events since the trigger, or -1 before any trigger.",
    "BETWEEN": "Return lower <= left <= upper; an inverted range is mathematically undefined.",
    "CLAMP": "Return lower when left is below lower, upper when left is above upper, otherwise left; an inverted range is mathematically undefined.",
    "COOLDOWN": "Allow a true trigger only when no cooldown remains, then suppress triggers for the configured window while the counter decreases.",
    "COUNT": "Return count(series).",
    "COUNTER": "Add each numeric series value to the retained counter and return the updated counter.",
    "DATE_RANGE": "Return true when evaluation_time's date is within the inclusive date_start to date_end range; an inverted range is mathematically undefined.",
    "DEBOUNCE": "Return true only after the input has remained true for the configured number of consecutive events.",
    "DIVIDE": "Return left / right; division by zero is mathematically undefined.",
    "DTE_GATE": "Return minimum_dte <= dte <= maximum_dte; an inverted range is mathematically undefined.",
    "EQ": "Return left == right.",
    "EXPLICIT_FALLBACK": "Return fallback only when left has one of the explicitly listed non-valid fallback states; otherwise retain left.",
    "FALLING_N": "Return true after the value has fallen strictly for the configured number of consecutive comparisons.",
    "GT": "Return left > right.",
    "GTE": "Return left >= right.",
    "HYSTERESIS": "Retain a boolean state, set it true at or above upper, set it false at or below lower, and keep it unchanged between the thresholds.",
    "IF_MISSING": "Return fallback only when left is MISSING; otherwise retain left.",
    "IS_MISSING": "Return true only when left has validity state MISSING.",
    "IS_STALE": "Return true only when left has validity state STALE.",
    "IS_UNDEFINED": "Return true only when left has validity state MATHEMATICALLY_UNDEFINED.",
    "IS_VALID": "Return true only when left has validity state VALID.",
    "LAG_N": "Return the value from window events earlier, or INSUFFICIENT_HISTORY until that value exists.",
    "LATCH": "Retain true after the first true event.",
    "LOG": "Return the natural logarithm of left; non-positive input is mathematically undefined.",
    "LT": "Return left < right.",
    "LTE": "Return left <= right.",
    "MAX": "Return max(series).",
    "MIN": "Return min(series).",
    "MINUTES_FROM_OPEN": "Return (evaluation_time - session_open_time) in minutes; a negative result is NOT_IN_SESSION.",
    "MINUTES_TO_CLOSE": "Return (session_close_time - evaluation_time) in minutes; a negative result is NOT_IN_SESSION.",
    "MODULO": "Return left % right; a zero divisor is mathematically undefined.",
    "MULTIPLY": "Return left * right.",
    "NEQ": "Return left != right.",
    "NOT": "Return not left.",
    "N_CONSECUTIVE": "Return true after series has remained true for the configured number of consecutive events.",
    "N_OF_LAST_M": "Return true when at least required_count values in the complete trailing window are true; before the window is complete return INSUFFICIENT_HISTORY.",
    "OR": "Return left or right.",
    "POWER": "Return left raised to right; a negative base with a non-integer exponent is mathematically undefined.",
    "PREVIOUS_VALUE": "Return the preceding series value, or INSUFFICIENT_HISTORY before one exists.",
    "RESETTABLE_LATCH": "Retain true after a true event, but set false when the aligned reset event is true.",
    "RISING_N": "Return true after the value has risen strictly for the configured number of consecutive comparisons.",
    "ROUND": "Return round(left) using the evaluator's integer rounding operation.",
    "SESSION_GATE": "Return true when evaluation_time's clock time lies within the inclusive session-open to session-close range, including a range that crosses midnight.",
    "SQRT": "Return sqrt(left); a negative input is mathematically undefined.",
    "STATE_MACHINE": "Use the exact four-entry boolean transition table keyed by retained state and current event, then return and retain the resulting state.",
    "SUBTRACT": "Return left - right.",
    "SUM": "Return sum(series).",
    "TIME_RANGE": "Return true when evaluation_time's clock time lies within the inclusive requested range, including a range that crosses midnight.",
    "TIME_SINCE": "Return elapsed seconds since the latest true A event, or -1 before any such event.",
    "TOGGLE": "Invert the retained boolean state on each true event and retain it on false events.",
    "WEEKDAY_GATE": "Return true when evaluation_time's weekday is in the canonical allowed_weekdays set, where Monday is 0 and Sunday is 6.",
    "XOR": "Return true when exactly one of left and right is true.",
})


def _target_semantics(name: str, spec: Mapping[str, Any]) -> str:
    return (
        f"When the valid condition is true, request monitoring target state {spec['target_state']}; "
        f"risk_reducing is {str(spec['risk_reducing']).lower()}. When the condition is false, "
        "retain the same target description with requested=false. This creates no order or execution authority."
    )


def _protection_semantics(name: str, spec: Mapping[str, Any]) -> str:
    if spec["input"] == "distance":
        resolution = (
            f"Multiply the verified PRICE_POINTS distance by the authored {spec['parameter']} "
            "to resolve the protection value."
        )
    else:
        resolution = (
            f"Use the authored {spec['parameter']} as the protection value and use the valid "
            "condition to set whether the protection is active."
        )
    return (
        f"{resolution} Emit monitoring-only {spec['kind']} protection with basis {spec['basis']} "
        f"and units {spec['units']}. This creates no broker instruction or execution authority."
    )


_TYPE_1_SEMANTICS = MappingProxyType({
    **{name: _target_semantics(name, spec)
       for name, spec in monitoring_intent_v2.TARGET_SPECS.items()},
    **{name: _protection_semantics(name, spec)
       for name, spec in monitoring_intent_v2.PROTECTION_SPECS.items()},
})


_ORIGINAL_HELP = {
    "close": ("FIELD_SELECTION", "Select the indexed close price. Missing or invalid prices remain invalid."),
    "high": ("FIELD_SELECTION", "Select the indexed high price. Missing or invalid prices remain invalid."),
    "low": ("FIELD_SELECTION", "Select the indexed low price. Missing or invalid prices remain invalid."),
    "true_range": ("MATHEMATICAL_FORMULA", "Return max(high-low, abs(high-prior close), abs(low-prior close)); the first event uses high-low."),
    "value": ("MATHEMATICAL_FORMULA", "Return the authored numeric constant at every event in the alignment input."),
    "ema_first_close": ("MATHEMATICAL_FORMULA", "Seed from the first source value, then use EMA = prior EMA + 2/(length+1) * (source-prior EMA). An invalid source keeps the remaining recurrence invalid."),
    "rolling_stddev_population": ("MATHEMATICAL_FORMULA", "Return sqrt(sum((x-mean(window))^2)/length) over the full trailing window. Incomplete history or an invalid member remains invalid."),
    "rma_sma_seed": ("MATHEMATICAL_FORMULA", "Seed with the mean of length source values, then use source/length + (1-1/length)*prior RMA. An invalid source keeps the remaining recurrence invalid."),
    "nearest_rank": ("MATHEMATICAL_FORMULA", "Sort the full trailing window and select rank max(1, ceil(percentile*length/100)). Incomplete history or an invalid member remains invalid."),
    "subtract": ("MATHEMATICAL_FORMULA", "Return left minus right; invalid inputs propagate."),
    "divide": ("MATHEMATICAL_FORMULA", "Return left divided by right; invalid inputs propagate and division by zero is mathematically undefined."),
    "multiply": ("MATHEMATICAL_FORMULA", "Return left multiplied by right; invalid inputs propagate."),
    "maximum": ("MATHEMATICAL_FORMULA", "Return the larger input; invalid inputs propagate."),
    "abs": ("MATHEMATICAL_FORMULA", "Return the absolute value; invalid input propagates."),
    "gt": ("LOGICAL_OPERATION", "Return whether left is strictly greater than right; invalid inputs propagate."),
    "lt": ("LOGICAL_OPERATION", "Return whether left is strictly less than right; invalid inputs propagate."),
    "le": ("LOGICAL_OPERATION", "Return whether left is less than or equal to right; invalid inputs propagate."),
    "and": ("LOGICAL_OPERATION", "Return boolean left AND right; invalid inputs propagate."),
    "or": ("LOGICAL_OPERATION", "Return boolean left OR right; invalid inputs propagate."),
    "lag": ("LOGICAL_OPERATION", "Return the source from length completed events earlier. Leading events have insufficient history."),
    "fallback_zero": ("LOGICAL_OPERATION", "Replace only insufficient history or mathematical undefined with zero. Preserve missing, stale and provider-unavailable states."),
    "fallback_false": ("LOGICAL_OPERATION", "Replace only insufficient history or mathematical undefined with false. Preserve missing, stale and provider-unavailable states."),
    "fallback_value": ("LOGICAL_OPERATION", "Replace left with right only when left has insufficient history or is mathematically undefined. Preserve missing, stale and provider-unavailable states."),
    "optional_condition": ("LOGICAL_OPERATION", "Return the source when enabled; otherwise return the authored otherwise boolean."),
}
_RECIPE_HELP = {
    "strategy.trend_impulse_v3": (
        "Trend Impulse V3 signal recipe",
        "Compose first-close EMA, population standard deviation of close, z=(close-EMA)/std(close), and EMA slope over slope_lookback events. Insufficient-history or zero standard deviation falls back to z=0. Long entry needs positive slope, prior z strictly below entry_z, current z strictly above it and increasing z; short entry mirrors the negative threshold and requires increasing absolute z. Long exit is z<0 or negative slope; short exit is z>0 or positive slope. Missing prices remain invalid.",
    ),
    "strategy.expanding_z_v4_pine": (
        "Original Pine V4 signal recipe",
        "Compose first-close EMA, population standard deviation of close-EMA, residual z, and SMA-seeded Wilder ATR. Entry and exit thresholds use prior-bar nearest-rank absolute-z values with the declared floors. A breakout uses prior absolute z less than or equal to its prior threshold and current absolute z above its current threshold. Optional re-expansion and required-expansion gates combine with z direction, ATR drift and signal-bar range. Discretionary exits use the declared contraction, drift and EMA toggles. Sizing, position gates, fill timing and ratchet stops are consumer behavior, not outputs of this compound. Missing prices remain invalid.",
    ),
}


def _original_source(component_id):
    title = _RECIPE_HELP[component_id][0] if component_id in _RECIPE_HELP else "Strategy OS typed series primitive"
    return _source_record(
        source_record_id=component_id + ".definition", title=title, organization="Strategy OS",
        publication="Frozen first-party component definition", year=2026, url=None,
        claim_scope="Defines this component's declared series behavior and validity boundary; it does not grant execution authority.",
    )


def _composition_binding(row):
    binding = row.get("composition_binding")
    if (row.get("implementation_address") is not None or not isinstance(binding, Mapping)
            or set(binding) != {"component_address", "registry_identity"}):
        raise CatalogueHelpError("compound composition binding is invalid")
    if binding["component_address"] != row.get("component_address") or not all(
            is_content_address(value) for value in binding.values()):
        raise CatalogueHelpError("compound composition binding is invalid")
    return {"implementation_binding": None, "composition_binding": dict(binding)}


def _help_binding(row):
    if row.get("component_kind") == "COMPOUND":
        return _composition_binding(row)
    implementation = row.get("implementation_address")
    if row.get("component_kind") != "LEAF" or not is_content_address(implementation):
        raise CatalogueHelpError("leaf implementation binding is invalid")
    return {"implementation_binding": implementation}


def _semantic_kind(component_id: str) -> str:
    if component_id in _RECIPE_HELP or component_id == "structure.historical_daily_gaps":
        return "MATHEMATICAL_FORMULA"
    if component_id.startswith("strategy_math."):
        try:
            return _ORIGINAL_HELP[component_id.split(".", 1)[1]][0]
        except KeyError as exc:
            raise CatalogueHelpError("original primitive semantics are unreviewed") from exc
    if component_id == "analytical.ohlcv":
        return "FIELD_SPLITTER"
    if component_id in _FIELD_SELECTIONS:
        return "FIELD_SELECTION"
    if component_id in _LOGICAL_OPERATIONS:
        return "LOGICAL_OPERATION"
    if component_id.startswith("intent."):
        return "INTENT_BEHAVIOR"
    if component_id.startswith(("analytical.", "derivative.", "logic.")):
        return "MATHEMATICAL_FORMULA"
    raise CatalogueHelpError(f"help semantic kind is unreviewed for {component_id!r}")


def _analytical_spec(component_id: str) -> Mapping[str, Any]:
    name = component_id.removeprefix("analytical.").upper()
    matches = [module.SPECS[name] for module in _ANALYTICAL_MODULES
               if name in getattr(module, "SPECS", {})]
    if len(matches) != 1 or matches[0].get("decision") == "REFUSE":
        raise CatalogueHelpError(f"accepted analytical help source is not unique for {component_id!r}")
    formula = matches[0].get("formula")
    if not isinstance(formula, str) or not formula.strip():
        raise CatalogueHelpError(f"accepted analytical formula is blank for {component_id!r}")
    return matches[0]


def _source_record(*, source_record_id: str, title: str, organization: str,
                   publication: str, year: int | None, url: str | None,
                   claim_scope: str) -> dict[str, Any]:
    return {
        "source_record_id": source_record_id,
        "title": title,
        "authors_or_organization": organization,
        "publication_or_version": publication,
        "year": year,
        "url": url,
        "claim_scope": claim_scope,
    }


def _analytical_source(component_id: str, spec: Mapping[str, Any]) -> dict[str, Any]:
    label = spec.get("source", "SPEC")
    scope = f"Defines the accepted {component_id} V2 formula and its stated validity boundary."
    if isinstance(label, str) and label.startswith("TA:"):
        function = label.split(":", 1)[1]
        return _source_record(
            source_record_id=f"ta-lib-0.7.1-{function.lower()}",
            title=f"TA-Lib {function} function source",
            organization="TA-Lib project",
            publication="TA-Lib core v0.7.1",
            year=None,
            url=f"https://github.com/TA-Lib/ta-lib/blob/2247d599bddf37ed37e3a709371517e46efc66f6/src/ta_func/ta_{function}.c",
            claim_scope=scope,
        )
    if label == "PAPER:RS":
        return _source_record(
            source_record_id="rogers-satchell-1991",
            title="Estimating variance from high, low and closing prices",
            organization="L. C. G. Rogers and S. E. Satchell",
            publication="The Annals of Applied Probability 1(4)", year=1991,
            url="https://www.skokholm.co.uk/wp-content/uploads/2016/01/R_Satchell_HLOC.pdf",
            claim_scope=scope,
        )
    if isinstance(label, str) and label.startswith("PAPER:YZ"):
        return _source_record(
            source_record_id="yang-zhang-2000",
            title="Drift-independent volatility estimation based on high, low, open, and close prices",
            organization="Dennis Yang and Qiang Zhang",
            publication="The Journal of Business 73(3)", year=2000,
            url="https://www.atmif.com/papers/range.pdf", claim_scope=scope,
        )
    if label == "STATISTICS":
        return _source_record(
            source_record_id="nist-measures-of-scale",
            title="Measures of Scale",
            organization="National Institute of Standards and Technology",
            publication="NIST/SEMATECH e-Handbook of Statistical Methods", year=None,
            url="https://www.itl.nist.gov/div898/handbook/eda/section3/eda356.htm",
            claim_scope=scope,
        )
    if label == "CANONICAL":
        return _source_record(
            source_record_id="strategy-os-canonical-candle-v2",
            title="Strategy OS canonical completed-candle semantics",
            organization="Strategy OS",
            publication="Analytical V2 session-data specification", year=2026, url=None,
            claim_scope=scope,
        )
    return _source_record(
        source_record_id="strategy-os-analytical-v2-specification",
        title="Strategy OS analytical V2 specification",
        organization="Strategy OS",
        publication="Accepted analytical V2 built-in semantics", year=2026, url=None,
        claim_scope=scope,
    )


def _strategy_os_source(component_id: str, family: str) -> dict[str, Any]:
    records = {
        "TYPE_3": ("strategy-os-type3-evaluator-v1", "Strategy OS point-in-time Type 3 evaluator", "First-party evaluator version 1"),
        "TYPE_5": ("strategy-os-type5-evaluator-v1", "Strategy OS logic and state evaluator", "First-party evaluator version 1"),
        "TYPE_1": ("strategy-os-monitoring-intent-v2", "Strategy OS monitoring intent contract", "Monitoring semantic version 2"),
    }
    try:
        record_id, title, publication = records[family]
    except KeyError as exc:
        raise CatalogueHelpError(f"help source family is unreviewed for {component_id!r}") from exc
    return _source_record(
        source_record_id=record_id, title=title, organization="Strategy OS",
        publication=publication, year=2026, url=None,
        claim_scope=f"Defines the exact built-in behavior and validity boundary for {component_id}.",
    )


def _semantic_text(component_id: str) -> tuple[str, dict[str, Any]]:
    if component_id == "structure.historical_daily_gaps":
        return (
            "A bullish full-session gap forms when the completed daily low exceeds the previous completed daily high; "
            "a bearish gap mirrors this rule. Exact canonical session-close inputs are required. Original edges stay fixed: "
            "proximal reach marks a partial gap and distal reach marks it filled. Select the nearest unresolved gap on the "
            "correct side of price, then the oldest formation and zone identity. Formation times are UTC epoch seconds. "
            "Partially reached gaps never reopen, missing history invalidates later outputs, and the 4096-zone bound refuses "
            "further formation without dropping history. Gap reaches do not prove order fills or core/overlay position ownership.",
            _source_record(source_record_id="strategy-os-full-session-gap-v1",
                title="Strategy OS full-session gap policy", organization="Strategy OS",
                publication="Historical daily gap policy version 1", year=2026, url=None,
                claim_scope="Defines completed-session formation, immutable geometry, monotone reach states and deterministic selection."),
        )
    if component_id in _RECIPE_HELP:
        return _RECIPE_HELP[component_id][1], _original_source(component_id)
    if component_id.startswith("strategy_math."):
        return _ORIGINAL_HELP[component_id.split(".", 1)[1]][1], _original_source(component_id)
    if component_id.startswith("analytical."):
        spec = _analytical_spec(component_id)
        return spec["formula"], _analytical_source(component_id, spec)
    return _legacy_semantic_text(component_id)


def _legacy_semantic_text(component_id):
    namespace, name = component_id.split(".", 1)
    families = {
        "derivative": (derivatives.TYPE_3_NAMES, _TYPE_3_SEMANTICS, "TYPE_3"),
        "logic": (logic_state.TYPE_5_NAMES, _TYPE_5_SEMANTICS, "TYPE_5"),
        "intent": (monitoring_intent_v2.NAMES, _TYPE_1_SEMANTICS, "TYPE_1"),
    }
    if namespace not in families:
        raise CatalogueHelpError(f"help semantics are unreviewed for {component_id!r}")
    names, semantics, family = families[namespace]
    name = name.upper()
    if name not in names or name not in semantics:
        raise CatalogueHelpError(f"help semantics are unreviewed for {component_id!r}")
    return semantics[name], _strategy_os_source(component_id, family)


def _description(component_id: str, semantic_kind: str) -> str:
    if component_id in _RECIPE_HELP:
        return "An immutable compound of the visible typed components. Edit the copied strategy through the listed parameters; data and resource requirements are resolved from its contents."
    if component_id.startswith("strategy_math."):
        return "Apply the typed series operation below to aligned completed events, using its explicit history and validity rules."
    if component_id == "analytical.ohlcv":
        return (
            "Splits each fully completed candle into five named outputs: open, high, low, "
            "close and volume. It does not calculate an indicator."
        )
    if semantic_kind == "INTENT_BEHAVIOR":
        return (
            "Returns the monitoring-only target or protection record defined below after its "
            "required input and authored parameters are valid. It cannot place a trade."
        )
    if component_id.startswith("derivative."):
        return (
            "Returns the point-in-time result defined below when the required member facts, "
            "ownership, rulebook and any capability evidence are valid."
        )
    if component_id.startswith("logic."):
        return (
            "Returns the result defined below when its inputs are valid; otherwise it preserves "
            "the evaluator's explicit validity state."
        )
    return (
        "Returns the value defined below after the required completed-bar inputs and warm-up "
        "history are valid."
    )


def _parameter_record(name: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "type", "required", "default", "enum", "domain", "units", "serialization",
    }:
        raise CatalogueHelpError(f"parameter descriptor is not closed for {name!r}")
    if not isinstance(value["type"], str) or not value["type"] \
            or type(value["required"]) is not bool or not isinstance(value["units"], str) \
            or not value["units"] or not isinstance(value["serialization"], str) \
            or not value["serialization"]:
        raise CatalogueHelpError(f"parameter descriptor is invalid for {name!r}")
    return {
        "name": name,
        "type": value["type"],
        "required": value["required"],
        "default": value["default"],
        "enum": value["enum"],
        "domain": value["domain"],
        "units": value["units"],
        "serialization": value["serialization"],
    }


def _customisation(row: Mapping[str, Any]) -> dict[str, Any]:
    descriptor = row.get("descriptor")
    raw = descriptor.get("parameters") if isinstance(descriptor, Mapping) else None
    if not isinstance(raw, Mapping) or any(not isinstance(name, str) or not name for name in raw):
        raise CatalogueHelpError(f"parameter surface is invalid for {row.get('component_id')!r}")
    parameters = [_parameter_record(name, raw[name]) for name in sorted(raw)]
    guidance = (
        "Set only these authored parameters: " + ", ".join(item["name"] for item in parameters) + "."
        if parameters else NO_PARAMETERS
    )
    return {
        "parameters": parameters,
        "guidance": guidance,
        "built_in_code_immutable": True,
        "immutable_boundary": IMMUTABLE_BOUNDARY,
    }


def _availability(row: Mapping[str, Any]) -> dict[str, str]:
    value = row.get("availability")
    status = value.get("status") if isinstance(value, Mapping) else None
    authority = value.get("authority") if isinstance(value, Mapping) else None
    if status not in {"AVAILABLE", "CONDITIONAL"} or authority not in {"NONE", "MONITORING_ONLY"}:
        raise CatalogueHelpError(f"availability is invalid for {row.get('component_id')!r}")
    if status == "CONDITIONAL":
        text = (
            "Conditional: use requires the row's declared data and provider conditions. "
            "This catalogue does not verify provider support, data rights or backtest eligibility."
        )
    elif authority == "MONITORING_ONLY":
        text = "Available only as a research monitoring description; it has no paper or live authority."
    else:
        text = "Available within the declared research contract when required inputs are valid."
    return {"status": status, "authority": authority, "condition": text}


def build_help_record(row: Mapping[str, Any]) -> dict[str, Any]:
    component_id = row.get("component_id")
    version = row.get("component_version")
    binding = _help_binding(row)
    if not isinstance(component_id, str) or not component_id or type(version) is not int \
            or version < 1:
        raise CatalogueHelpError("catalogue row identity or implementation binding is invalid")
    semantic_kind = _semantic_kind(component_id)
    semantic_text, source = _semantic_text(component_id)
    return {
        "component_id": component_id,
        "component_version": version,
        **binding,
        "semantic_kind": semantic_kind,
        "description": _description(component_id, semantic_kind),
        "semantic_text": semantic_text,
        "sources": [source],
        "customisation": _customisation(row),
        "availability": _availability(row),
    }


def _safe_text(value: Any, label: str, *, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise CatalogueHelpError(f"help {label} is blank or invalid")
    return value


def _validate_source(source: Any) -> None:
    if not isinstance(source, Mapping) or set(source) != {
        "source_record_id", "title", "authors_or_organization", "publication_or_version",
        "year", "url", "claim_scope",
    }:
        raise CatalogueHelpError("help source record is not closed")
    for field in (
        "source_record_id", "title", "authors_or_organization",
        "publication_or_version", "claim_scope",
    ):
        text = _safe_text(source[field], f"source {field}", maximum=1024)
        if RAW_ADDRESS_PATTERN.search(text):
            raise CatalogueHelpError("raw content address is forbidden in a help source")
    if source["year"] is not None and (type(source["year"]) is not int
                                        or not 1800 <= source["year"] <= 2200):
        raise CatalogueHelpError("help source year is invalid")
    if source["url"] is not None:
        url = _safe_text(source["url"], "source url", maximum=2048)
        if not url.startswith("https://") or RAW_ADDRESS_PATTERN.search(url):
            raise CatalogueHelpError("help source URL is unsafe")


def _validate_help_identity(row: Mapping[str, Any], help_record: Any) -> None:
    binding = _help_binding(row)
    if not isinstance(help_record, Mapping) or set(help_record) != {
        "component_id", "component_version", "implementation_binding", "semantic_kind",
        "description", "semantic_text", "sources", "customisation", "availability",
    } | set(binding):
        raise CatalogueHelpError("help record is not closed")
    identity = (help_record["component_id"], help_record["component_version"])
    if identity != (row.get("component_id"), row.get("component_version")):
        raise CatalogueHelpError("help identity differs from catalogue row identity")
    if any(help_record[key] != value for key, value in binding.items()):
        raise CatalogueHelpError("help identity binding differs from catalogue row")
    if help_record["semantic_kind"] not in SEMANTIC_KINDS \
            or help_record["semantic_kind"] != _semantic_kind(help_record["component_id"]):
        raise CatalogueHelpError("help semantic kind is invalid")


def _validate_help_content(help_record):
    _safe_text(help_record["description"], "description")
    _safe_text(help_record["semantic_text"], "semantic text", maximum=16384)
    sources = help_record["sources"]
    if not isinstance(sources, (tuple, list)) or not sources:
        raise CatalogueHelpError("help has no source record")
    for source in sources:
        _validate_source(source)


def _validate_help_customisation(row, help_record):
    customisation = help_record["customisation"]
    if not isinstance(customisation, Mapping) or set(customisation) != {
        "parameters", "guidance", "built_in_code_immutable", "immutable_boundary",
    } or customisation["built_in_code_immutable"] is not True:
        raise CatalogueHelpError("help customisation boundary is invalid")
    _safe_text(customisation["guidance"], "customisation guidance")
    if customisation["immutable_boundary"] != IMMUTABLE_BOUNDARY:
        raise CatalogueHelpError("help immutable boundary changed")
    expected = _customisation(row)
    if list(customisation["parameters"]) != expected["parameters"]:
        raise CatalogueHelpError("help parameters differ from the component descriptor")
    availability = help_record["availability"]
    if availability != _availability(row):
        raise CatalogueHelpError("help availability differs from the catalogue row")


def _validate_ohlcv_help(help_record):
    if help_record["component_id"] == "analytical.ohlcv":
        expected_description = (
            "Splits each fully completed candle into five named outputs: open, high, low, "
            "close and volume. It does not calculate an indicator."
        )
        if help_record["description"] != expected_description \
                or help_record["semantic_kind"] != "FIELD_SPLITTER" \
                or help_record["semantic_text"] != _analytical_spec("analytical.ohlcv")["formula"]:
            raise CatalogueHelpError("OHLCV help semantics were forged")


def validate_help_record(row: Mapping[str, Any], help_record: Any) -> None:
    _validate_help_identity(row, help_record)
    _validate_help_content(help_record)
    _validate_help_customisation(row, help_record)
    _validate_ohlcv_help(help_record)


def _closed_help_projection(rows: Sequence[Mapping[str, Any]],
                             help_records: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    records = tuple(help_records)
    row_by_identity = {
        (row.get("component_id"), row.get("component_version")): row for row in rows
    }
    identities = [(record.get("component_id"), record.get("component_version"))
                  if isinstance(record, Mapping) else (None, None) for record in records]
    if len(row_by_identity) != len(rows) or len(set(identities)) != len(identities):
        raise CatalogueHelpError("catalogue or help identities are duplicated")
    if set(identities) != set(row_by_identity) or len(records) != len(rows):
        raise CatalogueHelpError("catalogue and help identity sets differ")
    return records, row_by_identity


def _validate_help_counts(records):
    counts = Counter(record["semantic_kind"] for record in records)
    if dict(counts) != dict(EXPECTED_KIND_COUNTS):
        raise CatalogueHelpError(f"help semantic-kind closure changed: {dict(counts)!r}")
    parameterized = sum(bool(record["customisation"]["parameters"]) for record in records)
    if (parameterized, len(records) - parameterized) != (170, 100):
        raise CatalogueHelpError("help parameter/no-parameter closure changed")


def validate_help_projection(rows: Sequence[Mapping[str, Any]],
                             help_records: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    records, row_by_identity = _closed_help_projection(rows, help_records)
    for record in records:
        validate_help_record(row_by_identity[(record["component_id"], record["component_version"])], record)
    _validate_help_counts(records)
    return records


def project_help(rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    return validate_help_projection(rows, (build_help_record(row) for row in rows))


__all__ = [
    "CatalogueHelpError", "EXPECTED_KIND_COUNTS", "IMMUTABLE_BOUNDARY", "NO_PARAMETERS",
    "SEMANTIC_KINDS", "build_help_record", "project_help", "validate_help_projection",
    "validate_help_record",
]
