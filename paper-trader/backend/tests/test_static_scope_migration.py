"""Real SQLite/PG16 upgrade, transaction, CAS and restore evidence."""
from concurrent.futures import ThreadPoolExecutor
import json
import re
from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from alembic import command

from app.core import static_scopes as scopes
from app.db import migrate
from app.db.models import Base, StaticInstrumentScope, StaticInstrumentScopeRevision
from app.db.copy_contract import stream_table_summary, validate_content_addresses
from tests.test_static_scopes import seed, create
from tests.test_schema_migrations import _build_from_baseline_at_revision
from tests.test_capital_admission_schema import _contract, _seed_scope, _insert_policy_and_decision, TABLES as MONEY_TABLES

TABLES = ('static_instrument_scopes', 'static_instrument_scope_revisions')


@pytest.fixture(autouse=True)
def _freeze_provider_selection_migration(request, monkeypatch):
    if request.node.name.startswith("test_provider_selection_0054_"):
        monkeypatch.setattr(migrate, "head_revision", lambda: "0054")


def _upgrade(engine):
    with engine.begin() as connection:
        command.upgrade(migrate.alembic_config(connection), '0042')


def _prior_pg(engine, monkeypatch):
    # Reuse the accepted historical projection, explicitly excluding this additive slice.
    from tests import test_postgres_execution_schema as historical
    metadata = sa.MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name not in (*TABLES, "watchlist_monitoring_revisions"):
            table.to_metadata(metadata)
    with monkeypatch.context() as patch, engine.begin() as connection:
        patch.setattr(historical, 'Base', SimpleNamespace(metadata=metadata))
        historical._install_repository_0037_catalog(connection)
        command.stamp(migrate.alembic_config(connection), '0037')
        command.upgrade(migrate.alembic_config(connection), '0041')
    assert migrate.schema_version(engine) == '0041'
    assert set(TABLES).isdisjoint(sa.inspect(engine).get_table_names())


def _money(engine):
    with engine.connect() as c:
        return {name: {'rows': [tuple(row) for row in c.execute(sa.text(f'SELECT * FROM {name} ORDER BY 1'))],
                       'schema': _contract(engine, name)} for name in MONEY_TABLES}


def _restored_money_matches(source, restored, engine):
    # PG16 dump/reparse distributes ARRAY varchar→text casts into each element.
    # Normalize only that exact enum-array spelling, preserving all other SQL.
    def enum_array(sql):
        pattern = r"array\[(?:'[^']*'::charactervarying(?:::text)?,?)+\](?:::text\[\])?"
        return re.sub(pattern, lambda m: m[0].replace('::charactervarying::text',
                      '::charactervarying').removesuffix('::text[]'), sql)
    for name in MONEY_TABLES:
        assert restored[name]['rows'] == source[name]['rows']
        for field in source[name]['schema']:
            left, right = source[name]['schema'][field], restored[name]['schema'][field]
            if field == 'checks':
                left = [(key, enum_array(sql)) for key, sql in left]
                right = [(key, enum_array(sql)) for key, sql in right]
            assert left == right, (name, field, left, right)
    table = Base.metadata.tables['sizing_policies']
    with engine.connect() as c:
        policy = dict(c.execute(sa.select(table)).mappings().one())
    for field, value in [('mode', 'INVALID'), ('currency', 'inr'), ('policy_address', 'bad'),
                         ('fee_buffer_minor', -1), ('fixed_units', 0)]:
        row = dict(policy, policy_address='sha256:'+'f'*64)
        row[field] = value
        with pytest.raises(sa.exc.DBAPIError), engine.begin() as c:
            c.execute(table.insert().values(**row))
    with pytest.raises(sa.exc.DBAPIError, match='immutable'), engine.begin() as c:
        c.execute(table.update().values(policy_id='rewrite'))


def _cas(engine, members):
    first = create(engine, members[:1])
    barrier = threading.Barrier(2)
    def writer(index):
        barrier.wait()
        with Session(engine) as s:
            try:
                with s.begin():
                    return scopes.revise_scope(s, owner_id='a', project_id='pa', scope_id='scope.main',
                        expected_revision=1, name=f'Writer {index}', members=members[:index+2])
            except scopes.ScopeConflict:
                return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(writer, [0, 1]))
    assert results.count('conflict') == 1
    winner = next(r for r in results if isinstance(r, dict))
    assert winner['snapshot']['predecessor'] == first['address']
    with Session(engine) as s:
        assert s.scalar(sa.select(sa.func.count()).select_from(StaticInstrumentScopeRevision)) == 2
    return winner


def _summary(engine):
    with engine.connect() as connection:
        validate_content_addresses(connection, Base.metadata)
        return {name: stream_table_summary(connection, Base.metadata.tables[name]) for name in TABLES}


def _interrupt_and_upgrade(engine):
    def interrupt(_c, _cursor, statement, _parameters, _context, _many):
        if 'CREATE TABLE STATIC_INSTRUMENT_SCOPE_REVISIONS' in ' '.join(statement.upper().split()):
            raise RuntimeError('injected 0042 interruption')
    sa.event.listen(engine, 'after_cursor_execute', interrupt)
    try:
        with pytest.raises(RuntimeError, match='injected 0042'):
            _upgrade(engine)
    finally:
        sa.event.remove(engine, 'after_cursor_execute', interrupt)
    assert migrate.schema_version(engine) == '0041'
    assert set(TABLES).isdisjoint(sa.inspect(engine).get_table_names())
    engine.dispose()
    _upgrade(engine)
    _upgrade(engine)
    assert migrate.schema_version(engine) == '0042'


def test_sqlite_upgrade_interruption_money_cas_and_restore(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, 'static-0041.db', '0041')
    _seed_scope(engine)
    with engine.begin() as c:
        _insert_policy_and_decision(c)
    money = _money(engine)
    _interrupt_and_upgrade(engine)
    assert _money(engine) == money
    fresh = sa.create_engine(f'sqlite:///{tmp_path}/fresh.db')
    Base.metadata.create_all(fresh)
    for name in TABLES:
        assert _contract(engine, name) == _contract(fresh, name)
    members = seed(engine)
    winner = _cas(engine, members)
    summary = _summary(engine)
    import sqlite3
    with sqlite3.connect(engine.url.database) as source, sqlite3.connect(tmp_path / 'restored.db') as target:
        source.backup(target)
    restored = sa.create_engine(f'sqlite:///{tmp_path}/restored.db')
    assert _summary(restored) == summary
    restored_money = _money(restored)
    _restored_money_matches(money, restored_money, restored)
    with Session(restored) as s:
        assert scopes.get_scope(s, owner_id='a', project_id='pa', scope_id='scope.main') == winner
    # A real new interpreter reopens the exact persistent revision.
    code = """import json,sys; from sqlalchemy import create_engine; from sqlalchemy.orm import Session
from app.core.static_scopes import get_scope
with Session(create_engine(sys.argv[1])) as s:
 print(json.dumps(get_scope(s,owner_id='a',project_id='pa',scope_id='scope.main'),sort_keys=True))
"""
    import sys
    result = subprocess.run([sys.executable, '-c', code, str(restored.url)], check=True, capture_output=True, text=True)
    assert json.loads(result.stdout) == winner
    for e in (engine, fresh, restored):
        e.dispose()


def test_postgresql16_upgrade_interruption_money_cas_and_restore(pg_sandbox, monkeypatch, tmp_path):
    fresh, upgraded, restored = [pg_sandbox.engine('static_'+r) for r in ('fresh', 'upgrade', 'restore')]
    with fresh.connect() as c:
        version = c.execute(sa.text('SHOW server_version')).scalar_one()
        assert version.startswith('16.')
        print('PostgreSQL server', version)
    assert migrate.init_schema(fresh, create_all=lambda: Base.metadata.create_all(fresh),
        legacy_migrate=lambda: pytest.fail('legacy migration'), expected_tables=Base.metadata.tables) == '0042'
    _prior_pg(upgraded, monkeypatch)
    _seed_scope(upgraded)
    with upgraded.begin() as c:
        _insert_policy_and_decision(c)
    money = _money(upgraded)
    _interrupt_and_upgrade(upgraded)
    assert _money(upgraded) == money
    for name in TABLES:
        assert _contract(upgraded, name) == _contract(fresh, name)
    members = seed(upgraded)
    winner = _cas(upgraded, members)
    summary = _summary(upgraded)
    from app.operations.postgresql_backup import resolve_postgresql16_tools
    pg_dump, pg_restore = resolve_postgresql16_tools()
    backup = tmp_path / 'static.dump'
    source_url = str(sa.engine.make_url(pg_sandbox.url('static_upgrade')).set(drivername='postgresql'))
    target_url = str(sa.engine.make_url(pg_sandbox.url('static_restore')).set(drivername='postgresql'))
    subprocess.run([str(pg_dump), '--format=custom', '--no-owner', '--no-acl', f'--file={backup}', source_url],
                   check=True, capture_output=True, text=True)
    subprocess.run([str(pg_restore), '--no-owner', '--no-acl', '--exit-on-error', f'--dbname={target_url}', str(backup)],
                   check=True, capture_output=True, text=True)
    assert migrate.schema_version(restored) == '0042'
    assert _summary(restored) == summary
    restored_money = _money(restored)
    _restored_money_matches(money, restored_money, restored)
    with Session(restored) as s:
        assert scopes.get_scope(s, owner_id='a', project_id='pa', scope_id='scope.main') == winner
    with restored.begin() as c, pytest.raises(sa.exc.DBAPIError, match='immutable'):
        c.execute(sa.update(StaticInstrumentScopeRevision).values(canonical_json='{}'))
    print('0041→0042; clean install; interrupted rollback/retry; two-writer CAS; PG dump/restore digests PASS')


@pytest.mark.parametrize('dialect', ['sqlite', 'postgresql'])
def test_partial_schema_refusal_and_nondestructive_policy(dialect, request, tmp_path, monkeypatch):
    if dialect == 'postgresql':
        engine = request.getfixturevalue('pg_sandbox').engine('static_partial')
        _prior_pg(engine, monkeypatch)
    else:
        engine = _build_from_baseline_at_revision(tmp_path, 'partial.db', '0041')
    with engine.begin() as c:
        c.execute(sa.text('CREATE TABLE static_instrument_scopes (wrong INTEGER)'))
        c.execute(sa.text('INSERT INTO static_instrument_scopes VALUES (7)'))
    with pytest.raises(RuntimeError, match='partial/unproven'):
        _upgrade(engine)
    assert migrate.schema_version(engine) == '0041'
    with engine.connect() as c:
        assert c.execute(sa.text('SELECT wrong FROM static_instrument_scopes')).scalar_one() == 7
    # Exercise the forward-only refusal without attempting any destructive downgrade.
    from importlib.util import module_from_spec, spec_from_file_location
    path = Path(__file__).parents[1] / 'migrations/versions/20260828_0042_static_instrument_scopes.py'
    spec = spec_from_file_location('static_migration', path)
    module = module_from_spec(spec); spec.loader.exec_module(module)
    with pytest.raises(RuntimeError, match='retained'):
        module.downgrade()


def test_sqlite_to_pg16_copy_contract_preserves_scope_row_keys_and_digests(pg_sandbox, tmp_path):
    from app.db.copy_contract import CopyPlane, copy_planes, verify_planes
    source = sa.create_engine(f'sqlite:///{tmp_path}/copy-source.db')
    migrate.init_schema(source, create_all=lambda: Base.metadata.create_all(source), legacy_migrate=lambda: None)
    members = seed(source)
    winner = _cas(source, members)
    source.dispose()  # Frozen local source, no writers during copy.
    destination = pg_sandbox.url('static_copy')
    def initialize(engine):
        migrate.init_schema(engine, create_all=lambda: Base.metadata.create_all(engine),
            legacy_migrate=lambda: pytest.fail('legacy migration'), expected_tables=Base.metadata.tables)
    def validate(engine):
        assert migrate.schema_version(engine) == '0042'
        migrate._validate_current_schema(engine, Base.metadata.tables)
    plane = CopyPlane(name='execution', source_path=Path(source.url.database).resolve(),
        destination_url=destination, metadata=Base.metadata, marker_table='alembic_version',
        source_head='0042', initialize_destination=initialize, validate_destination=validate)
    report = copy_planes([plane], batch_size=2)
    verify_planes([plane], report)
    with Session(pg_sandbox.engine('static_copy')) as s:
        assert scopes.get_scope(s, owner_id='a', project_id='pa', scope_id='scope.main') == winner
    assert _summary(source) == _summary(pg_sandbox.engine('static_copy'))


def _provider_selection_summary(engine):
    from app.db.models import OwnerProviderInstrumentSelection
    from app.core.provider_selections import validate_persisted_provider_selections
    with engine.connect() as connection:
        validate_persisted_provider_selections(connection)
        scopes.validate_persisted_scopes(connection)
        return stream_table_summary(connection, OwnerProviderInstrumentSelection.__table__)


def _provider_selection_upgrade_scope(engine, first, members):
    from tests.test_static_scopes import provider_selection, provider_member
    selected = provider_selection(engine)
    with Session(engine) as session, session.begin():
        saved = scopes.revise_scope(session, owner_id='a', project_id='pa', scope_id='scope.main',
            expected_revision=1, name='Unknown provider instrument',
            members=[{'kind': 'CANONICAL', 'instrument_address': members[0]}, provider_member(selected)])
    with Session(engine) as session:
        old = scopes.get_scope(session, owner_id='a', project_id='pa', scope_id='scope.main', revision=1)
        assert old['snapshot'] == first['snapshot'] and old['address'] == first['address']
    return saved


def test_provider_selection_0054_sqlite_upgrade_restore_and_immutability(tmp_path):
    import sqlite3
    from app.db.models import OwnerProviderInstrumentSelection
    engine = _build_from_baseline_at_revision(tmp_path, 'selections-0053.db', '0053')
    members = seed(engine)
    first = create(engine, members[:1])
    with engine.connect() as connection:
        scopes.validate_persisted_scopes(connection)  # Prior-head USER snapshots have no new table.
    _seed_scope(engine)
    with engine.begin() as connection:
        _insert_policy_and_decision(connection)
    before_money = _money(engine)
    assert migrate.upgrade_to_head(engine) == '0054'
    assert migrate.upgrade_to_head(engine) == '0054'
    assert _money(engine) == before_money
    fresh = sa.create_engine(f'sqlite:///{tmp_path}/selections-empty.db')
    assert migrate.init_schema(fresh, create_all=lambda: Base.metadata.create_all(fresh),
        legacy_migrate=lambda: pytest.fail('legacy migration'), expected_tables=Base.metadata.tables) == '0054'
    assert _contract(engine, OwnerProviderInstrumentSelection.__tablename__) == _contract(fresh, OwnerProviderInstrumentSelection.__tablename__)
    saved = _provider_selection_upgrade_scope(engine, first, members)
    summary = _provider_selection_summary(engine)
    with engine.begin() as connection, pytest.raises(RuntimeError, match='retains provider selections'):
        command.downgrade(migrate.alembic_config(connection), '0053')
    assert _provider_selection_summary(engine) == summary
    with sqlite3.connect(engine.url.database) as source, sqlite3.connect(tmp_path/'selections-restored.db') as target:
        source.backup(target)
    restored = sa.create_engine(f'sqlite:///{tmp_path}/selections-restored.db')
    assert migrate.schema_version(restored) == '0054'
    assert _provider_selection_summary(restored) == summary
    assert _money(restored) == before_money
    with Session(restored) as session:
        assert scopes.get_scope(session, owner_id='a', project_id='pa', scope_id='scope.main') == saved
    with restored.begin() as connection, pytest.raises(sa.exc.DBAPIError, match='immutable'):
        connection.execute(sa.delete(OwnerProviderInstrumentSelection))
    for current in (engine, fresh, restored):
        current.dispose()


@pytest.mark.parametrize('failure', ['partial', 'stale', 'interrupted'])
def test_provider_selection_0054_refuses_partial_or_stale_and_rolls_back_interruption(tmp_path, failure):
    table = 'owner_provider_instrument_selections'
    engine = _build_from_baseline_at_revision(tmp_path, 'selections-refusal.db', '0053')
    if failure == 'partial':
        with engine.begin() as connection:
            connection.exec_driver_sql(f'CREATE TABLE {table} (unproven INTEGER)')
        with pytest.raises(RuntimeError, match='partial'):
            migrate.upgrade_to_head(engine)
    elif failure == 'stale':
        with engine.begin() as connection:
            command.stamp(migrate.alembic_config(connection), '0052', purge=True)
        with pytest.raises(RuntimeError, match='0053'):
            migrate.upgrade_to_head(engine)
    else:
        def interrupt(_conn, _cursor, statement, *_args):
            if f'CREATE TABLE {table.upper()}' in ' '.join(statement.upper().split()):
                raise RuntimeError('injected selection DDL failure')
        sa.event.listen(engine, 'after_cursor_execute', interrupt)
        try:
            with pytest.raises(RuntimeError, match='injected selection'):
                migrate.upgrade_to_head(engine)
        finally:
            sa.event.remove(engine, 'after_cursor_execute', interrupt)
        assert table not in sa.inspect(engine).get_table_names()
        assert migrate.schema_version(engine) == '0053'
        assert migrate.upgrade_to_head(engine) == '0054'
    engine.dispose()


def test_provider_selection_0054_postgresql_upgrade_restore_and_dedupe(pg_sandbox, tmp_path):
    from app.db.models import OwnerProviderInstrumentSelection
    from tests.test_static_scopes import provider_selection
    table = OwnerProviderInstrumentSelection.__table__
    upgraded = pg_sandbox.engine('provider_selection_upgrade')
    fresh = pg_sandbox.engine('provider_selection_fresh')
    restored = pg_sandbox.engine('provider_selection_restored')
    # Construct the immediately previous accepted schema without replaying
    # historical SQLite-only migrations against PostgreSQL.
    with upgraded.begin() as connection:
        Base.metadata.create_all(connection, tables=[item for item in Base.metadata.sorted_tables if item.name != table.name])
        command.stamp(migrate.alembic_config(connection), '0053')
    members = seed(upgraded)
    first = create(upgraded, members[:1])
    assert migrate.init_schema(upgraded, create_all=lambda: pytest.fail('managed create_all'),
        legacy_migrate=lambda: pytest.fail('legacy migration'), expected_tables=Base.metadata.tables) == '0054'
    assert migrate.init_schema(fresh, create_all=lambda: Base.metadata.create_all(fresh),
        legacy_migrate=lambda: pytest.fail('legacy migration'), expected_tables=Base.metadata.tables) == '0054'
    assert _contract(upgraded, table.name) == _contract(fresh, table.name)
    saved = _provider_selection_upgrade_scope(upgraded, first, members)
    barrier = threading.Barrier(2)
    def save_again(index):
        barrier.wait(timeout=5)
        return provider_selection(upgraded, data_account_id='concurrent-new', connection_id=90+index)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save_again, (0, 1)))
    assert results[0] == results[1]
    summary = _provider_selection_summary(upgraded)
    from app.operations.postgresql_backup import resolve_postgresql16_tools
    pg_dump, pg_restore = resolve_postgresql16_tools()
    backup = tmp_path/'provider-selection.dump'
    source_url = str(sa.engine.make_url(pg_sandbox.url('provider_selection_upgrade')).set(drivername='postgresql'))
    target_url = str(sa.engine.make_url(pg_sandbox.url('provider_selection_restored')).set(drivername='postgresql'))
    subprocess.run([str(pg_dump), '--format=custom', '--no-owner', '--no-acl', f'--file={backup}', source_url],
                   check=True, capture_output=True, text=True)
    subprocess.run([str(pg_restore), '--no-owner', '--no-acl', '--exit-on-error', f'--dbname={target_url}', str(backup)],
                   check=True, capture_output=True, text=True)
    assert migrate.schema_version(restored) == '0054'
    assert _provider_selection_summary(restored) == summary
    with Session(restored) as session:
        assert scopes.get_scope(session, owner_id='a', project_id='pa', scope_id='scope.main') == saved
    with restored.begin() as connection, pytest.raises(sa.exc.DBAPIError, match='immutable'):
        connection.execute(sa.update(OwnerProviderInstrumentSelection).values(connection_id=999))
    assert migrate.init_schema(restored, create_all=lambda: pytest.fail('restore create_all'),
        legacy_migrate=lambda: pytest.fail('legacy migration'), expected_tables=Base.metadata.tables) == '0054'
