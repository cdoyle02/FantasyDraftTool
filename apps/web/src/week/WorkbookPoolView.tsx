import { useCallback, useEffect, useMemo, useState } from 'react'
import { draftApi } from '../api/client'
import type { WorkbookP2Controls } from './WeekWorkbookP2Tabs'
import type { WorkbookPoolRankResponse, WorkbookPoolRankRow } from './types'
import { parseDfsCsv, type PoolPlayerInput } from './workbookPoolCsv'
import {
  loadWorkbookPool,
  saveWorkbookPoolCsv,
  saveWorkbookPoolTags,
  WORKBOOK_POOL_CSV_STORAGE_KEY
} from './workbookPoolPersistence'

/** @deprecated Prefer Dexie via workbookPoolPersistence — kept for test imports. */
export { WORKBOOK_POOL_CSV_STORAGE_KEY }

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

export function WorkbookPoolView({ controls }: { controls: WorkbookP2Controls }) {
  const [hydrated, setHydrated] = useState(false)
  const [csvText, setCsvText] = useState('')
  const [parseErrors, setParseErrors] = useState<string[]>([])
  const [parsedPlayers, setParsedPlayers] = useState<PoolPlayerInput[]>([])
  const [rankData, setRankData] = useState<WorkbookPoolRankResponse | null>(null)
  const [rankError, setRankError] = useState('')
  const [ranking, setRanking] = useState(false)
  const [manualTags, setManualTags] = useState<Record<string, PoolManualTag>>({})
  const [joinFilter, setJoinFilter] = useState<'all' | 'unmatched'>('all')

  useEffect(() => {
    let cancelled = false
    void loadWorkbookPool().then((row) => {
      if (cancelled) return
      setCsvText(row.csvText)
      setManualTags(row.manualTags)
      setHydrated(true)
    })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (!hydrated) return
    void saveWorkbookPoolCsv(csvText)
  }, [csvText, hydrated])

  useEffect(() => {
    if (!hydrated) return
    void saveWorkbookPoolTags(manualTags)
  }, [manualTags, hydrated])

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

  const onRank = useCallback(async () => {
    if (parsedPlayers.length === 0 || parseErrors.length > 0) return
    setRanking(true)
    setRankError('')
    try {
      const data = await draftApi.workbookPoolRank({
        ...windowBody(controls),
        players: parsedPlayers
      })
      setRankData(data)
    } catch (err) {
      setRankError(err instanceof Error ? err.message : 'Could not rank pool.')
    } finally {
      setRanking(false)
    }
  }, [controls, parseErrors.length, parsedPlayers])

  const cycleTag = (row: WorkbookPoolRankRow) => {
    const key = poolPlayerKey(row)
    const current = manualTags[key]
    const updated = { ...manualTags }
    if (!current) {
      updated[key] = 'target'
    } else if (current === 'target') {
      updated[key] = 'fade'
    } else {
      delete updated[key]
    }
    setManualTags(updated)
  }

  return (
    <section className="panel overflow-hidden" data-testid="workbook-pool-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">DFS pool</p>
          <h2>Paste DK / FanDuel salaries</h2>
          <p className="mt-1 text-[11px] text-muted" data-testid="workbook-pool-persist-note">
            Persists in this browser (Dexie) — survives tab close; not synced across devices.
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
          className="rounded-lg bg-accent px-3 py-2 text-xs font-bold text-ink disabled:opacity-40"
          disabled={parsedPlayers.length === 0 || parseErrors.length > 0 || ranking}
          onClick={() => void onRank()}
        >
          Rank pool
        </button>

        {rankError && (
          <p role="alert" className="text-xs text-rose-200">
            {rankError}
          </p>
        )}
      </div>

      {rankData && (
        <>
          <div className="flex flex-wrap items-center gap-2 px-4 pb-2">
            <p className="text-xs text-muted" data-testid="workbook-pool-join-stats">
              {rankData.players.length} ranked · {unmatchedCount} unmatched
            </p>
            <div className="ml-auto flex gap-1">
              <button
                type="button"
                data-testid="workbook-pool-filter-all"
                className={`rounded px-2 py-1 text-[10px] font-bold uppercase ${
                  joinFilter === 'all' ? 'bg-line text-slate-100' : 'text-muted'
                }`}
                onClick={() => setJoinFilter('all')}
              >
                All
              </button>
              <button
                type="button"
                data-testid="workbook-pool-filter-unmatched"
                className={`rounded px-2 py-1 text-[10px] font-bold uppercase ${
                  joinFilter === 'unmatched' ? 'bg-line text-slate-100' : 'text-muted'
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
                  <th className="px-3 py-2">Player</th>
                  <th className="px-3 py-2">Pos</th>
                  <th className="px-3 py-2 text-right">Sal</th>
                  <th className="px-3 py-2 text-right">Net FP/G</th>
                  <th className="px-3 py-2 text-right">Val</th>
                  <th className="px-3 py-2">Tier</th>
                  <th className="px-3 py-2">Join</th>
                  <th className="px-3 py-2">Tag</th>
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((row) => {
                  const tag = manualTags[poolPlayerKey(row)]
                  return (
                    <tr
                      key={`${row.name}|${row.team}|${row.salary}`}
                      className="border-b border-line/60"
                      data-testid={`workbook-pool-row-${row.name.replace(/\s+/g, '-')}`}
                    >
                      <td className="px-3 py-1.5 font-semibold">
                        {row.name}{' '}
                        <span className="text-muted font-normal">{row.team}</span>
                      </td>
                      <td className="px-3 py-1.5">{row.position}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums">{row.salary}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums">
                        {formatValue(row.netFpG, 1)}
                      </td>
                      <td className="px-3 py-1.5 text-right tabular-nums">
                        {formatValue(row.value, 2)}
                      </td>
                      <td className="px-3 py-1.5">{tierAbbrev(row.tier)}</td>
                      <td className="px-3 py-1.5 text-muted">{row.joinStatus}</td>
                      <td className="px-3 py-1.5">
                        <button
                          type="button"
                          data-testid={`workbook-pool-tag-${row.name.replace(/\s+/g, '-')}`}
                          className="rounded border border-line px-1.5 py-0.5 text-[10px] font-bold uppercase"
                          onClick={() => cycleTag(row)}
                        >
                          {tag ?? '—'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <p className="px-4 pb-3 text-[10px] text-muted" data-testid="workbook-pool-attribution">
            {rankData.attribution}
          </p>
        </>
      )}
    </section>
  )
}
