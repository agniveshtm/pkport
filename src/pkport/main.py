import sys
from dataclasses import dataclass, field
from typing import cast
import click
import psutil
import questionary
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from questionary.prompts.common import InquirerControl
from pkport.ui import HINT, STYLE, print_banner, print_cancelled


@dataclass
class PortRow:
    port: int
    pids: set[int] = field(default_factory=set)
    names: set[str] = field(default_factory=set)
    paths: set[str] = field(default_factory=set)


class CustomPortRequest:
    """Sentinel: the user pressed 'a' to kill a custom (typed) port."""


CUSTOM_PORT_REQUEST = CustomPortRequest()


def validate_port(text: str) -> bool | str:
    if not text.isdigit():
        return "Port must be a number"
    if not 1 <= int(text) <= 65535:
        return "Port must be between 1 and 65535"
    return True


def prompt_custom_port() -> int | None:
    value = questionary.text(
        "Enter a port to kill",
        validate=validate_port,
        style=STYLE,
    ).ask(kbi_msg="")
    return int(value) if value is not None else None


def collect_listening_ports() -> list[PortRow]:
    rows: dict[int, PortRow] = {}
    for conn in psutil.net_connections(kind="tcp"):
        if conn.status != psutil.CONN_LISTEN:
            continue
        port = getattr(conn.laddr, "port", None)
        if port is None:
            continue
        row = rows.setdefault(port, PortRow(port=port))
        if conn.pid is not None:
            row.pids.add(conn.pid)
            try:
                proc = psutil.Process(conn.pid)
                row.names.add(proc.name())
                row.paths.add(proc.exe())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    return [rows[port] for port in sorted(rows)]


def kill_row(row: PortRow) -> str:
    terminated = []
    denied = 0
    for pid in row.pids:
        try:
            proc = psutil.Process(pid)
            proc.terminate()
            terminated.append(proc)
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied:
            denied += 1
    if terminated:
        # brief grace period so the freed port disappears from the next refresh
        gone, alive = psutil.wait_procs(terminated, timeout=2)
        killed = [proc.pid for proc in gone]
    else:
        killed = []
        alive = []

    names = ", ".join(sorted(row.names))
    if killed:
        suffix = f"; {denied} process(es) need elevated permissions" if denied else ""
        if alive:
            suffix += f"; {len(alive)} process(es) still running"
        return f"Killed PID {', '.join(map(str, killed))} ({names}) on port {row.port}{suffix}"
    if denied:
        return f"Port {row.port}: permission denied, {denied} process(es) not killed"
    return f"Port {row.port}: process already gone"


def format_row(row: PortRow, show_paths: bool = False) -> str:
    pids = ", ".join(map(str, sorted(row.pids))) or "-"
    names = ", ".join(sorted(row.names)) or "?"
    if not show_paths:
        return f"{row.port:<6} {pids:<8} {names}"
    paths = ", ".join(sorted(row.paths)) or "?"
    return f"{row.port:<6} {pids:<8} {names:<24} {paths}"


def select_row(rows: list[PortRow]) -> PortRow | CustomPortRequest | None:
    state = {"show_paths": False}

    def build_choices() -> list:
        choices = []
        for row in rows:
            label = format_row(row, state["show_paths"])
            if row.pids:
                choices.append(questionary.Choice(title=label, value=row))
            else:
                choices.append(questionary.Choice(title=label, disabled="cannot resolve pid"))
        choices.append(questionary.Separator(HINT))
        return choices

    question = questionary.select(
        "Select a port to kill",
        choices=build_choices(),
        # non-empty so questionary doesn't render its default "(Use arrow keys)" at the top
        instruction=" ",
        style=STYLE,
    )

    bindings = cast(KeyBindings, question.application.key_bindings)

    def inquirer_control(event):
        return next(
            (
                w.content
                for w in event.app.layout.find_all_windows()
                if isinstance(w.content, InquirerControl)
            ),
            None,
        )

    @bindings.add("q", eager=True)
    def cancel_selection(event):
        event.app.exit(result=None)

    @bindings.add("a", eager=True)
    def custom_port(event):
        event.app.exit(result=CUSTOM_PORT_REQUEST)

    @bindings.add("p", eager=True)
    def toggle_paths(event):
        state["show_paths"] = not state["show_paths"]
        ic = inquirer_control(event)
        if ic is None:
            return
        for choice, row in zip(ic.choices, rows):
            if isinstance(choice, questionary.Choice):
                choice.title = format_row(row, state["show_paths"])
        event.app.invalidate()

    @bindings.add(Keys.ControlM, eager=True)
    def pick_row(event):
        ic = inquirer_control(event)
        # exit without marking the question answered, so the picked
        # row's text is not appended to the "? Select a port to kill" line
        event.app.exit(result=ic.get_pointed_at().value if ic else None)

    return question.ask(kbi_msg="")


def confirm_kill(row: PortRow) -> bool | None:
    pids = ", ".join(map(str, sorted(row.pids)))
    return questionary.confirm(
        f"Kill port {row.port} (PID {pids})?",
        default=False,
        style=STYLE,
    ).ask(kbi_msg="")


def resolve_port(rows: list[PortRow], port: int) -> PortRow | None:
    """Look up `port` in `rows`; print a warning and return None if it can't be killed."""
    row = next((r for r in rows if r.port == port), None)
    if row is None:
        click.echo(click.style(f"Port {port}: no process is listening on it", fg="yellow"))
        return None
    if not row.pids:
        click.echo(click.style(f"Port {port}: listening, but no process could be identified", fg="yellow"))
        return None
    return row


def interactive_tui(subtitle: str) -> None:
    print_banner(subtitle)
    while True:
        rows = collect_listening_ports()
        if not rows:
            click.echo(click.style("No TCP ports are being listened on.", fg="yellow"))
            return
        picked = select_row(rows)
        if picked is None:
            print_cancelled()
            return
        if isinstance(picked, CustomPortRequest):
            port = prompt_custom_port()
            if port is None:
                print_cancelled()
                return
            row = resolve_port(rows, port)
            if row is None:
                continue
        else:
            row = picked
        confirmed = confirm_kill(row)
        if confirmed is None:
            print_cancelled()
            return
        if confirmed:
            click.echo(click.style(kill_row(row), fg="green"))


def list_plain(show_paths: bool = False) -> None:
    rows = collect_listening_ports()
    if not rows:
        click.echo(click.style("No TCP ports are being listened on.", fg="yellow"))
        return
    if show_paths:
        click.echo(f"{'PORT':<6} {'PID':<8} {'PROCESS':<24} {'PATH'}")
    else:
        name_width = max(len(", ".join(sorted(r.names)) or "?") for r in rows)
        click.echo(f"{'PORT':<6} {'PID':<8} {'PROCESS':<{name_width}}")
    for row in rows:
        click.echo(format_row(row, show_paths))


def run(subtitle: str) -> None:
    if sys.stdin.isatty() and sys.stdout.isatty():
        interactive_tui(subtitle)
    else:
        print_banner(subtitle)
        list_plain()


def kill_port_flow(port: int, assume_yes: bool) -> None:
    print_banner(f"Kill process on port {port}")
    row = resolve_port(collect_listening_ports(), port)
    if row is None:
        return
    if not assume_yes:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            click.echo(click.style(f"Port {port}: confirmation needs a terminal; use -y to bypass", fg="yellow"))
            return
        if confirm_kill(row) is not True:
            print_cancelled()
            return
    click.echo(click.style(kill_row(row), fg="green"))


def _list_callback(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    print_banner("Listening TCP ports")
    list_plain()
    ctx.exit()


@click.command(
    context_settings={"ignore_unknown_options": False},
)
@click.option(
    "--list", "-l",
    is_flag=True,
    callback=_list_callback,
    expose_value=False,
    is_eager=True,
    help="List all listening TCP ports with their owning process.",
)
@click.option(
    "--kill", "-k",
    type=click.IntRange(1, 65535),
    help="Kill the process listening on PORT.",
)
@click.option("-y", "--yes", is_flag=True, help="Skip the confirmation prompt.")
@click.pass_context
def main(ctx, kill, yes):
    """Discover and kill dev server ports"""
    if kill is not None:
        kill_port_flow(kill, yes)
        return
    run("Discover and kill dev server ports")


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    # Click injects `ctx` via @click.pass_context at runtime
    main()
