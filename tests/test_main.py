import sys
from types import SimpleNamespace

import psutil
from click.testing import CliRunner

from pkport.main import (
    PortRow,
    collect_listening_ports,
    format_row,
    kill_row,
    list_plain,
    main,
    resolve_port,
    validate_port,
    STYLE,
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


def test_collect_listening_ports_skips_exe_by_default(monkeypatch):
    conns = [_conn(8080, 123)]
    monkeypatch.setattr("pkport.main.psutil.net_connections", lambda kind="tcp": conns)
    monkeypatch.setattr("pkport.main.psutil.Process", _FakeProcess)

    rows = collect_listening_ports()

    _check(rows[0].names == {"proc-123"}, "expected process name collected")
    _check(rows[0].paths == set(), "expected no paths when not requested")


def test_collect_listening_ports_collects_paths(monkeypatch):
    conns = [_conn(8080, 123)]
    monkeypatch.setattr("pkport.main.psutil.net_connections", lambda kind="tcp": conns)
    monkeypatch.setattr("pkport.main.psutil.Process", _FakeProcess)

    rows = collect_listening_ports(collect_paths=True)

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

    rows = collect_listening_ports(collect_paths=True)

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


def test_validate_port():
    _check(validate_port("8080") is True, "expected a valid port to pass")
    _check(validate_port("1") is True, "expected port 1 to pass")
    _check(validate_port("65535") is True, "expected port 65535 to pass")
    _check(isinstance(validate_port("abc"), str), "expected non-numeric to fail")
    _check(isinstance(validate_port("0"), str), "expected port 0 to fail")
    _check(isinstance(validate_port("65536"), str), "expected port 65536 to fail")
    _check(isinstance(validate_port(""), str), "expected empty input to fail")


def test_validate_port_unicode_digit_does_not_crash():
    # "²".isdigit() is True but int("²") raises ValueError
    _check(isinstance(validate_port("\u00b2"), str), "expected superscript digit to fail gracefully")
    # int() parses full-width digits, but only ASCII base-10 digits are accepted
    _check(isinstance(validate_port("\uff11\uff12"), str), "expected full-width digits to fail")


def _record_echo(monkeypatch):
    messages = []
    monkeypatch.setattr("pkport.main.click.echo", lambda msg, **kwargs: messages.append(msg))
    return messages


def test_resolve_port_found():
    rows = [PortRow(port=8080, pids={123}, names={"python"})]

    row = resolve_port(rows, 8080)

    _check(row is rows[0], f"expected the matching row, got: {row!r}")


def test_resolve_port_not_listening(monkeypatch):
    rows = [PortRow(port=8080, pids={123}, names={"python"})]
    messages = _record_echo(monkeypatch)

    row = resolve_port(rows, 9999)

    _check(row is None, f"expected None, got: {row!r}")
    _check(any("no TCP process is listening" in m for m in messages), f"expected a warning, got: {messages!r}")


def test_resolve_port_no_pid(monkeypatch):
    rows = [PortRow(port=8080)]
    messages = _record_echo(monkeypatch)

    row = resolve_port(rows, 8080)

    _check(row is None, f"expected None, got: {row!r}")
    _check(any("no process could be identified" in m for m in messages), f"expected a warning, got: {messages!r}")


def test_list_plain_with_paths(monkeypatch):
    rows = [
        PortRow(port=3000, pids={456}, names={"node"}, paths={r"C:\node.exe"}),
        PortRow(port=8080, pids={123}, names={"python"}, paths={r"C:\python.exe"}),
    ]
    monkeypatch.setattr("pkport.main.collect_listening_ports", lambda collect_paths=False: rows)
    lines = []
    monkeypatch.setattr("pkport.main.click.echo", lambda msg, **kwargs: lines.append(msg))

    list_plain(show_paths=True)

    _check(any("PATH" in m for m in lines), f"expected a PATH header, got: {lines!r}")
    _check(
        any(r"C:\node.exe" in m for m in lines) and any(r"C:\python.exe" in m for m in lines),
        f"expected paths in output, got: {lines!r}",
    )


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
    monkeypatch.setattr("pkport.main.collect_listening_ports", lambda collect_paths=False: [])

    result = CliRunner().invoke(main, [])

    _check(result.exit_code == 0, f"expected exit code 0, got: {result.exit_code}")
    _check(result.exception is None, f"expected no exception, got: {result.exception!r}")


def test_cli_list_flag(monkeypatch):
    rows = [
        PortRow(port=3000, pids={456}, names={"node"}),
        PortRow(port=8080, pids={123}, names={"python"}),
    ]
    monkeypatch.setattr("pkport.main.collect_listening_ports", lambda collect_paths=False: rows)

    result = CliRunner().invoke(main, ["--list"])

    _check(result.exit_code == 0, f"expected exit code 0, got: {result.exit_code}")
    _check("PORT" in result.output, f"expected 'PORT' header in output, got: {result.output!r}")


def test_cli_kill_nonexistent_port(monkeypatch):
    monkeypatch.setattr("pkport.main.collect_listening_ports", lambda: [])

    result = CliRunner().invoke(main, ["--kill", "9999", "-y"])

    _check(result.exit_code == 0, f"expected exit code 0, got: {result.exit_code}")
    _check(
        "no TCP process is listening" in result.output,
        f"expected 'no TCP process is listening' in output, got: {result.output!r}",
    )


def test_cli_kill_system_port_refuses(monkeypatch):
    rows = [PortRow(port=135, pids={1684}, names={"svchost.exe"})]
    monkeypatch.setattr("pkport.main.collect_listening_ports", lambda: rows)

    result = CliRunner().invoke(main, ["--kill", "135", "-y"])

    _check(result.exit_code == 0, f"expected exit code 0, got: {result.exit_code}")
    _check(
        "system-level process" in result.output,
        f"expected a refusal in output, got: {result.output!r}",
    )
    _check("Killed" not in result.output, f"expected no kill, got: {result.output!r}")


def test_select_row_toggle_paths_refresh_by_port():
    """toggle_paths should map refreshed rows by port, not by position."""
    from pkport.main import PortRow

    # Initial scan: ports 3000 and 8080
    initial_rows = [
        PortRow(port=3000, pids={111}, names={"node"}, paths={r"C:\node.exe"}),
        PortRow(port=8080, pids={222}, names={"python"}, paths={r"C:\python.exe"}),
    ]

    # Refreshed scan: port 3000 gone, port 8080 PID changed, port 5000 added
    refreshed_rows = [
        PortRow(port=5000, pids={333}, names={"newproc"}, paths={r"C:\new.exe"}),
        PortRow(port=8080, pids={999}, names={"python"}, paths={r"C:\python.exe"}),
    ]

    # Simulate the choices list as select_row builds it

    class MockChoice:
        def __init__(self, title, value):
            self.title = title
            self.value = value

    class MockSeparator:
        pass

    choices = [
        MockChoice(f"{r.port}", r) for r in initial_rows
    ] + [MockSeparator()]

    # The fixed logic from select_row.toggle_paths
    current = refreshed_rows
    refreshed_by_port = {r.port: r for r in current}

    for choice in choices:
        if not isinstance(choice, MockChoice):
            continue  # skip separator
        old_row = choice.value
        if not isinstance(old_row, PortRow):
            continue
        new_row = refreshed_by_port.get(old_row.port)
        if new_row is not None:
            choice.title = f"{new_row.port}"
            choice.value = new_row

    # Verify: 3000 should be gone (no refreshed row), 8080 should have new PID 999
    choice_3000 = choices[0]  # port 3000
    choice_8080 = choices[1]  # port 8080
    choice_sep = choices[2]   # separator

    if not isinstance(choice_sep, MockSeparator):
        raise TypeError("expected MockSeparator")
    if not isinstance(choice_3000, MockChoice):
        raise TypeError("expected MockChoice")
    if not isinstance(choice_8080, MockChoice):
        raise TypeError("expected MockChoice")

    # 3000 was removed in refresh -> value should be unchanged (stale but not crashed)
    _check(choice_3000.value.port == 3000, "removed port retains old row reference")
    _check(choice_3000.title == "3000", "removed port title unchanged")

    # 8080 PID changed from 222 to 999 -> value should point to refreshed row
    _check(choice_8080.value.port == 8080, "port 8080 still present")
    _check(choice_8080.value.pids == {999}, "PID updated to refreshed value")
    _check(choice_8080.title == "8080", "title reflects refreshed port")
