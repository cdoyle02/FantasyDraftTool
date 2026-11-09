# SoS Clay Out/Slot Splits — Implementation Plan

> **For agentic workers:** TDD; commit per task. Stay on `feature/A.1-nfl-week-dst-odds`.

**Goal:** `wrRole=all|outside|slot` on SoS Tier 1/2 WR grid + opportunity using Clay roles.

**Design SSOT:** `docs/superpowers/specs/2026-11-08-sos-clay-out-slot-splits-design.md`

## Global Constraints

- Reuse `draft_api.workbook.roles` / `clay_pdf` — do not duplicate classify rules
- Do not change behavior when `wrRole` omitted or `all`
- Never invent roles for unlisted WRs
- No secrets; CI offline via fixtures

## File map

| Path | Responsibility |
|------|----------------|
| `sos/clay_roles.py` | Resolve role index (live/snapshot); filter stats rows by role |
| `sos/snapshot.py` / `refresh.py` / `nflverse.SosDataset` | Optional `clayRoles` |
| `sos/usage.py` | Add `fantasy_points_ppr` to trim fields |
| `sos/tier2_epa.py` | Accept optional role filter when summing WR EPA |
| `sos/tier1.py` / `calculate` helpers | Role-filtered aFPA from stats fantasy points |
| `sos/service.py` + `main.py` | `wrRole` query param |
| `WeekSosView.tsx` | WR role toggle |
| tests | Pure + API + vitest |

---

### Task 1: Resolve Clay roles + filter stats

- Create `sos/clay_roles.py`: `resolve_clay_role_index(season, …)`, `filter_stats_by_clay_role(rows, role_index, wr_role)`
- Tests with fixture roles
- Commit `feat: SoS Clay role index and WR stats filter`

### Task 2: Package clayRoles on sos snapshot

- `SosDataset.clay_roles`; snapshot `clayRoles`; refresh loads Clay PDF (merge last-known)
- Fallback chain in service
- Commit `feat: embed clayRoles in SoS snapshot`

### Task 3: Tier 2 EPA + Tier 1 aFPA honor wrRole

- Wire filter into tier2 EPA WR path and tier1 shrunk aFPA from `fantasy_points_ppr`
- Add `fantasy_points_ppr` to `USAGE_STATS_FIELDS`
- API tests: slot vs outside ranks differ on fixture
- Commit `feat: SoS Tier1/Tier2 WR Out/Slot Clay splits`

### Task 4: Opportunity + UI

- Opportunity filters players to matching role; uses role-specific softness
- WeekSosView WR toggle All/Out/Slot; client passes `wrRole`
- Commit `feat: SoS UI Clay Out/Slot WR role toggle`

### Task 5: Refresh sos snapshot + verify + push

- Refresh; pytest sos; vitest WeekSosView; push branch
