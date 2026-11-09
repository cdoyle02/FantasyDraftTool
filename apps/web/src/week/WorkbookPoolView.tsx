import { useCallback, useEffect, useMemo, useState } from 'react'
import { draftApi } from '../api/client'
import type { WorkbookP2Controls } from './WeekWorkbookP2Tabs'
import type { WorkbookPoolRankResponse, WorkbookPoolRankRow } from './types'
import { parseDfsCsv, type PoolPlayerInput } from './workbookPoolCsv'

/** sessionStorage — cleared when the browser tab closes (Dexie migration TBD). */
export const WORKBOOK_POOL_CSV_STORAGE_KEY = 'workbook-pool-csv-text'
const WORKBOOK_POOL_TAGS_STORAGE_KEY = 'workbook-pool-manual-tags'

export type PoolManualTag = 'target' | 'fade'

function poolPlayerKey(row: Pick<WorkbookPoolRankRow, 'name' | 'team'>): string {
  return `${row.name}|${row.team}`
}

function windowBody(controls: WorkbookP2Controls) {
  return {
    week: controls.week,
    window: controls.window,
    scoring: controls.scoring,
    startWeek: controls.window === 'custom' ? controls.customStart : undefined,
    endWeek: controls.window === 'custom' ? controls.customEnd : undefined
  }
}

function tierAbbrev(tier: WorkbookPoolRankRow['tier']): string {
  if (tier === 'top') return 'T'
  if (tier === 'mid') return 'M'
  if (tier === 'bottom') return 'B'
  return '—'
}

function formatValue(value: number | null, decimals: number): string {
  if (value == null) return '—'
  return value.toFixed(decimals)
}

function readTags(): Record<string, PoolManualTag> {
  try {
    const raw = sessionStorage.getItem(WORKBOOK_POOL_TAGS_STORAGE_KEY)
    if (!raw) return {}
    return JSON.parse(raw) as Record<string, PoolManualTag>
  } catch {
    return {}
  }
}

function writeTags(tags: Record<string, PoolManualTag>) {
  try {
    sessionStorage.setItem(WORKBOOK_POOL_TAGS_STORAGE_KEY, JSON.stringify(tags))
  } catch {
    // private mode
  }
}

export function WorkbookPoolView({ controls }: { controls: WorkbookP2Controls }) {
  const [csvText, setCsvText] = useState(() => {
    try {
      return sessionStorage.getItem(WORKBOOK_POOL_CSV_STORAGE_KEY) ?? ''
    } catch {
      return ''
    }
  })
  const [parseErrors, setParseErrors] = useState<string[]>([])
  const [parsedPlayers, setParsedPlayers] = useState<PoolPlayerInput[]>([])
  const [rankData, setRankData] = useState<WorkbookPoolRankResponse | null>(null)
  const [rankError, setRankError] = useState('')
  const [ranking, setRanking] = useState(false)
  const [manualTags, setManualTags] = useState<Record<string, PoolManualTag>>(readTags)
  const [joinFilter, setJoinFilter] = useState<'all' | 'unmatched'>('all')


  useEffect(() => {
    try {
      if (csvText) {
        sessionStorage.setItem(WORKBOOK_POOL_CSV_STORAGE_KEY, csvText)
      } else {
        sessionStorage.removeItem(WORKBOOK_POOL_CSV_STORAGE_KEY)
      }
    } catch {
      // ignore
    }
  }, [csvText])

  useEffect(() => {
    if (!csvText.trim()) {
      setParseErrors([])
      setParsedPlayers([])
      return
    }
    const { players, errors } = parseDfsCsv(csvText)
    setParsedPlayers(players)
    setParseErrors(errors)
  }, [csvText])

  const rankedRows = useMemo(() => rankData?.players ?? [], [rankData?.players])
  const unmatchedCount = useMemo(
    () => rankedRows.filter((row) => row.joinStatus === 'unmatched').length,
    [rankedRows]
  )
  const visibleRows = useMemo(() => {
    if (joinFilter === 'unmatched') {
      return rankedRows.filter((row) => row.joinStatus === 'unmatched')
    }
    return rankedRows
  }, [joinFilter, rankedRows])


  const rankPool = useCallback(async () => {
    if (parsedPlayers.length === 0) {
      setRankError('Paste a valid salary CSV with at least one player.')
      return
    }
    setRanking(true)
    setRankError('')
    try {
      const payload = await draftApi.workbookPoolRank({
        ...windowBody(controls),
        players: parsedPlayers
      })
      setRankData(payload)
    } catch (err) {
      setRankData(null)
      setRankError(err instanceof Error ? err.message : 'Could not rank pool.')
    } finally {
      setRanking(false)
    }
  }, [controls, parsedPlayers])

  const cycleTag = (row: WorkbookPoolRankRow) => {
    const key = poolPlayerKey(row)
    const order: Array<PoolManualTag | null> = [null, 'target', 'fade']
    const current = manualTags[key] ?? null
    const next = order[(order.indexOf(current) + 1) % order.length] ?? null
    const updated = { ...manualTags }
    if (next) {
      updated[key] = next
    } else {
      delete updated[key]
    }
    setManualTags(updated)
    writeTags(updated)
  }

  return (
    <section className="panel overflow-hidden" data-testid="workbook-pool-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">DFS pool</p>
          <h2>Paste DK / FanDuel salaries</h2>
          <p className="mt-1 text-[11px] text-muted">
            Salaries stay in this browser until you rank — cleared when the tab closes.
          </p>
        </div>
        {ranking && <p className="text-xs text-muted">Ranking…</p>}
      </div>

      <div className="space-y-3 px-4 pb-4">
        <label className="flex flex-col gap-1 text-[10px] font-bold uppercase tracking-wider text-muted">
          Salary CSV
          <textarea
            data-testid="workbook-pool-csv-input"
            className="min-h-[120px] w-full rounded-lg border border-line bg-ink px-3 py-2 font-mono text-xs text-slate-100"
            placeholder="Name,Position,Team,Salary&#10;..."
            value={csvText}
            onChange={(event) => setCsvText(event.target.value)}
          />
        </label>

        {parseErrors.length > 0 && (
          <ul
            role="alert"
            data-testid="workbook-pool-parse-errors"
            className="list-inside list-disc text-xs text-rose-200"
          >
            {parseErrors.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        )}

        {parsedPlayers.length > 0 && parseErrors.length === 0 && (
          <p className="text-xs text-muted" data-testid="workbook-pool-parse-count">
            {parsedPlayers.length} player{parsedPlayers.length === 1 ? '' : 's'} ready to rank
          </p>
        )}

        <button
          type="button"
          data-testid="workbook-pool-rank-button"
          className="button-primary text-sm"
          disabled={ranking || parsedPlayers.length === 0 || parseErrors.length > 0}
          onClick={() => void rankPool()}
        >
          Rank with Workbook
        </button>

        {rankError && (
          <p role="alert" className="text-xs text-rose-200">
            {rankError}
          </p>
        )}
      </div>

      {rankData && (
        <div className="border-t border-line">
          <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2">
            <p className="text-xs text-muted" data-testid="workbook-pool-join-stats">
              {rankedRows.length} ranked
              {unmatchedCount > 0
                ? ` · ${unmatchedCount} unmatched`
                : ' · all matched'}
            </p>
            <div
              className="flex gap-1 rounded-lg border border-line bg-ink/40 p-0.5"
              role="group"
              aria-label="Pool join filter"
            >
              <button
                type="button"
                data-testid="workbook-pool-filter-all"
                className={`rounded-md px-2.5 py-1 text-[10px] font-semibold uppercase ${
                  joinFilter === 'all' ? 'bg-mint text-ink' : 'text-muted hover:text-white'
                }`}
                onClick={() => setJoinFilter('all')}
              >
                All
              </button>
              <button
                type="button"
                data-testid="workbook-pool-filter-unmatched"
                className={`rounded-md px-2.5 py-1 text-[10px] font-semibold uppercase ${
                  joinFilter === 'unmatched' ? 'bg-mint text-ink' : 'text-muted hover:text-white'
                }`}
                onClick={() => setJoinFilter('unmatched')}
              >
                Unmatched
              </button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-left text-xs" data-testid="workbook-pool-table">
              <thead>
                <tr className="border-b border-line text-[10px] uppercase tracking-wider text-muted">
                  <th className="px-3 py-2">Name</th>
                  <th className="px-3 py-2 text-right">Salary</th>
                  <th className="px-3 py-2">Pos</th>
                  <th className="px-3 py-2">Opp</th>
                  <th className="px-3 py-2 text-right">Net FP/G</th>
                  <th className="px-3 py-2 text-center">Tier</th>
                  <th className="px-3 py-2 text-right">Value</th>
                  <th className="px-3 py-2">Match</th>
                  <th className="px-3 py-2">Tag</th>
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((row) => {
                  const tag = manualTags[poolPlayerKey(row)]
                  const unmatched = row.joinStatus === 'unmatched'
                  return (
                    <tr
                      key={`${row.name}-${row.team}-${row.salary}`}
                      className={`border-b border-line/60 ${unmatched ? 'bg-rose-500/10' : ''}`}
                      data-testid={`workbook-pool-row-${row.name.replace(/\s+/g, '-')}`}
                    >
                      <td className="px-3 py-1.5 font-semibold">
                        {row.name}
                        <span className="ml-1 text-[10px] text-muted">{row.team}</span>
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums">${row.salary.toLocaleString()}</td>
                      <td className="px-3 py-1.5">{row.position}</td>
                      <td className="px-3 py-1.5 text-muted">{row.opponent ?? '—'}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums font-semibold">
                        {formatValue(row.netFpG, 1)}
                      </td>
                      <td className="px-3 py-1.5 text-center font-bold text-muted">{tierAbbrev(row.tier)}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums">{formatValue(row.value, 2)}</td>
                      <td className="px-3 py-1.5">
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                            unmatched ? 'bg-rose-500/30 text-rose-100' : 'bg-mint/20 text-mint'
                          }`}
                        >
                          {row.joinStatus}
                        </span>
                      </td>
                      <td className="px-3 py-1.5">
                        <button
                          type="button"
                          data-testid={`workbook-pool-tag-${row.name.replace(/\s+/g, '-')}`}
                          className="rounded border border-line px-2 py-0.5 text-[10px] font-semibold uppercase text-muted hover:text-white"
                          onClick={() => cycleTag(row)}
                        >
                          {tag ?? '—'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
                {visibleRows.length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-4 py-6 text-center text-muted">
                      {joinFilter === 'unmatched' ? 'No unmatched players.' : 'No ranked players.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {rankData?.attribution && (
        <p className="px-4 pb-3 text-[10px] text-muted" data-testid="workbook-pool-attribution">
          {rankData.attribution}
        </p>
      )}
    </section>
  )
}
