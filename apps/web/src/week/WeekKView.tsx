import { useEffect, useState } from 'react'
import { draftApi } from '../api/client'
import type {
  EspnLeague,
  JaredKAvailableResponse,
  JaredKRankingsResponse
} from './types'

const LEAGUE_STORAGE_KEY = 'fdt.week-k.leagueId'

function formatOwned(value: number | null | undefined): string {
  if (typeof value !== 'number') return '—'
  return value.toFixed(1)
}

export function WeekKView() {
  const [leagues, setLeagues] = useState<EspnLeague[]>([])
  const [leagueId, setLeagueId] = useState(() => {
    try {
      return localStorage.getItem(LEAGUE_STORAGE_KEY) ?? ''
    } catch {
      return ''
    }
  })
  const [rankings, setRankings] = useState<JaredKRankingsResponse | null>(null)
  const [available, setAvailable] = useState<JaredKAvailableResponse | null>(null)
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
        draftApi.jaredKRankings()
      ])
      setLeagues(leaguePayload.leagues)
      setRankings(rankingPayload)
      if (!leagueId && leaguePayload.leagues[0]) {
        setLeagueId(leaguePayload.leagues[0].id)
      }
    } catch (err) {
      setRankings(null)
      setError(err instanceof Error ? err.message : 'Could not load Jared K rankings.')
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
      const payload = await draftApi.jaredKAvailable(id)
      setAvailable(payload)
    } catch (err) {
      setAvailable(null)
      setAvailableError(err instanceof Error ? err.message : 'Could not load available kickers.')
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
    <div className="space-y-4" data-testid="week-k-view">
      <section className="mb-1 grid gap-3 rounded-2xl border border-line bg-gradient-to-r from-panel to-ink p-4 shadow-glow lg:grid-cols-[1fr_auto_auto] lg:items-center">
        <div>
          <p className="eyebrow">Expert board</p>
          <h2 className="text-lg font-semibold">Jared Smola · {weekLabel} K</h2>
          <p className="mt-1 text-xs text-muted">
            Draft Sharks weekly kickers on FantasyPros · map to FREEAGENT / WAIVERS in your ESPN league
          </p>
        </div>
        <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-muted">
          League
          <select
            data-testid="jared-league-select"
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
          data-testid="jared-refresh"
          onClick={() => {
            void loadRankings()
            void loadAvailable(leagueId)
          }}
          disabled={loading || availableLoading}
        >
          {loading || availableLoading ? 'Loading…' : 'Refresh'}
        </button>
      </section>

      {error && (
        <div
          role="alert"
          data-testid="jared-error"
          className="rounded-lg border border-rose-300/30 bg-rose-300/5 px-4 py-3 text-sm text-rose-200"
        >
          {error}
        </div>
      )}

      {!error && loading && !rankings && (
        <p className="text-sm text-muted">Loading Jared K rankings…</p>
      )}

      {rankings && (
        <div className="grid gap-4 lg:grid-cols-12">
          <section className="panel lg:col-span-7">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">Full board</p>
                <h2>Jared rankings</h2>
              </div>
              <span className="text-[10px] text-muted">{rankings.rankings.length} kickers</span>
            </div>
            <div className="overflow-x-auto">
              <table data-testid="jared-rankings-table" className="w-full min-w-[560px] text-left text-sm">
                <thead className="border-b border-line bg-ink/50">
                  <tr className="[&>th]:px-3 [&>th]:py-2">
                    <th className="text-[10px] font-bold uppercase tracking-wider text-muted">Rank</th>
                    <th className="text-[10px] font-bold uppercase tracking-wider text-muted">Player</th>
                    <th className="text-[10px] font-bold uppercase tracking-wider text-muted">Team</th>
                    <th className="text-[10px] font-bold uppercase tracking-wider text-muted">Opp</th>
                    <th className="text-[10px] font-bold uppercase tracking-wider text-muted">ECR</th>
                    <th className="text-[10px] font-bold uppercase tracking-wider text-muted">vs ECR</th>
                  </tr>
                </thead>
                <tbody>
                  {rankings.rankings.map((row) => (
                    <tr
                      key={`${row.rank}-${row.player}`}
                      className="border-b border-line/60 bg-ink/30 last:border-0"
                    >
                      <td className="px-3 py-2 font-semibold text-mint">{row.rank}</td>
                      <td className="px-3 py-2 font-semibold">{row.player}</td>
                      <td className="px-3 py-2 text-muted">{row.team}</td>
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
              <p className="p-4 text-xs text-muted">
                Select a league to map Jared’s ranks to FREEAGENT / WAIVERS.
              </p>
            )}
            {availableError && (
              <div
                role="alert"
                data-testid="jared-available-error"
                className="m-3 rounded-lg border border-rose-300/30 bg-rose-300/5 px-3 py-2 text-sm text-rose-200"
              >
                {availableError}
              </div>
            )}
            {leagueId && !availableError && availableLoading && !available && (
              <p className="p-4 text-xs text-muted">Loading available kickers…</p>
            )}
            {available && (
              <div className="overflow-x-auto">
                <table data-testid="jared-available-table" className="w-full min-w-[420px] text-left text-sm">
                  <thead className="border-b border-line bg-ink/50">
                    <tr className="[&>th]:px-3 [&>th]:py-2">
                      <th className="text-[10px] font-bold uppercase tracking-wider text-muted">Rank</th>
                      <th className="text-[10px] font-bold uppercase tracking-wider text-muted">Player</th>
                      <th className="text-[10px] font-bold uppercase tracking-wider text-muted">Opp</th>
                      <th className="text-[10px] font-bold uppercase tracking-wider text-muted">Status</th>
                      <th className="text-[10px] font-bold uppercase tracking-wider text-muted">% Own</th>
                    </tr>
                  </thead>
                  <tbody>
                    {available.available.map((row) => (
                      <tr
                        key={`${row.rank}-${row.player}`}
                        className="border-b border-line/60 bg-ink/30 last:border-0"
                      >
                        <td className="px-3 py-2 font-semibold text-mint">{row.rank}</td>
                        <td className="px-3 py-2">
                          <span className="font-semibold">{row.player}</span>
                          <span className="ml-2 text-xs text-muted">{row.team}</span>
                        </td>
                        <td className="px-3 py-2 text-muted">{row.opponent}</td>
                        <td className="px-3 py-2 text-xs">{row.status}</td>
                        <td className="px-3 py-2">{formatOwned(row.percentOwned)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!available.available.length && (
                  <p className="p-4 text-xs text-muted">
                    No Jared-ranked kickers are on FREEAGENT / WAIVERS in this league.
                  </p>
                )}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  )
}
