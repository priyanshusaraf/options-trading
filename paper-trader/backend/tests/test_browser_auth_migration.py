"""0042→0043 additive schema, failure rollback, real concurrency and restore."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
import datetime as dt
import importlib.util
import json
import subprocess
import sys
import os

from alembic import command
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from app.accounts import browser_auth as auth
from app.db import migrate
from app.db.models import Base, BrowserAuthAttempt, BrowserCredential, UserSession
from app.db.copy_contract import stream_table_summary, _validate_semantic_ownership, CopyRefusal
from tests.test_schema_migrations import _build_from_baseline_at_revision
from tests.test_capital_admission_schema import _contract

TABLES = ('browser_credentials', 'enrollment_invites', 'browser_sessions', 'browser_auth_attempts')


def upgrade(engine):
    with engine.begin() as c:
        command.upgrade(migrate.alembic_config(c), '0043')


def prior_pg(engine, monkeypatch):
    from tests import test_postgres_execution_schema as historical
    metadata = sa.MetaData()
    for table in Base.metadata.sorted_tables:
        if table.name not in (*TABLES, 'static_instrument_scopes', 'static_instrument_scope_revisions'):
            table.to_metadata(metadata)
    with monkeypatch.context() as patch, engine.begin() as c:
        patch.setattr(historical, 'Base', SimpleNamespace(metadata=metadata))
        historical._install_repository_0037_catalog(c)
        command.stamp(migrate.alembic_config(c), '0037')
        command.upgrade(migrate.alembic_config(c), '0042')


def snapshot(engine, names):
    present = set(sa.inspect(engine).get_table_names()).intersection(names)
    reflected = sa.MetaData()
    reflected.reflect(bind=engine, only=present, resolve_fks=False)
    with engine.connect() as c:
        return {name: stream_table_summary(c, reflected.tables[name]) for name in sorted(present)}


def old_schema(engine, names):
    inspector = sa.inspect(engine)
    present = set(inspector.get_table_names()).intersection(names)
    return {name: {kind: json.dumps(getattr(inspector, 'get_' + kind)(name), default=str, sort_keys=True)
                   for kind in ['columns', 'pk_constraint', 'foreign_keys', 'unique_constraints', 'indexes', 'check_constraints']}
            for name in sorted(present)}


def assert_atomic_failure(engine):
    def fail_second(conn, cursor, statement, parameters, context, executemany):
        if 'CREATE TABLE enrollment_invites' in statement:
            raise RuntimeError('synthetic interrupted migration')
    sa.event.listen(engine, 'before_cursor_execute', fail_second)
    try:
        with pytest.raises(RuntimeError, match='synthetic interrupted'):
            upgrade(engine)
    finally:
        sa.event.remove(engine, 'before_cursor_execute', fail_second)
    assert migrate.schema_version(engine) == '0042'
    assert not set(TABLES).intersection(sa.inspect(engine).get_table_names())
    upgrade(engine)
    upgrade(engine)
    assert migrate.schema_version(engine) == '0043'


def exercise_lifecycle(engine, monkeypatch):
    factory = sessionmaker(engine)
    monkeypatch.setattr(auth, 'SessionLocal', factory)
    invite = auth.create_invite('race@example.test')
    def enroll(_):
        try:
            return auth.enroll('race@example.test', 'synthetic concurrency passphrase', 'Race', invite.token)
        except auth.AuthRefusal:
            return None
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(enroll, range(2)))
    assert sum(r is not None for r in results) == 1
    issued = next(r for r in results if r)
    assert auth.browser_principal(issued.token).kind == 'user'
    return issued


def test_sqlite_upgrade_interruption_restore_and_preservation(tmp_path, monkeypatch):
    engine = _build_from_baseline_at_revision(tmp_path, 'auth-prior', '0042')
    old_names = [t for t in Base.metadata.tables if t not in TABLES]
    before = snapshot(engine, old_names)
    schemas = old_schema(engine, old_names)
    assert_atomic_failure(engine)
    assert snapshot(engine, old_names) == before
    assert old_schema(engine, old_names) == schemas
    issued = exercise_lifecycle(engine, monkeypatch)
    import sqlite3
    restored_path = tmp_path / 'restored.db'
    with sqlite3.connect(engine.url.database) as source, sqlite3.connect(restored_path) as target:
        source.backup(target)
    restored = sa.create_engine('sqlite:///' + str(restored_path))
    assert snapshot(restored, list(Base.metadata.tables)) == snapshot(engine, list(Base.metadata.tables))
    monkeypatch.setattr(auth, 'SessionLocal', sessionmaker(restored))
    assert auth.bootstrap(issued.token)['user']['display_name'] == 'Race'
    auth.mutate_session(issued.token, 'logout')
    with pytest.raises(auth.AuthRefusal):
        auth.browser_principal(issued.token)
    fresh = sa.create_engine('sqlite:///' + str(tmp_path / 'fresh.db'))
    Base.metadata.create_all(fresh)
    for table in TABLES:
        assert _contract(engine, table) == _contract(fresh, table)
    for e in [engine, restored, fresh]:
        e.dispose()


def test_pg16_upgrade_restore_concurrency(pg_sandbox, monkeypatch, tmp_path):
    engine, restored = pg_sandbox.engine('auth_upgrade'), pg_sandbox.engine('auth_restore')
    with engine.connect() as c:
        assert c.exec_driver_sql('SHOW server_version').scalar().startswith('16.')
    prior_pg(engine, monkeypatch)
    old_names = [t for t in Base.metadata.tables if t not in TABLES]
    before = snapshot(engine, old_names)
    schemas = old_schema(engine, old_names)
    assert_atomic_failure(engine)
    assert snapshot(engine, old_names) == before
    assert old_schema(engine, old_names) == schemas
    fresh = pg_sandbox.engine('auth_fresh')
    assert migrate.init_schema(fresh, create_all=lambda: Base.metadata.create_all(fresh),
                               legacy_migrate=lambda: pytest.fail('unexpected legacy migration'),
                               expected_tables=Base.metadata.tables) == '0049'
    for table in TABLES:
        assert _contract(engine, table) == _contract(fresh, table)
    issued = exercise_lifecycle(engine, monkeypatch)
    from app.operations.postgresql_backup import resolve_postgresql16_tools
    # Independent Python processes share only PostgreSQL, not the Python lock
    # or ORM sessions. Exactly ten attempts may pass the account window.
    code = '''
import json,sys
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from app.accounts import browser_auth as auth
from app.core.config import get_settings
auth.SessionLocal=sessionmaker(sa.create_engine(sys.argv[1]))
get_settings().browser_auth_counter_secret='a1'*32
passed=0
for _ in range(10):
    try:
        auth.admit_attempt('process@example.test','synthetic-client')
        passed+=1
    except auth.AuthRefusal as error:
        assert error.status==429
print(json.dumps({'passed':passed}))
'''
    env = dict(os.environ, PT_DISABLE_DOTENV='1')
    workers = [subprocess.Popen([sys.executable, '-c', code, str(engine.url)], env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
    results = [worker.communicate(timeout=60) for worker in workers]
    assert all(worker.returncode == 0 for worker in workers)
    assert sum(json.loads(stdout)['passed'] for stdout, _ in results) == 10
    dump, restore = resolve_postgresql16_tools()
    artifact = tmp_path / 'auth.dump'
    source_url = str(sa.engine.make_url(pg_sandbox.url('auth_upgrade')).set(drivername='postgresql'))
    target_url = str(sa.engine.make_url(pg_sandbox.url('auth_restore')).set(drivername='postgresql'))
    subprocess.run([str(dump), '--format=custom', '--no-owner', '--no-acl', f'--file={artifact}', source_url], check=True, capture_output=True)
    subprocess.run([str(restore), '--no-owner', '--no-acl', '--exit-on-error', f'--dbname={target_url}', str(artifact)], check=True, capture_output=True)
    assert migrate.schema_version(restored) == '0043'
    assert snapshot(restored, list(Base.metadata.tables)) == snapshot(engine, list(Base.metadata.tables))
    monkeypatch.setattr(auth, 'SessionLocal', sessionmaker(restored))
    assert auth.bootstrap(issued.token)['user']['display_name'] == 'Race'
    with restored.connect() as c:
        _validate_semantic_ownership(c, Base.metadata)
    with pytest.raises(CopyRefusal, match='credential profile'), restored.begin() as c:
        c.execute(sa.update(BrowserCredential).values(verifier='unsupported-profile'))
        _validate_semantic_ownership(c, Base.metadata)


def test_counter_capacity_cleanup_and_expiry(monkeypatch, tmp_path):
    from app.core.config import get_settings
    engine = sa.create_engine('sqlite:///' + str(tmp_path / 'counters.db'))
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    monkeypatch.setattr(auth, 'SessionLocal', factory)
    monkeypatch.setattr(get_settings(), 'browser_auth_counter_secret', 'a1'*32)
    now = dt.datetime(2026, 8, 29, 1, 0)
    monkeypatch.setattr(auth, '_now', lambda: now)
    with engine.begin() as c:
        c.execute(sa.insert(BrowserAuthAttempt), [{'key_digest': f'{i:064x}', 'attempts': 1,
            'expires_at': now + dt.timedelta(minutes=15)} for i in range(auth.MAX_COUNTERS)])
    with pytest.raises(auth.AuthRefusal) as refused:
        auth.admit_attempt('new@example.test', 'synthetic-client')
    assert refused.value.status == 429
    with factory() as s:
        assert s.scalar(sa.select(sa.func.count()).select_from(BrowserAuthAttempt)) == auth.MAX_COUNTERS
    now += dt.timedelta(minutes=16)
    auth.admit_attempt('new@example.test', 'synthetic-client')
    with factory() as s:
        rows = s.scalars(sa.select(BrowserAuthAttempt)).all()
        assert len(rows) == 2
        assert all(row.attempts == 1 for row in rows)
        assert 'new@example.test' not in repr(rows)
    engine.dispose()


@pytest.mark.parametrize('revision', ['0049', None], ids=['outdated-schema', 'current-schema'])
def test_local_invite_cli_delivers_only_invite_and_never_precreates_user(tmp_path, revision):
    from app.db.models import Base, EnrollmentInvite
    revision = revision or migrate.head_revision()
    if revision == migrate.head_revision():
        engine = sa.create_engine('sqlite:///' + str(tmp_path / 'cli.db'))
        assert migrate.init_schema(
            engine, create_all=lambda: Base.metadata.create_all(engine),
            legacy_migrate=lambda: pytest.fail('fresh invitation database attempted legacy migration'),
            expected_tables=Base.metadata.tables,
        ) == revision
    else:
        engine = _build_from_baseline_at_revision(tmp_path, 'cli.db', revision)
    identity_tables = ['users', 'organizations', 'memberships', 'user_sessions']
    before = snapshot(engine, identity_tables)
    command_line = [sys.executable, str(Path(__file__).resolve().parents[1]/'scripts/create_enrollment_invite.py'),
                    '--database', engine.url.database, '--email', 'cli@example.test']
    env = dict(os.environ, PT_DISABLE_DOTENV='1', PT_PROVIDER='mock', PT_EXECUTION='paper', PT_LIVE_ACK='')
    result = subprocess.run(command_line, env=env, capture_output=True, text=True, timeout=30)
    if revision != migrate.head_revision():
        assert result.returncode != 0 and not result.stdout
        assert 'database must already have the current schema' in result.stderr
        assert migrate.schema_version(engine) == revision
        assert snapshot(engine, identity_tables) == before
        with engine.connect() as c:
            assert c.scalar(sa.select(sa.func.count()).select_from(EnrollmentInvite)) == 0
        engine.dispose()
        return
    assert result.returncode == 0
    assert auth.TOKEN_PATTERN.fullmatch(result.stdout.strip())
    assert not result.stderr
    assert snapshot(engine, identity_tables) == before
    with engine.connect() as c:
        assert c.scalar(sa.select(sa.func.count()).select_from(EnrollmentInvite)) == 1
    denied = subprocess.run(command_line, env=dict(env, PT_DISABLE_DOTENV='0'), capture_output=True, text=True, timeout=30)
    assert denied.returncode != 0 and not denied.stdout
    engine.dispose()


def test_partial_schema_and_destructive_downgrade_refuse(tmp_path):
    engine = _build_from_baseline_at_revision(tmp_path, 'partial.db', '0042')
    BrowserAuthAttempt.__table__.create(engine)
    with pytest.raises(RuntimeError, match='partial/unproven'):
        upgrade(engine)
    assert migrate.schema_version(engine) == '0042'
    assert set(TABLES).intersection(sa.inspect(engine).get_table_names()) == {'browser_auth_attempts'}
    engine.dispose()
    complete = _build_from_baseline_at_revision(tmp_path, 'complete.db', '0043')
    before = snapshot(complete, list(Base.metadata.tables))
    with pytest.raises(RuntimeError, match='destructive downgrade'), complete.begin() as c:
        command.downgrade(migrate.alembic_config(c), '0042')
    assert migrate.schema_version(complete) == '0043'
    assert snapshot(complete, list(Base.metadata.tables)) == before
    complete.dispose()


def test_exhausted_client_cannot_allocate_new_identity_counters(tmp_path, monkeypatch):
    from app.core.config import get_settings
    engine = sa.create_engine('sqlite:///' + str(tmp_path / 'client-bound.db'))
    BrowserAuthAttempt.__table__.create(engine)
    monkeypatch.setattr(auth, 'SessionLocal', sessionmaker(engine))
    monkeypatch.setattr(get_settings(), 'browser_auth_counter_secret', 'a1'*32)
    monkeypatch.setattr(auth, '_now', lambda: dt.datetime(2026, 8, 29, 1, 0))
    for i in range(60):
        auth.admit_attempt(f'account{i}@example.test', 'same-trusted-client')
    before = snapshot(engine, ['browser_auth_attempts'])
    assert before['browser_auth_attempts']['rows'] == 61
    for i in range(100):
        with pytest.raises(auth.AuthRefusal) as refused:
            auth.admit_attempt(f'new{i}@example.test', 'same-trusted-client')
        assert refused.value.status == 429
    assert snapshot(engine, ['browser_auth_attempts']) == before
    engine.dispose()


@pytest.mark.parametrize('dialect', ['sqlite', 'postgresql'])
def test_copy_contract_rejects_future_and_over_capacity_attempt_windows(tmp_path, dialect, request, monkeypatch):
    from app.db.copy_contract import _validate_semantic_ownership
    if dialect == 'postgresql':
        engine = request.getfixturevalue('pg_sandbox').engine('attempt_copy')
        migrate.init_schema(engine, create_all=lambda: Base.metadata.create_all(engine),
                            legacy_migrate=lambda: pytest.fail('unexpected legacy migration'),
                            expected_tables=Base.metadata.tables)
    else:
        engine = sa.create_engine('sqlite:///' + str(tmp_path / 'attempt-copy.db'))
        Base.metadata.create_all(engine)
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    with pytest.raises(CopyRefusal, match='attempt window'), engine.begin() as c:
        c.execute(sa.insert(BrowserAuthAttempt).values(key_digest='a'*64, attempts=1,
                  expires_at=now + dt.timedelta(days=365)))
        _validate_semantic_ownership(c, Base.metadata)
    with pytest.raises(CopyRefusal, match='attempt counter capacity'), engine.begin() as c:
        c.execute(sa.insert(BrowserAuthAttempt), [{'key_digest': f'{i:064x}', 'attempts': 1,
                  'expires_at': now - dt.timedelta(minutes=1)} for i in range(auth.MAX_COUNTERS + 1)])
        _validate_semantic_ownership(c, Base.metadata)
    with engine.begin() as c:
        c.execute(sa.insert(BrowserAuthAttempt).values(key_digest='b'*64, attempts=60,
                  expires_at=now - dt.timedelta(minutes=1)))
        _validate_semantic_ownership(c, Base.metadata)
    monkeypatch.setattr(auth, 'SessionLocal', sessionmaker(engine))
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), 'browser_auth_counter_secret', 'a1'*32)
    auth.admit_attempt('recovered@example.test', 'recovered-client')
    with engine.connect() as c:
        assert c.scalar(sa.select(sa.func.count()).select_from(BrowserAuthAttempt)) == 2
    engine.dispose()
