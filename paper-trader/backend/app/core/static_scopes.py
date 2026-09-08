"""Versioned owner watchlists. No strategy, broker or execution authority.

Writers require a fresh caller-owned transaction; they neither commit nor roll back
the caller. Canonical members reference MARKET values; provider selections are
USER records. Neither kind introduces a cross-plane foreign key.
"""
from __future__ import annotations

import json
import re
from uuid import uuid4

from sqlalchemy import func, inspect, select, update
from sqlalchemy.exc import IntegrityError

from app.db.concurrency import begin_reservation, caller_owned_savepoint
from app.db.models import Project, StaticInstrumentScope as Root, StaticInstrumentScopeRevision as Revision
from app.ir.hashing import canonical_json, content_address
from app.market_truth.identity import MarketTruthError, load_canonical_instrument

SCHEMA = 'static-instrument-scope/1'
MEMBERSHIP_SCHEMA = 'static-instrument-membership/1'
REFERENCE_SCHEMA = 'static-instrument-scope/2'
REFERENCE_MEMBERSHIP_SCHEMA = 'static-instrument-membership/2'
_ADDRESS = re.compile(r'sha256:[0-9a-f]{64}\Z')


class ScopeInvalid(ValueError):
    pass


class ScopeNotFound(LookupError):
    pass


class ScopeConflict(RuntimeError):
    pass


def _text(value, field, maximum=64):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ScopeInvalid(f'{field} must contain 1–{maximum} characters')
    if value != value.strip() or any(ord(c) < 32 for c in value):
        raise ScopeInvalid(f'{field} must be trimmed text without control characters')
    return value


def _positive(value):
    if type(value) is not int or value < 1:
        raise ScopeInvalid('revision must be a positive integer')
    return value


def _members(members):
    if not isinstance(members, (list, tuple)) or not 1 <= len(members) <= 32:
        raise ScopeInvalid('membership must contain 1–32 distinct instruments')
    if not isinstance(members[0], str):
        return _typed_members(members)
    if any(not isinstance(m, str) or not _ADDRESS.fullmatch(m) for m in members):
        raise ScopeInvalid('membership requires canonical instrument addresses')
    if len(set(members)) != len(members):
        raise ScopeInvalid('membership must be unique')
    return sorted(members)


def _typed_member(member):
    if type(member) is not dict or member.get('kind') not in ('CANONICAL', 'PROVIDER_REFERENCE'):
        raise ScopeInvalid('typed membership kind is invalid')
    key = 'instrument_address' if member['kind'] == 'CANONICAL' else 'selection_address'
    if set(member) != {'kind', key} or not isinstance(member[key], str) or not _ADDRESS.fullmatch(member[key]):
        raise ScopeInvalid('typed membership requires its exact address field')
    return {'kind': member['kind'], key: member[key]}


def _typed_member_key(member):
    key = 'instrument_address' if member['kind'] == 'CANONICAL' else 'selection_address'
    return member['kind'], member[key]


def _typed_members(members):
    result = sorted((_typed_member(member) for member in members), key=_typed_member_key)
    if len({_typed_member_key(member) for member in result}) != len(result):
        raise ScopeInvalid('membership must be unique')
    return result


def _schema(members):
    return SCHEMA if isinstance(members[0], str) else REFERENCE_SCHEMA


def _version_transition(previous, current):
    if previous == REFERENCE_SCHEMA and current != REFERENCE_SCHEMA:
        raise ScopeInvalid('version 2 watchlists require typed membership; downgrade is unavailable')


def _identity(owner_id, project_id, scope_id):
    identity = tuple(_text(v, k) for k, v in zip(('owner_id', 'project_id', 'scope_id'),
                                                (owner_id, project_id, scope_id)))
    if re.fullmatch(r'scope\.[A-Za-z0-9][A-Za-z0-9._-]{0,57}', scope_id) is None:
        raise ScopeInvalid('scope_id must be a scope.-prefixed opaque URL-safe identifier')
    return identity


def _where(model, owner_id, project_id, scope_id):
    return (model.owner_id == owner_id, model.project_id == project_id, model.scope_id == scope_id)


def _project(session, owner_id, project_id, *, write=False):
    project = session.scalar(select(Project).where(Project.owner_id == owner_id,
                                                    Project.project_id == project_id))
    if project is None:
        raise ScopeNotFound('project not found')
    if write and project.status != 'active':
        raise ScopeConflict('project is archived')


def _validate_instruments(session, members):
    try:
        for member in members:
            load_canonical_instrument(session, member)
    except MarketTruthError as exc:
        raise ScopeInvalid('canonical instrument authority is absent or invalid') from exc


def _document(owner_id, project_id, scope_id, revision, predecessor, members):
    return dict(schema=_schema(members), owner_id=owner_id, project_id=project_id, scope_id=scope_id,
                revision=revision, predecessor=predecessor, members=members)


def _membership_address(members):
    schema = MEMBERSHIP_SCHEMA if _schema(members) == SCHEMA else REFERENCE_MEMBERSHIP_SCHEMA
    return content_address({'schema': schema, 'members': members})


def validate_revision(row):
    """Validate canonical bytes and all copied identity fields, including membership."""
    try:
        doc = json.loads(row.canonical_json)
        owner, project, scope = _identity(row.owner_id, row.project_id, row.scope_id)
        revision = _positive(row.revision)
        members = _members(doc['members'])
        if (revision == 1) != (row.predecessor is None):
            raise ValueError('predecessor')
        if row.predecessor is not None and not _ADDRESS.fullmatch(row.predecessor):
            raise ValueError('predecessor address')
        expected = _document(owner, project, scope, revision, row.predecessor, members)
        if (doc != expected or canonical_json(expected) != row.canonical_json
                or content_address(expected) != row.address
                or _membership_address(members) != row.membership_address):
            raise ValueError('digest or copied fields')
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ScopeInvalid('static scope canonical revision is invalid') from exc
    return expected


def _selected_revision(name, status, current_revision, requested):
    observed = _positive(current_revision)
    _text(name, 'name', 128)
    if status not in ('active', 'archived'):
        raise ScopeInvalid('static scope status is invalid')
    selected = observed if requested is None else requested
    if selected > observed:
        raise ScopeNotFound('scope revision not found')
    return observed, selected


def _verified_chain_row(row, count, previous, previous_schema=None):
    if row is None:
        raise ScopeInvalid('static scope root/revision mismatch')
    doc = validate_revision(row)
    if row.revision != count or row.predecessor != previous:
        raise ScopeInvalid('static scope predecessor chain is invalid')
    _version_transition(previous_schema, doc['schema'])
    return doc


def _member_labels(members):
    from app.market_truth.cash_reference import source_reference_label
    return [{"instrument_address": member, "display_name": source_reference_label(member)}
            for member in members]


def _provider_member_label(session, owner_id, member):
    from app.core.provider_selections import load_provider_selection, ProviderSelectionInvalid, ProviderSelectionNotFound
    try:
        selected = load_provider_selection(session, owner_id=owner_id, selection_address=member['selection_address'])['selection']
    except (ProviderSelectionInvalid, ProviderSelectionNotFound) as exc:
        raise ScopeInvalid('provider selection is unavailable in this workspace') from exc
    reference = selected['reference']
    return {'member': member, 'display_name': f"{reference['symbol']} · {reference['exchange']}",
            'provider_reference': reference, 'observed_at': selected['observed_at']}


def _typed_member_label(session, owner_id, member):
    if member['kind'] == 'PROVIDER_REFERENCE':
        return _provider_member_label(session, owner_id, member)
    from app.market_truth.cash_reference import source_reference_label
    load_canonical_instrument(session, member['instrument_address'])
    return {'member': member, 'display_name': source_reference_label(member['instrument_address']),
            'provider_reference': None, 'observed_at': None}


def _validated_labels(session, owner_id, members):
    if _schema(members) == SCHEMA:
        _validate_instruments(session, members)
        return _member_labels(members)
    try:
        return [_typed_member_label(session, owner_id, member) for member in members]
    except MarketTruthError as exc:
        raise ScopeInvalid('canonical instrument authority is absent or invalid') from exc


def _read(session, root, revision=None):
    if revision is not None:
        _positive(revision)
    previous = None
    previous_schema = None
    result = None
    observed_revision = None
    # One statement observes the root and its entire chain at the same point.
    # Scalar root columns deliberately bypass an older ORM identity-map entry.
    # Never limit the chain to a previously observed head: extra rows are corruption.
    query = (select(Root.name, Root.status, Root.revision, Revision).select_from(Root)
        .outerjoin(Revision, (Revision.owner_id == Root.owner_id)
            & (Revision.project_id == Root.project_id) & (Revision.scope_id == Root.scope_id))
        .where(*_where(Root, root.owner_id, root.project_id, root.scope_id))
        .order_by(Revision.revision).execution_options(yield_per=100, populate_existing=True))
    rows = session.execute(query)
    count = 0
    try:
        for name, status, current_revision, row in rows:
            if observed_revision is None:
                observed_revision, selected = _selected_revision(name, status, current_revision, revision)
            count += 1
            doc = _verified_chain_row(row, count, previous, previous_schema)
            previous = row.address
            previous_schema = doc['schema']
            if row.revision == selected:
                labels = _validated_labels(session, root.owner_id, doc['members'])
                result = dict(scope_id=root.scope_id, name=name, status=status,
                              current_revision=observed_revision, address=row.address,
                              membership_address=row.membership_address, snapshot=doc,
                              member_labels=labels)
    finally:
        rows.close()
    if count != observed_revision or result is None:
        raise ScopeInvalid('static scope root/revision mismatch')
    return result


def get_scope(session, *, owner_id, project_id, scope_id, revision=None):
    _identity(owner_id, project_id, scope_id)
    _project(session, owner_id, project_id)
    root = session.scalar(select(Root).where(*_where(Root, owner_id, project_id, scope_id)))
    if root is None:
        raise ScopeNotFound('scope not found')
    return _read(session, root, revision)


def list_scopes(session, *, owner_id, project_id, limit=50, after=None, include_archived=False):
    _text(owner_id, 'owner_id'); _text(project_id, 'project_id')
    if type(limit) is not int or not 1 <= limit <= 50 or type(include_archived) is not bool:
        raise ScopeInvalid('invalid list bounds')
    _project(session, owner_id, project_id)
    query = select(Root).where(Root.owner_id == owner_id, Root.project_id == project_id)
    if not include_archived:
        query = query.where(Root.status == 'active')
    if after is not None:
        query = query.where(Root.scope_id > _text(after, 'after'))
    roots = list(session.scalars(query.order_by(Root.scope_id).limit(limit + 1)))
    return dict(items=[_read(session, r) for r in roots[:limit]],
                next_cursor=roots[limit-1].scope_id if len(roots) > limit else None)


def _append(session, root, members, predecessor):
    doc = _document(root.owner_id, root.project_id, root.scope_id, root.revision, predecessor, members)
    session.add(Revision(owner_id=root.owner_id, project_id=root.project_id, scope_id=root.scope_id,
        revision=root.revision, predecessor=predecessor, address=content_address(doc),
        membership_address=_membership_address(members), canonical_json=canonical_json(doc)))
    session.flush()


def create_scope(session, *, owner_id, project_id, name, members, scope_id=None):
    scope_id = 'scope.' + uuid4().hex if scope_id is None else scope_id
    _identity(owner_id, project_id, scope_id); _text(name, 'name', 128)
    members = _members(members)
    begin_reservation(session, scope=f'static-scope:{owner_id}:{project_id}')
    _project(session, owner_id, project_id, write=True)
    _validated_labels(session, owner_id, members)
    root = session.scalar(select(Root).where(*_where(Root, owner_id, project_id, scope_id)))
    if root is not None:
        existing = _read(session, root)
        if root.revision == 1 and root.status == 'active' and root.name == name and existing['snapshot']['members'] == members:
            return existing
        raise ScopeConflict('scope ID already exists with different state')
    try:
        with caller_owned_savepoint(session, scope='create-static-scope'):
            root = Root(owner_id=owner_id, project_id=project_id, scope_id=scope_id,
                        name=name, revision=1, status='active')
            session.add(root); session.flush()
            _append(session, root, members, None)
    except IntegrityError as exc:
        raise ScopeConflict('scope name or identity already exists') from exc
    return _read(session, root)


def revise_scope(session, *, owner_id, project_id, scope_id, expected_revision, name, members):
    _identity(owner_id, project_id, scope_id); _positive(expected_revision); _text(name, 'name', 128)
    members = _members(members)
    begin_reservation(session, scope=f'static-scope:{owner_id}:{project_id}')
    _project(session, owner_id, project_id, write=True)
    before = get_scope(session, owner_id=owner_id, project_id=project_id, scope_id=scope_id)
    if before['status'] != 'active' or before['current_revision'] != expected_revision:
        raise ScopeConflict('expected revision conflict or archived scope')
    _version_transition(before['snapshot']['schema'], _schema(members))
    _validated_labels(session, owner_id, members)
    try:
        with caller_owned_savepoint(session, scope='revise-static-scope'):
            changed = session.execute(update(Root).where(*_where(Root, owner_id, project_id, scope_id),
                Root.revision == expected_revision, Root.status == 'active').values(
                revision=expected_revision + 1, name=name))
            if changed.rowcount != 1:
                raise ScopeConflict('expected revision conflict')
            root = session.scalar(select(Root).where(*_where(Root, owner_id, project_id, scope_id))
                                  .execution_options(populate_existing=True))
            _append(session, root, members, before['address'])
    except IntegrityError as exc:
        raise ScopeConflict('scope name or revision conflict') from exc
    return _read(session, root)


def archive_scope(session, *, owner_id, project_id, scope_id, expected_revision):
    _identity(owner_id, project_id, scope_id); _positive(expected_revision)
    begin_reservation(session, scope=f'static-scope:{owner_id}:{project_id}')
    _project(session, owner_id, project_id, write=True)
    before = get_scope(session, owner_id=owner_id, project_id=project_id, scope_id=scope_id)
    if before['current_revision'] != expected_revision:
        raise ScopeConflict('expected revision conflict')
    changed = session.execute(update(Root).where(*_where(Root, owner_id, project_id, scope_id),
        Root.revision == expected_revision).values(status='archived'))
    if changed.rowcount != 1:
        raise ScopeConflict('expected revision conflict')
    return get_scope(session, owner_id=owner_id, project_id=project_id, scope_id=scope_id)


def _validate_selection_inventory(connection):
    # Accepted pre-0054 snapshots have no selection inventory. Current-plane
    # schema validation separately requires the new table at the new head.
    if not inspect(connection).has_table('owner_provider_instrument_selections'):
        return
    from app.core.provider_selections import (validate_persisted_provider_selections,
        ProviderSelectionInvalid, ProviderSelectionNotFound)
    try:
        validate_persisted_provider_selections(connection)
    except (ProviderSelectionInvalid, ProviderSelectionNotFound) as exc:
        raise ScopeInvalid('provider selection inventory is invalid') from exc


def validate_persisted_scopes(connection):
    """Restore/copy gate: recompute every revision and root/owner/predecessor link."""
    from sqlalchemy.orm import Session
    _validate_selection_inventory(connection)
    with Session(bind=connection) as session:
        for root in session.scalars(select(Root).execution_options(yield_per=100)):
            _project(session, root.owner_id, root.project_id)
            _read(session, root)
        orphan = session.scalar(select(func.count()).select_from(Revision).outerjoin(Root,
            (Revision.owner_id == Root.owner_id) & (Revision.project_id == Root.project_id)
            & (Revision.scope_id == Root.scope_id)).where(Root.scope_id.is_(None)))
        if orphan:
            raise ScopeInvalid('orphan static scope revision')
        for row in session.scalars(select(Revision).execution_options(yield_per=100)):
            _validated_labels(session, row.owner_id, validate_revision(row)['members'])
