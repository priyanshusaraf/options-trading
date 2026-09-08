"""The shared PostgreSQL test-sandbox contract.

Every PostgreSQL-backed test owns a private set of uniquely named databases
created off the harness cluster (`PT_TEST_POSTGRES_URL`).  The contract:

1. Each target database is named ``pt_sandbox_<role>_<uuid>`` — never fixed.
2. Execution, research, and ledger targets are separate databases.
3. Every target is verified empty (no user tables in ``public``, no extra
   schemas) immediately after creation, before any engine is handed out.
4. ``close()`` drops exactly the databases this sandbox created and is
   idempotent; tests call it in ``finally`` (or use the context manager /
   ``pg_sandbox`` fixture) so cleanup survives setup and assertion failures.
5. No shared or fixed database name is ever dropped or altered.
6. Because names are unique per sandbox, two tests — in threads, processes,
   or pytest shards — can run against the same cluster without touching each
   other's state.
"""

from __future__ import annotations

import os
import uuid
from typing import Iterator

import sqlalchemy as sa
from sqlalchemy.engine import Engine, make_url

BASE_ENV = "PT_TEST_POSTGRES_URL"


def postgres_url_available() -> str | None:
    """Return the harness cluster URL, or None when PostgreSQL tests must skip."""
    return os.environ.get(BASE_ENV) or None


class PostgresSandbox:
    """A set of disposable, verified-empty databases owned by one test."""

    def __init__(self, base_url: str | None = None) -> None:
        resolved = base_url or postgres_url_available()
        if not resolved:
            raise RuntimeError(
                f"{BASE_ENV} is required to open a PostgresSandbox"
            )
        self._base_url = resolved
        self._urls: dict[str, str] = {}
        self._engines: dict[str, Engine] = {}
        self._closed = False

    def url(self, role: str) -> str:
        """Return (creating on first use) the URL for one isolated target."""
        if role in self._urls:
            return self._urls[role]
        if self._closed:
            raise RuntimeError("sandbox already closed")
        database = f"pt_sandbox_{role}_{uuid.uuid4().hex}"
        admin = sa.create_engine(self._base_url, isolation_level="AUTOCOMMIT", future=True)
        try:
            with admin.connect() as connection:
                exists = connection.execute(
                    sa.text("SELECT 1 FROM pg_database WHERE datname = :name"),
                    {"name": database},
                ).scalar()
                if exists:  # practically impossible with a fresh uuid4 hex
                    raise RuntimeError(f"refusing to reuse existing database {database}")
                connection.exec_driver_sql(f'CREATE DATABASE "{database}"')
        finally:
            admin.dispose()
        target = str(make_url(self._base_url).set(database=database))
        self._verify_empty(target, database)
        self._urls[role] = target
        return target

    @property
    def execution_url(self) -> str:
        return self.url("execution")

    @property
    def research_url(self) -> str:
        return self.url("research")

    @property
    def ledger_url(self) -> str:
        return self.url("ledger")

    def engine(self, role: str, **engine_kwargs) -> Engine:
        """Return a cached engine for one isolated target."""
        if role not in self._engines:
            connect_args = engine_kwargs.pop("connect_args", {})
            self._engines[role] = sa.create_engine(
                self.url(role), future=True, connect_args=connect_args, **engine_kwargs
            )
        return self._engines[role]

    @property
    def execution_engine(self) -> Engine:
        return self.engine("execution")

    @property
    def research_engine(self) -> Engine:
        return self.engine("research")

    def _verify_empty(self, target_url: str, database: str) -> None:
        probe = sa.create_engine(target_url, future=True)
        try:
            with probe.connect() as connection:
                tables = connection.execute(sa.text(
                    "SELECT count(*) FROM pg_tables "
                    "WHERE schemaname NOT IN ('pg_catalog', 'information_schema')"
                )).scalar_one()
                schemas = connection.execute(sa.text(
                    "SELECT count(*) FROM pg_namespace "
                    "WHERE nspname NOT IN ('public', 'information_schema') "
                    "AND nspname NOT LIKE 'pg_%'"
                )).scalar_one()
            if tables != 0 or schemas != 0:
                raise RuntimeError(
                    f"freshly created sandbox database {database!r} is not empty: "
                    f"tables={tables} extra_schemas={schemas}"
                )
        finally:
            probe.dispose()

    def close(self) -> None:
        """Dispose engines, then drop exactly the databases this sandbox created."""
        if self._closed:
            return
        self._closed = True
        for engine in self._engines.values():
            engine.dispose()
        admin = None
        try:
            admin = sa.create_engine(self._base_url, isolation_level="AUTOCOMMIT", future=True)
            for role, target in sorted(self._urls.items()):
                database = make_url(target).database
                with admin.connect() as connection:
                    exists = connection.execute(
                        sa.text("SELECT 1 FROM pg_database WHERE datname = :name"),
                        {"name": database},
                    ).scalar()
                    if not exists:
                        continue
                    connection.exec_driver_sql(f'DROP DATABASE "{database}" WITH (FORCE)')
        finally:
            if admin is not None:
                admin.dispose()
            self._urls.clear()
            self._engines.clear()

    def __enter__(self) -> "PostgresSandbox":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def open_sandbox() -> PostgresSandbox | None:
    """Open a sandbox when PostgreSQL is configured; otherwise return None."""
    if not postgres_url_available():
        return None
    return PostgresSandbox()
