import sys
from types import SimpleNamespace

import psutil
from click.testing import CliRunner

from pkport.main import (
    PortRow,
    collect_listening_ports,
    format_row,
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
    def __init__(self, pid, name=None, exe=None, terminate_raises=None):
        self.pid = pid
        self._name = name
        self._exe = exe
        self._terminate_raises = terminate_raises

    def name(self):
        if self._name is None:
            return f"proc-{self.pid}"
        if isinstance(self._name, Exception):
            raise self._name
        return self._name

    def exe(self):
        if self._exe is None:
            return f"C:\\fake\\proc-{self.pid}.exe"
        if isinstance(self._exe, Exception):
            raise self._exe
        return self._exe

    def terminate(self):
        if self._terminate_raises is not None:
            raise self._terminate_raises


def _check(condition, message):
    if not condition:
        raise AssertionError(message)


def test_collect_listening_ports_normal(monkeypatch):
    conns = [
        _conn(8080, 123),
        _conn(3000, 456),
    ]
    monkeypatch.setattr("pkport.main.psutil.net_connections", lambda kind="tcp": conns)
    monkeypatch.setattr("pkport.main.psutil.Process", _FakeProcess)

    rows = collect_listening_ports()

    _check([r.port for r in rows] == [3000, 8080], "expected sorted ports [3000, 8080]")
    _check(rows[0].pids == {456}, "expected row[0] pids {456}")
    _check(rows[0].names == {"proc-456"}, "expected row[0] names {'proc-456'}")
    _check(rows[1].pids == {123}, "expected row[1] pids {123}")
    _check(rows[1].names == {"proc-123"}, "expected row[1] names {'proc-123'}")


def test_collect_listening_ports_skips_none_pid(monkeypatch):
    conns = [_conn(8080, None)]
    monkeypatch.setattr("pkport.main.psutil.net_connections", lambda kind="tcp": conns)
    monkeypatch.setattr("pkport.main.psutil.Process", _FakeProcess)

    rows = collect_listening_ports()

    _check(len(rows) == 1, "expected exactly 1 row")
    _check(rows[0].port == 8080, "expected port 8080")
    _check(rows[0].pids == set(), "expected empty pids")
    _check(rows[0].names == set(), "expected empty names")


def test_collect_listening_ports_handles_access_denied(monkeypatch):
    conns = [_conn(8080, 123)]
    monkeypatch.setattr("pkport.main.psutil.net_connections", lambda kind="tcp": conns)
    monkeypatch.setattr(
        "pkport.main.psutil.Process",
        lambda pid: _FakeProcess(pid, name=psutil.AccessDenied(pid=123)),
    )

    rows = collect_listening_ports()

    _check(len(rows) == 1, "expected exactly 1 row")
    _check(rows[0].pids == {123}, "expected pids {123}")
    _check(rows[0].names == set(), "expected empty names")


def test_collect_listening_ports_handles_no_such_process(monkeypatch):
    conns = [_conn(8080, 123)]
    monkeypatch.setattr("pkport.main.psutil.net_connections", lambda kind="tcp": conns)
    monkeypatch.setattr(
        "pkport.main.psutil.Process",
        lambda pid: _FakeProcess(pid, name=psutil.NoSuchProcess(pid=123)),
    )

    rows = collect_listening_ports()

    _check(len(rows) == 1, "expected exactly 1 row")
    _check(rows[0].pids == {123}, "expected pids {123}")
    _check(rows[0].names == set(), "expected empty names")


def test_collect_listening_ports_collects_paths(monkeypatch):
    conns = [_conn(8080, 123)]
    monkeypatch.setattr("pkport.main.psutil.net_connections", lambda kind="tcp": conns)
    monkeypatch.setattr("pkport.main.psutil.Process", _FakeProcess)

    rows = collect_listening_ports()

    _check(
        rows[0].paths == {r"C:\fake\proc-123.exe"},
        f"expected executable path, got: {rows[0].paths!r}",
    )


def test_collect_listening_ports_handles_exe_access_denied(monkeypatch):
    conns = [_conn(8080, 123)]
    monkeypatch.setattr("pkport.main.psutil.net_connections", lambda kind="tcp": conns)
    monkeypatch.setattr(
        "pkport.main.psutil.Process",
        lambda pid: _FakeProcess(pid, name=f"proc-{pid}", exe=psutil.AccessDenied(pid=123)),
    )

    rows = collect_listening_ports()

    _check(rows[0].pids == {123}, "expected pids {123}")
    _check(rows[0].names == {"proc-123"}, "expected name retained")
    _check(rows[0].paths == set(), "expected empty paths")


def test_format_row_hides_paths_by_default():
    row = PortRow(port=8828, pids={29272}, names={"Code.exe"}, paths={"C:\\Code.exe"})

    label = format_row(row)

    _check("8828" in label and "29272" in label and "Code.exe" in label, f"unexpected label: {label!r}")
    _check("C:\\Code.exe" not in label, f"path should be hidden, got: {label!r}")


def test_format_row_shows_paths_when_enabled():
    row = PortRow(port=8828, pids={29272}, names={"Code.exe"}, paths={"C:\\Code.exe"})

    label = format_row(row, show_paths=True)

    _check("C:\\Code.exe" in label, f"expected path in label, got: {label!r}")
    head, _, _ = label.partition("C:\\Code.exe")
    _check(head.endswith("  "), f"expected a gap before the path, got: {label!r}")


def test_kill_row_success(monkeypatch):
    row = PortRow(port=8080, pids={123}, names={"node"})
    proc = _FakeProcess(123)
    monkeypatch.setattr("pkport.main.psutil.Process", lambda pid: proc)
    monkeypatch.setattr(
        "pkport.main.psutil.wait_procs", lambda procs, timeout=2: ([proc], [])
    )

    msg = kill_row(row)

    _check("Killed" in msg, f"expected 'Killed' in message, got: {msg!r}")
    _check("8080" in msg, f"expected port 8080 in message, got: {msg!r}")
    _check("123" in msg, f"expected pid 123 in message, got: {msg!r}")


def test_kill_row_access_denied(monkeypatch):
    row = PortRow(port=8080, pids={123}, names={"node"})
    proc = _FakeProcess(123, terminate_raises=psutil.AccessDenied(pid=123))
    monkeypatch.setattr("pkport.main.psutil.Process", lambda pid: proc)

    msg = kill_row(row)

    _check("permission denied" in msg, f"expected 'permission denied' in message, got: {msg!r}")


def test_kill_row_no_such_process(monkeypatch):
    row = PortRow(port=8080, pids={123}, names={"node"})
    proc = _FakeProcess(123, terminate_raises=psutil.NoSuchProcess(pid=123))
    monkeypatch.setattr("pkport.main.psutil.Process", lambda pid: proc)

    msg = kill_row(row)

    _check("already gone" in msg, f"expected 'already gone' in message, got: {msg!r}")


def test_cli_bare_non_tty(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
    monkeypatch.setattr("pkport.main.collect_listening_ports", lambda: [])

    result = CliRunner().invoke(main, [])

    _check(result.exit_code == 0, f"expected exit code 0, got: {result.exit_code}")
    _check(result.exception is None, f"expected no exception, got: {result.exception!r}")


def test_cli_list_flag(monkeypatch):
    rows = [
        PortRow(port=3000, pids={456}, names={"node"}),
        PortRow(port=8080, pids={123}, names={"python"}),
    ]
    monkeypatch.setattr("pkport.main.collect_listening_ports", lambda: rows)

    result = CliRunner().invoke(main, ["--list"])

    _check(result.exit_code == 0, f"expected exit code 0, got: {result.exit_code}")
    _check("PORT" in result.output, f"expected 'PORT' header in output, got: {result.output!r}")


def test_cli_kill_nonexistent_port(monkeypatch):
    monkeypatch.setattr("pkport.main.collect_listening_ports", lambda: [])

    result = CliRunner().invoke(main, ["--kill", "9999", "-y"])

    _check(result.exit_code == 0, f"expected exit code 0, got: {result.exit_code}")
    _check(
        "no process is listening" in result.output,
        f"expected 'no process is listening' in output, got: {result.output!r}",
    )
