"""A personal multi-tool command-line app."""

__version__ = "0.1.0"


def main() -> None:
    from toolbox.cli import app

    app()
