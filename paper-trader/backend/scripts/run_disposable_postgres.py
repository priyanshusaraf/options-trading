#!/usr/bin/env python3
"""Run one command against a fresh, loopback-only PostgreSQL 16 instance."""

from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import quote


TOOL_NAMES = ("initdb", "pg_ctl", "createdb")
SUPPORTED_BIN_DIRECTORIES = (
    Path("/opt/homebrew/opt/postgresql@16/bin"),
    Path("/usr/local/opt/postgresql@16/bin"),
    Path("/opt/local/lib/postgresql16/bin"),
)
POSTGRES_ENVIRONMENT_KEYS = frozenset(
    {
        "PT_TEST_POSTGRES_URL",
        "PGDATABASE",
        "PGHOST",
        "PGHOSTADDR",
        "PGPASSWORD",
        "PGPASSFILE",
        "PGPORT",
        "PGSERVICE",
        "PGSERVICEFILE",
        "PGUSER",
    }
)


class HarnessError(RuntimeError):
    """A disposable PostgreSQL instance could not be safely prepared."""


@dataclass(frozen=True)
class PostgresTools:
    initdb: Path
    pg_ctl: Path
    createdb: Path


def _is_postgres_16(version_output: str) -> bool:
    tokens = version_output.replace("(", " ").replace(")", " ").split()
    return any(token == "16" or token.startswith("16.") for token in tokens)


def locate_postgres_16_tools(
    *,
    which: Callable[[str], str | None] = shutil.which,
    bin_directories: Sequence[Path] = SUPPORTED_BIN_DIRECTORIES,
    version_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> PostgresTools:
    """Find a coherent PostgreSQL 16 toolset without accepting another major."""

    candidates: list[Path] = []
    path_initdb = which("initdb")
    if path_initdb:
        candidates.append(Path(path_initdb).parent)
    candidates.extend(bin_directories)

    seen: set[Path] = set()
    for directory in candidates:
        directory = directory.resolve()
        if directory in seen:
            continue
        seen.add(directory)
        tool_paths = {name: directory / name for name in TOOL_NAMES}
        if not all(path.is_file() and os.access(path, os.X_OK) for path in tool_paths.values()):
            continue
        result = version_runner(
            [str(tool_paths["initdb"]), "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and _is_postgres_16(result.stdout):
            return PostgresTools(**tool_paths)

    raise HarnessError(
        "PostgreSQL 16 tools were not found on PATH or in supported package-manager prefixes"
    )


def _private_environment(environ: Mapping[str, str]) -> dict[str, str]:
    return {key: value for key, value in environ.items() if key not in POSTGRES_ENVIRONMENT_KEYS}


def _find_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _run_required(
    command: Sequence[str],
    *,
    environ: Mapping[str, str],
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    try:
        result = runner(list(command), check=False, env=dict(environ))
    except OSError as error:
        raise HarnessError("could not launch a temporary PostgreSQL setup command") from error
    if result.returncode != 0:
        raise HarnessError("a temporary PostgreSQL setup command failed")


def _stop_server(
    tools: PostgresTools,
    data_directory: Path,
    environ: Mapping[str, str],
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    try:
        runner(
            [str(tools.pg_ctl), "-D", str(data_directory), "stop", "-m", "immediate", "-w", "-t", "15"],
            check=False,
            env=dict(environ),
        )
    except OSError:
        # Directory removal is still required even if pg_ctl itself became unavailable.
        pass


class _InterruptionGuard:
    def __enter__(self) -> "_InterruptionGuard":
        self._previous = {
            signum: signal.getsignal(signum) for signum in (signal.SIGINT, signal.SIGTERM)
        }
        for signum in self._previous:
            signal.signal(signum, self._interrupt)
        return self

    def __exit__(self, *unused: object) -> None:
        for signum, handler in self._previous.items():
            signal.signal(signum, handler)

    @staticmethod
    def _interrupt(signum: int, frame: object) -> None:
        raise KeyboardInterrupt(f"interrupted by signal {signum}")


def run_disposable_postgres(
    child_command: Sequence[str],
    *,
    tools: PostgresTools | None = None,
    environ: Mapping[str, str] | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    temporary_directory_factory: Callable[..., str] = tempfile.mkdtemp,
    port_finder: Callable[[], int] = _find_loopback_port,
) -> int:
    """Provision a cluster, run ``child_command``, then remove all local state."""

    if not child_command:
        raise HarnessError("a child command is required after --")
    source_environment = os.environ if environ is None else environ
    environment = _private_environment(source_environment)
    if "PT_TEST_POSTGRES_URL" in source_environment:
        print("Replacing inherited PT_TEST_POSTGRES_URL for the child.", file=sys.stderr)
    tools = tools or locate_postgres_16_tools()
    root = Path(temporary_directory_factory(prefix="strategy-os-postgres-"))
    data_directory = root / "data"
    socket_directory = root / "socket"
    server_start_attempted = False

    try:
        with _InterruptionGuard():
            socket_directory.mkdir(mode=0o700)
            os.chmod(socket_directory, 0o700)
            user = getpass.getuser()
            database = f"pt_harness_{uuid.uuid4().hex}"
            port = port_finder()
            _run_required(
                [
                    str(tools.initdb), "-D", str(data_directory), "--no-locale", "--encoding=UTF8",
                    "-U", user, "--auth=trust",
                ],
                environ=environment,
                runner=runner,
            )
            server_start_attempted = True
            _run_required(
                [
                    str(tools.pg_ctl), "-D", str(data_directory), "start", "-w", "-t", "15",
                    "-o", f"-h 127.0.0.1 -k {socket_directory} -p {port}",
                ],
                environ=environment,
                runner=runner,
            )
            _run_required(
                [str(tools.createdb), "--host", str(socket_directory), "--port", str(port), "--username", user, database],
                environ=environment,
                runner=runner,
            )
            child_environment = dict(environment)
            child_environment["PT_TEST_POSTGRES_URL"] = (
                f"postgresql+psycopg://{quote(user, safe='')}@127.0.0.1:{port}/{database}"
            )
            try:
                result = runner(list(child_command), check=False, env=child_environment)
            except OSError as error:
                raise HarnessError("could not launch child command") from error
        return int(result.returncode)
    finally:
        if server_start_attempted:
            _stop_server(tools, data_directory, environment, runner)
        shutil.rmtree(root, ignore_errors=True)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("child_command", nargs=argparse.REMAINDER, metavar="COMMAND")
    args = parser.parse_args(argv)
    if args.child_command and args.child_command[0] == "--":
        args.child_command = args.child_command[1:]
    if not args.child_command:
        parser.error("a child command is required after --")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        return run_disposable_postgres(args.child_command)
    except KeyboardInterrupt:
        print("Interrupted; disposable PostgreSQL cleanup was attempted.", file=sys.stderr)
        return 130
    except HarnessError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
