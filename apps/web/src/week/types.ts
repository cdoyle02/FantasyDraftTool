/** Provider-agnostic NFL week odds + D/ST stream rows from the API. */

export interface WeekOddsGame {
  homeTeam: string
  awayTeam: string
  commenceTime: string
  spread: number
  total: number
  favoriteTeam: string
  underdogTeam: string
  /** Implied points the favorite offense scores (= underdog D/ST points allowed). */
  favoriteImplied: number
  /** Implied points the underdog offense scores (= favorite D/ST points allowed). */
  underdogImplied: number
  dstPlayTeam: string
  bookmaker: string
}

export interface WeekOddsResponse {
  week: number
  windowStart: string
  windowEnd: string
  fetchedAt: string
  games: WeekOddsGame[]
}

export type WeekOddsSortKey =
  | 'underdogImplied'
  | 'favoriteImplied'
  | 'spread'
  | 'total'
  | 'commenceTime'
  | 'dstPlayTeam'

export interface EspnLeague {
  id: string
  name: string
}

export interface EspnLeaguesResponse {
  leagues: EspnLeague[]
}

export interface KyleDstRanking {
  rank: number
  team: string
  teamName: string
  opponent: string
  ecr: number | null
  vsEcr: string
}

export interface KyleDstRankingsResponse {
  week: number | null
  fetchedAt: string
  sourceUrl: string
  rankings: KyleDstRanking[]
}

export interface KyleDstAvailableRow extends KyleDstRanking {
  status: string
  percentOwned: number | null
}

export interface KyleDstAvailableResponse extends KyleDstRankingsResponse {
  leagueId: string
  leagueName: string
  available: KyleDstAvailableRow[]
}

export interface JaredKRanking {
  rank: number
  player: string
  team: string
  opponent: string
  ecr: number | null
  vsEcr: string
}

export interface JaredKRankingsResponse {
  week: number | null
  fetchedAt: string
  sourceUrl: string
  rankings: JaredKRanking[]
}

export interface JaredKAvailableRow extends JaredKRanking {
  status: string
  percentOwned: number | null
}

export interface JaredKAvailableResponse extends JaredKRankingsResponse {
  leagueId: string
  leagueName: string
  available: JaredKAvailableRow[]
}

export type SosPosition = 'QB' | 'RB' | 'WR' | 'TE' | 'DST'
export type SosMetric = 'fpa' | 'pae'

export interface SosWeekCell {
  week: number
  opponent: string | null
  opponentRank: number | null
  opponentValue: number | null
  bye: boolean
  inWindow: boolean
}

export interface SosTeamRow {
  team: string
  rank: number
  opponentAverage: number | null
  weeks: SosWeekCell[]
}

export interface StrengthOfScheduleResponse {
  season: number
  position: SosPosition
  metric: SosMetric
  startWeek: number
  endWeek: number
  ratedThroughWeek: number
  fetchedAt: string
  source: string
  stale: boolean
  teams: SosTeamRow[]
}

export interface StrengthOfScheduleQuery {
  position: SosPosition
  metric: SosMetric
  startWeek?: number
  endWeek?: number
  season?: number
}

export type SosTier1Window = 'l4' | 'l8' | 'season'
export type SosSoftness = 'soft' | 'neutral' | 'tough'

export interface SosTier1WeekCell {
  week: number
  opponent: string | null
  shrunkAfpa: number | null
  rank: number | null
  softness: SosSoftness | null
  softnessScore: number | null
  bye: boolean
  inWindow: boolean
}

export interface SosTier1TeamRow {
  team: string
  rank: number
  opponentAverage: number | null
  weeks: SosTier1WeekCell[]
}

export interface StrengthOfScheduleTier1Response {
  season: number
  position: SosPosition
  window: SosTier1Window
  startWeek: number
  endWeek: number
  ratedThroughWeek: number
  ratingWeeks: number[]
  shrinkK: number
  fetchedAt: string
  source: string
  stale: boolean
  teams: SosTier1TeamRow[]
}

export interface StrengthOfScheduleTier1Query {
  position: SosPosition
  window?: SosTier1Window
  startWeek?: number
  endWeek?: number
  season?: number
}

/** Workbook Net Matchups — see `apps/api/src/draft_api/workbook/README.md` (SSOT for the math). */

export type WorkbookWindow = 'l4' | 'season' | 'custom'
export type WorkbookScoring = 'ppr' | 'half_ppr'
export type WorkbookSlate = 'main' | 'all'
export type WorkbookExplainMetric =
  | 'dsr'
  | 'qb_fp'
  | 'wr_fp'
  | 'te_fp'
  | 'rb_fp'
  | 'out_wr_fp'
  | 'slot_wr_fp'
export type WorkbookFeederGroup = 'dsr' | 'qb' | 'wr' | 'te' | 'rb' | 'targets' | 'yards' | 'tds'

export interface WorkbookGameEnvironment {
  netDsr: number | null
  combNetDsr: number | null
  netDsrDiff: number | null
  netProe: number | null
  netPassPlays: number | null
  netEpaPass: number | null
  netXplsvPass: number | null
  netRunPlays: number | null
  netEpaRun: number | null
  netXplsvRun: number | null
  vegasImpliedPoints: number | null
}

/** One OFF/DEF-netted positional block (QB / ALL WR / Out WR / Slot WR / TE / RB). Keys vary
 * per group (see README); `reason` is set instead of metrics when Out/Slot sample is too thin. */
export interface WorkbookPositionalBlock {
  [metric: string]: number | string | null | undefined
  reason?: string
}

export interface WorkbookTeamRow {
  team: string
  homeAway: 'home' | 'away'
  opponent: string
  gameEnvironment: WorkbookGameEnvironment
  qb: WorkbookPositionalBlock
  allWr: WorkbookPositionalBlock
  outWr: WorkbookPositionalBlock
  slotWr: WorkbookPositionalBlock
  te: WorkbookPositionalBlock
  rb: WorkbookPositionalBlock
}

export interface WorkbookGame {
  away: string
  home: string
  kickoff: string | null
  mainSlate: boolean
  rows: WorkbookTeamRow[]
}

export type WorkbookHighlightRole = 'roster' | 'free_agent' | 'waiver'

export interface WorkbookHighlight {
  playerId: number
  displayName: string
  nflTeam: string
  matchupTeam: string
  opponent: string
  role: WorkbookHighlightRole
  rosterSlot: string | null
}

export interface WorkbookJoinStats {
  matched: number
  unmatched_team: number
  unmatched_name_only: number
}

export interface WorkbookMatchupsResponse {
  season: number
  week: number
  window: WorkbookWindow
  scoring: WorkbookScoring
  slate: WorkbookSlate
  ratedThroughWeek: number
  fetchedAt: string
  source: string
  stale: boolean
  attribution: string
  games: WorkbookGame[]
  highlights?: WorkbookHighlight[]
  joinStats?: WorkbookJoinStats
  overlayError?: string
}

export interface WorkbookMatchupsQuery {
  week: number
  window: WorkbookWindow
  scoring: WorkbookScoring
  slate: WorkbookSlate
  startWeek?: number
  endWeek?: number
  season?: number
  leagueId?: string
  ownerTeamId?: number
  includeFa?: boolean
}

export interface WorkbookFeederRow {
  team: string
  off: number | null
  def: number | null
  net: number | null
}

export interface WorkbookFeederResponse {
  season: number
  week: number
  window: WorkbookWindow
  scoring: WorkbookScoring
  group: WorkbookFeederGroup
  ratedThroughWeek: number
  fetchedAt: string
  source: string
  stale: boolean
  attribution: string
  teams: WorkbookFeederRow[]
}

export interface WorkbookFeederQuery {
  group: WorkbookFeederGroup
  week: number
  window: WorkbookWindow
  scoring: WorkbookScoring
  startWeek?: number
  endWeek?: number
  season?: number
}

export interface WorkbookExplainResponse {
  season: number
  week: number
  team: string
  opponent: string | null
  metric: WorkbookExplainMetric
  window: WorkbookWindow
  scoring: WorkbookScoring
  ratedThroughWeek: number
  fetchedAt: string
  source: string
  stale: boolean
  attribution: string
  off: number | null
  def: number | null
  net: number | null
}

export interface WorkbookExplainQuery {
  team: string
  week: number
  metric: WorkbookExplainMetric
  window: WorkbookWindow
  scoring: WorkbookScoring
  startWeek?: number
  endWeek?: number
  season?: number
}
