import { useEffect, useMemo, useState } from 'react'
import { draftApi } from '../api/client'
import type {
  EspnLeague,
  KyleDstAvailableResponse,
  KyleDstRankingsResponse,
  WeekOddsGame,
  WeekOddsResponse,
  WeekOddsSortKey
} from './types'

const LEAGUE_STORAGE_KEY = 'week-dst-espn-league-id'

function formatKickoff(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit'
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

function formatWindow(startIso: string, endIso: string): string {
  try {
    const fmt = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' })
    return `${fmt.format(new Date(startIso))} – ${fmt.format(new Date(endIso))}`
  } catch {
    return `${startIso} – ${endIso}`
  }
}

function formatSpread(spread: number, favorite: string): string {
  const mag = Math.abs(spread)
  const signed = spread === 0 ? 'PK' : `-${mag}`
  return `${favorite} ${signed}`
}

function formatOwned(value: number | null | undefined): string {
  if (typeof value !== 'number') return '—'
  return value.toFixed(1)
}

function sortGames(games: WeekOddsGame[], key: WeekOddsSortKey, dir: 'asc' | 'desc'): WeekOddsGame[] {
  const factor = dir === 'asc' ? 1 : -1
  return [...games].sort((a, b) => {
    const av = a[key]
    const bv = b[key]
    if (typeof av === 'number' && typeof bv === 'number') {
      return (av - bv) * factor
    }
    return String(av).localeCompare(String(bv)) * factor
  })
}

function SortHeader({
  label,
  active,
  dir,
  onClick,
  testId
}: {
  label: string
  active: boolean
  dir: 'asc' | 'desc'
  onClick: () => void
  testId?: string
}) {
  return (
    <button
      type="button"
      data-testid={testId}
      className={`text-left text-[10px] font-bold uppercase tracking-wider ${active ? 'text-mint' : 'text-muted hover:text-white'}`}
      onClick={onClick}
    >
      {label}
      {active ? (dir === 'asc' ? ' ↑' : ' ↓') : ''}
    </button>
  )
}

function DstPlayCard({ game, rank }: { game: WeekOddsGame; rank: number }) {
  return (
    <article
      className={`rounded-xl border p-4 ${rank === 0 ? 'border-mint/50 bg-mint/[.06] shadow-glow' : 'border-line bg-ink/35'}`}
      data-testid={`dst-play-${game.dstPlayTeam}`}
    >
      <div className="flex items-start gap-3">
        <span className="grid h-7 w-7 place-items-center rounded-full bg-white/5 text-xs font-bold text-muted">
          {rank + 1}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate font-semibold">{game.dstPlayTeam} D/ST</h3>
            <span className="rounded-full bg-white/10 px-2 py-0.5 text-[9px] font-black tracking-wider text-muted">
              vs {game.underdogTeam}
            </span>
          </div>
          <p className="mt-1 text-xs leading-5 text-muted">
            {formatSpread(game.spread, game.favoriteTeam)} · O/U {game.total} · {formatKickoff(game.commenceTime)}
          </p>
        </div>
        <div className="text-right">
          <div className="text-xl font-bold text-mint">{game.underdogImplied.toFixed(1)}</div>
          <div className="text-[9px] uppercase tracking-wider text-muted">Impl PA</div>
        </div>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3 text-xs text-muted">
        <div>
          {game.favoriteTeam} D/ST PA{' '}
          <span className="font-semibold text-slate-200">{game.underdogImplied.toFixed(1)}</span>
        </div>
        <div className="text-right">
          {game.underdogTeam} D/ST PA{' '}
          <span className="font-semibold text-slate-200">{game.favoriteImplied.toFixed(1)}</span>
        </div>
      </div>
    </article>
  )
}

function KyleDstSection() {
  const [leagues, setLeagues] = useState<EspnLeague[]>([])
  const [leagueId, setLeagueId] = useState(() => {
    try {
      return localStorage.getItem(LEAGUE_STORAGE_KEY) ?? ''
    } catch {
      return ''
    }
  })
  const [rankings, setRankings] = useState<KyleDstRankingsResponse | null>(null)
  const [available, setAvailable] = useState<KyleDstAvailableResponse | null>(null)
  const [error, setError] = useState('')
  const [availableError, setAvailableError] = useState('')
  const [loading, setLoading] = useState(true)
  const [availableLoading, setAvailableLoading] = useState(false)

  const loadRankings = async () => {
    setLoading(true)
    setError('')
    try {
      const [leaguePayload, rankingPayload] = await Promise.all([
        draftApi.espnLeagues(),
        draftApi.kyleDstRankings()
      ])
      setLeagues(leaguePayload.leagues)
      setRankings(rankingPayload)
      if (!leagueId && leaguePayload.leagues[0]) {
        setLeagueId(leaguePayload.leagues[0].id)
      }
    } catch (err) {
      setRankings(null)
      setError(err instanceof Error ? err.message : 'Could not load Kyle DST rankings.')
    } finally {
      setLoading(false)
    }
  }

  const loadAvailable = async (id: string) => {
    if (!id) {
      setAvailable(null)
      setAvailableError('')
      return
    }
    setAvailableLoading(true)
    setAvailableError('')
    try {
      const payload = await draftApi.kyleDstAvailable(id)
      setAvailable(payload)
    } catch (err) {
      setAvailable(null)
      setAvailableError(err instanceof Error ? err.message : 'Could not load available defenses.')
    } finally {
      setAvailableLoading(false)
    }
  }

  useEffect(() => {
    void loadRankings()
  }, [])

  useEffect(() => {
    try {
      if (leagueId) localStorage.setItem(LEAGUE_STORAGE_KEY, leagueId)
    } catch {
      // ignore quota / private mode
    }
    void loadAvailable(leagueId)
  }, [leagueId])

  const weekLabel = rankings?.week != null ? `Week ${rankings.week}` : 'current week'

  return (
    <section className="space-y-4" data-testid="kyle-dst-section">
      <div className="grid gap-3 rounded-2xl border border-line bg-gradient-to-r from-panel to-ink p-4 lg:grid-cols-[1fr_auto_auto] lg:items-center">
        <div>
          <p className="eyebrow">Expert board</p>
          <h2 className="text-lg font-semibold">Kyle Krajewski · {weekLabel} DST</h2>
          <p className="mt-1 text-xs text-muted">
            FantasyPros weekly ranks · map to FREEAGENT / WAIVERS in your ESPN league
          </p>
        </div>
        <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-muted">
          League
          <select
            data-testid="kyle-league-select"
            className="rounded-lg border border-line bg-ink px-3 py-2 text-sm font-semibold normal-case tracking-normal text-slate-100"
            value={leagueId}
            onChange={(event) => setLeagueId(event.target.value)}
          >
            <option value="">Select a league…</option>
            {leagues.map((league) => (
              <option key={league.id} value={league.id}>
                {league.name}
              </option>
            ))}
          </select>
        </label>
        <button
          className="button-secondary"
          type="button"
          data-testid="kyle-refresh"
          onClick={() => {
            void loadRankings()
            void loadAvailable(leagueId)
          }}
          disabled={loading || availableLoading}
        >
          {loading || availableLoading ? 'Loading…' : 'Refresh Kyle'}
        </button>
      </div>

      {error && (
        <div role="alert" data-testid="kyle-error" className="rounded-lg border border-rose-300/30 bg-rose-300/5 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      )}

      {!error && loading && !rankings && (
        <p className="text-sm text-muted">Loading Kyle DST rankings…</p>
      )}

      {rankings && (
        <div className="grid gap-4 lg:grid-cols-12">
          <section className="panel lg:col-span-7">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Full board</p>
                <h2>Kyle rankings</h2>
              </div>
              <span className="text-[10px] text-muted">{rankings.rankings.length} DSTs</span>
            </div>
            <div className="overflow-x-auto">
              <table data-testid="kyle-rankings-table" className="w-full min-w-[560px] text-left text-sm">
                <thead className="border-b border-line bg-ink/50">
                  <tr className="[&>th]:px-3 [&>th]:py-2">
                    <th className="text-[10px] font-bold uppercase tracking-wider text-muted">Rank</th>
                    <th className="text-[10px] font-bold uppercase tracking-wider text-muted">Team</th>
                    <th className="text-[10px] font-bold uppercase tracking-wider text-muted">Opp</th>
                    <th className="text-[10px] font-bold uppercase tracking-wider text-muted">ECR</th>
                    <th className="text-[10px] font-bold uppercase tracking-wider text-muted">vs ECR</th>
                  </tr>
                </thead>
                <tbody>
                  {rankings.rankings.map((row) => (
                    <tr key={`${row.rank}-${row.team}`} className="border-b border-line/60 bg-ink/30 last:border-0">
                      <td className="px-3 py-2 font-semibold text-mint">{row.rank}</td>
                      <td className="px-3 py-2">
                        <span className="font-semibold">{row.team}</span>
                        <span className="ml-2 text-xs text-muted">{row.teamName}</span>
                      </td>
                      <td className="px-3 py-2 text-muted">{row.opponent}</td>
                      <td className="px-3 py-2">{row.ecr ?? '—'}</td>
                      <td className="px-3 py-2">{row.vsEcr}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="panel lg:col-span-5">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Waiver map</p>
                <h2>Available in league</h2>
              </div>
              <span className="text-[10px] text-muted">
                {available ? `${available.available.length} open` : '—'}
              </span>
            </div>
            {!leagueId && (
              <p className="p-4 text-xs text-muted">Select a league to map Kyle’s ranks to FREEAGENT / WAIVERS.</p>
            )}
            {availableError && (
              <div role="alert" data-testid="kyle-available-error" className="m-3 rounded-lg border border-rose-300/30 bg-rose-300/5 px-3 py-2 text-sm text-rose-200">
                {availableError}
              </div>
            )}
            {leagueId && !availableError && availableLoading && !available && (
              <p className="p-4 text-xs text-muted">Loading available defenses…</p>
            )}
            {available && (
              <div className="overflow-x-auto">
                <table data-testid="kyle-available-table" className="w-full min-w-[420px] text-left text-sm">
                  <thead className="border-b border-line bg-ink/50">
                    <tr className="[&>th]:px-3 [&>th]:py-2">
                      <th className="text-[10px] font-bold uppercase tracking-wider text-muted">Rank</th>
                      <th className="text-[10px] font-bold uppercase tracking-wider text-muted">Team</th>
                      <th className="text-[10px] font-bold uppercase tracking-wider text-muted">Opp</th>
                      <th className="text-[10px] font-bold uppercase tracking-wider text-muted">Status</th>
                      <th className="text-[10px] font-bold uppercase tracking-wider text-muted">% Own</th>
                    </tr>
                  </thead>
                  <tbody>
                    {available.available.map((row) => (
                      <tr key={`${row.rank}-${row.team}`} className="border-b border-line/60 bg-ink/30 last:border-0">
                        <td className="px-3 py-2 font-semibold text-mint">{row.rank}</td>
                        <td className="px-3 py-2 font-semibold">{row.team}</td>
                        <td className="px-3 py-2 text-muted">{row.opponent}</td>
                        <td className="px-3 py-2 text-xs">{row.status}</td>
                        <td className="px-3 py-2">{formatOwned(row.percentOwned)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!available.available.length && (
                  <p className="p-4 text-xs text-muted">No Kyle-ranked DSTs are on FREEAGENT / WAIVERS in this league.</p>
                )}
              </div>
            )}
          </section>
        </div>
      )}
    </section>
  )
}

export function WeekDstView() {
  const [data, setData] = useState<WeekOddsResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [sortKey, setSortKey] = useState<WeekOddsSortKey>('underdogImplied')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const payload = await draftApi.weekOdds()
      setData(payload)
    } catch (err) {
      setData(null)
      setError(err instanceof Error ? err.message : 'Could not load week odds.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const ranked = useMemo(
    () => (data ? sortGames(data.games, 'underdogImplied', 'asc') : []),
    [data]
  )
  const tableRows = useMemo(
    () => (data ? sortGames(data.games, sortKey, sortDir) : []),
    [data, sortKey, sortDir]
  )

  const onSort = (key: WeekOddsSortKey) => {
    if (key === sortKey) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'))
      return
    }
    setSortKey(key)
    // Lower PA / earlier kickoff / lower total are usually the useful default.
    setSortDir(
      key === 'underdogImplied' || key === 'favoriteImplied' || key === 'total' || key === 'commenceTime'
        ? 'asc'
        : 'desc'
    )
  }

  return (
    <div className="space-y-4" data-testid="week-dst-view">
      <section className="mb-1 grid gap-3 rounded-2xl border border-line bg-gradient-to-r from-panel to-ink p-4 shadow-glow lg:grid-cols-[1fr_auto] lg:items-center">
        <div>
          <p className="eyebrow">Current slate</p>
          <h2 className="text-lg font-semibold">
            {data ? `Week ${data.week}` : 'Week D/ST'}
          </h2>
          <p className="mt-1 text-xs text-muted">
            {data
              ? `${formatWindow(data.windowStart, data.windowEnd)} · Tue–Mon fantasy week · ranked by lowest implied points allowed`
              : 'Favorite defenses in low-scoring matchups'}
          </p>
        </div>
        <button className="button-secondary" type="button" onClick={() => void load()} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh odds'}
        </button>
      </section>

      {error && (
        <div role="alert" className="rounded-lg border border-rose-300/30 bg-rose-300/5 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      )}

      {!error && loading && !data && (
        <p className="text-sm text-muted">Loading NFL odds for this fantasy week…</p>
      )}

      {data && (
        <div className="grid gap-4 lg:grid-cols-12">
          <section className="panel lg:col-span-5">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Stream board</p>
                <h2>Ranked D/ST plays</h2>
              </div>
              <span className="text-[10px] text-muted">{ranked.length} games</span>
            </div>
            <div className="max-h-[720px] space-y-3 overflow-auto p-3">
              {ranked.map((game, index) => (
                <DstPlayCard key={`${game.dstPlayTeam}-${game.commenceTime}`} game={game} rank={index} />
              ))}
              {!ranked.length && <p className="p-2 text-xs text-muted">No games in the current week window.</p>}
            </div>
          </section>

          <section className="panel lg:col-span-7">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Odds table</p>
                <h2>Sortable slate</h2>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table data-testid="week-odds-table" className="w-full min-w-[720px] text-left text-sm">
                <thead className="border-b border-line bg-ink/50">
                  <tr className="[&>th]:px-3 [&>th]:py-2">
                    <th><SortHeader label="Fav" active={sortKey === 'dstPlayTeam'} dir={sortDir} onClick={() => onSort('dstPlayTeam')} /></th>
                    <th className="text-[10px] font-bold uppercase tracking-wider text-muted">Dog</th>
                    <th><SortHeader label="Spread" active={sortKey === 'spread'} dir={sortDir} onClick={() => onSort('spread')} /></th>
                    <th><SortHeader label="O/U" testId="sort-total" active={sortKey === 'total'} dir={sortDir} onClick={() => onSort('total')} /></th>
                    <th title="Implied points the favorite D/ST is projected to allow (underdog team total)">
                      <SortHeader
                        label="Fav D/ST PA"
                        testId="sort-fav-dst-pa"
                        active={sortKey === 'underdogImplied'}
                        dir={sortDir}
                        onClick={() => onSort('underdogImplied')}
                      />
                    </th>
                    <th title="Implied points the underdog D/ST is projected to allow (favorite team total)">
                      <SortHeader
                        label="Dog D/ST PA"
                        testId="sort-dog-dst-pa"
                        active={sortKey === 'favoriteImplied'}
                        dir={sortDir}
                        onClick={() => onSort('favoriteImplied')}
                      />
                    </th>
                    <th><SortHeader label="Kickoff" active={sortKey === 'commenceTime'} dir={sortDir} onClick={() => onSort('commenceTime')} /></th>
                  </tr>
                </thead>
                <tbody>
                  {tableRows.map((game) => (
                    <tr key={`${game.homeTeam}-${game.awayTeam}-${game.commenceTime}`} className="border-b border-line/60 bg-ink/30 last:border-0">
                      <td className="px-3 py-2 font-semibold text-mint">{game.favoriteTeam}</td>
                      <td className="px-3 py-2 text-muted">{game.underdogTeam}</td>
                      <td className="px-3 py-2">{formatSpread(game.spread, game.favoriteTeam)}</td>
                      <td className="px-3 py-2">{game.total}</td>
                      <td className="px-3 py-2 font-semibold">
                        {game.underdogImplied.toFixed(1)}
                        <span className="ml-1 text-[10px] font-normal text-muted">{game.favoriteTeam}</span>
                      </td>
                      <td className="px-3 py-2">
                        {game.favoriteImplied.toFixed(1)}
                        <span className="ml-1 text-[10px] text-muted">{game.underdogTeam}</span>
                      </td>
                      <td className="px-3 py-2 text-xs text-muted">{formatKickoff(game.commenceTime)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!tableRows.length && <p className="p-4 text-xs text-muted">No games to display.</p>}
            </div>
          </section>
        </div>
      )}

      <KyleDstSection />
    </div>
  )
}
