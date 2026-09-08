from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select, update

from app.chart.annotation_context import MarketContextIdentity
from app.chart.annotation_geometry import CausalApplicability, Level, Zone
from app.chart.annotation_repository import (
    AnnotationConflict, AnnotationLimit, AnnotationNotFound, create_annotation, delete_annotation,
    list_annotations, update_annotation,
)
from app.db.models import ChartContextAnnotation, Organization
from app.db.session import SessionLocal, init_db

UTC = dt.timezone.utc


def address(digit: str) -> str:
    return "sha256:" + digit * 64


def identity(owner: str = "owner.a") -> MarketContextIdentity:
    return MarketContextIdentity(owner, address("a"),
        {"project_id": "project.a", "identifier": "strategy.a", "version": 1,
         "content_address": address("f")}, address("b"), address("c"),
        "XNSE · EQUITY · SPOT", 60, dt.datetime(2026, 1, 1, 10, 0, tzinfo=UTC))


def values(kind: str = "level") -> tuple[str, str]:
    geometry = Level("100") if kind == "level" else Zone("99", "101")
    applicability = CausalApplicability(
        dt.datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
        dt.datetime(2026, 1, 1, 9, 1, tzinfo=UTC),
        dt.datetime(2026, 1, 1, 9, 2, tzinfo=UTC),
    )
    return geometry.canonical_bytes.decode(), applicability.canonical_bytes.decode()


@pytest.fixture(autouse=True)
def database():
    init_db(reset=True)
    with SessionLocal.begin() as session:
        session.add_all([Organization(organization_id="owner.a", name="A"),
                         Organization(organization_id="owner.b", name="B")])


def test_create_list_update_delete_and_revision_conflict():
    geometry, applicability = values()
    created = create_annotation(identity(), geometry, applicability)
    assert created["revision"] == 1
    assert list_annotations(identity(), after=None, limit=50)["items"] == [created]
    changed_geometry, changed_applicability = values("zone")
    changed = update_annotation(identity(), created["annotation_id"], 1,
                                changed_geometry, changed_applicability)
    assert changed["revision"] == 2
    with pytest.raises(AnnotationConflict):
        update_annotation(identity(), created["annotation_id"], 1, geometry, applicability)
    delete_annotation(identity(), created["annotation_id"], 2)
    assert list_annotations(identity(), after=None, limit=50)["items"] == []


def test_foreign_owner_and_forged_context_are_indistinguishable_and_do_not_mutate():
    geometry, applicability = values()
    created = create_annotation(identity(), geometry, applicability)
    foreign = identity("owner.b")
    forged = MarketContextIdentity(**{**{
        name: getattr(identity(), name) for name in identity().__dataclass_fields__},
        "dataset_manifest_address": address("d")})
    for candidate in (foreign, forged):
        with pytest.raises(AnnotationNotFound):
            update_annotation(candidate, created["annotation_id"], 1, geometry, applicability)
        with pytest.raises(AnnotationNotFound):
            delete_annotation(candidate, created["annotation_id"], 1)
    assert list_annotations(identity(), after=None, limit=50)["items"][0]["revision"] == 1


def test_corrupt_persisted_bytes_refuse_on_read():
    geometry, applicability = values()
    created = create_annotation(identity(), geometry, applicability)
    with SessionLocal.begin() as session:
        session.execute(update(ChartContextAnnotation).where(
            ChartContextAnnotation.annotation_id == created["annotation_id"]
        ).values(geometry_address=address("e")))
    with pytest.raises(AnnotationNotFound):
        list_annotations(identity(), after=None, limit=50)


def test_failed_update_rolls_back_original_row():
    geometry, applicability = values()
    created = create_annotation(identity(), geometry, applicability)
    with pytest.raises(AnnotationConflict):
        update_annotation(identity(), created["annotation_id"], 9, *values("zone"))
    with SessionLocal() as session:
        row = session.scalar(select(ChartContextAnnotation).where(
            ChartContextAnnotation.annotation_id == created["annotation_id"]))
        assert (row.revision, row.geometry_json) == (1, geometry)


def test_exact_256_drawing_ceiling_refuses_257_without_side_effect():
    geometry, applicability = values()
    first = create_annotation(identity(), geometry, applicability)
    with SessionLocal.begin() as session:
        source = session.get(ChartContextAnnotation,
            (identity().owner_id, identity().market_context_address, first["annotation_id"]))
        for index in range(2, 257):
            session.add(ChartContextAnnotation(
                owner_id=source.owner_id, market_context_address=source.market_context_address,
                annotation_id=f"00000000-0000-0000-0000-{index:012d}", revision=1,
                dataset_manifest_address=source.dataset_manifest_address,
                canonical_instrument_address=source.canonical_instrument_address,
                timeframe_seconds=source.timeframe_seconds,
                geometry_address=source.geometry_address, geometry_json=source.geometry_json,
                applicability_address=source.applicability_address,
                applicability_json=source.applicability_json,
                created_at=source.created_at, updated_at=source.updated_at))
    with pytest.raises(AnnotationLimit):
        create_annotation(identity(), geometry, applicability)
    with SessionLocal() as session:
        assert session.query(ChartContextAnnotation).count() == 256


def test_list_refuses_an_otherwise_valid_persisted_group_of_257_without_mutation():
    geometry, applicability = values()
    first = create_annotation(identity(), geometry, applicability)
    healthy = create_annotation(identity("owner.b"), geometry, applicability)
    with SessionLocal.begin() as session:
        source = session.get(ChartContextAnnotation,
            (identity().owner_id, identity().market_context_address, first["annotation_id"]))
        for index in range(2, 258):
            session.add(ChartContextAnnotation(
                owner_id=source.owner_id, market_context_address=source.market_context_address,
                annotation_id=f"00000000-0000-0000-0000-{index:012d}", revision=1,
                dataset_manifest_address=source.dataset_manifest_address,
                canonical_instrument_address=source.canonical_instrument_address,
                timeframe_seconds=source.timeframe_seconds,
                geometry_address=source.geometry_address, geometry_json=source.geometry_json,
                applicability_address=source.applicability_address,
                applicability_json=source.applicability_json,
                created_at=source.created_at, updated_at=source.updated_at))
    with pytest.raises(AnnotationLimit):
        list_annotations(identity(), after=None, limit=50)
    assert list_annotations(identity("owner.b"), after=None, limit=50)["items"] == [healthy]
    with SessionLocal() as session:
        assert session.query(ChartContextAnnotation).count() == 258
