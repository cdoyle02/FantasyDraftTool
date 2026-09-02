export const FOOTBALLERS_HEADER = [
  'season',
  'as_of_date',
  'ranking_type',
  'scoring_profile',
  'league_size',
  'position',
  'position_rank',
  'tier_number',
  'tier_rank',
  'tier_size',
  'tier_value_multiplier',
  'player_id',
  'player_name',
  'player_slug',
  'team',
  'bye_week',
  'age',
  'experience',
  'adp_round_pick',
  'adp_overall',
  'risk_score',
  'upside_score',
  'tags',
  'is_my_guy',
  'is_value',
  'is_bust',
  'is_sleeper',
  'is_rookie',
  'is_injury_concern',
  'is_breakout',
  'source_page',
  'source_cheatsheet_id',
  'source_url'
].join(',')

const DEFAULT_META = {
  season: '2026',
  asOfDate: '2026-08-31',
  rankingType: 'redraft',
  scoringProfile: 'Two Flex Too Furious',
  leagueSize: '8',
  sourceCheatsheetId: 'sheet-a',
  sourceUrl: 'https://example.com/cheatsheet'
}

type RowInput = Partial<Record<string, string | number | undefined>> & {
  position: string
  positionRank: number
  playerName: string
  team?: string
}

function row(input: RowInput): string {
  const values: Record<string, string> = {
    season: DEFAULT_META.season,
    as_of_date: DEFAULT_META.asOfDate,
    ranking_type: DEFAULT_META.rankingType,
    scoring_profile: input.scoringProfile?.toString() ?? DEFAULT_META.scoringProfile,
    league_size: input.leagueSize?.toString() ?? DEFAULT_META.leagueSize,
    position: input.position,
    position_rank: String(input.positionRank),
    tier_number: input.tierNumber?.toString() ?? '',
    tier_rank: input.tierRank?.toString() ?? '',
    tier_size: input.tierSize?.toString() ?? '',
    tier_value_multiplier: input.tierValueMultiplier?.toString() ?? '',
    player_id: input.playerId?.toString() ?? '',
    player_name: input.playerName,
    player_slug: input.playerSlug?.toString() ?? '',
    team: input.team ?? 'BUF',
    bye_week: input.byeWeek?.toString() ?? '',
    age: input.age?.toString() ?? '',
    experience: input.experience?.toString() ?? '',
    adp_round_pick: input.adpRoundPick?.toString() ?? '',
    adp_overall: input.adpOverall?.toString() ?? '',
    risk_score: input.riskScore?.toString() ?? '',
    upside_score: input.upsideScore?.toString() ?? '',
    tags: input.tags?.toString() ?? '',
    is_my_guy: input.isMyGuy?.toString() ?? '0',
    is_value: input.isValue?.toString() ?? '0',
    is_bust: input.isBust?.toString() ?? '0',
    is_sleeper: input.isSleeper?.toString() ?? '0',
    is_rookie: input.isRookie?.toString() ?? '0',
    is_injury_concern: input.isInjuryConcern?.toString() ?? '0',
    is_breakout: input.isBreakout?.toString() ?? '0',
    source_page: '1',
    source_cheatsheet_id: input.sourceCheatsheetId?.toString() ?? DEFAULT_META.sourceCheatsheetId,
    source_url: DEFAULT_META.sourceUrl
  }
  return FOOTBALLERS_HEADER.split(',').map((header) => values[header] ?? '').join(',')
}

export function buildFootballersCsv(rows: RowInput[], options?: { leagueSize?: number; scoringProfile?: string; sourceCheatsheetId?: string }): string {
  const enriched = rows.map((entry) => ({
    ...entry,
    leagueSize: options?.leagueSize ?? entry.leagueSize,
    scoringProfile: options?.scoringProfile ?? entry.scoringProfile,
    sourceCheatsheetId: options?.sourceCheatsheetId ?? entry.sourceCheatsheetId
  }))
  return [FOOTBALLERS_HEADER, ...enriched.map((rowInput) => row({
    ...rowInput,
    sourceCheatsheetId: options?.sourceCheatsheetId ?? rowInput.sourceCheatsheetId
  }))].join('\n')
}

export function leagueARows(): RowInput[] {
  return [
    {
      position: 'QB',
      positionRank: 1,
      playerName: 'Josh Allen',
      playerSlug: 'josh-allen',
      team: 'BUF',
      tierNumber: 9,
      tierRank: 1,
      tierSize: 1,
      tierValueMultiplier: 0.99,
      adpOverall: 901,
      adpRoundPick: '901.01',
      riskScore: 9.01,
      upsideScore: 9.91,
      tags: 'my_guy|breakout',
      isMyGuy: 1,
      isBreakout: 1
    },
    {
      position: 'DST',
      positionRank: 1,
      playerName: 'Philadelphia Eagles',
      playerSlug: 'philadelphia-eagles',
      team: 'PHI'
    }
  ]
}

export function leagueBRows(): RowInput[] {
  return [
    {
      position: 'QB',
      positionRank: 1,
      playerName: 'Josh Allen',
      playerSlug: 'josh-allen',
      team: 'BUF',
      tierNumber: 2,
      tierRank: 1,
      tierSize: 1,
      tierValueMultiplier: 0.77,
      adpOverall: 802,
      adpRoundPick: '802.02',
      riskScore: 8.02,
      upsideScore: 8.82,
      sourceCheatsheetId: 'sheet-b'
    },
    {
      position: 'DST',
      positionRank: 1,
      playerName: 'Philadelphia Eagles',
      playerSlug: 'philadelphia-eagles',
      team: 'PHI'
    }
  ]
}

export const defaultLeagueSettings = {
  name: 'Two Flex Too Furious',
  teamCount: 8,
  userTeam: 4,
  rosterSlots: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 2, SUPERFLEX: 0, BENCH: 6, K: 0, DST: 1 },
  scoring: 'PPR' as const,
  draftType: 'SNAKE' as const,
  formulaVersion: 4
}
