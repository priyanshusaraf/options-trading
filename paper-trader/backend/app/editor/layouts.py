"""Transactional persistence for sparse IR editor layout overrides."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.db.models import IrGraphLayout, IrGraphLayoutPosition
from app.db.session import SessionLocal


@dataclass(frozen=True)
class Position:
    instance_id: str
    x: float
    y: float


@dataclass(frozen=True)
class Layout:
    graph_identifier: str
    graph_version: int
    revision: int
    positions: tuple[Position, ...]


class LayoutConflict(Exception):
    def __init__(self, current_revision: int):
        super().__init__(f"layout is at revision {current_revision}")
        self.current_revision = current_revision


def _current_revision(graph_identifier: str, graph_version: int) -> int:
    with SessionLocal() as session:
        revision = session.scalar(
            select(IrGraphLayout.revision).where(
                IrGraphLayout.graph_identifier == graph_identifier,
                IrGraphLayout.graph_version == graph_version,
            )
        )
    return int(revision or 0)


def load_layout(
    graph_identifier: str,
    graph_version: int,
    *,
    valid_instance_ids: frozenset[str],
) -> Layout:
    with SessionLocal() as session:
        revision = session.scalar(
            select(IrGraphLayout.revision).where(
                IrGraphLayout.graph_identifier == graph_identifier,
                IrGraphLayout.graph_version == graph_version,
            )
        )
        if revision is None:
            return Layout(graph_identifier, graph_version, 0, ())
        rows = session.scalars(
            select(IrGraphLayoutPosition).where(
                IrGraphLayoutPosition.graph_identifier == graph_identifier,
                IrGraphLayoutPosition.graph_version == graph_version,
            ).order_by(IrGraphLayoutPosition.instance_id)
        )
        positions = tuple(
            Position(row.instance_id, row.x, row.y)
            for row in rows
            if row.instance_id in valid_instance_ids
        )
    return Layout(graph_identifier, graph_version, revision, positions)


def save_layout(
    graph_identifier: str,
    graph_version: int,
    *,
    base_revision: int,
    positions: Iterable[Position],
) -> Layout:
    """Replace a sparse set if and only if its revision is still current."""
    ordered = tuple(sorted(positions, key=lambda item: item.instance_id))
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    try:
        with SessionLocal() as session:
            current = session.get(IrGraphLayout, (graph_identifier, graph_version))
            current_revision = current.revision if current is not None else 0
            if current_revision != base_revision:
                raise LayoutConflict(current_revision)

            next_revision = base_revision + 1
            if current is None:
                session.add(IrGraphLayout(
                    graph_identifier=graph_identifier,
                    graph_version=graph_version,
                    revision=next_revision,
                    updated_at=now,
                ))
                session.flush()
            else:
                claimed = session.execute(
                    update(IrGraphLayout)
                    .where(
                        IrGraphLayout.graph_identifier == graph_identifier,
                        IrGraphLayout.graph_version == graph_version,
                        IrGraphLayout.revision == base_revision,
                    )
                    .values(revision=next_revision, updated_at=now)
                )
                if claimed.rowcount != 1:
                    session.rollback()
                    raise LayoutConflict(
                        _current_revision(graph_identifier, graph_version))

            session.execute(
                delete(IrGraphLayoutPosition).where(
                    IrGraphLayoutPosition.graph_identifier == graph_identifier,
                    IrGraphLayoutPosition.graph_version == graph_version,
                )
            )
            session.add_all([
                IrGraphLayoutPosition(
                    graph_identifier=graph_identifier,
                    graph_version=graph_version,
                    instance_id=position.instance_id,
                    x=position.x,
                    y=position.y,
                )
                for position in ordered
            ])
            session.commit()
    except IntegrityError as exc:
        raise LayoutConflict(
            _current_revision(graph_identifier, graph_version)) from exc

    return Layout(
        graph_identifier,
        graph_version,
        next_revision,
        ordered,
    )
