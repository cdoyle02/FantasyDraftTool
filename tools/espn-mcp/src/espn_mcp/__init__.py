"""MCP server for ESPN fantasy football v3 endpoint exploration."""

__all__ = ["main"]


def main() -> None:
    from .server import main as _main

    _main()
