"""Pure content identities for reusable backtest results.

The dataset address is deliberately stricter than the old final-timestamp key:
it binds ordered candle bytes and the context needed to explain which series
was requested.  Execution identity is built below from a closed manifest.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import base64
import hashlib
import functools
import importlib
import inspect
import json
import math
import re
from pathlib import Path
import struct
import sys
import zlib
from collections.abc import Mapping, Sequence
from typing import Any
from zoneinfo import ZoneInfo

from app.market_data.numeric import NumericIngressError, market_float


DATASET_IDENTITY_SCHEME = "backtest-dataset/1"
EXECUTION_IDENTITY_SCHEME = "backtest-execution/1"
PHASE4_RESULT_IDENTITY_SCHEME = "backtest-phase4-result/1"
LEGACY_V1_RESULT_COMPATIBILITY_SCHEME = "backtest-v1-charge-compatibility/1"
_LEGACY_ACCEPTED_BASE_SHA = "de6faae3e97cf5537338bee2143350e53f70da1c"
_LEGACY_V1_MANIFEST_KEYS = frozenset({
    "legacy_result_cache_address", "legacy_base_sha", "canonical_preimage_b85",
    "charge_schedule_id", "charge_schedule_address", "charge_legs",
    "answer_legs", "total_minor",
})
# Exact canonical preimage captured from the accepted base, compressed only to
# keep the checked-in frozen manifest reviewable. Lookup decompresses and hashes
# these bytes before it admits the one historical answer.
_LEGACY_V1_RESULT_MANIFESTS = ({
    "legacy_result_cache_address":
        "0858bfd935682389979abc90658974c93631f29d4263b751e4aa9d1f74bfc166",
    "legacy_base_sha": _LEGACY_ACCEPTED_BASE_SHA,
    "canonical_preimage_b85": (
        "c-rk6+fv&`^j9=`YNt3^-6i@20WwU9X@RuKbUHgL?UB8MEUCLIgOka>_pC0qq1cc>lS~Ia7-@Cxw>{d!N1O4PP)bxKWt>Y;%HFlrl(|8;>pb$ZckGm9ml~9&a4j^gt3qT8d-o%*mmC>!AtBSqoD~RMRvK`ztgNX}x{@Meg;mw&{iv2O6V1$0AO$E3$tkTYU0E<^MZ+{$%v!?es(z`NoPf62go#q=pDjHFOVyROYNn@_mW(4Av)GgzWU&zCWXHOif`oRp5Oc83PhMX9Y8hEAp)6L{g#d1)ixvXPi71gRzC^(-3AL<vlOcd1g6iP2HrmaBcIxJ=P_Sc5rn4z%dsoW_9~H`?VX~lk!6s^0?Zl^0vb2B!_tTm|6-;JOYC2=JG3fr$DVlD4bV`rjULf=R^Fw^bUwZgk_h@d`R^GgNhmZK%BaB}i9GaE(@33}@=(r_19!QJ_qWukum$6!CbS6qfQK5=yI)!UW5r|wnFXE7q<yHUW1TD_g=t>nDg*OE(wZSNn)g?%VFVQx76H%X#b)vqZIYA56*+!IzFpm#E^~f_Q3R1BRhh$+MF_H$rV_uJ3(jsX#t7+OSwqfQ`;1Hh&fy2Y39yy`G)a)94SQJ}XhOW=Kn>#GYGem4z>g#eFPT*%r9ONX-!^B4%*Zzb^`@Iiu7&Yrc=b<)TA#P#svBYH_2?EazosRu?<_$lO(;$w)3*+4R9B(i$1Q${#^F0??I^F}k;kq6`?j}y`Mt;Za(<&Pu7UARtdZ5*h*PW2tvLU_cIq$o(|Lq9z2K(QGcXu-UM_F`R$YANW<MGAW-of7c=Tv&a!sdRlOWJMhd8fE-Q0D;#y#uE+=<`nT#5;xm0B?jOa0B83WKotZcZ$9%``-lk7n*dn1>R%D+X)n`toR(&-_!-q9sQT~B4HkooTOfmf*UV8`tfr|{~dMo<L8e4JMZXo*N@{Uh<%8H^oHM_JNj?b(ck3~lM_rc1$yl~GEEu56wM<y<{6NP1YR0PIpH4R0I`Rx!_eh!%2<?eFU>L%XDs1P;wGL)QhUdSxj8J8O#w*o&yP0CHAp%WWuwiCgC2yulCWCxh!JI>X#WDPYati*ZrKzC($iFnnK`a>2!bL9lfoLx9(*{*yM%>dXpi?U-k$B9yxu!E2WNX1=H@SaE!uO?Mo|fMB{jY*SPBKM9UkvlCDV;$#c0BmIn^}rWi0`_^G4m0?@mdTQS|Rd=miy}IpSmsBUpn(P$Oh_1#oE=cfC(LU*86=&fXpzo*thd;Bfoq0Y)%F7YnNfEvo|B^IbHH>J4H2kjaLFB}(Jr%A5}W_(<cpPima*@wR39v*2ZT93Nf0U$ey^%gPchL~n~x$I7~BKy^@esk^R{^Yv9aKg8ntZmUimh}Cf!;XCVM+Q=;`eVg!pkh=SO<6rLg;u30I=|6y%@B~^vGH%_^Rr&Sl$-x_x<^1^M_rtUGRIXQKSGuQ26ZPpQItnw^jBf_0`y$v#^wqt((g>I=MLAJx`efCtX63>fURf`(B&nv*%6hynTXk{446kHkCOu{soiarSN~_{JR0ktlrKu7hP?0Fuu}jug=Puv^Q=t2)Q8(4G+u@VA1gbP_>~@ly-A+5Q(Tmy;ZU<4ziIm_-8C82hk5@t?aLpvjfnHOF1<V*Npq%Kby&IsX5J+zC68#(eyS}X-_0d_yp`A8$PB!S3qziP3+W0vYIZ5t?#K9YEs1hThn9~fz#<3N-X#%H5X_;*_+uDU}+9nZ0l=k{|@;{8>$hpIeEg7zXno!3)@LQ4OoX#);g_%@t6wM9SuKq)0FsQ;C#<zZLMGTz&2fMbg>n*FA7L`(4zhiH(9d#XIH|E^dGp}F0DKK+Hv6_wc6VrAv7t#zzF`iML>~b6BTOJBml)nVsU!h}8O(s~RJ_{MKrBIhNmjKjEgg3^<+V_Cp^F_B`VV$b3`e<;8N%gEMIeG-Tguue+1Q_>(7>8w3Xluiez1UJf)|krj(#-8uA?o^`ubDf~oK@Ax4Ay#gCyBg-2WcJ?61zDIh@Uxr62x9aG6z4V35yxh@v*N@coKL{7C_7+k3|R@henthtJ*LnUN2z%SbCVC8$mf_1(U$(6_c~3HoF1tYaDWhX+hf@dcrc)6<@49tmL=_&<}L(+r1-~rHN^|WM$H{3ld!2I3@pAxj|NQOnmeXg0M$k#!X$c7y-~+vl`a^I|276j0dw~<L4Ff{s&<@|3v"
    ),
    "charge_schedule_id": "zerodha_charges_v1",
    "charge_schedule_address":
        "sha256:e45ffe58cfceba12a08a4a64990c2863bb1fdb3295c0d467f85fa2a13c19d6ad",
    "charge_legs": ({"segment": "NFO", "side": "BUY", "price": "172.8", "qty": 75},),
    "answer_legs": ({
        "segment": "NFO", "side": "BUY", "price_minor": 17_280, "qty": 75,
        "brokerage_minor": 2_000, "stt_ctt_minor": 0,
        "exchange_txn_minor": 454, "sebi_minor": 1, "stamp_minor": 39,
        "dp_minor": 0, "gst_minor": 442, "total_minor": 2_936,
    },),
    "total_minor": 2_936,
},)
_IST = ZoneInfo("Asia/Kolkata")
_UTC = dt.timezone.utc
_EPOCH = dt.datetime(1970, 1, 1, tzinfo=_UTC)
_CANDLE_FLOATS = ("open", "high", "low", "close", "volume")
_PHASE4_ADDRESS = re.compile(r"sha256:[0-9a-f]{64}")
# The exact field sets `ordered_dataset_address` resolves its source context
# from.  A store that persists a dataset must record the SAME resolution, or a
# reloaded dataset re-addresses differently and is (correctly) refused.
PROVIDER_IDENTITY_FIELDS = ("key", "name", "provider")
INSTRUMENT_IDENTITY_FIELDS = ("key", "spot_exchange", "spot_symbol")


def _stable(value: Any) -> Any:
    """A deterministic JSON value, preserving distinctions relevant to identity."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"identity metadata contains non-finite float {value!r}")
        return {"__float_hex__": value.hex()}
    if isinstance(value, dt.datetime):
        return {"__timestamp_us__": _timestamp_us(value)}
    if isinstance(value, dt.date):
        return {"__date__": value.isoformat()}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _stable(dataclasses.asdict(value))
    if isinstance(value, Mapping):
        return {str(k): _stable(v) for k, v in sorted(value.items(), key=lambda x: str(x[0]))}
    if isinstance(value, (list, tuple)):
        return [_stable(v) for v in value]
    if isinstance(value, (set, frozenset)):
        items = [_stable(v) for v in value]
        return sorted(items, key=lambda item: _canonical_json(item))
    raise ValueError(f"identity metadata cannot encode {type(value).__name__}")


def _canonical_json(value: Any) -> str:
    return json.dumps(_stable(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def _timestamp_us(value: Any) -> int:
    if not isinstance(value, dt.datetime):
        raise ValueError(f"candle timestamp must be datetime, not {type(value).__name__}")
    aware = value.replace(tzinfo=_IST) if value.tzinfo is None else value.astimezone(_UTC)
    utc = aware.astimezone(_UTC)
    delta = utc - _EPOCH
    return ((delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds)


def _field(candle: Any, name: str) -> Any:
    if isinstance(candle, Mapping):
        return candle.get(name)
    return getattr(candle, name, None)


def _named_identity(value: Any, *, fields: Sequence[str]) -> Any:
    if isinstance(value, (str, int, float, bool, Mapping)) or value is None:
        return value
    explicit = getattr(value, "cache_identity", None)
    if callable(explicit):
        explicit = explicit()
    if explicit is not None:
        return explicit
    found = {name: getattr(value, name) for name in fields if hasattr(value, name)}
    found["type"] = f"{type(value).__module__}.{type(value).__qualname__}"
    return found


def source_identity(value: Any, *, fields: Sequence[str]) -> Any:
    """Public form of the source-context resolution used by the dataset address."""
    return _named_identity(value, fields=fields)


def ordered_dataset_address(candles: Sequence[Any], *, provider: Any,
                            instrument: Any, interval: str,
                            requested_window: Any,
                            effective_window: Any) -> str:
    """Return SHA-256 for the exact ordered OHLCV dataset and its source context.

    Naive timestamps are the project's native naive-IST clock.  Aware timestamps
    are normalized to the same instant, at microsecond precision.  Floats are
    packed as IEEE-754 binary64, avoiding rounded display serialization.
    """
    metadata = {
        "scheme": DATASET_IDENTITY_SCHEME,
        "provider": _named_identity(provider, fields=PROVIDER_IDENTITY_FIELDS),
        "instrument": _named_identity(
            instrument, fields=INSTRUMENT_IDENTITY_FIELDS),
        "interval": interval,
        "requested_window": requested_window,
        "effective_window": effective_window,
    }
    digest = hashlib.sha256()
    encoded = _canonical_json(metadata).encode("utf-8")
    digest.update(struct.pack(">I", len(encoded)))
    digest.update(encoded)
    digest.update(struct.pack(">Q", len(candles)))

    for index, candle in enumerate(candles):
        stamp = _timestamp_us(_field(candle, "ts"))
        values = []
        for name in _CANDLE_FLOATS:
            raw = _field(candle, name)
            try:
                number = market_float(raw, field=f"candle {index} {name}")
            except NumericIngressError:
                raise ValueError(f"candle {index} {name} must be a finite number") from None
            values.append(number)
        digest.update(struct.pack(">q5d", stamp, *values))
    return digest.hexdigest()


def _module_bytes(module: Any) -> bytes | None:
    """Read source bytes afresh so an in-process deploy cannot reuse old code."""
    path = getattr(module, "__file__", None)
    if not path:
        return None
    source = Path(path)
    if source.suffix in {".pyc", ".pyo"}:
        source = source.with_suffix(".py")
    try:
        return source.read_bytes()
    except OSError:
        return None


def _callable_identity(fn: Any) -> dict[str, Any] | None:
    target = getattr(fn, "__func__", fn)
    try:
        source = inspect.getsource(target)
    except (OSError, TypeError):
        return None
    return {
        "module": getattr(target, "__module__", ""),
        "qualname": getattr(target, "__qualname__", ""),
        "source": source,
    }


def transitive_module_source_digest(*, modules: Sequence[Any],
                                    implementation_maps: Sequence[Mapping] = ()) \
        -> str | None:
    """Hash executable module bytes plus dynamically selected implementations.

    A missing source is a safe cache miss, represented by ``None``.  Falling back
    to a module name would be a plausible-looking identity that survives a code
    change, which is the unsafe direction for a result cache.
    """
    all_modules = {getattr(module, "__name__", ""): module for module in modules}
    implementation_rows = []
    for map_index, impl_map in enumerate(implementation_maps):
        for address, fn in sorted(impl_map.items(), key=lambda item: str(item[0])):
            manifest = _callable_identity(fn)
            module_name = getattr(fn, "__module__", "")
            module = sys.modules.get(module_name)
            if manifest is None or module is None:
                return None
            all_modules[module_name] = module
            implementation_rows.append({
                "map": map_index, "address": str(address), "callable": manifest,
            })

    digest = hashlib.sha256()
    digest.update(b"backtest-module-source/1\0")
    for name, module in sorted(all_modules.items()):
        name = getattr(module, "__name__", "")
        source = _module_bytes(module)
        if not name or source is None:
            return None
        name_bytes = name.encode("utf-8")
        digest.update(struct.pack(">I", len(name_bytes)))
        digest.update(name_bytes)
        digest.update(struct.pack(">Q", len(source)))
        digest.update(source)

    encoded = _canonical_json(implementation_rows).encode()
    digest.update(struct.pack(">I", len(encoded)))
    digest.update(encoded)
    return digest.hexdigest()


def _execution_modules(strategy: Any) -> tuple[Any, ...]:
    names = {
        "app.backtest.engine",
        "app.backtest.metrics",
        "app.backtest.premium",
        "app.backtest.ratchet",
        "app.engine.charges",
        "app.engine.decision_kernel",
        "app.engine.equity_entry",
        "app.engine.event_risk",
        "app.engine.exit_monitor",
        "app.market_data.candles",
        "app.options.pricing",
        "app.strategy.replay_decisions",
        type(strategy).__module__,
    }
    try:
        return tuple(sys.modules.get(name) or importlib.import_module(name)
                     for name in sorted(names))
    except (ImportError, ValueError):
        return ()


def execution_result_address(*, dataset_address: str, instrument: Any,
                             strategy: Any, parameters: Mapping[str, Any],
                             capital: float, window: Any, slippage_pct: float,
                             admission_address: str, phase4_binding: Mapping[str, Any] | None = None,
                             strategy_key: str | None = None,
                             strategy_version: str | None = None,
                             graph_address: str | None = None,
                             attribution_state: str | None = None,
                             charge_schedule_id: str | None = None,
                             implementation_maps: Sequence[Mapping] = ()) -> str | None:
    """Return the full address of one deterministic backtest computation.

    The manifest deliberately reads mutable policy globals at call time.  A rate,
    event rule, premium assumption, exit policy, or selected implementation change
    must make the next run cold even when candle data and timestamps are unchanged.
    """
    from app.backtest import engine, premium
    from app.engine import charges, event_risk

    charge_schedule_id = (
        charge_schedule_id or charges.CORRECTED_RESEARCH_CHARGE_SCHEDULE
    )

    version = getattr(strategy, "version", None)
    if not version or str(version).lower() == "unknown":
        return None
    if len(dataset_address) != 64 or any(c not in "0123456789abcdefABCDEF"
                                         for c in dataset_address):
        return None
    try:
        admission_address = require_content_address(admission_address)
    except ValueError:
        return None
    runtime_key = getattr(strategy, "key", "")
    if strategy_key is None and not str(runtime_key).startswith("ir."):
        strategy_key = str(runtime_key)
        strategy_version = str(version)
        graph_address = None
        attribution_state = "NON_GRAPH"
    try:
        from app.strategy.admission import require_attribution_tuple
        require_attribution_tuple(
            strategy_key=strategy_key, strategy_version=strategy_version,
            graph_address=graph_address, admission_address=admission_address,
            attribution_state=attribution_state)
    except ValueError:
        return None
    if attribution_state == "VERIFIED_GRAPH" and (
            runtime_key != strategy_key or str(version) != graph_address
            or getattr(strategy, "graph_version_label", None) != strategy_version):
        return None
    if not math.isfinite(float(capital)) or not math.isfinite(float(slippage_pct)):
        return None
    maps = list(implementation_maps)
    strategy_implementations = getattr(strategy, "implementations", None)
    if isinstance(strategy_implementations, Mapping) and not any(
            strategy_implementations is item for item in maps):
        maps.append(strategy_implementations)
    modules = _execution_modules(strategy)
    if not modules:
        return None
    source_address = transitive_module_source_digest(
        modules=modules, implementation_maps=maps)
    if source_address is None:
        return None

    resolved_premium = dict(premium.DEFAULT_PREMIUM_PARAMS)
    resolved_premium.update({
        key: value for key, value in parameters.items()
        if key in resolved_premium
    })
    try:
        charge_segment = engine.backtest_charge_segment(instrument)
        charge_document = charges.charge_schedule_document(charge_schedule_id)
    except charges.ChargeScheduleRefusal:
        return None
    segment_document = charge_document["segments"].get(charge_segment)
    if segment_document is None:
        return None
    charge_binding = {
        "schedule_id": charge_schedule_id,
        "schedule_address": charge_document["address"],
        "segment": charge_segment,
        "product_class": segment_document.get("product_class", "legacy_unspecified_v1"),
        "turnover_unit": segment_document.get("turnover_unit", "legacy_float_price_times_quantity"),
        "sides": segment_document.get("supported_sides", ["BUY", "SELL"]),
        "rounding_policy": charge_document["rounding_policy"],
        "application_mode": charge_document.get(
            "application_mode", "legacy_historical_reconstruction"
        ),
    }
    manifest = {
        "scheme": EXECUTION_IDENTITY_SCHEME,
        "dataset_address": dataset_address.lower(),
        "admission_address": admission_address,
        "instrument": _named_identity(
            instrument,
            fields=("key", "name", "segment", "lot_size", "strike_step", "has_options"),
        ),
        "strategy": {
            "runtime_key": runtime_key,
            "runtime_content_version": str(version),
            "source_key": strategy_key,
            "source_version": strategy_version,
            "graph_address": graph_address,
            "attribution_state": attribution_state,
            "default_params": getattr(strategy, "default_params", {}),
            "declared_warmup": getattr(strategy, "declared_warmup", None),
            "risk_model": getattr(strategy, "risk_model", None),
        },
        "parameters": parameters,
        "capital": capital,
        "window": window,
        "slippage_pct": slippage_pct,
        "source_address": source_address,
        "charge_schedule": charge_binding,
        "backtest_segment_map": engine._BACKTEST_SEGMENT,
        "spot_charge_segment": charge_segment,
        "event_rules": event_risk.DEFAULT_RULES,
        "backtest_exit_policy": engine.BACKTEST_EXIT_POLICY,
        "premium_model": {
            "parameters": resolved_premium,
            "risk_free_rate": premium.RISK_FREE_RATE,
            "rv_window_days": premium.RV_WINDOW_DAYS,
            "iv_floor": premium.IV_FLOOR,
            "iv_ceil": premium.IV_CEIL,
            "expiry_floor_years": premium.EXPIRY_FLOOR_YEARS,
            "min_entry_premium": premium.MIN_ENTRY_PREMIUM,
            "seconds_per_year": premium.SECONDS_PER_YEAR,
        },
    }
    if phase4_binding is not None:
        try:
            phase4_binding = phase4_binding_payload(phase4_binding)
        except ValueError:
            return None
        if not phase4_binding["owner_id"]:
            return None
        manifest["phase4"] = {"scheme": PHASE4_RESULT_IDENTITY_SCHEME,
                              **dict(phase4_binding)}
    return hashlib.sha256(_canonical_json(manifest).encode("utf-8")).hexdigest()


def _validated_legacy_v1_result_manifests(
        manifests: Sequence[Mapping[str, Any]] = _LEGACY_V1_RESULT_MANIFESTS,
) -> dict[str, dict[str, Any]]:
    """Build the frozen one-to-one compatibility registry or refuse all of it."""
    from app.engine import charges

    if (not isinstance(manifests, Sequence) or isinstance(manifests, (str, bytes))
            or not manifests):
        raise ValueError("legacy manifest registry is incomplete")
    registry: dict[str, dict[str, Any]] = {}
    for manifest in manifests:
        if not isinstance(manifest, Mapping) or set(manifest) != _LEGACY_V1_MANIFEST_KEYS:
            raise ValueError("legacy manifest has an incomplete identity")
        identity = manifest["legacy_result_cache_address"]
        if (not isinstance(identity, str) or len(identity) != 64
                or any(char not in "0123456789abcdef" for char in identity)):
            raise ValueError("legacy manifest identity must be lower-case sha256")
        if identity in registry:
            raise ValueError("duplicate legacy result/cache identity")
        if manifest["legacy_base_sha"] != _LEGACY_ACCEPTED_BASE_SHA:
            raise ValueError("legacy manifest base does not match the accepted base")
        encoded_preimage = manifest["canonical_preimage_b85"]
        try:
            preimage = zlib.decompress(base64.b85decode(encoded_preimage.encode("ascii")))
            preimage_document = json.loads(preimage)
        except Exception as exc:
            raise ValueError("legacy manifest preimage is invalid") from exc
        if (not isinstance(preimage_document, dict)
                or preimage_document.get("scheme") != "backtest-execution/1"
                or hashlib.sha256(preimage).hexdigest() != identity):
            raise ValueError("legacy manifest preimage does not produce its identity")
        if manifest["charge_schedule_id"] != charges.ZERODHA_CHARGES_V1:
            raise ValueError("legacy manifest schedule is not frozen v1")
        if manifest["charge_schedule_address"] != charges.charge_schedule_address(
                charges.ZERODHA_CHARGES_V1):
            raise ValueError("legacy manifest schedule address does not match")
        charge_legs = manifest["charge_legs"]
        if (not isinstance(charge_legs, tuple) or not charge_legs
                or len(charge_legs) > 1_000):
            raise ValueError("legacy manifest charge legs are incomplete")
        resolved_legs = []
        for leg in charge_legs:
            if not isinstance(leg, Mapping) or set(leg) != {"segment", "side", "price", "qty"}:
                raise ValueError("legacy manifest charge leg has an incomplete identity")
            answer = charges.compute_charges(
                leg["segment"], leg["side"], leg["price"], leg["qty"],
                schedule_id=charges.ZERODHA_CHARGES_V1,
            )
            components = {
                f"{component}_minor": charges.monetary_minor(answer[component])
                for component in charges.CHARGE_COMPONENTS
            }
            resolved_legs.append({
                "segment": answer["segment"],
                "side": answer["side"],
                "price_minor": charges.monetary_minor(leg["price"]),
                "qty": leg["qty"],
                **components,
                "total_minor": charges.monetary_minor(answer["total"]),
            })
        if (tuple(resolved_legs) != manifest["answer_legs"]
                or sum(leg["total_minor"] for leg in resolved_legs)
                != manifest["total_minor"]):
            raise ValueError("legacy manifest frozen answer does not match v1")
        registry[identity] = {
            "legacy_result_cache_address": identity,
            "legacy_base_sha": manifest["legacy_base_sha"],
            "charge_schedule_id": manifest["charge_schedule_id"],
            "charge_schedule_address": manifest["charge_schedule_address"],
            "legs": list(manifest["answer_legs"]),
            "total_minor": manifest["total_minor"],
        }
    return registry


@functools.lru_cache(maxsize=1)
def _frozen_legacy_v1_result_manifests() -> dict[str, dict[str, Any]]:
    return _validated_legacy_v1_result_manifests()


def legacy_v1_result_compatibility_receipt(
        legacy_result_cache_address: str) -> dict[str, Any]:
    """Return the sole exact answer for one checked-in historical preimage."""
    registry = _frozen_legacy_v1_result_manifests()
    try:
        frozen = registry[legacy_result_cache_address]
    except (KeyError, TypeError):
        raise ValueError("unknown legacy result/cache identity") from None
    payload = {
        "scheme": LEGACY_V1_RESULT_COMPATIBILITY_SCHEME,
        **frozen,
    }
    return {
        "compatibility_address": "sha256:" + hashlib.sha256(
            _canonical_json(payload).encode("utf-8")
        ).hexdigest(),
        **payload,
    }


def is_legacy_result_compatibility_alias(value: object) -> bool:
    """Identify both old keys and their compatibility receipts at current boundaries."""
    if not isinstance(value, str):
        return False
    raw = value[7:] if value.startswith("sha256:") else value
    for identity in _frozen_legacy_v1_result_manifests():
        receipt = legacy_v1_result_compatibility_receipt(identity)
        if raw in {identity, receipt["compatibility_address"][7:]}:
            return True
    return False


def phase4_binding_payload(binding: Mapping[str, Any]) -> dict[str, Any]:
    required = {"owner_id", "authored_ir_address", "registry_snapshot_address", "resolved_graph_address",
                "implementation_closure_address", "declaration_addresses", "plan_address",
                "capability_assessment_address", "dataset_manifest_address",
                "market_truth_snapshot_address", "evaluation_policy_address"}
    if set(binding) != required or not isinstance(binding["owner_id"], str) or not binding["owner_id"]:
        raise ValueError("incomplete Phase 4 binding")
    addresses = required - {"owner_id", "declaration_addresses"}
    if any(not isinstance(binding[key], str) or not _PHASE4_ADDRESS.fullmatch(binding[key])
           for key in addresses):
        raise ValueError("malformed Phase 4 binding address")
    declarations = binding["declaration_addresses"]
    if (not isinstance(declarations, tuple) or not declarations
            or tuple(sorted(declarations)) != declarations or len(set(declarations)) != len(declarations)
            or any(not isinstance(value, str) or not _PHASE4_ADDRESS.fullmatch(value)
                   for value in declarations)):
        raise ValueError("malformed Phase 4 declarations")
    return {key: binding[key] for key in sorted(required)}


def require_content_address(value: object) -> str:
    """Validate the canonical lower-case sha256 provenance address."""
    if not isinstance(value, str) or not _PHASE4_ADDRESS.fullmatch(value):
        raise ValueError("malformed content address")
    return value


__all__ = ["DATASET_IDENTITY_SCHEME", "EXECUTION_IDENTITY_SCHEME",
           "LEGACY_V1_RESULT_COMPATIBILITY_SCHEME", "PHASE4_RESULT_IDENTITY_SCHEME",
           "PROVIDER_IDENTITY_FIELDS", "INSTRUMENT_IDENTITY_FIELDS",
           "source_identity", "ordered_dataset_address",
           "transitive_module_source_digest", "execution_result_address",
           "legacy_v1_result_compatibility_receipt", "phase4_binding_payload",
           "is_legacy_result_compatibility_alias",
           "require_content_address"]
