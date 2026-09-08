"""Static research scope contracts; real canonical instruments, no execution authority."""
import pytest
import sqlalchemy as sa
import datetime as dt
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session

from app.core import static_scopes as scopes
from app.db.models import Base, Organization, Project, StaticInstrumentScopeRevision
from app.market_truth.identity import CanonicalPhysicalInstrument, persist_canonical_instrument


def provider_reference(**changes):
    return {"token": 1234567, "symbol": "SMALLCAP-X", "name": "An unconfigured small company",
            "exchange": "NSE", "segment": "NSE", "instrument_type": "EQ", "expiry": None,
            "strike": "0", "lot_size": "1", "tick_size": "0.05", **changes}


def provider_selection(engine, **changes):
    from app.core.provider_selections import persist_provider_selection
    values = {"owner_id": "a", "data_account_id": "data-account-a", "connection_id": 71,
              "provider": "ZERODHA", "reference": provider_reference(),
              "observed_at": dt.datetime(2026, 9, 6, 10, 20, 30, 123456, tzinfo=dt.timezone.utc), **changes}
    with Session(engine) as session, session.begin():
        return persist_provider_selection(session, **values)


def provider_member(selection):
    return {"kind": "PROVIDER_REFERENCE", "selection_address": selection["selection_address"]}


def seed(engine):
    with Session(engine) as session, session.begin():
        session.add_all([Organization(organization_id=o, name=o) for o in ('a', 'b')])
        session.flush()
        session.add_all([Project(project_id=p, owner_id=o, name=p)
                         for o, p in [('a', 'pa'), ('a', 'pa2'), ('b', 'pb')]])
        instruments = [CanonicalPhysicalInstrument('test', str(i), 'NSE', 'EQUITY',
                                                  'SPOT', 'INR', None) for i in range(33)]
        for instrument in instruments:
            persist_canonical_instrument(session, instrument)
    return [i.address for i in instruments]


@pytest.fixture
def db(tmp_path):
    engine = sa.create_engine(f'sqlite:///{tmp_path}/scopes.db')
    Base.metadata.create_all(engine)
    members = seed(engine)
    yield engine, members
    engine.dispose()


def create(engine, members, **kw):
    with Session(engine) as session, session.begin():
        return scopes.create_scope(session, owner_id='a', project_id='pa',
                                   scope_id='scope.main', name='Research', members=members, **kw)


def test_revision_identity_reopen_archive_and_idempotency(db):
    engine, members = db
    first = create(engine, members[:2][::-1])
    assert first['snapshot']['members'] == sorted(members[:2])
    assert create(engine, members[:2]) == first
    with Session(engine) as s, s.begin():
        second = scopes.revise_scope(s, owner_id='a', project_id='pa', scope_id='scope.main',
                                     expected_revision=1, name='Renamed', members=members[:3])
    assert second['snapshot']['predecessor'] == first['address']
    assert second['snapshot']['revision'] == 2
    with Session(engine) as s:
        assert scopes.get_scope(s, owner_id='a', project_id='pa', scope_id='scope.main', revision=1)['address'] == first['address']
    with Session(engine) as s, s.begin():
        scopes.archive_scope(s, owner_id='a', project_id='pa', scope_id='scope.main', expected_revision=2)
    with Session(engine) as s:
        assert scopes.get_scope(s, owner_id='a', project_id='pa', scope_id='scope.main')['status'] == 'archived'
        assert scopes.list_scopes(s, owner_id='a', project_id='pa')['items'] == []
    with Session(engine) as s, s.begin(), pytest.raises(scopes.ScopeConflict):
        scopes.revise_scope(s, owner_id='a', project_id='pa', scope_id='scope.main', expected_revision=2,
                            name='No', members=members[:1])


def test_sourced_index_label_reopens_without_datasets_and_does_not_change_identity(db):
    from app.market_truth.index_reference import nifty_50_price_return_reference
    from app.ir.hashing import content_address
    engine, members = db
    instrument, _ = nifty_50_price_return_reference()
    with Session(engine) as s, s.begin():
        persist_canonical_instrument(s, instrument)
    first = create(engine, [instrument.address, members[0]])
    expected = [{"instrument_address": address, "display_name":
                "Nifty 50 · INR · Price return" if address == instrument.address else None}
               for address in first['snapshot']['members']]
    assert first['member_labels'] == expected
    assert first['address'] == content_address(first['snapshot'])
    assert 'member_labels' not in first['snapshot']
    with Session(engine) as s, s.begin():
        revised = scopes.revise_scope(s, owner_id='a', project_id='pa', scope_id='scope.main',
            expected_revision=1, name='Index only', members=[instrument.address])
    with Session(engine) as s:
        old = scopes.get_scope(s, owner_id='a', project_id='pa', scope_id='scope.main', revision=1)
        assert old['member_labels'] == expected and old['address'] == first['address']
        assert scopes.get_scope(s, owner_id='a', project_id='pa', scope_id='scope.main')['member_labels'] == revised['member_labels']
        assert scopes.list_scopes(s, owner_id='a', project_id='pa')['items'][0]['member_labels'] == revised['member_labels']


def test_sourced_equity_label_reopens_without_datasets(db):
    from app.market_truth.equity_reference import infosys_equity_reference
    from app.ir.hashing import content_address
    engine, _ = db
    instrument, _ = infosys_equity_reference()
    with Session(engine) as session, session.begin():
        persist_canonical_instrument(session, instrument)
    first = create(engine, [instrument.address])
    expected = [{"instrument_address": instrument.address, "display_name": "Infosys Limited · NSE · Equity · INR"}]
    assert first['member_labels'] == expected
    assert first['address'] == content_address(first['snapshot'])
    assert 'member_labels' not in first['snapshot']
    with Session(engine) as session:
        assert scopes.get_scope(session, owner_id='a', project_id='pa', scope_id='scope.main')['member_labels'] == expected
        assert scopes.list_scopes(session, owner_id='a', project_id='pa')['items'][0]['member_labels'] == expected


@pytest.mark.parametrize('owner,project', [('b', 'pa'), ('b', 'pb'), ('a', 'pa2')])
def test_owner_and_project_substitution(db, owner, project):
    engine, members = db
    create(engine, members[:1])
    with Session(engine) as s, pytest.raises(scopes.ScopeNotFound):
        scopes.get_scope(s, owner_id=owner, project_id=project, scope_id='scope.main')


@pytest.mark.parametrize('case', ['empty', 'duplicate', 'too_many', 'unknown', 'symbol'])
def test_invalid_membership(db, case):
    engine, m = db
    bad = {'empty': [], 'duplicate': [m[0], m[0]], 'too_many': m,
           'unknown': ['sha256:' + '0'*64], 'symbol': ['NSE:INFY']}[case]
    with pytest.raises(scopes.ScopeInvalid):
        create(engine, bad)


def test_revisions_are_immutable_even_to_direct_sql(db):
    engine, m = db
    create(engine, m[:1])
    for statement in [sa.update(StaticInstrumentScopeRevision).values(canonical_json='{}'),
                      sa.delete(StaticInstrumentScopeRevision)]:
        with engine.begin() as c, pytest.raises(sa.exc.DBAPIError, match='immutable'):
            c.execute(statement)


def test_bounded_keyset_membership_and_presentation_identity(db):
    engine, m = db
    first = create(engine, m[:32])
    with Session(engine) as s, s.begin():
        renamed = scopes.revise_scope(s, owner_id='a', project_id='pa', scope_id='scope.main',
            expected_revision=1, name='Display only', members=m[:32][::-1])
    assert renamed['membership_address'] == first['membership_address']
    assert renamed['address'] != first['address']
    for i in range(51):
        with Session(engine) as s, s.begin():
            scopes.create_scope(s, owner_id='a', project_id='pa', scope_id=f'scope.s{i:03}',
                                name=f'Name {i}', members=m[:1])
    with Session(engine) as s:
        first_page = scopes.list_scopes(s, owner_id='a', project_id='pa')
        last_page = scopes.list_scopes(s, owner_id='a', project_id='pa', after=first_page['next_cursor'])
    assert len(first_page['items']) == 50 and len(last_page['items']) == 2
    assert len({r['scope_id'] for r in first_page['items'] + last_page['items']}) == 52
    assert last_page['next_cursor'] is None


def test_collision_and_caller_rollback_do_not_publish_partial_successor(db):
    engine, m = db
    first = create(engine, m[:1])
    with Session(engine) as s, s.begin():
        scopes.create_scope(s, owner_id='a', project_id='pa', scope_id='scope.other', name='Taken', members=m[:1])
    with Session(engine) as s, s.begin():
        with pytest.raises(scopes.ScopeConflict):
            scopes.revise_scope(s, owner_id='a', project_id='pa', scope_id='scope.main',
                expected_revision=1, name='Taken', members=m[:2])
    with Session(engine) as s:
        assert scopes.get_scope(s, owner_id='a', project_id='pa', scope_id='scope.main') == first
    with Session(engine) as s:
        scopes.revise_scope(s, owner_id='a', project_id='pa', scope_id='scope.main',
                            expected_revision=1, name='Rollback', members=m[:2])
        s.rollback()
    with Session(engine) as s:
        assert scopes.get_scope(s, owner_id='a', project_id='pa', scope_id='scope.main') == first


@pytest.mark.parametrize('revision', [0, -1, True, 1.5, '1'])
def test_revision_bounds_are_strict(db, revision):
    engine, m = db
    create(engine, m[:1])
    with Session(engine) as s, pytest.raises(scopes.ScopeInvalid):
        scopes.get_scope(s, owner_id='a', project_id='pa', scope_id='scope.main', revision=revision)


@pytest.mark.parametrize('field,value', [('scope_id', ''), ('scope_id', 's'*65),
                                       ('scope_id', 'a/b'), ('scope_id', '..'), ('scope_id', 'a?b'),
                                       ('name', ''), ('name', 'x'*129), ('name', ' x ')])
def test_scope_text_bounds(db, field, value):
    engine, m = db
    kwargs = dict(owner_id='a', project_id='pa', scope_id='scope.main', name='name', members=m[:1])
    kwargs[field] = value
    with Session(engine) as s, pytest.raises(scopes.ScopeInvalid):
        scopes.create_scope(s, **kwargs)


@pytest.fixture(params=['sqlite', 'postgresql'])
def read_race_db(request):
    if request.param == 'sqlite':
        return request.getfixturevalue('db')
    engine = request.getfixturevalue('pg_sandbox').engine('static_read_race')
    Base.metadata.create_all(engine)
    return engine, seed(engine)


def _consume_scope(session, consumer):
    kwargs = dict(owner_id='a', project_id='pa')
    if consumer == 'list':
        page = scopes.list_scopes(session, **kwargs)
        assert page['next_cursor'] is None
        return page['items'][0]
    return scopes.get_scope(session, **kwargs, scope_id='scope.main',
                            revision=1 if consumer == 'historical' else None)


@pytest.mark.parametrize('consumer', ['current', 'historical', 'list'])
def test_read_observes_coherent_scope_during_legal_revision_commit(read_race_db, consumer):
    """A real writer commits after root selection, before the chain read begins."""
    engine, members = read_race_db
    first = create(engine, members[:1])
    committed = []

    def append():
        with Session(engine) as writer, writer.begin():
            return scopes.revise_scope(writer, owner_id='a', project_id='pa', scope_id='scope.main',
                expected_revision=1, name='Successor', members=members[:2])

    with ThreadPoolExecutor(max_workers=1) as pool:
        def interleave(_connection, _cursor, statement, _parameters, _context, _many):
            if (not committed and statement.lstrip().startswith('SELECT')
                    and 'static_instrument_scope_revisions' in statement):
                committed.append(None)  # Also prevents the writer's own reads from recursing.
                committed[0] = pool.submit(append).result(timeout=20)

        sa.event.listen(engine, 'before_cursor_execute', interleave)
        try:
            with Session(engine) as reader:
                observed = _consume_scope(reader, consumer)
                assert committed and committed[0]['current_revision'] == 2
                expected = dict(committed[0])
                if consumer == 'historical':
                    expected.update({key: first[key] for key in ('address', 'membership_address', 'snapshot', 'member_labels')})
                assert observed == expected
                assert _consume_scope(reader, consumer) == expected
        finally:
            sa.event.remove(engine, 'before_cursor_execute', interleave)


@pytest.mark.parametrize('consumer', ['current', 'historical', 'list'])
def test_read_still_refuses_unexplained_extra_revision(read_race_db, consumer):
    """A corrupt head must not be fixed by limiting the chain to its stale count."""
    engine, members = read_race_db
    create(engine, members[:1])
    with Session(engine) as writer, writer.begin():
        scopes.revise_scope(writer, owner_id='a', project_id='pa', scope_id='scope.main',
                            expected_revision=1, name='Successor', members=members[:2])
    with engine.begin() as connection:
        connection.execute(sa.text('UPDATE static_instrument_scopes SET revision=1'))
    with Session(engine) as reader, pytest.raises(scopes.ScopeInvalid, match='root/revision mismatch'):
        _consume_scope(reader, consumer)


def test_read_refuses_hash_valid_successor_that_skips_its_predecessor(db):
    from app.ir.hashing import canonical_json, content_address
    engine, members = db
    first = create(engine, members[:1])
    with Session(engine) as writer, writer.begin():
        scopes.revise_scope(writer, owner_id='a', project_id='pa', scope_id='scope.main',
                            expected_revision=1, name='Second', members=members[:2])
    # All copied fields, hashes and the FK are valid, but revision 3 illegally
    # points to revision 1. The reader must verify the complete predecessor chain.
    forged = {**first['snapshot'], 'revision': 3, 'predecessor': first['address']}
    with Session(engine) as writer, writer.begin():
        writer.add(StaticInstrumentScopeRevision(owner_id='a', project_id='pa',
            scope_id='scope.main', revision=3, predecessor=first['address'],
            address=content_address(forged), membership_address=first['membership_address'],
            canonical_json=canonical_json(forged)))
        writer.execute(sa.text('UPDATE static_instrument_scopes SET revision=3'))
    with Session(engine) as reader, pytest.raises(scopes.ScopeInvalid, match='predecessor chain'):
        scopes.get_scope(reader, owner_id='a', project_id='pa', scope_id='scope.main')


def test_provider_selection_keeps_first_receipt_and_is_owner_scoped(db):
    from app.core.provider_selections import load_provider_selection, ProviderSelectionNotFound
    from app.db.models import OwnerProviderInstrumentSelection, AuthorityCanonicalInstrument
    from app.ir.hashing import content_address
    engine, _ = db
    first = provider_selection(engine)
    later = provider_selection(engine, connection_id=99, observed_at=dt.datetime(2026, 9, 7, tzinfo=dt.timezone.utc))
    assert first == later
    assert first['selection_address'] == content_address(first['selection'])
    assert first['selection']['connection_id'] == 71
    assert first['selection']['observed_at'] == '2026-09-06T10:20:30.123456+00:00'
    foreign = provider_selection(engine, owner_id='b')
    another_account = provider_selection(engine, data_account_id='different-account')
    assert len({first['selection_address'], foreign['selection_address'], another_account['selection_address']}) == 3
    with Session(engine) as session:
        assert load_provider_selection(session, owner_id='a', selection_address=first['selection_address']) == first
        with pytest.raises(ProviderSelectionNotFound):
            load_provider_selection(session, owner_id='b', selection_address=first['selection_address'])
        assert session.scalar(sa.select(sa.func.count()).select_from(OwnerProviderInstrumentSelection)) == 3
        assert session.scalar(sa.select(sa.func.count()).select_from(AuthorityCanonicalInstrument)) == 33
    table = OwnerProviderInstrumentSelection.__table__
    assert {fk.column.table.name for fk in table.foreign_keys} == {'organizations'}


def test_provider_selection_concurrent_same_descriptor_converges(db):
    import time
    from app.db.models import OwnerProviderInstrumentSelection
    engine, _ = db
    barrier = threading.Barrier(2)
    def writer(index):
        barrier.wait(timeout=5)
        return provider_selection(engine, connection_id=71+index,
            observed_at=dt.datetime(2026, 9, 6, 10, 20, 30, index, tzinfo=dt.timezone.utc))
    def delay_insert(*_args):
        time.sleep(0.05)
    sa.event.listen(OwnerProviderInstrumentSelection, 'before_insert', delay_insert)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(writer, (0, 1)))
    finally:
        sa.event.remove(OwnerProviderInstrumentSelection, 'before_insert', delay_insert)
    assert results[0] == results[1]
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(OwnerProviderInstrumentSelection)) == 1


@pytest.mark.parametrize('changes', [
    {'connection_id': True}, {'connection_id': 0}, {'provider': 'OTHER'},
    {'observed_at': dt.datetime(2026, 9, 6)},
    {'reference': provider_reference(last_price='1')},
    {'reference': provider_reference(strike='0.0')}, {'owner_id': ' a'},
])
def test_provider_selection_rejects_open_or_unnormalized_facts_before_write(db, changes):
    from app.db.models import OwnerProviderInstrumentSelection
    engine, _ = db
    with pytest.raises(ValueError):
        provider_selection(engine, **changes)
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(OwnerProviderInstrumentSelection)) == 0


def test_v2_watchlist_saves_unconfigured_reference_and_exact_labels_without_history(db):
    from app.ir.hashing import content_address
    engine, members = db
    selected = provider_selection(engine)
    pointers = [provider_member(selected), {'kind': 'CANONICAL', 'instrument_address': members[0]}]
    saved = create(engine, pointers)
    expected = [pointers[1], pointers[0]]
    assert saved['snapshot']['schema'] == 'static-instrument-scope/2'
    assert saved['snapshot']['members'] == expected
    assert saved['address'] == content_address(saved['snapshot'])
    assert saved['membership_address'] == content_address({'schema': 'static-instrument-membership/2', 'members': expected})
    assert saved['member_labels'] == [
        {'member': pointers[1], 'display_name': None, 'provider_reference': None, 'observed_at': None},
        {'member': pointers[0], 'display_name': 'SMALLCAP-X · NSE',
         'provider_reference': selected['selection']['reference'], 'observed_at': selected['selection']['observed_at']},
    ]
    with Session(engine) as session:
        assert scopes.get_scope(session, owner_id='a', project_id='pa', scope_id='scope.main') == saved
        assert scopes.list_scopes(session, owner_id='a', project_id='pa')['items'] == [saved]
    with engine.connect() as connection:
        scopes.validate_persisted_scopes(connection)


def test_v1_to_v2_is_explicit_and_preserves_prior_bytes_without_downgrade(db):
    engine, members = db
    first = create(engine, members[:1])
    assert first['snapshot']['schema'] == 'static-instrument-scope/1'
    with Session(engine) as session:
        original = session.scalar(sa.select(StaticInstrumentScopeRevision.canonical_json))
    selected = provider_selection(engine)
    with Session(engine) as session, session.begin():
        second = scopes.revise_scope(session, owner_id='a', project_id='pa', scope_id='scope.main',
            expected_revision=1, name='With provider references',
            members=[{'kind': 'CANONICAL', 'instrument_address': members[0]}, provider_member(selected)])
    with Session(engine) as session, session.begin(), pytest.raises(scopes.ScopeInvalid, match='downgrade'):
        scopes.revise_scope(session, owner_id='a', project_id='pa', scope_id='scope.main', expected_revision=2,
                            name='Invalid downgrade', members=members[:1])
    with Session(engine) as session:
        old = scopes.get_scope(session, owner_id='a', project_id='pa', scope_id='scope.main', revision=1)
        assert old['snapshot'] == first['snapshot'] and old['address'] == first['address']
        assert old['membership_address'] == first['membership_address']
        assert session.scalar(sa.select(StaticInstrumentScopeRevision.canonical_json).where(
            StaticInstrumentScopeRevision.revision == 1)) == original
        assert scopes.get_scope(session, owner_id='a', project_id='pa', scope_id='scope.main') == second


@pytest.mark.parametrize('kind', ['foreign', 'unknown', 'canonical_alias', 'duplicate', 'extra', 'mixed'])
def test_v2_watchlist_refuses_unattributed_or_ambiguous_members(db, kind):
    engine, members = db
    selected = provider_selection(engine, owner_id='b' if kind == 'foreign' else 'a')
    pointer = provider_member(selected)
    bad = {
        'foreign': [pointer], 'unknown': [{'kind': 'PROVIDER_REFERENCE', 'selection_address': 'sha256:'+'0'*64}],
        'canonical_alias': [{'kind': 'CANONICAL', 'instrument_address': selected['selection_address']}],
        'duplicate': [pointer, pointer], 'extra': [{**pointer, 'instrument_address': members[0]}],
        'mixed': [pointer, members[0]],
    }[kind]
    with pytest.raises(scopes.ScopeInvalid):
        create(engine, bad)


@pytest.mark.parametrize('referenced', [False, True])
def test_provider_selection_copied_facts_and_restore_hook_refuse_corruption(db, referenced):
    from app.core.provider_selections import load_provider_selection, ProviderSelectionInvalid, validate_persisted_provider_selections
    from app.db.copy_contract import validate_content_addresses, CopyRefusal
    engine, _ = db
    selected = provider_selection(engine)
    if referenced:
        create(engine, [provider_member(selected)])
    with engine.begin() as connection:
        connection.exec_driver_sql('DROP TRIGGER owner_provider_instrument_selections_refuse_update')
        connection.exec_driver_sql('UPDATE owner_provider_instrument_selections SET connection_id=999')
    with Session(engine) as session, pytest.raises(ProviderSelectionInvalid, match='copied'):
        load_provider_selection(session, owner_id='a', selection_address=selected['selection_address'])
    with engine.connect() as connection, pytest.raises(ProviderSelectionInvalid, match='copied'):
        validate_persisted_provider_selections(connection)
    with engine.connect() as connection, pytest.raises(CopyRefusal, match='static scope'):
        validate_content_addresses(connection, Base.metadata)


def test_provider_selection_native_immutability_keeps_user_metadata(db):
    from app.db.models import OwnerProviderInstrumentSelection
    engine, _ = db
    provider_selection(engine)
    for operation in (sa.update(OwnerProviderInstrumentSelection).values(connection_id=99),
                      sa.delete(OwnerProviderInstrumentSelection)):
        with engine.begin() as connection, pytest.raises(sa.exc.DBAPIError, match='immutable'):
            connection.execute(operation)


def test_v2_restore_refuses_hash_valid_v1_downgrade_in_the_chain(db):
    from app.ir.hashing import canonical_json, content_address
    engine, members = db
    first = create(engine, [{'kind': 'CANONICAL', 'instrument_address': members[0]}])
    forged = {**first['snapshot'], 'schema': scopes.SCHEMA, 'revision': 2,
              'predecessor': first['address'], 'members': members[:1]}
    with Session(engine) as session, session.begin():
        session.add(StaticInstrumentScopeRevision(owner_id='a', project_id='pa', scope_id='scope.main', revision=2,
            predecessor=first['address'], address=content_address(forged),
            membership_address=content_address({'schema': scopes.MEMBERSHIP_SCHEMA, 'members': members[:1]}),
            canonical_json=canonical_json(forged)))
        session.execute(sa.text('UPDATE static_instrument_scopes SET revision=2'))
    with engine.connect() as connection, pytest.raises(scopes.ScopeInvalid, match='downgrade'):
        scopes.validate_persisted_scopes(connection)


@pytest.mark.parametrize('corruption', [
    'first_predecessor', 'missing_predecessor', 'malformed_predecessor',
    'address', 'membership_address', 'owner_id', 'noncanonical_json', 'extra_field',
])
def test_v2_revision_decoder_refuses_forged_copied_fields_and_predecessors(db, corruption):
    from types import SimpleNamespace
    engine, members = db
    first = create(engine, [{'kind': 'CANONICAL', 'instrument_address': members[0]}])
    with Session(engine) as session, session.begin():
        second = scopes.revise_scope(session, owner_id='a', project_id='pa', scope_id='scope.main',
            expected_revision=1, name='Second', members=first['snapshot']['members'])
    selected = first if corruption == 'first_predecessor' else second
    with Session(engine) as session:
        stored = session.scalar(sa.select(StaticInstrumentScopeRevision).where(
            StaticInstrumentScopeRevision.revision == selected['snapshot']['revision']))
        row = SimpleNamespace(**{column.name: getattr(stored, column.name)
                                 for column in StaticInstrumentScopeRevision.__table__.columns})
    assert scopes.validate_revision(row) == selected['snapshot']
    if corruption == 'first_predecessor': row.predecessor = first['address']
    elif corruption == 'missing_predecessor': row.predecessor = None
    elif corruption == 'malformed_predecessor': row.predecessor = 'not-an-address'
    elif corruption in ('address', 'membership_address'): setattr(row, corruption, 'sha256:'+'0'*64)
    elif corruption == 'owner_id': row.owner_id = 'b'
    elif corruption == 'noncanonical_json': row.canonical_json = json.dumps(selected['snapshot'], sort_keys=True)
    else: row.canonical_json = json.dumps({**selected['snapshot'], 'extra': 'unadmitted'})
    with pytest.raises(scopes.ScopeInvalid, match='canonical revision'):
        scopes.validate_revision(row)
