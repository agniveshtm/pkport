import sys
from types import SimpleNamespace

import psutil
from click.testing import CliRunner

from pkport.main import (
    PortRow,
    collect_listening_ports,
    kill_row,
    main,
)


def _conn(port, pid, status=None):
    return SimpleNamespace(
        status=status if status is not None else psutil.CONN_LISTEN,
        laddr=SimpleNamespace(port=port),
        pid=pid,
    )


class _FakeProcess:
    def __init__(self, pid, name=None, terminate_raises=None):
        self.pid = pid
        self._name = name
        self._terminate_raises = terminate_raises

    def name(self):
        if self._name is None:
            return f"proc-{self.pid}"
        if isinstance(self._name, Exception):
            raise self._name
        return self._name

    def terminate(self):
        if self._terminate_raises is not None:
            raise self._terminate_raises


def test_collect_listening_ports_normal(monkeypatch):
    conns = [
        _conn(8080, 123),
        _conn(3000, 456),
    ]
    monkeypatch.setattr("pkport.main.psutil.net_connections", lambda kind="tcp": conns)
    monkeypatch.setattr("pkport.main.psutil.Process", _FakeProcess)

    rows = collect_listening_ports()

    assert [r.port for r in rows] == [3000, 8080]  # noqa: S101
    assert rows[0].pids == {456}  # noqa: S101
    assert rows[0].names == {"proc-456"}  # noqa: S101
    assert rows[1].pids == {123}  # noqa: S101
    assert rows[1].names == {"proc-123"}  # noqa: S101


def test_collect_listening_ports_skips_none_pid(monkeypatch):
    conns = [_conn(8080, None)]
    monkeypatch.setattr("pkport.main.psutil.net_connections", lambda kind="tcp": conns)
    monkeypatch.setattr("pkport.main.psutil.Process", _FakeProcess)

    rows = collect_listening_ports()

    assert len(rows) == 1  # noqa: S101
    assert rows[0].port == 8080  # noqa: S101
    assert rows[0].pids == set()  # noqa: S101
    assert rows[0].names == set()  # noqa: S101


def test_collect_listening_ports_handles_access_denied(monkeypatch):
    conns = [_conn(8080, 123)]
    monkeypatch.setattr("pkport.main.psutil.net_connections", lambda kind="tcp": conns)
    monkeypatch.setattr(
        "pkport.main.psutil.Process",
        lambda pid: _FakeProcess(pid, name=psutil.AccessDenied(pid=123)),
    )

    rows = collect_listening_ports()

    assert len(rows) == 1  # noqa: S101
    assert rows[0].pids == {123}  # noqa: S101
    assert rows[0].names == set()  # noqa: S101


def test_collect_listening_ports_handles_no_such_process(monkeypatch):
    conns = [_conn(8080, 123)]
    monkeypatch.setattr("pkport.main.psutil.net_connections", lambda kind="tcp": conns)
    monkeypatch.setattr(
        "pkport.main.psutil.Process",
        lambda pid: _FakeProcess(pid, name=psutil.NoSuchProcess(pid=123)),
    )

    rows = collect_listening_ports()

    assert len(rows) == 1  # noqa: S101
    assert rows[0].pids == {123}  # noqa: S101
    assert rows[0].names == set()  # noqa: S101


def test_kill_row_success(monkeypatch):
    row = PortRow(port=8080, pids={123}, names={"node"})
    proc = _FakeProcess(123)
    monkeypatch.setattr("pkport.main.psutil.Process", lambda pid: proc)
    monkeypatch.setattr(
        "pkport.main.psutil.wait_procs", lambda procs, timeout=2: ([proc], [])
    )

    msg = kill_row(row)

    assert "Killed" in msg  # noqa: S101
    assert "8080" in msg  # noqa: S101
    assert "123" in msg  # noqa: S101


def test_kill_row_access_denied(monkeypatch):
    row = PortRow(port=8080, pids={123}, names={"node"})
    proc = _FakeProcess(123, terminate_raises=psutil.AccessDenied(pid=123))
    monkeypatch.setattr("pkport.main.psutil.Process", lambda pid: proc)

    msg = kill_row(row)

    assert "permission denied" in msg  # noqa: S101


def test_kill_row_no_such_process(monkeypatch):
    row = PortRow(port=8080, pids={123}, names={"node"})
    proc = _FakeProcess(123, terminate_raises=psutil.NoSuchProcess(pid=123))
    monkeypatch.setattr("pkport.main.psutil.Process", lambda pid: proc)

    msg = kill_row(row)

    assert "already gone" in msg  # noqa: S101


def test_cli_bare_non_tty(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    monkeypatch.setattr("pkport.main.collect_listening_ports", lambda: [])

    result = CliRunner().invoke(main, [])

    assert result.exit_code == 0  # noqa: S101


def test_cli_list_flag(monkeypatch):
    rows = [
        PortRow(port=3000, pids={456}, names={"node"}),
        PortRow(port=8080, pids={123}, names={"python"}),
    ]
    monkeypatch.setattr("pkport.main.collect_listening_ports", lambda: rows)

    result = CliRunner().invoke(main, ["--list"])

    assert result.exit_code == 0  # noqa: S101
    assert "PORT" in result.output  # noqa: S101


def test_cli_kill_nonexistent_port(monkeypatch):
    monkeypatch.setattr("pkport.main.collect_listening_ports", lambda: [])

    result = CliRunner().invoke(main, ["--kill", "9999", "-y"])

    assert result.exit_code == 0  # noqa: S101
    assert "no process is listening" in result.output  # noqa: S101