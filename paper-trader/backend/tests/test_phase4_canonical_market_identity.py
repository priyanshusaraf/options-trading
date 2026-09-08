"""Adversarial proof for closed canonical market identity and observations."""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models import Base
from app.ir.validity import valid
from app.market_data.observations import (
    NormalizedMarketObservation, ProviderObservation, RawObservationSegment,
    load_normalized_observation, load_provider_observation, load_raw_segment,
    persist_normalized_observation, persist_provider_observation, persist_raw_segment,
)
from app.market_truth.identity import (
    CanonicalPhysicalInstrument, MarketTruthError, ProviderContract, ProviderEntity,
    ProviderInstrumentAlias, ProviderProduct, load_canonical_instrument,
    load_provider_alias, load_provider_identity, persist_canonical_instrument, persist_provider_alias,
    persist_provider_identity, validate_provider_aliases,
)

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 8, 17, 9, tzinfo=UTC)
A = lambda char: "sha256:" + char * 64


def _facts():
    underlier = CanonicalPhysicalInstrument(
        "strategy-os", "1", "XNSE", "INDEX", "SPOT", "INR", None)
    option = CanonicalPhysicalInstrument(
        "strategy-os", "1", "XNSE", "OPTION", "WEEKLY_OPTION", "INR",
        underlier.address, T0 + dt.timedelta(days=3), "25000", "CALL", "50")
    entity = ProviderEntity("strategy-os", "data-vendor", "Data Vendor Ltd")
    product = ProviderProduct(entity.address, "historical-v1", "vendor-bars", "1")
    contract = ProviderContract(
        "owner-a", product.address, "RESEARCH", ("HISTORICAL",), T0, None, A("e"))
    alias = ProviderInstrumentAlias(
        product.address, "token-1", "NIFTY26AUG25000CE", option.address, "1", T0,
        None, "vendor-bars", A("f"))
    payload = b'{"close":123.5}'
    segment = RawObservationSegment(
        "owner-a", product.address, contract.address, "application/json", "vendor-bar/1",
        payload, T0 + dt.timedelta(minutes=2))
    import hashlib
    raw = ProviderObservation(
        "owner-a", entity.address, product.address, contract.address, alias.address,
        "token-1", "vendor-bar/1", "close", 60, T0, T0 + dt.timedelta(minutes=1),
        T0 + dt.timedelta(minutes=1, seconds=2), T0 + dt.timedelta(minutes=2), "seq-1",
        "original", segment.address, 0, len(payload), hashlib.sha256(payload).hexdigest(),
        valid(1).state)
    normalized = NormalizedMarketObservation(
        option.address, (raw.address,), A("1"), "1", A("2"), A("3"), "1", A("4"),
        "strategy-bar/1", "close", 60, T0, T0 + dt.timedelta(minutes=1),
        T0 + dt.timedelta(minutes=1, seconds=2), T0 + dt.timedelta(minutes=2), valid(123.5))
    return underlier, option, entity, product, contract, alias, segment, raw, normalized


@pytest.fixture
def session():
    engine = sa.create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as value:
        yield value


def _persist_chain(session):
    underlier, option, entity, product, contract, alias, segment, raw, normalized = _facts()
    persist_canonical_instrument(session, underlier)
    persist_canonical_instrument(session, option)
    persist_provider_identity(session, entity, product, contract)
    persist_provider_alias(session, alias)
    persist_raw_segment(session, segment)
    persist_provider_observation(session, raw)
    persist_normalized_observation(session, normalized)
    session.commit()
    return underlier, option, entity, product, contract, alias, segment, raw, normalized


def test_adv_001_fresh_interpreter_reloads_exact_dependency_bytes(tmp_path):
    path = tmp_path / "authority.db"
    engine = sa.create_engine(f"sqlite:///{path}", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as first:
        values = _persist_chain(first)
    engine.dispose()
    program = """
import json, sys, sqlalchemy as sa
from sqlalchemy.orm import Session
from app.market_truth.identity import load_provider_alias
from app.market_data.observations import load_normalized_observation
engine=sa.create_engine('sqlite:///'+sys.argv[1], future=True)
with Session(engine) as session:
    alias=load_provider_alias(session, sys.argv[2])
    normalized=load_normalized_observation(session, sys.argv[3])
print(json.dumps([alias.canonical_bytes.hex(), normalized.canonical_bytes.hex()]))
"""
    result = subprocess.run(
        [sys.executable, "-c", program, str(path), values[5].address, values[8].address],
        check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == [
        values[5].canonical_bytes.hex(), values[8].canonical_bytes.hex()]


def test_adv_002_crash_boundaries_leave_no_authoritative_prefix(tmp_path):
    path = tmp_path / "crash.db"
    engine = sa.create_engine(f"sqlite:///{path}", future=True)
    Base.metadata.create_all(engine)
    values = _facts()
    writes = (
        lambda s: persist_canonical_instrument(s, values[0]),
        lambda s: persist_canonical_instrument(s, values[1]),
        lambda s: persist_provider_identity(s, values[2], values[3], values[4]),
        lambda s: persist_provider_alias(s, values[5]),
        lambda s: persist_raw_segment(s, values[6]),
        lambda s: persist_provider_observation(s, values[7]),
        lambda s: persist_normalized_observation(s, values[8]),
    )
    tables = tuple(name for name in Base.metadata.tables if name.startswith("authority_"))
    for boundary in range(1, len(writes) + 1):
        with Session(engine) as writer:
            for write in writes[:boundary]:
                write(writer)
            writer.rollback()  # process loss before commit
        with engine.connect() as reader:
            assert all(reader.scalar(sa.text(f'SELECT count(*) FROM "{table}"')) == 0
                       for table in tables)


def test_adv_003_last_statement_failure_rolls_back_and_loader_refuses(session):
    values = _facts()
    for instrument in values[:2]:
        persist_canonical_instrument(session, instrument)
    persist_provider_identity(session, values[2], values[3], values[4])
    persist_provider_alias(session, values[5])
    persist_raw_segment(session, values[6])
    persist_provider_observation(session, values[7])
    with pytest.raises(sa.exc.IntegrityError):
        session.execute(sa.text(
            "INSERT INTO authority_normalized_observation_inputs "
            "(normalized_address, ordinal, provider_observation_address) VALUES (:a,-1,:p)"),
            {"a": values[8].address, "p": values[7].address})
    session.rollback()
    with pytest.raises(MarketTruthError, match="absent"):
        load_provider_observation(session, values[7].address)


def test_adv_009_malformed_serialized_state_is_closed_before_authority():
    underlier, *_prefix, segment, raw, _normalized = _facts()
    malformed = (
        b"\xff", b"{}", underlier.canonical_bytes[:-1],
        underlier.canonical_bytes.replace(b'"venue_code":"XNSE"', b'"venue_code":false'),
        underlier.canonical_bytes.replace(b'"currency":"INR"', b'"currency":"INR","extra":1'),
    )
    for payload in malformed:
        with pytest.raises(MarketTruthError):
            CanonicalPhysicalInstrument.from_bytes(payload)
    damaged_range = ProviderObservation(**{
        **raw.__dict__, "raw_byte_offset": len(segment.payload)})
    with pytest.raises(ValueError, match="range"):
        damaged_range.verify_segment(segment)


def test_adv_010_hostile_values_refuse_or_have_distinct_bounded_identity():
    underlier, option, *_ = _facts()
    for strike in ("NaN", "Infinity", "01", "1e999999"):
        with pytest.raises(MarketTruthError):
            CanonicalPhysicalInstrument(
                "strategy-os", "1", "XNSE", "OPTION", "WEEKLY_OPTION", "INR",
                underlier.address, option.expiry, strike, "CALL", "50")
    with pytest.raises(MarketTruthError):
        ProviderEntity("strategy-os", "e" * 257, "legal")
    with pytest.raises(ValueError):
        ProviderObservation(**{**_facts()[7].__dict__, "resolution_seconds": True})
    confusable = ProviderEntity("strategy-os", "vendor", "Latin A")
    distinct = ProviderEntity("strategy-os", "vendor", "Cyrillic А")
    assert confusable.address != distinct.address


def test_adv_016_missing_catalogue_and_provider_dependencies_refuse(session):
    values = _facts()
    for loader, address in (
        (load_canonical_instrument, values[1].address),
        (load_provider_identity, values[4].address),
        (load_provider_alias, values[5].address),
        (load_raw_segment, values[6].address),
    ):
        with pytest.raises(MarketTruthError, match="absent"):
            loader(session, address)


def test_adv_017_identical_facts_converge_and_alias_collision_refuses(session):
    values = _facts()
    persist_canonical_instrument(session, values[0])
    persist_canonical_instrument(session, values[0])
    persist_canonical_instrument(session, values[1])
    persist_provider_identity(session, values[2], values[3], values[4])
    persist_provider_alias(session, values[5])
    collision = ProviderInstrumentAlias(
        values[5].product_address, values[5].provider_token, "other",
        values[5].canonical_instrument_address, "1", T0 + dt.timedelta(hours=1), None,
        values[5].observation_namespace, A("a"))
    with pytest.raises(MarketTruthError, match="overlaps"):
        persist_provider_alias(session, collision)


def test_adv_018_forged_address_and_copied_columns_refuse(session):
    values = _persist_chain(session)
    with pytest.raises((ValueError, MarketTruthError)):
        NormalizedMarketObservation.from_bytes(values[7].canonical_bytes)
    with pytest.raises((ValueError, MarketTruthError)):
        ProviderObservation.from_bytes(values[8].canonical_bytes)
    session.execute(sa.text(
        "INSERT INTO authority_canonical_instruments "
        "(address,schema,canonical_json,venue_code,asset_class,contract_kind,currency,"
        "economic_underlier_address,authority_state,created_at) VALUES "
        "(:a,'canonical-instrument/1',:j,'XNSE','INDEX','SPOT','INR',NULL,'VERIFIED_V2',CURRENT_TIMESTAMP)"),
        {"a": A("9"), "j": values[0].canonical_bytes.decode()})
    with pytest.raises(MarketTruthError, match="copied columns"):
        load_canonical_instrument(session, A("9"))
    session.rollback()
    with pytest.raises(sa.exc.IntegrityError, match="immutable"):
        session.execute(sa.text(
            "UPDATE authority_provider_observations SET field='open' WHERE address=:address"),
            {"address": values[7].address})
    session.rollback()


def test_adv_020_deleted_dependency_refuses_and_replacement_mints_address(session):
    values = _persist_chain(session)
    with pytest.raises(sa.exc.IntegrityError, match="immutable"):
        session.execute(sa.text(
            "DELETE FROM authority_provider_aliases WHERE address=:address"),
            {"address": values[5].address})
    session.rollback()
    replacement = CanonicalPhysicalInstrument(
        "strategy-os", "1", "XNSE", "OPTION", "WEEKLY_OPTION", "INR",
        values[0].address, values[1].expiry, "25100", "CALL", "50")
    assert replacement.address != values[1].address
    assert load_normalized_observation(session, values[8].address) == values[8]


def test_adv_021_independent_sessions_alias_race_has_one_winner(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'race.db'}", future=True)
    Base.metadata.create_all(engine)
    values = _facts()
    with Session(engine) as seed:
        persist_canonical_instrument(seed, values[0]); persist_canonical_instrument(seed, values[1])
        persist_provider_identity(seed, values[2], values[3], values[4]); seed.commit()
    competing = ProviderInstrumentAlias(
        values[5].product_address, values[5].provider_token, "racer",
        values[5].canonical_instrument_address, "1", T0, None,
        values[5].observation_namespace, A("8"))
    first, second = Session(engine), Session(engine)
    try:
        persist_provider_alias(first, values[5]); first.commit()
        with pytest.raises((MarketTruthError, sa.exc.IntegrityError), match="overlap"):
            persist_provider_alias(second, competing)
        second.rollback()
    finally:
        first.close(); second.close()
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT count(*) FROM authority_provider_aliases")) == 1


def test_adv_022_owner_product_contract_underlier_substitutions_refuse(session):
    values = _facts()
    for instrument in values[:2]: persist_canonical_instrument(session, instrument)
    persist_provider_identity(session, values[2], values[3], values[4])
    persist_provider_alias(session, values[5]); persist_raw_segment(session, values[6])
    for changes in (
        {"owner_id": "owner-b"}, {"provider_product_address": A("8")},
        {"provider_contract_address": A("7")},
    ):
        wrong = ProviderObservation(**{**values[7].__dict__, **changes})
        with pytest.raises(MarketTruthError):
            persist_provider_observation(session, wrong)
    persist_provider_observation(session, values[7])
    other = CanonicalPhysicalInstrument("strategy-os", "1", "XBOM", "INDEX", "SPOT", "INR", None)
    persist_canonical_instrument(session, other)
    wrong_normalized = NormalizedMarketObservation(**{
        **values[8].__dict__, "canonical_instrument_address": other.address})
    with pytest.raises(MarketTruthError, match="another instrument"):
        persist_normalized_observation(session, wrong_normalized)


def test_adv_023_timezone_conversion_is_stable_and_causality_refuses():
    values = _facts()
    offset = dt.timezone(dt.timedelta(hours=5, minutes=30))
    shifted = ProviderContract(
        values[4].owner_id, values[4].product_address, values[4].mode,
        values[4].permitted_uses, values[4].effective_from.astimezone(offset), None,
        values[4].evidence_address)
    assert shifted.canonical_bytes == values[4].canonical_bytes
    with pytest.raises(ValueError, match="causal"):
        ProviderObservation(**{
            **values[7].__dict__, "available_at": values[7].event_time - dt.timedelta(seconds=1)})


def test_adv_025_oversized_documents_segments_and_inputs_refuse():
    values = _facts()
    with pytest.raises(MarketTruthError, match="bounded"):
        ProviderEntity("strategy-os", "x" * 257, "legal")
    with pytest.raises(ValueError, match="oversized"):
        RawObservationSegment(
            values[6].owner_id, values[6].product_address, values[6].contract_address,
            values[6].media_type, values[6].raw_schema, b"x" * (4 * 1024 * 1024 + 1),
            values[6].recorded_at)
    with pytest.raises(ValueError, match="bounded"):
        NormalizedMarketObservation(**{
            **values[8].__dict__, "provider_observation_addresses": tuple(A("1") for _ in range(65))})


def test_adv_025_underlier_chain_is_iterative_and_bounded(session):
    instrument = CanonicalPhysicalInstrument(
        "strategy-os", "1", "XNSE", "INDEX", "SPOT", "INR", None)
    persist_canonical_instrument(session, instrument)
    for ordinal in range(64):
        instrument = CanonicalPhysicalInstrument(
            "strategy-os", "1", "XNSE", "FUTURE", "FUTURE", "INR",
            instrument.address, T0 + dt.timedelta(days=ordinal + 1), None, None, "1")
        persist_canonical_instrument(session, instrument)
    assert load_canonical_instrument(session, instrument.address) == instrument

    too_deep = CanonicalPhysicalInstrument(
        "strategy-os", "1", "XNSE", "FUTURE", "FUTURE", "INR",
        instrument.address, T0 + dt.timedelta(days=65), None, None, "1")
    with pytest.raises(MarketTruthError, match="chain exceeds"):
        persist_canonical_instrument(session, too_deep)


def test_adv_026_database_write_exhaustion_rolls_back_and_retry_reloads(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'exhaustion.db'}", future=True)
    Base.metadata.create_all(engine)
    values = _facts()
    failed = False
    def exhaust(_session, _context, _instances):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("injected disk/write exhaustion")
    with Session(engine) as writer:
        sa.event.listen(writer, "before_flush", exhaust)
        with pytest.raises(OSError, match="exhaustion"):
            persist_canonical_instrument(writer, values[0])
        writer.rollback()
        sa.event.remove(writer, "before_flush", exhaust)
    with Session(engine) as retry:
        persist_canonical_instrument(retry, values[0]); retry.commit()
    with Session(engine) as reader:
        assert load_canonical_instrument(reader, values[0].address) == values[0]


def test_adv_027_cancellation_unwinds_and_restart_has_no_partial_chain(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'cancel.db'}", future=True)
    Base.metadata.create_all(engine)
    values = _facts()
    class Cancelled(BaseException):
        pass
    try:
        with Session(engine) as writer:
            with writer.begin():
                persist_canonical_instrument(writer, values[0])
                persist_canonical_instrument(writer, values[1])
                raise Cancelled()
    except Cancelled:
        pass
    engine.dispose()
    reloaded = sa.create_engine(f"sqlite:///{tmp_path / 'cancel.db'}", future=True)
    with Session(reloaded) as reader:
        with pytest.raises(MarketTruthError, match="absent"):
            load_canonical_instrument(reader, values[0].address)


def test_authority_chain_atomic_failure_rolls_back_all_facts(session):
    underlier, option, entity, product, contract, alias, segment, raw, normalized = _facts()
    persist_canonical_instrument(session, underlier)
    persist_canonical_instrument(session, option)
    persist_provider_identity(session, entity, product, contract)
    persist_provider_alias(session, alias)
    persist_raw_segment(session, segment)
    persist_provider_observation(session, raw)
    with pytest.raises(sa.exc.IntegrityError):
        session.execute(sa.text(
            "INSERT INTO authority_normalized_observation_inputs "
            "(normalized_address, ordinal, provider_observation_address) VALUES (:a,-1,:p)"),
            {"a": normalized.address, "p": raw.address})
        session.flush()
    session.rollback()
    assert session.scalar(sa.text("SELECT count(*) FROM authority_canonical_instruments")) == 0
