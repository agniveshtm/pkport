import questionary

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
