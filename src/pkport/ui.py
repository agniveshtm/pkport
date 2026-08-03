import click
import questionary

HINT = "(↑/↓: move · Enter: kill selected · q: quit)"

LOGO = """██████╗ ██╗  ██╗██████╗  ██████╗ ██████╗ ████████╗
██╔══██╗██║ ██╔╝██╔══██╗██╔═══██╗██╔══██╗╚══██╔══╝
██████╔╝█████╔╝ ██████╔╝██║   ██║██████╔╝   ██║
██╔═══╝ ██╔═██╗ ██╔═══╝ ██║   ██║██╔══██╗   ██║
██║     ██║  ██╗██║     ╚██████╔╝██║  ██║   ██║
╚═╝     ╚═╝  ╚═╝╚═╝      ╚═════╝ ╚═╝  ╚═╝   ╚═╝"""

STYLE = questionary.Style(
    [
        ("qmark", "fg:ansigreen bold"),
        ("question", "bold"),
        ("instruction", "fg:ansibrightblack"),
        ("pointer", "fg:ansibrightcyan bold"),
        ("highlighted", "fg:white bold"),
        ("selected", "fg:ansigreen"),
        ("separator", "fg:ansibrightblack"),
        ("disabled", "fg:ansired"),
    ]
)


def print_banner(subtitle: str) -> None:
    for line in LOGO.splitlines():
        click.echo(click.style(line, fg="cyan", bold=True))
    click.echo(click.style(subtitle, fg="bright_black"))


def print_cancelled() -> None:
    click.clear()
    for line in LOGO.splitlines():
        click.echo(click.style(line, fg="yellow", bold=True))
    click.echo(click.style("Cancelled by user", fg="blue"))
