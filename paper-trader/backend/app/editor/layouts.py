"""Transactional persistence for sparse IR editor layout overrides."""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

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


@dataclass(frozen=True)
class PresentationDelta:
    forward_operations: tuple[dict[str, Any], ...]
    inverse_operations: tuple[dict[str, Any], ...]


class LayoutConflict(Exception):
    def __init__(self, current_revision: int):
        super().__init__(f"layout is at revision {current_revision}")
        self.current_revision = current_revision


class LayoutRejected(Exception):
    def __init__(
        self,
        message: str,
        *,
        operation_index: int | None = None,
        path: tuple[str | int, ...] = (),
    ) -> None:
        super().__init__(message)
        self.operation_index = operation_index
        self.path = path


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


def _after_presentation_reconcile(_session: Session, _layout: IrGraphLayout) -> None:
    """Failure-injection seam for semantic/presentation publication atomicity."""


def carry_and_reconcile_presentation(
    session: Session,
    graph_identifier: str,
    from_version: int,
    to_version: int,
    *,
    base_revision: int,
    source_instance_ids: frozenset[str],
    target_instance_ids: frozenset[str],
    operations: Sequence[Mapping[str, Any]] = (),
) -> tuple[Layout, PresentationDelta]:
    """Carry presentation to an immutable graph version and prune removed nodes."""
    source = load_layout_in_session(
        session, graph_identifier, from_version, source_instance_ids
    )
    if source.revision != base_revision:
        raise LayoutConflict(source.revision)
    added_ids = target_instance_ids - source_instance_ids
    positions = {
        position.instance_id: position
        for position in source.positions
        if position.instance_id in target_instance_ids
    }
    carried_groups = tuple(
        VisualGroup(
            group.identifier,
            group.display_name,
            group.frame,
            group.collapsed,
            tuple(member for member in group.members if member in target_instance_ids),
        )
        for group in source.groups
    )
    groups = {group.identifier: group for group in carried_groups}
    forward: list[dict[str, Any]] = []
    inverse: list[dict[str, Any]] = []
    for position in source.positions:
        if position.instance_id not in target_instance_ids:
            forward.append({
                "operation": "clear_position",
                "instance_id": position.instance_id,
            })
            inverse.insert(0, {
                "operation": "set_position",
                "instance_id": position.instance_id,
                "x": position.x,
                "y": position.y,
            })
    for group in source.groups:
        for member in group.members:
            if member not in target_instance_ids:
                forward.append({
                    "operation": "remove_group_member",
                    "identifier": group.identifier,
                    "instance_id": member,
                })
                inverse.insert(0, {
                    "operation": "add_group_member",
                    "identifier": group.identifier,
                    "instance_id": member,
                })
    for index, raw in enumerate(operations):
        operation = dict(raw)
        kind = str(operation.get("operation"))
        instance_id = str(operation.get("instance_id", ""))
        if kind == "set_position":
            if instance_id not in added_ids:
                raise LayoutRejected(
                    "a same-request position may reference only a newly added authored node",
                    operation_index=index,
                    path=("presentation_edits", index, "instance_id"),
                )
            if instance_id in positions:
                raise LayoutRejected(
                    f"position for {instance_id!r} appears more than once",
                    operation_index=index,
                    path=("presentation_edits", index, "instance_id"),
                )
            x, y = float(operation["x"]), float(operation["y"])
            if not math.isfinite(x) or not math.isfinite(y):
                raise LayoutRejected(
                    "positions must contain finite numbers",
                    operation_index=index,
                    path=("presentation_edits", index),
                )
            positions[instance_id] = Position(instance_id, x, y)
            forward.append({
                "operation": "set_position", "instance_id": instance_id,
                "x": x, "y": y,
            })
            inverse.insert(0, {
                "operation": "clear_position", "instance_id": instance_id,
            })
        elif kind == "clear_position":
            removed = next(
                (item for item in source.positions if item.instance_id == instance_id),
                None,
            )
            if instance_id not in source_instance_ids - target_instance_ids or removed is None:
                raise LayoutRejected(
                    "clear_position may confirm only a position pruned for a removed node",
                    operation_index=index,
                    path=("presentation_edits", index, "instance_id"),
                )
        elif kind in {"add_group_member", "remove_group_member"}:
            identifier = str(operation["identifier"])
            group = groups.get(identifier)
            if group is None:
                raise LayoutRejected(
                    f"visual group {identifier!r} does not exist",
                    operation_index=index,
                    path=("presentation_edits", index, "identifier"),
                )
            members = set(group.members)
            if kind == "add_group_member":
                if instance_id not in target_instance_ids or instance_id in members:
                    raise LayoutRejected(
                        "add_group_member must restore a missing current authored member",
                        operation_index=index,
                        path=("presentation_edits", index, "instance_id"),
                    )
                members.add(instance_id)
                forward.append(dict(operation))
                inverse.insert(0, {**operation, "operation": "remove_group_member"})
            elif instance_id in members:
                members.remove(instance_id)
                forward.append(dict(operation))
                inverse.insert(0, {**operation, "operation": "add_group_member"})
            elif instance_id not in source_instance_ids - target_instance_ids:
                raise LayoutRejected(
                    "remove_group_member must remove or confirm a removed authored member",
                    operation_index=index,
                    path=("presentation_edits", index, "instance_id"),
                )
            groups[identifier] = VisualGroup(
                identifier, group.display_name, group.frame,
                group.collapsed, tuple(sorted(members)),
            )
        elif kind in {"put_group", "remove_group"}:
            identifier = str(operation["identifier"])
            existing = groups.get(identifier)
            if kind == "put_group":
                candidate = VisualGroup(
                    identifier,
                    str(operation["display_name"]),
                    _frame_from_operation(operation),
                    bool(operation["collapsed"]),
                    tuple(sorted(str(item) for item in operation["members"])),
                )
                _validate_groups((candidate,), target_instance_ids)
                groups[identifier] = candidate
                forward.append(_group_operation(candidate, kind))
                inverse.insert(0, (
                    _group_operation(existing, "put_group")
                    if existing is not None
                    else {"operation": "remove_group", "identifier": identifier}
                ))
            else:
                if existing is None:
                    raise LayoutRejected(
                        f"visual group {identifier!r} does not exist",
                        operation_index=index,
                        path=("presentation_edits", index, "identifier"),
                    )
                del groups[identifier]
                forward.append({"operation": kind, "identifier": identifier})
                inverse.insert(0, _group_operation(existing, "put_group"))
        else:
            raise LayoutRejected(
                f"unsupported semantic presentation delta {kind!r}",
                operation_index=index,
                path=("presentation_edits", index, "operation"),
            )

    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    target = IrGraphLayout(
        graph_identifier=graph_identifier,
        graph_version=to_version,
        revision=1,
        updated_at=now,
    )
    session.add(target)
    session.flush()
    session.add_all([
        IrGraphLayoutPosition(
            graph_identifier=graph_identifier,
            graph_version=to_version,
            instance_id=position.instance_id,
            x=position.x,
            y=position.y,
        )
        for position in sorted(positions.values(), key=lambda item: item.instance_id)
    ])
    ordered_groups = _validate_groups(tuple(groups.values()), target_instance_ids)
    _replace_groups_in_session(
        session, graph_identifier, to_version, ordered_groups
    )
    session.flush()
    _after_layout_prepare(session, target)
    _after_presentation_reconcile(session, target)
    return (
        load_layout_in_session(
            session, graph_identifier, to_version, target_instance_ids
        ),
        PresentationDelta(tuple(forward), tuple(inverse)),
    )


def carry_layout_forward(
    session: Session,
    graph_identifier: str,
    from_version: int,
    to_version: int,
    valid_instance_ids: frozenset[str],
) -> Layout:
    """Create a fresh revision-one layout stream inside the caller's transaction."""
    layout, _ = carry_and_reconcile_presentation(
        session,
        graph_identifier,
        from_version,
        to_version,
        base_revision=load_layout_in_session(
            session, graph_identifier, from_version, valid_instance_ids
        ).revision,
        source_instance_ids=valid_instance_ids,
        target_instance_ids=valid_instance_ids,
    )
    return layout


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


def _group_operation(group: VisualGroup, operation: str) -> dict[str, Any]:
    return {
        "operation": operation,
        "identifier": group.identifier,
        "display_name": group.display_name,
        "members": list(group.members),
        "frame": {
            "x": group.frame.x,
            "y": group.frame.y,
            "width": group.frame.width,
            "height": group.frame.height,
        },
        "collapsed": group.collapsed,
    }


def _claim_layout_revision_in_session(
    session: Session,
    graph_identifier: str,
    graph_version: int,
    base_revision: int,
) -> None:
    current = session.get(IrGraphLayout, (graph_identifier, graph_version))
    current_revision = current.revision if current is not None else 0
    if current_revision != base_revision:
        raise LayoutConflict(current_revision)
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
    if current is None:
        session.add(IrGraphLayout(
            graph_identifier=graph_identifier,
            graph_version=graph_version,
            revision=1,
            updated_at=now,
        ))
        session.flush()
        return
    claimed = session.execute(
        update(IrGraphLayout)
        .where(
            IrGraphLayout.graph_identifier == graph_identifier,
            IrGraphLayout.graph_version == graph_version,
            IrGraphLayout.revision == base_revision,
        )
        .values(revision=base_revision + 1, updated_at=now)
    )
    if claimed.rowcount != 1:
        raise LayoutConflict(current_revision)


def _replace_groups_in_session(
    session: Session,
    graph_identifier: str,
    graph_version: int,
    groups: tuple[VisualGroup, ...],
) -> None:
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
        for group in groups
    ])
    session.flush()
    session.add_all([
        IrGraphLayoutGroupMember(
            graph_identifier=graph_identifier,
            graph_version=graph_version,
            group_identifier=group.identifier,
            instance_id=member,
        )
        for group in groups
        for member in group.members
    ])
    session.flush()


def _replace_positions_in_session(
    session: Session,
    graph_identifier: str,
    graph_version: int,
    positions: Iterable[Position],
) -> None:
    session.execute(delete(IrGraphLayoutPosition).where(
        IrGraphLayoutPosition.graph_identifier == graph_identifier,
        IrGraphLayoutPosition.graph_version == graph_version,
    ))
    session.add_all([
        IrGraphLayoutPosition(
            graph_identifier=graph_identifier,
            graph_version=graph_version,
            instance_id=position.instance_id,
            x=position.x,
            y=position.y,
        )
        for position in sorted(positions, key=lambda item: item.instance_id)
    ])
    session.flush()


def _frame_from_operation(operation: Mapping[str, Any]) -> GroupFrame:
    frame = operation["frame"]
    return GroupFrame(
        float(frame["x"]),
        float(frame["y"]),
        float(frame["width"]),
        float(frame["height"]),
    )


def apply_presentation_batch_in_session(
    session: Session,
    graph_identifier: str,
    graph_version: int,
    *,
    base_revision: int,
    operations: Sequence[Mapping[str, Any]],
    valid_instance_ids: frozenset[str],
) -> tuple[Layout, PresentationDelta]:
    """Apply a closed presentation batch and return its exact replay delta."""
    current = load_layout_in_session(
        session, graph_identifier, graph_version, valid_instance_ids
    )
    if current.revision != base_revision:
        raise LayoutConflict(current.revision)
    groups = {group.identifier: group for group in current.groups}
    positions = {position.instance_id: position for position in current.positions}
    forward: list[dict[str, Any]] = []
    inverse: list[dict[str, Any]] = []

    def reject(index: int, field: str, message: str) -> None:
        raise LayoutRejected(
            message, operation_index=index, path=("edits", index, field)
        )

    for index, raw in enumerate(operations):
        operation = dict(raw)
        kind = operation["operation"]
        identifier = str(operation.get("identifier", ""))
        existing = groups.get(identifier)
        if kind == "set_position":
            instance_id = str(operation["instance_id"])
            if instance_id not in valid_instance_ids:
                reject(index, "instance_id", f"instance {instance_id!r} is not an authored node")
            x, y = float(operation["x"]), float(operation["y"])
            if not math.isfinite(x) or not math.isfinite(y):
                reject(index, "x", "positions must contain finite numbers")
            previous = positions.get(instance_id)
            positions[instance_id] = Position(instance_id, x, y)
            forward.append({
                "operation": kind, "instance_id": instance_id, "x": x, "y": y,
            })
            inverse.insert(0, (
                {
                    "operation": "set_position",
                    "instance_id": instance_id,
                    "x": previous.x,
                    "y": previous.y,
                }
                if previous is not None
                else {"operation": "clear_position", "instance_id": instance_id}
            ))
        elif kind == "clear_position":
            instance_id = str(operation["instance_id"])
            previous = positions.pop(instance_id, None)
            if previous is None:
                reject(index, "instance_id", f"position for {instance_id!r} does not exist")
            forward.append({"operation": kind, "instance_id": instance_id})
            inverse.insert(0, {
                "operation": "set_position", "instance_id": instance_id,
                "x": previous.x, "y": previous.y,
            })
        elif kind in {"create_group", "put_group"}:
            if kind == "create_group" and existing is not None:
                reject(index, "identifier", f"visual group {identifier!r} already exists")
            group = VisualGroup(
                identifier=identifier,
                display_name=str(operation["display_name"]),
                frame=_frame_from_operation(operation),
                collapsed=bool(operation["collapsed"]),
                members=tuple(sorted(str(item) for item in operation["members"])),
            )
            try:
                _validate_groups((group,), valid_instance_ids)
            except LayoutRejected as exc:
                field = "members" if "unknown or derived" in str(exc) else "frame"
                reject(index, field, str(exc))
            groups[identifier] = group
            forward.append(_group_operation(group, kind))
            inverse[0:0] = (
                [_group_operation(existing, "put_group")]
                if existing is not None
                else [{"operation": "remove_group", "identifier": identifier}]
            )
        elif kind == "remove_group":
            if existing is None:
                reject(index, "identifier", f"visual group {identifier!r} does not exist")
            del groups[identifier]
            forward.append({"operation": kind, "identifier": identifier})
            inverse.insert(0, _group_operation(existing, "put_group"))
        elif kind == "rename_group":
            if existing is None:
                reject(index, "identifier", f"visual group {identifier!r} does not exist")
            display_name = str(operation["display_name"])
            groups[identifier] = VisualGroup(
                identifier, display_name, existing.frame, existing.collapsed, existing.members
            )
            forward.append({
                "operation": kind, "identifier": identifier,
                "display_name": display_name,
            })
            inverse.insert(0, {
                "operation": kind, "identifier": identifier,
                "display_name": existing.display_name,
            })
        elif kind in {"add_group_member", "remove_group_member"}:
            if existing is None:
                reject(index, "identifier", f"visual group {identifier!r} does not exist")
            instance_id = str(operation["instance_id"])
            members = set(existing.members)
            if kind == "add_group_member":
                if instance_id not in valid_instance_ids:
                    reject(index, "instance_id", f"instance {instance_id!r} is not an authored node")
                if instance_id in members:
                    reject(index, "instance_id", f"instance {instance_id!r} is already a member")
                members.add(instance_id)
                inverse_kind = "remove_group_member"
            else:
                if instance_id not in members:
                    reject(index, "instance_id", f"instance {instance_id!r} is not a member")
                members.remove(instance_id)
                inverse_kind = "add_group_member"
            groups[identifier] = VisualGroup(
                identifier, existing.display_name, existing.frame,
                existing.collapsed, tuple(sorted(members)),
            )
            normalized = {
                "operation": kind, "identifier": identifier,
                "instance_id": instance_id,
            }
            forward.append(normalized)
            inverse.insert(0, {**normalized, "operation": inverse_kind})
        elif kind == "set_group_frame":
            if existing is None:
                reject(index, "identifier", f"visual group {identifier!r} does not exist")
            frame = _frame_from_operation(operation)
            candidate = VisualGroup(
                identifier, existing.display_name, frame,
                existing.collapsed, existing.members,
            )
            try:
                _validate_groups((candidate,), valid_instance_ids)
            except LayoutRejected as exc:
                reject(index, "frame", str(exc))
            groups[identifier] = candidate
            forward.append({
                "operation": kind, "identifier": identifier,
                "frame": _group_operation(candidate, "put_group")["frame"],
            })
            inverse.insert(0, {
                "operation": kind, "identifier": identifier,
                "frame": _group_operation(existing, "put_group")["frame"],
            })
        elif kind == "set_group_collapsed":
            if existing is None:
                reject(index, "identifier", f"visual group {identifier!r} does not exist")
            collapsed = bool(operation["collapsed"])
            groups[identifier] = VisualGroup(
                identifier, existing.display_name, existing.frame,
                collapsed, existing.members,
            )
            forward.append({
                "operation": kind, "identifier": identifier,
                "collapsed": collapsed,
            })
            inverse.insert(0, {
                "operation": kind, "identifier": identifier,
                "collapsed": existing.collapsed,
            })
        else:
            reject(index, "operation", f"unsupported presentation operation {kind!r}")

    ordered = _validate_groups(tuple(groups.values()), valid_instance_ids)
    _claim_layout_revision_in_session(
        session, graph_identifier, graph_version, base_revision
    )
    _replace_groups_in_session(session, graph_identifier, graph_version, ordered)
    _replace_positions_in_session(
        session, graph_identifier, graph_version, positions.values()
    )
    result = load_layout_in_session(
        session, graph_identifier, graph_version, valid_instance_ids
    )
    return result, PresentationDelta(tuple(forward), tuple(inverse))
