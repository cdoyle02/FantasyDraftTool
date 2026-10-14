# Desired features from chats (wishlist)

**Date:** 2026-10-10  
**Mode:** Evidence-only wishlist from Cursor transcripts + skills. Not a build plan. Surfaces listed unranked. No invented capabilities.  
**Implementation design:** deferred until after the full audit — see [full codebase analysis](./2026-10-10-full-codebase-analysis.md).

**Sources:** Cursor `agent-transcripts` (~31 parents, 2026-08-18 → 2026-10-10), project/personal skills, MCP/API inventory.

---

## Capability wishlist

| Capability name | Evidence (chat UUIDs + skill names) | Frequency | Exists today? | Candidate surfaces UNRANKED | Data deps | Priority hint |
|-----------------|-------------------------------------|-----------|---------------|----------------------------|-----------|---------------|
| Katie weekly waiver briefing | Chats: `1ad4c10a`, `c092f4a7`, `0e83ed62`, `0bfcb9ed`; skills: `kyle-weekly-dst`, `thorman-rb-cross-ref`; MCP prompts `katie_roster` / tools `espn_league_rosters`, `espn_free_agents` | High (~12 GWB-centric chats; dominant ops theme) | Chat-only orchestration (pieces exist) | web / API / MCP / skill | ESPN roster+FA (Katie/GWB cookies); expert boards (Kyle DST, Thorman RB, etc.); optional Ballers ep | P0 |
| Best available D/ST (expert × FA) | Chats: `6b6542f3`, `b2926d83`, `1e832c3d`, `3d4b6bc8`; skills: `kyle-weekly-dst`, `ted-blueprint-weekly-def`, `espn-available-dst`; MCP `kyle_dst_available`; API `/nfl/kyle-dst-available`; Week D/ST UI | High (multiple weeks W1–2; fix + product chats) | API + MCP + web UI + skill (Kyle path); Ted skill-only | web / API / MCP / skill | FantasyPros Kyle HTML; optional Blueprint Ted; ESPN slot-16 FA/WAIVERS; leagueId | P0 |
| Best available K (Jared × FA) | Chats: `5861069e`, `41bb919c`; skill: `jared-smola-weekly-k`; MCP `jared_k_available`; API `/nfl/jared-k-available`; Week K UI | Medium–high (Katie + Michael leagues; UX parity fix) | API + MCP + web UI + skill | web / API / MCP / skill | FantasyPros Jared HTML; ESPN slot-17 FA/WAIVERS; leagueId | P0 |
| Thorman / Calandro WR × roster/FA | Chat: `3984b0b2`; skills: `patrick-thorman-weekly-wr`, `thorman-wr-cross-ref`, `jamie-calandro-2026-wr1-weekly-wr`, `calandro-2026-wr1-cross-ref` | Medium (named weeks W1/3/4; cross-ref pattern) | Skill-only (WR plan: no UI) | web / API / MCP / skill | Comet CDP → FantasyPros partners (filters 534 / 636); ESPN WR FA + owner roster | P1 |
| Ballers episode → team roster briefing | Chats: `ad78401b`, `9296c748`, `0e83ed62`; MCP `ballers_latest` + prompt `ballers_and_roster`; Firecrawl in chat | Medium (mid-Sep → early Oct cluster) | MCP partial (`ballers_latest`); full team briefing chat-only | web / API / MCP / skill | FFBallers scrape + captions; ESPN live roster/FA; player-name join | P1 |
| Thorman RB × Katie starters/FA | Chats: `c092f4a7`, `1ad4c10a`; skills: `patrick-thorman-weekly-rb`, `thorman-rb-cross-ref` | Medium (paired with Katie waiver) | Skill-only | web / API / MCP / skill | Comet + FP filter 534; ESPN RB FA + roster | P1 |
| Ted / multi-expert DEF × available DST | Chats: `b2926d83`, `bffdc359`; skills: `ted-blueprint-weekly-def`, `espn-available-dst`; explore Mick Ciallela | Low–medium (Ted once + Mick explore) | Skill-only (Ted); Mick none | web / API / MCP / skill | Blueprint / Fantrax/web ranks; ESPN DST FA | P2 |
| Draft-day / weekly odds → DST sort | Chats: `3d4b6bc8`, `f8bff345`, `3b6a7eab`; MCP `week_odds`; API `/nfl/week-odds`; Week D/ST UI | Medium (DVS W1–2 + hardening) | API + MCP + web UI (partial) | web / API / MCP / skill | Odds API key; NFL week boundary; DST join | P1 |
| Hosted household ESPN MCP (Katie + Michael) | Chats: `4112d41f`, `29246076`, `e475898a`, `0bfcb9ed` | Medium–high (Oct 6–10 peak) | MCP partial (HTTP + profiles/OAuth exist) | MCP / skill | ESPN cookies per profile; bearer/OAuth; league directory | P1 |
| Live multi-league roster dataset / “my players” | Chats: `0bfcb9ed`, `e475898a`, `28fcc2ee`; MCP `espn_league_rosters`, `espn_league_directory`; `data/rosters` snapshots | Medium | MCP + offline snapshot; web roster page desired in chat | web / API / MCP / skill | ESPN cookies; `espn_leagues.json` | P1 |
| Walking Wounded team alias in waiver flows | Chat: `0e83ed62` (named with Katie/GWB) | Low (named once clearly) | None / chat naming only | MCP / skill / web | Owner→team mapping beyond Katie default | P2 |
| NoExpert / FFBallers RB rank scrape | Chats: `9296c748`, `dcfd451a` | Low | None (chat Firecrawl demos) | skill / MCP / API | External scrape; paywall risk | P2 |
| Durable scrape/transcript store for hosted use | Chat: `524dae01` (`.firecrawl` / hosting) | Low | None (ops question) | API / MCP | Blob/store for Ballers/Firecrawl artifacts | P2 |
| ChatGPT phone / remote client parity | Chat: `4112d41f` (ChatGPT OAuth path vs Claude) | Low–medium (hosting theme) | MCP partial (OAuth exists; phone path unclear) | MCP | Same as hosted MCP auth | P2 |
| Schedule-aware “who plays today on my team?” | Gap note in K (early MCP ask; not repeated product) | Low | None clear | MCP / API / web | NFL schedule + ESPN roster | P2 |
| FootClan **strength-of-schedule** positional matchups chart | User ask (2026-10-11); [FFB SoS](https://www.thefantasyfootballers.com/footclan/strength-of-schedule/); PPG-allowed / EPA heat map (WR1/WR2/Slot/TE/RB/QB) | Weekly habit | None in FantasyDraftTool | web / API / MCP / skill | FootClan SoS page (scrape or licensed export); week schedule | P1 |
| **Mike Clay WR shadow report** (WR vs CB matchup cheatsheet) | Perplexity [search](https://www.perplexity.ai/search/80d4eb18-30aa-48bf-9041-f9c27ddbd716); ESPN Week 5 Playbook/shadow story; ESPN PDF `NFL26_CS_WRCB.pdf`; local research notes | Weekly (in-season) | None (Perplexity/ESPN PDF today) | web / API / MCP / skill / Perplexity project | ESPN draft-kit PDF or story; alignment L/R/S + shadow F/R Diff/Score; optional join to Katie roster | P1 |
| **Headless screenshot / page-capture** for automated research | Perplexity Computer + Cloudflare Browser Rendering handoff (text scrape OK; screenshot file path unreliable → prefer Comet tab capture or PDF→images) | Occasional (automation infra) | Partial outside repo; not in FantasyDraftTool | skill / MCP / external connector | CF Browser Rendering or local Comet/PDF pipeline; never store API tokens in git | P2 |
| **Perplexity project + Deep Research harness** | [Perplexity project Fantasy Draft Tool - ESPN NFL](https://www.perplexity.ai/projects/fantasy-draft-tool-espn-nfl-7i.qF9HERduncme832PrEw); Deep Research builder notes; project activity (Clay shadow, injury/matchup research) | Ongoing | External (Perplexity); not wired into apps/MCP | skill / MCP / docs / Perplexity automation | Perplexity project context + ESPN MCP when available; FantasyDraftTool remains SoT for live rosters | P1 |
| **Sunday morning / gameday player-status research routine** | Perplexity Computer task; Katie team player-notes research; checklist (inactives, elevations) + automations: retry Katie BIG TDs roster, official inactive lists, replacement if starter out | Weekly Sunday habit | Chat/Perplexity only | skill / MCP / Perplexity automation / web | Live ESPN roster (Katie); NFL inactive lists; injury news; optional week tools for replacements | P0 |
| **Player intelligence dashboard** (unified per-player view) | User ask (2026-10-11): after Clay shadow, show WR matchup F/R Diff/Score tied to that player plus news, Ballers mentions, SoS, roster/FA, expert ranks | Weekly (lineup + waiver) | None (data in silos) | web (primary) / API / MCP | Player identity join; Clay F/R; FootClan SoS; Ballers notes; news/status; ESPN roster/FA; optional expert boards | P0 |
| **Injury impact model (same-team context)** | Apple Note “Fantasy Ideas”: how injuries change points — same-position teammates, stars (e.g. Saquon / DeVonta / Goedert-style), starters vs handcuffs; snap %, attempts, opportunities, game script; upward/downward alerts | Product concept (recurring ops need) | None | web / API / MCP / skill | Injury/status feeds; teammate graph; snap/opportunity stats; game script | P1 |
| **Player attribute ledger + “why this week?”** | Apple Note “Fantasy Ideas”: tracked attributes (gameflow, injuries, …); position-weighted importance; explain past weeks (targets/attempts); map attributes onto upcoming games (season history + roster/opponent factors) | Product concept | None | web / API / MCP / skill | Attribute store; weekly stats; schedule/opponent; roster changes | P1 |
| **RB starter/handcuff relationship graph** | Apple Note “Fantasy Ideas”: explicit starter↔handcuff pairs; paired alerts on status/workload changes | Overlaps Thorman RB / handcuff chat patterns | Skill glue only (no first-class product) | web / API / MCP / skill | Depth charts; ESPN roster/injury; RB expert boards | P1 |
| **Shared research inbox / triage queue (Katie ↔ Michael)** | Shared iCloud Apple Note [Fantasy](https://www.icloud.com/notes/0ecG24yXNqS8c_wABa8cMsgVA#Fantasy); week-of 2026-10-10 examples: Tate injury/replacement; Meyers↔Chase/Higgins; Allgeier game environment; E. Wilson backfield share | Weekly household ops | Chat-only (Apple Notes + ask Michael/Cursor) | MCP / skill / web | ESPN roster/injury; teammate context; schedule/environment; FA replacements | P0 |

---

## Addendum (2026-10-11) — Perplexity, matchups, unified dashboard

User-requested expansions beyond the original Cursor-transcript mine. Still wishlist-only; **no implementation design** in this doc.

### External research surfaces (Perplexity)

- Project: [Fantasy Draft Tool - ESPN NFL](https://www.perplexity.ai/projects/fantasy-draft-tool-espn-nfl-7i.qF9HERduncme832PrEw) — Deep Research, web search, Computer tasks, optional Browser Rendering connector.
- Role vs Cursor/Claude MCP: complementary research + automations; **live ESPN rosters/FA stay on FantasyDraftTool MCP/API**.
- Do not commit Cloudflare/Pipedream secrets or account IDs from local handoff notes.

### Player intelligence dashboard

- **Unit of view:** one NFL player (start with WRs; extend later).
- **Join siloed signals** onto one card: Clay shadow F/R Diff/Score, FootClan SoS positional rank, Ballers transcript hits, Sunday/news status, ESPN roster/FA, expert cross-refs when available.
- **Entry points (unranked):** team board → player drill-down; or “Katie starters this week” with columns per signal.
- **Hard problem:** name/team identity matching across ESPN, Clay PDF, Ballers text, and news — not solved here.

---

## Addendum (2026-10-13) — Apple Notes evidence

Still wishlist-only; no Apple Notes sync or injury-model implementation in this pass.

### Fantasy Ideas (product concepts)

From the personal “Fantasy Ideas” note: injury impact in same-team context; attribute ledger with “why this week?” explanations; RB starter/handcuff graph with paired alerts. Exact attribute schemas deferred.

### Shared Katie ↔ Michael ops inbox

Shared note [Fantasy](https://www.icloud.com/notes/0ecG24yXNqS8c_wABa8cMsgVA#Fantasy) acts as a triage queue (example week 2026-10-10: Tate, Meyers/Chase-Higgins, Allgeier, E. Wilson). Desired capability: capture questions and research/triage them in-app or via MCP/skill, eventually replacing or syncing from Apple Notes.

---

## Already covered by MCP/API

Evidence from E + C (and product use in K):

| Capability slice | Where it lives today |
|------------------|----------------------|
| Kyle DST ranks × league-available DST | API `GET /api/v1/nfl/kyle-dst-{rankings,available}`; MCP `kyle_dst_available`; web Week D/ST; skill `kyle-weekly-dst` |
| Jared K ranks × league-available K | API `GET /api/v1/nfl/jared-k-{rankings,available}`; MCP `jared_k_available`; web Week K; skill `jared-smola-weekly-k` |
| Current-week NFL odds / implied totals | API `GET /api/v1/nfl/week-odds`; MCP `week_odds` |
| Live league rosters + directory | MCP `espn_league_rosters`, `espn_league_directory` (not mirrored as first-class week HTTP routes in C) |
| Free agents / waivers query | MCP `espn_free_agents` |
| Latest Ballers episode summary (+ captions when available) | MCP `ballers_latest` only (no draft_api route in C) |
| Draft recommendations / CSV import | API `/recommendations`, `/imports/csv` (draft path; not the weekly waiver journey) |
| MCP prompts for common bundles | `katie_roster`, `league_rosters`, `ballers_and_roster`, `week_dst_k` (prompt composition, not new data tools) |

**Note:** “Exists” for DST/K does not mean chat journeys stop—K still runs skills and asks for Katie cross-refs / UX fixes (`1e832c3d`, `41bb919c`).

---

## Chat-only today

Workflows repeated or strongly desired in K with **no** equivalent first-class MCP tool or API route (skills and/or agent glue only):

1. **One-shot Katie waiver briefing** — Ballers waiver talk + GWB roster/FA + multi-position experts (“who beats my starters?”) — `1ad4c10a`, `0e83ed62`, `c092f4a7`.
2. **Thorman / Calandro WR cross-ref** — full-PPR boards × Katie roster/FA — `3984b0b2` + project WR skills (G: skills-only per 2026-10-01 spec).
3. **Thorman RB cross-ref** — personal skills; used inside Katie weekly chats — `c092f4a7`, `1ad4c10a`.
4. **Ted Blueprint DEF × FA** — skill `ted-blueprint-weekly-def`; not an MCP/API twin — `b2926d83`.
5. **Mick / extra DEF expert boards** — explore only — `bffdc359`.
6. **Ballers → team-specific waiver markdown** beyond `ballers_latest` raw episode — `ad78401b`, `0e83ed62`.
7. **NoExpert / paywalled RB ranking scrapes** — `9296c748`, `dcfd451a`.
8. **Walking Wounded as normalized team target** — chat-named — `0e83ed62`.
9. **Comet-dependent expert boards in cloud** — G: Thorman/Calandro not portable without local Comet; chats still invoke them locally.
10. **FootClan SoS positional chart** — external site only today.
11. **Mike Clay WR shadow report** — ESPN PDF / Perplexity research only.
12. **Sunday morning inactive / elevation checklist** — Perplexity Computer / chat only.
13. **Player intelligence dashboard** — no unified UI; signals stay siloed.
14. **Perplexity Deep Research harness** — project exists outside the repo.
15. **Shared Apple Notes Fantasy triage with Katie** — inbox in iCloud Notes only.
16. **Injury impact / attribute ledger / RB handcuff graph** — Fantasy Ideas concepts only.

---

## Explicit out of scope

Out of scope for this wishlist (evidence from K omissions / non-fantasy clusters; do not treat as product asks):

- Pure git / branch / RDP / generic cloud-agent config chats (`dd9b02d9`, `23a88641`, `2bb0bf9e`, `d61f30b4`, `a856c966`, `f960a921`).
- FantasyPros **login mechanics** as a product feature (`d372ec43`) — auth side-quest, not a ranked capability.
- Choosing **source of truth** among Claude remote vs Cursor vs web UI (open question in K; not a feature row).
- Committing secrets, reading `.env`, Cloudflare/Pipedream tokens, or account IDs into the repo.
- Designing credential UX beyond “private-league access without pasting passwords” as observed in `29246076` / hosting chats.
- Inventing new expert sources, leagues, or UI tabs not named in evidence above.
- Ranking or sequencing implementation (architecture / build plan deferred).
- Licensed scrape approach for ESPN Clay PDF / FootClan SoS (source TBD: PDF ingest vs scrape vs manual upload).
- Full UI mockups for the player intelligence dashboard.

---

## Evidence notes (non-normative)

- **Cross-ref pattern** (expert × ESPN FA × owner roster) is the recurring shape across DST → K → RB → WR (K frequency notes).
- **Katie / Girls Who Ball** dominates; Michael/DVS appears mainly for odds/DST app work.
- **WR** remains skill-only by approved design; **DST/K** already have API/MCP/web twins of personal skills.
- Priority hints = recurrence + ops centrality in K, not roadmap commitments (P0 ≈ weekly household ops; P1 ≈ repeated adjacent journeys; P2 ≈ one-off / explore / unclear ship state).