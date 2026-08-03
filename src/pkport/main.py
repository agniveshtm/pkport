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
                row.names.add(psutil.Process(conn.pid).name())
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


def select_row(rows: list[PortRow]) -> PortRow | None:
    choices = []
    for row in rows:
        pids = ", ".join(map(str, sorted(row.pids))) or "-"
        names = ", ".join(sorted(row.names)) or "?"
        label = f"{row.port:<6} {pids:<8} {names}"
        if row.pids:
            choices.append(questionary.Choice(title=label, value=row))
        else:
            choices.append(questionary.Choice(title=label, disabled="cannot resolve pid"))
    choices.append(questionary.Separator(HINT))

    question = questionary.select(
        "Select a port to kill",
        choices=choices,
        # non-empty so questionary doesn't render its default "(Use arrow keys)" at the top
        instruction=" ",
        style=STYLE,
    )

    bindings = cast(KeyBindings, question.application.key_bindings)

    @bindings.add("q", eager=True)
    def cancel_selection(event):
        event.app.exit(result=None)

    @bindings.add(Keys.ControlM, eager=True)
    def pick_row(event):
        ic = next(
            (
                w.content
                for w in event.app.layout.find_all_windows()
                if isinstance(w.content, InquirerControl)
            ),
            None,
        )
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
        confirmed = confirm_kill(picked)
        if confirmed is None:
            print_cancelled()
            return
        if confirmed:
            click.echo(click.style(kill_row(picked), fg="green"))


def list_plain() -> None:
    rows = collect_listening_ports()
    if not rows:
        click.echo(click.style("No TCP ports are being listened on.", fg="yellow"))
        return
    name_width = max(len(", ".join(sorted(r.names)) or "?") for r in rows)
    click.echo(f"{'PORT':<6} {'PID':<8} {'PROCESS':<{name_width}}")
    for row in rows:
        pids = ", ".join(map(str, sorted(row.pids))) or "-"
        names = ", ".join(sorted(row.names)) or "?"
        click.echo(f"{row.port:<6} {pids:<8} {names}")


def run(subtitle: str) -> None:
    if sys.stdin.isatty() and sys.stdout.isatty():
        interactive_tui(subtitle)
    else:
        print_banner(subtitle)
        list_plain()


def kill_port_flow(port: int, assume_yes: bool) -> None:
    print_banner(f"Kill process on port {port}")
    row = next((r for r in collect_listening_ports() if r.port == port), None)
    if row is None:
        click.echo(click.style(f"Port {port}: no process is listening on it", fg="yellow"))
        return
    if not row.pids:
        click.echo(click.style(f"Port {port}: listening, but no process could be identified", fg="yellow"))
        return
    if not assume_yes:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            click.echo(click.style(f"Port {port}: confirmation needs a terminal; use -y to bypass", fg="yellow"))
            return
        if confirm_kill(row) is not True:
            print_cancelled()
            return
    click.echo(click.style(kill_row(row), fg="green"))


@click.command(
    context_settings={"ignore_unknown_options": False},
)
@click.option(
    "--list", "-l",
    is_flag=True,
    expose_value=False,
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
    if ctx.params.get("list"):
        print_banner("Listening TCP ports")
        list_plain()
        return
    if kill is not None:
        kill_port_flow(kill, yes)
        return
    run("Discover and kill dev server ports")


if __name__ == "__main__":
    # pylint: disable=no-value-for-parameter
    # Click injects `ctx` via @click.pass_context at runtime
    main()
