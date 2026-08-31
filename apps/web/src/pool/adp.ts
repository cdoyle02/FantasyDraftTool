import type { Player } from '../types'

export type AdpSource = 'adp' | 'espnAdp' | 'sleeperAdp'
export type SortDir = 'asc' | 'desc'

export const ADP_SOURCES = [
  { key: 'adp', short: 'TFF', label: 'Footballers' },
  { key: 'espnAdp', short: 'ESPN', label: 'ESPN' },
  { key: 'sleeperAdp', short: 'Sleeper', label: 'Sleeper' }
] as const satisfies ReadonlyArray<{ key: AdpSource; short: string; label: string }>

export function adpSourceMeta(source: AdpSource) {
  return ADP_SOURCES.find((item) => item.key === source) ?? ADP_SOURCES[0]
}

export function adpForSource(player: Player, source: AdpSource): number | undefined {
  const value = player[source]
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : undefined
}

export function formatAdp(value: number | undefined): string {
  return value === undefined ? '—' : String(value)
}

export function compareAvailablePlayers(
  a: Player,
  b: Player,
  source: AdpSource,
  dir: SortDir,
  adjustments: Record<string, { pointsDelta?: number } | undefined>
): number {
  const aValue = adpForSource(a, source)
  const bValue = adpForSource(b, source)
  if (aValue === undefined && bValue === undefined) return a.name.localeCompare(b.name)
  if (aValue === undefined) return 1
  if (bValue === undefined) return -1
  const aSort = aValue - (adjustments[a.id]?.pointsDelta ?? 0) / 10
  const bSort = bValue - (adjustments[b.id]?.pointsDelta ?? 0) / 10
  const diff = dir === 'asc' ? aSort - bSort : bSort - aSort
  return diff || a.name.localeCompare(b.name)
}
