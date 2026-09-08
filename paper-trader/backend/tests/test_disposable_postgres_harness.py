"""Unit contracts for the local disposable PostgreSQL wrapper."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "run_disposable_postgres.py"
SPEC = importlib.util.spec_from_file_location("disposable_postgres_harness", SCRIPT)
assert SPEC and SPEC.loader
harness = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = harness
SPEC.loader.exec_module(harness)


def _tools(tmp_path: Path) -> harness.PostgresTools:
    paths = []
    for name in harness.TOOL_NAMES:
        path = tmp_path / name
        path.write_text("#!/bin/sh\n")
        path.chmod(0o755)
        paths.append(path)
    return harness.PostgresTools(*paths)


def _temporary_directory(root: Path) -> str:
    root.mkdir(mode=0o700)
    return str(root)


def test_locates_postgres_16_from_path(tmp_path: Path) -> None:
    tools = _tools(tmp_path)

    found = harness.locate_postgres_16_tools(
        which=lambda name: str(tools.initdb) if name == "initdb" else None,
        bin_directories=(),
        version_runner=lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "initdb (PostgreSQL) 16.4", ""),
    )

    assert found == tools


def test_refuses_non_16_tools(tmp_path: Path) -> None:
    tools = _tools(tmp_path)

    with pytest.raises(harness.HarnessError, match="PostgreSQL 16 tools"):
        harness.locate_postgres_16_tools(
            which=lambda name: str(tools.initdb),
            bin_directories=(),
            version_runner=lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "initdb (PostgreSQL) 15.8", ""),
        )


def test_locates_postgres_16_from_supported_prefix(tmp_path: Path) -> None:
    tools = _tools(tmp_path)

    found = harness.locate_postgres_16_tools(
        which=lambda name: None,
        bin_directories=(tmp_path,),
        version_runner=lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "initdb (PostgreSQL) 16.0", ""),
    )

    assert found == tools


def test_child_receives_replacement_url_and_success_cleans_up(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[tuple[list[str], dict[str, str]]] = []
    root = tmp_path / "cluster"

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs["env"]))  # type: ignore[arg-type,index]
        return subprocess.CompletedProcess(command, 0)

    result = harness.run_disposable_postgres(
        ["child", "test"], tools=_tools(tmp_path),
        environ={"PATH": os.environ["PATH"], "PT_TEST_POSTGRES_URL": "postgresql://inherited/never-use", "PGHOST": "remote"},
        runner=runner, temporary_directory_factory=lambda **kwargs: _temporary_directory(root), port_finder=lambda: 55432,
    )

    assert result == 0
    assert "Replacing inherited PT_TEST_POSTGRES_URL" in capsys.readouterr().err
    child_command, child_environment = calls[-2]
    assert child_command == ["child", "test"]
    assert child_environment["PT_TEST_POSTGRES_URL"].startswith("postgresql+psycopg://")
    assert child_environment["PT_TEST_POSTGRES_URL"] != "postgresql://inherited/never-use"
    assert "PGHOST" not in child_environment
    assert all("PT_TEST_POSTGRES_URL" not in environment for _, environment in calls[:-2])
    assert not root.exists()
    assert calls[-1][0][1:] == ["-D", str(root / "data"), "stop", "-m", "immediate", "-w", "-t", "15"]


def test_child_url_percent_encodes_username_but_setup_uses_raw_username(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict[str, str]]] = []
    root = tmp_path / "cluster"
    monkeypatch.setattr(harness.getpass, "getuser", lambda: "local/user@name")

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs["env"]))  # type: ignore[arg-type,index]
        return subprocess.CompletedProcess(command, 0)

    harness.run_disposable_postgres(
        ["child"], tools=_tools(tmp_path), environ={}, runner=runner,
        temporary_directory_factory=lambda **kwargs: _temporary_directory(root), port_finder=lambda: 55432,
    )

    assert "local/user@name" in calls[0][0]
    assert calls[-2][1]["PT_TEST_POSTGRES_URL"].startswith("postgresql+psycopg://local%2Fuser%40name@")


def test_child_exit_code_is_preserved_and_cleanup_runs(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    root = tmp_path / "cluster"

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 23 if command[0] == "child" else 0)

    assert harness.run_disposable_postgres(
        ["child"], tools=_tools(tmp_path), environ={}, runner=runner,
        temporary_directory_factory=lambda **kwargs: _temporary_directory(root), port_finder=lambda: 55432,
    ) == 23
    assert calls[-1][0].endswith("pg_ctl")
    assert not root.exists()


def test_failed_start_attempts_bounded_stop_and_removes_directory(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    root = tmp_path / "cluster"

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        failed_start = command[0].endswith("pg_ctl") and "start" in command
        return subprocess.CompletedProcess(command, 1 if failed_start else 0)

    with pytest.raises(harness.HarnessError, match="setup command failed"):
        harness.run_disposable_postgres(
            ["child"], tools=_tools(tmp_path), environ={}, runner=runner,
            temporary_directory_factory=lambda **kwargs: _temporary_directory(root), port_finder=lambda: 55432,
        )
    assert calls[-1][0].endswith("pg_ctl")
    assert "stop" in calls[-1]
    assert not root.exists()


def test_setup_launch_error_is_clean_and_removes_directory(tmp_path: Path) -> None:
    root = tmp_path / "cluster"

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError

    with pytest.raises(harness.HarnessError, match="could not launch a temporary PostgreSQL setup command"):
        harness.run_disposable_postgres(
            ["child"], tools=_tools(tmp_path), environ={}, runner=runner,
            temporary_directory_factory=lambda **kwargs: _temporary_directory(root), port_finder=lambda: 55432,
        )
    assert not root.exists()


def test_child_launch_error_is_clean_and_removes_directory(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    root = tmp_path / "cluster"

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[0] == "child":
            raise FileNotFoundError
        return subprocess.CompletedProcess(command, 0)

    with pytest.raises(harness.HarnessError, match="could not launch child command"):
        harness.run_disposable_postgres(
            ["child"], tools=_tools(tmp_path), environ={}, runner=runner,
            temporary_directory_factory=lambda **kwargs: _temporary_directory(root), port_finder=lambda: 55432,
        )
    assert calls[-1][0].endswith("pg_ctl")
    assert not root.exists()


def test_startup_failure_removes_directory_without_running_child(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    root = tmp_path / "cluster"

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 1)

    with pytest.raises(harness.HarnessError, match="setup command failed"):
        harness.run_disposable_postgres(
            ["child"], tools=_tools(tmp_path), environ={}, runner=runner,
            temporary_directory_factory=lambda **kwargs: _temporary_directory(root), port_finder=lambda: 55432,
        )
    assert calls == [[
        str(_tools(tmp_path).initdb), "-D", str(root / "data"), "--no-locale", "--encoding=UTF8",
        "-U", harness.getpass.getuser(), "--auth=trust",
    ]]
    assert not root.exists()


def test_database_creation_failure_stops_started_server_and_removes_directory(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    root = tmp_path / "cluster"

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 1 if command[0].endswith("createdb") else 0)

    with pytest.raises(harness.HarnessError, match="setup command failed"):
        harness.run_disposable_postgres(
            ["child"], tools=_tools(tmp_path), environ={}, runner=runner,
            temporary_directory_factory=lambda **kwargs: _temporary_directory(root), port_finder=lambda: 55432,
        )
    assert calls[-1][0].endswith("pg_ctl")
    assert not root.exists()


def test_interruption_stops_server_and_removes_directory(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    root = tmp_path / "cluster"

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[0] == "child":
            raise KeyboardInterrupt
        return subprocess.CompletedProcess(command, 0)

    with pytest.raises(KeyboardInterrupt):
        harness.run_disposable_postgres(
            ["child"], tools=_tools(tmp_path), environ={}, runner=runner,
            temporary_directory_factory=lambda **kwargs: _temporary_directory(root), port_finder=lambda: 55432,
        )
    assert calls[-1][0].endswith("pg_ctl")
    assert not root.exists()
