---
name: run-espn-draft-smoke-test
description: Run and report the credential-free public ESPN draft-pick smoke test for this Fantasy Draft Tool repository. Use for verifying the ESPN MCP draft normalization path, not private leagues.
---

# Run ESPN draft smoke test

Run the repository's public ESPN draft smoke test from `tools/espn-mcp`:

```bash
uv run python scripts/public_draft_smoke_test.py
```

The script calls the existing ESPN MCP draft-pick normalization path against a
known completed public 2020 football league. It deliberately builds a
credential-free configuration; do not read `.env`, browser cookies, or request
private-league data.

Report whether the command passed and summarize the returned draft status and
pick count. If `uv` or the declared Python runtime is unavailable, state that
limitation exactly. Do not substitute credentials or alter the test target; the
last verified public-data result was a completed 220-pick draft for league
`899513`, season `2020`.
