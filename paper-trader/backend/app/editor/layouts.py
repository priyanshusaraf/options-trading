"""Transactional persistence for sparse IR editor layout overrides."""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    IrGraphLayout,
    IrGraphLayoutGroup,
    IrGraphLayoutGroupMember,
    IrGraphLayoutPosition,
)
from app.db.session import SessionLocal


@dataclass(frozen=True)
class Position:
    instance_id: str
    x: float
    y: float


@dataclass(frozen=True)
class GroupFrame:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class VisualGroup:
    identifier: str
    display_name: str
    frame: GroupFrame
    collapsed: bool
    members: tuple[str, ...]


@dataclass(frozen=True)
class Layout:
    graph_identifier: str
    graph_version: int
    revision: int
    positions: tuple[Position, ...]
    groups: tuple[VisualGroup, ...] = ()


class LayoutConflict(Exception):
    def __init__(self, current_revision: int):
        super().__init__(f"layout is at revision {current_revision}")
        self.current_revision = current_revision


class LayoutRejected(Exception):
    pass


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
        return load_layout_in_session(
            session, graph_identifier, graph_version, valid_instance_ids
        )


def load_layout_in_session(
    session: Session,
    graph_identifier: str,
    graph_version: int,
    valid_instance_ids: frozenset[str],
) -> Layout:
    head = session.get(IrGraphLayout, (graph_identifier, graph_version))
    if head is None:
        return Layout(graph_identifier, graph_version, 0, ())
    position_rows = session.scalars(
        select(IrGraphLayoutPosition).where(
            IrGraphLayoutPosition.graph_identifier == graph_identifier,
            IrGraphLayoutPosition.graph_version == graph_version,
        ).order_by(IrGraphLayoutPosition.instance_id)
    ).all()
    group_rows = session.scalars(
        select(IrGraphLayoutGroup).where(
            IrGraphLayoutGroup.graph_identifier == graph_identifier,
            IrGraphLayoutGroup.graph_version == graph_version,
        ).order_by(IrGraphLayoutGroup.identifier)
    ).all()
    member_rows = session.scalars(
        select(IrGraphLayoutGroupMember).where(
            IrGraphLayoutGroupMember.graph_identifier == graph_identifier,
            IrGraphLayoutGroupMember.graph_version == graph_version,
        ).order_by(
            IrGraphLayoutGroupMember.group_identifier,
            IrGraphLayoutGroupMember.instance_id,
        )
    ).all()
    members: dict[str, list[str]] = {}
    for row in member_rows:
        if row.instance_id not in valid_instance_ids:
            raise LayoutRejected(
                f"visual group {row.group_identifier!r} contains unknown or derived "
                f"instance {row.instance_id!r}"
            )
        members.setdefault(row.group_identifier, []).append(row.instance_id)
    return Layout(
        graph_identifier,
        graph_version,
        head.revision,
        tuple(
            Position(row.instance_id, row.x, row.y)
            for row in position_rows
            if row.instance_id in valid_instance_ids
        ),
        tuple(
            VisualGroup(
                row.identifier,
                row.display_name,
                GroupFrame(row.x, row.y, row.width, row.height),
                row.collapsed,
                tuple(members.get(row.identifier, ())),
            )
            for row in group_rows
        ),
    )


def _after_layout_prepare(_session: Session, _layout: IrGraphLayout) -> None:
    """Failure-injection seam proving graph and carried layout are atomic."""


def carry_layout_forward(
    session: Session,
    graph_identifier: str,
    from_version: int,
    to_version: int,
    valid_instance_ids: frozenset[str],
) -> Layout:
    """Create a fresh revision-one layout stream inside the caller's transaction."""
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    target = IrGraphLayout(
        graph_identifier=graph_identifier,
        graph_version=to_version,
        revision=1,
        updated_at=now,
    )
    session.add(target)
    source_rows = session.scalars(
        select(IrGraphLayoutPosition).where(
            IrGraphLayoutPosition.graph_identifier == graph_identifier,
            IrGraphLayoutPosition.graph_version == from_version,
        ).order_by(IrGraphLayoutPosition.instance_id)
    )
    session.add_all([
        IrGraphLayoutPosition(
            graph_identifier=graph_identifier,
            graph_version=to_version,
            instance_id=row.instance_id,
            x=row.x,
            y=row.y,
        )
        for row in source_rows
        if row.instance_id in valid_instance_ids
    ])
    session.flush()
    _after_layout_prepare(session, target)
    return load_layout_in_session(
        session, graph_identifier, to_version, valid_instance_ids
    )


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
            session.flush()
            result = load_layout_in_session(
                session,
                graph_identifier,
                graph_version,
                frozenset(position.instance_id for position in ordered) | frozenset(
                    row.instance_id
                    for row in session.scalars(
                        select(IrGraphLayoutGroupMember).where(
                            IrGraphLayoutGroupMember.graph_identifier == graph_identifier,
                            IrGraphLayoutGroupMember.graph_version == graph_version,
                        )
                    )
                ),
            )
            session.commit()
    except IntegrityError as exc:
        raise LayoutConflict(
            _current_revision(graph_identifier, graph_version)) from exc

    return result


def _validate_groups(
    groups: tuple[VisualGroup, ...], valid_instance_ids: frozenset[str]
) -> tuple[VisualGroup, ...]:
    identifiers = [group.identifier for group in groups]
    if len(identifiers) != len(set(identifiers)):
        raise LayoutRejected("visual groups contain duplicate identifiers")
    for group in groups:
        values = (
            group.frame.x, group.frame.y, group.frame.width, group.frame.height
        )
        if not all(math.isfinite(value) for value in values):
            raise LayoutRejected("visual group frames must contain finite numbers")
        if group.frame.width <= 0 or group.frame.height <= 0:
            raise LayoutRejected("visual group width and height must be positive")
        if not group.identifier or not group.display_name:
            raise LayoutRejected("visual group identifiers and display names cannot be empty")
        if len(group.members) != len(set(group.members)):
            raise LayoutRejected(
                f"visual group {group.identifier!r} contains duplicate members"
            )
        unknown = sorted(set(group.members) - valid_instance_ids)
        if unknown:
            raise LayoutRejected(
                f"visual group {group.identifier!r} contains unknown or derived "
                f"instance IDs: {unknown}"
            )
    return tuple(sorted(groups, key=lambda group: group.identifier))


def save_groups(
    graph_identifier: str,
    graph_version: int,
    *,
    base_revision: int,
    groups: Iterable[VisualGroup],
    valid_instance_ids: frozenset[str],
) -> Layout:
    """Replace visual groups while preserving positions under one revision."""
    ordered = _validate_groups(tuple(groups), valid_instance_ids)
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
                        _current_revision(graph_identifier, graph_version)
                    )
            session.execute(delete(IrGraphLayoutGroupMember).where(
                IrGraphLayoutGroupMember.graph_identifier == graph_identifier,
                IrGraphLayoutGroupMember.graph_version == graph_version,
            ))
            session.execute(delete(IrGraphLayoutGroup).where(
                IrGraphLayoutGroup.graph_identifier == graph_identifier,
                IrGraphLayoutGroup.graph_version == graph_version,
            ))
            session.add_all([
                IrGraphLayoutGroup(
                    graph_identifier=graph_identifier,
                    graph_version=graph_version,
                    identifier=group.identifier,
                    display_name=group.display_name,
                    x=group.frame.x,
                    y=group.frame.y,
                    width=group.frame.width,
                    height=group.frame.height,
                    collapsed=group.collapsed,
                )
                for group in ordered
            ])
            session.flush()
            session.add_all([
                IrGraphLayoutGroupMember(
                    graph_identifier=graph_identifier,
                    graph_version=graph_version,
                    group_identifier=group.identifier,
                    instance_id=member,
                )
                for group in ordered
                for member in sorted(group.members)
            ])
            session.flush()
            result = load_layout_in_session(
                session, graph_identifier, graph_version, valid_instance_ids
            )
            session.commit()
    except IntegrityError as exc:
        raise LayoutConflict(
            _current_revision(graph_identifier, graph_version)
        ) from exc
    return result
