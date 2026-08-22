"""Exercise normalized ESPN draft picks against a known public historical league.

Run with ``uv run python scripts/public_draft_smoke_test.py`` from tools/espn-mcp.
This intentionally builds a credential-free configuration and never reads .env.
"""

from __future__ import annotations

import asyncio
import json

from espn_mcp.client import EspnConfig
from espn_mcp.server import draft_picks

# A completed, publicly readable ESPN football draft referenced by ffscrapr's
# ESPN endpoint documentation. Historical data makes the smoke test stable.
PUBLIC_SEASON = 2020
PUBLIC_LEAGUE_ID = "899513"


async def main() -> int:
    result = json.loads(
        await draft_picks(
            EspnConfig(
                season=PUBLIC_SEASON,
                league_id=PUBLIC_LEAGUE_ID,
                espn_s2=None,
                swid=None,
            ),
            PUBLIC_LEAGUE_ID,
            limit=3,
        )
    )

    assert result["season"] == PUBLIC_SEASON
    assert result["league_id"] == PUBLIC_LEAGUE_ID
    assert result["total_picks"] >= 3
    assert result["returned"] == 3
    assert [pick["overall_pick"] for pick in result["picks"]] == [1, 2, 3]
    assert all(pick["player_id"] for pick in result["picks"])
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
