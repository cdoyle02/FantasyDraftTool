Status: done

Commit:
- 51fee31 feat: expose Workbook matchups, feeders, and explain API routes

Implemented:
- Added GET routes for `/api/v1/nfl/workbook/matchups`, `/feeders/{group}`, and `/explain`.
- Mapped workbook invalid parameters to HTTP 400 `invalid_params`.
- Mapped workbook dataset/load failures to HTTP 503 `workbook_unavailable`.
- Added FastAPI route tests using `set_workbook_dataset_override`.

Verification:
- RED: `uv run pytest apps/api/tests/workbook/test_api_workbook.py` failed with 404s before route wiring.
- GREEN: `uv run pytest apps/api/tests/workbook/test_api_workbook.py`
- Regression: `uv run pytest apps/api/tests/workbook/test_api_workbook.py apps/api/tests/workbook/test_service.py apps/api/tests/sos/test_api_sos.py`
- Lint: `uv run ruff check apps/api/src/draft_api/main.py apps/api/tests/workbook/test_api_workbook.py`

Concerns:
- `main.py` already contained uncommitted SoS route/import WIP; the commit includes those coherent `main.py` lines as allowed. The untracked `apps/api/src/draft_api/sos/` package was not added.

Follow-up fix:
- Committed the missing `draft_api.sos` package, packaged `sos_2026.json` snapshot, and `tests/sos` coverage so the SoS route imported by `main.py` works from a clean checkout.
- Left web SoS UI WIP files uncommitted.
- Verified with `uv run --directory apps/api pytest tests/sos tests/workbook -q` (66 passed, 1 Starlette/httpx deprecation warning).
