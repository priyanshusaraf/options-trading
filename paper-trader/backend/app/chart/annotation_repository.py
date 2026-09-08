"""Mutable, owner-scoped presentation rows for research chart annotations."""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.engine import Connection
from sqlalchemy.sql.schema import Table
from sqlalchemy.exc import IntegrityError

from app.chart.annotation_context import MarketContextIdentity
from app.chart.annotation_geometry import decode_applicability, decode_geometry
from app.db.models import ChartContextAnnotation
from app.db.session import SessionLocal

MAX_ANNOTATIONS = 256


class AnnotationNotFound(LookupError):
    pass


class AnnotationConflict(RuntimeError):
    pass


class AnnotationLimit(RuntimeError):
    pass


def validate_annotation_group_ceiling(connection: Connection, table: Table, *,
                                      owner_id: str | None = None,
                                      context_address: str | None = None) -> None:
    statement = select(
        table.c.owner_id, table.c.market_context_address,
    ).group_by(
        table.c.owner_id, table.c.market_context_address,
    ).having(func.count() > MAX_ANNOTATIONS)
    if owner_id is not None and context_address is not None:
        statement = statement.where(table.c.owner_id == owner_id,
                                    table.c.market_context_address == context_address)
    over_limit = connection.execute(statement.limit(1)).first()
    if over_limit is not None:
        raise AnnotationLimit()


def _document(row: ChartContextAnnotation) -> dict:
    geometry = decode_geometry(row.geometry_json)
    applicability = decode_applicability(row.applicability_json)
    if (geometry.address != row.geometry_address
            or applicability.address != row.applicability_address
            or geometry.canonical_bytes.decode() != row.geometry_json
            or applicability.canonical_bytes.decode() != row.applicability_json):
        raise AnnotationNotFound()
    return {
        "annotation_id": row.annotation_id,
        "revision": row.revision,
        "geometry": geometry.to_dict(),
        "geometry_address": row.geometry_address,
        "applicability": applicability.to_dict(),
        "applicability_address": row.applicability_address,
        "created_at": row.created_at.replace(tzinfo=dt.timezone.utc).isoformat(),
        "updated_at": row.updated_at.replace(tzinfo=dt.timezone.utc).isoformat(),
    }


def list_annotations(identity: MarketContextIdentity, *, after: str | None, limit: int) -> dict:
    if not 1 <= limit <= 50:
        raise AnnotationNotFound()
    with SessionLocal() as session:
        validate_annotation_group_ceiling(session.connection(),
            ChartContextAnnotation.__table__, owner_id=identity.owner_id,
            context_address=identity.market_context_address)
        statement = select(ChartContextAnnotation).where(
            ChartContextAnnotation.owner_id == identity.owner_id,
            ChartContextAnnotation.market_context_address == identity.market_context_address,
        )
        if after is not None:
            statement = statement.where(ChartContextAnnotation.annotation_id > after)
        rows = session.scalars(statement.order_by(ChartContextAnnotation.annotation_id).limit(limit + 1)).all()
        page = rows[:limit]
        return {"schema": "strategy-os-chart-annotation-presentation/1",
                "market_context_address": identity.market_context_address,
                "items": [_document(row) for row in page],
                "next_cursor": page[-1].annotation_id if len(rows) > limit else None}


def create_annotation(identity: MarketContextIdentity, geometry_payload: str, applicability_payload: str) -> dict:
    geometry = decode_geometry(geometry_payload)
    applicability = decode_applicability(applicability_payload)
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    row = ChartContextAnnotation(
        owner_id=identity.owner_id, market_context_address=identity.market_context_address,
        annotation_id=str(uuid.uuid4()), revision=1,
        dataset_manifest_address=identity.dataset_manifest_address,
        canonical_instrument_address=identity.canonical_instrument_address,
        timeframe_seconds=identity.timeframe_seconds,
        geometry_address=geometry.address, geometry_json=geometry.canonical_bytes.decode(),
        applicability_address=applicability.address,
        applicability_json=applicability.canonical_bytes.decode(), created_at=now, updated_at=now,
    )
    try:
        with SessionLocal.begin() as session:
            if session.bind.dialect.name == "sqlite":
                session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            elif session.bind.dialect.name == "postgresql":
                session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
                                {"scope": identity.owner_id + identity.market_context_address})
            count = session.scalar(select(func.count()).select_from(ChartContextAnnotation).where(
                ChartContextAnnotation.owner_id == identity.owner_id,
                ChartContextAnnotation.market_context_address == identity.market_context_address,
            ))
            if int(count or 0) >= MAX_ANNOTATIONS:
                raise AnnotationLimit()
            session.add(row)
    except IntegrityError as exc:
        raise AnnotationConflict() from exc
    return _document(row)


def update_annotation(identity: MarketContextIdentity, annotation_id: str, expected_revision: int,
                      geometry_payload: str, applicability_payload: str) -> dict:
    geometry = decode_geometry(geometry_payload)
    applicability = decode_applicability(applicability_payload)
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    with SessionLocal.begin() as session:
        result = session.execute(update(ChartContextAnnotation).where(
            ChartContextAnnotation.owner_id == identity.owner_id,
            ChartContextAnnotation.market_context_address == identity.market_context_address,
            ChartContextAnnotation.annotation_id == annotation_id,
            ChartContextAnnotation.revision == expected_revision,
        ).values(revision=expected_revision + 1, geometry_address=geometry.address,
                 geometry_json=geometry.canonical_bytes.decode(),
                 applicability_address=applicability.address,
                 applicability_json=applicability.canonical_bytes.decode(), updated_at=now))
        if result.rowcount != 1:
            exists = session.scalar(select(ChartContextAnnotation.annotation_id).where(
                ChartContextAnnotation.owner_id == identity.owner_id,
                ChartContextAnnotation.market_context_address == identity.market_context_address,
                ChartContextAnnotation.annotation_id == annotation_id))
            if exists is None:
                raise AnnotationNotFound()
            raise AnnotationConflict()
        row = session.get(ChartContextAnnotation,
                          (identity.owner_id, identity.market_context_address, annotation_id))
        return _document(row)


def delete_annotation(identity: MarketContextIdentity, annotation_id: str,
                      expected_revision: int) -> None:
    with SessionLocal.begin() as session:
        result = session.execute(delete(ChartContextAnnotation).where(
            ChartContextAnnotation.owner_id == identity.owner_id,
            ChartContextAnnotation.market_context_address == identity.market_context_address,
            ChartContextAnnotation.annotation_id == annotation_id,
            ChartContextAnnotation.revision == expected_revision,
        ))
        if result.rowcount != 1:
            exists = session.scalar(select(ChartContextAnnotation.annotation_id).where(
                ChartContextAnnotation.owner_id == identity.owner_id,
                ChartContextAnnotation.market_context_address == identity.market_context_address,
                ChartContextAnnotation.annotation_id == annotation_id))
            if exists is None:
                raise AnnotationNotFound()
            raise AnnotationConflict()
