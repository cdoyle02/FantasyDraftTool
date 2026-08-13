"""Connect to the server over stdio and exercise the read-only tools.

Run with: uv run python scripts/smoke_test.py
"""

from __future__ import annotations

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters, stdio_client


async def main() -> int:
    params = StdioServerParameters(command=sys.executable, args=["-m", "espn_mcp.server"])
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()

        tools = await session.list_tools()
        print("tools:", ", ".join(tool.name for tool in tools.tools))

        status = await session.call_tool("espn_status", {})
        print("\nespn_status ->")
        print(_text(status))

        players = await session.call_tool(
            "espn_players", {"limit": 3, "position": "QB", "include_projections": False}
        )
        print("\nespn_players ->")
        print(_text(players))
    return 0


def _text(result: object) -> str:
    content = getattr(result, "content", [])
    return "\n".join(getattr(block, "text", "") for block in content)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
