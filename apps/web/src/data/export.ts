import type {
  DraftEvaluationExport,
  DraftEvaluationRecord,
  DraftPick,
  KeeperAssignment,
  LeagueSettings,
  Player,
  UserAdjustment
} from '../types'

interface ExportSource {
  settings: LeagueSettings
  players: Player[]
  adjustments: Record<string, UserAdjustment>
  picks: DraftPick[]
  keepers: KeeperAssignment[]
  evaluationRecords: DraftEvaluationRecord[]
}

export function buildDraftEvaluationExport(
  source: ExportSource,
  exportedAt = new Date().toISOString()
): DraftEvaluationExport {
  return {
    schemaVersion: 2,
    exportedAt,
    finalState: {
      settings: source.settings,
      players: source.players,
      adjustments: source.adjustments,
      picks: source.picks,
      keepers: source.keepers
    },
    evaluationRecords: source.evaluationRecords
  }
}

export function downloadDraftEvaluationExport(bundle: DraftEvaluationExport): void {
  const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `fantasy-draft-evaluation-${bundle.exportedAt.slice(0, 10)}.json`
  document.body.append(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
