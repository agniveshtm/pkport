# PKPORT

```
██████╗ ██╗  ██╗██████╗  ██████╗ ██████╗ ████████╗
██╔══██╗██║ ██╔╝██╔══██╗██╔═══██╗██╔══██╗╚══██╔══╝
██████╔╝█████╔╝ ██████╔╝██║   ██║██████╔╝   ██║
██╔═══╝ ██╔═██╗ ██╔═══╝ ██║   ██║██╔══██╗   ██║
██║     ██║  ██╗██║     ╚██████╔╝██║  ██║   ██║
╚═╝     ╚═╝  ╚═╝╚═╝      ╚═════╝ ╚═╝  ╚═╝   ╚═╝
```

Discover and kill dev server ports from an interactive terminal picker or directly via CLI flags.

## Features

- 🔍 **Auto-discovery** — scans all TCP listening ports and resolves the owning process names.
- 🎛️ **Interactive TUI** — pick a port from a searchable/enhanced menu, confirm, and kill it without leaving the terminal.
- 🗂️ **Plain-text listing** — `pkport -l` prints a clean table of ports, PIDs, and process names.
- 🎯 **Kill by port** — `pkport -k <PORT>` terminates the process listening on a specific port.
- ✅ **Safe by default** — asks for confirmation before killing, with `-y` to bypass.
- 🛡️ **Robust error handling** — gracefully handles `AccessDenied` (permission errors) and `NoSuchProcess` (already-gone processes).
- 🚫 **Non-TTY friendly** — falls back to plain listing when stdin/stdout aren't a terminal (perfect for CI/scripts).
- 🖥️ **Cross-platform** — Linux, macOS, and Windows.

## Architecture

```
pkport/
├── .github/
│   └── workflows/
│       ├── test.yml              # CI: pytest matrix (ubuntu/windows/macos)
│       └── release.yml           # CD: sdist/wheel + Windows .exe on v* tags
├── src/
│   └── pkport/
│       ├── __init__.py
│       ├── main.py               # CLI entry point, port collection, kill logic
│       └── ui.py                 # Banner, TUI styling, shared UI helpers
├── tests/
│   └── test_main.py              # 10 unit + CLI tests (psutil mocked)
├── .python-version               # Python 3.12
├── Makefile                      # make test → pytest
├── pyproject.toml                # Project metadata + uv_build backend
└── uv.lock                       # Locked dependency graph
```

## Flow

```
$ pkport
        │
        ▼
┌───────────────────────┐
│   Print ASCII banner  │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│  Scan TCP listening   │
│  ports (psutil)       │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐        ┌───────────────────────────────┐
│   Interactive picker  │───────▶│  Confirm kill (y/n)           │
│   (↑/↓ · Enter · q)   │        │  → kills process(es) on port │
└───────────────────────┘        └───────────────────────────────┘
        │
        ▼
   Refresh & repeat
```

Non-interactive paths: `pkport -l` lists ports and exits; `pkport -k <PORT> [-y]` kills a specific port.

## Tech Stack

| Category     | Technology                                   |
| ------------ | -------------------------------------------- |
| Language     | Python 3.12                                  |
| CLI          | [Click](https://click.palletsprojects.com/)  |
| Process info | [psutil](https://github.com/giampaolo/psutil) |
| Interactive  | [questionary](https://questionary.readthedocs.io/) / [prompt_toolkit](https://python-prompt-toolkit.readthedocs.io/) |
| Testing      | pytest                                       |
| Packaging    | uv / uv_build / PyInstaller                  |

## Keybindings & Commands

### TUI Keybindings

| Key      | Action                      |
| -------- | --------------------------- |
| `↑` / `↓` | Move through the port list |
| `Enter`  | Kill the selected port      |
| `q`      | Quit the picker             |

### CLI Commands

| Command                 | Description                                              |
| ----------------------- | -------------------------------------------------------- |
| `pkport`                | Launch the interactive TUI (or plain list if not a TTY)  |
| `pkport --list` / `-l`  | List all listening TCP ports with PID and process name   |
| `pkport --kill PORT` / `-k PORT` | Kill the process listening on `PORT`          |
| `pkport -y` / `--yes`   | Skip the confirmation prompt (used with `--kill`)        |

Example:

```bash
pkport -k 8080 -y     # kill whatever is on port 8080, no questions asked
```

## Benchmark

Run the test suite with `make test` (or `uv run pytest tests/`):

```
============================================ test session starts ============================================
platform win32 -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\Projects\pkport
configfile: pyproject.toml
collected 10 items

tests\test_main.py ..........                                                                          [100%]

============================================ 10 passed in 1.03s =============================================
```

## Installation

### Prerequisites

- **Python 3.12+** — the package supports Python >= 3.12.
- One of: [uv](https://docs.astral.sh/uv/), [pipx](https://pipx.pypa.io/), or `pip` (bundled with Python).

### Install via Executables (.exe)

Windows users can download the pre-built standalone executable from the [Releases](https://github.com/agniveshtm/pkport/releases) page — no Python required:

1. Download `pkport.exe` from the latest release.
2. Run it from a terminal:

```bat
pkport.exe -l
```

### Install via uv tool

```bash
uv tool install pkport
```

### Install via pipx

```bash
pipx install pkport
```

### Install via pip

```bash
pip install pkport
```

### Install via Wheel

Download the `.whl` file from the [Releases](https://github.com/agniveshtm/pkport/releases) page, then:

```bash
pip install pkport-0.1.0-py3-none-any.whl
```

### Install from Source (Development)

```bash
git clone https://github.com/agniveshtm/pkport.git
cd pkport
uv sync                    # create venv + install dev deps (pytest, pyinstaller)
uv run pkport              # or: uv run python -m pkport.main
```

## Usage

```bash
# Interactive picker (TTY)
pkport

# List listening ports
pkport -l

# Kill a specific port with confirmation
pkport -k 3000

# Kill a specific port without confirmation
pkport -k 3000 -y
```

Example `pkport -l` output:

```
PORT   PID      PROCESS
3000   456      node
8080   123      python
```

## Project Links

- [uv](https://docs.astral.sh/uv/) — Python package manager used for sync/build/install
- [Click](https://click.palletsprojects.com/) — CLI framework
- [Python Standard Library](https://docs.python.org/3/library/) — core building blocks
- [questionary](https://questionary.readthedocs.io/) — interactive prompts
- [psutil](https://github.com/giampaolo/psutil) — process/system utilities
- [PyInstaller](https://pyinstaller.org/) — standalone executable builds
- [GitHub Repository](https://github.com/agniveshtm/pkport)
- [Releases](https://github.com/agniveshtm/pkport/releases)

## License

[MIT](LICENSE) © 2026 [agniveshtm](https://github.com/agniveshtm)
