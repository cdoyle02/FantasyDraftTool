import { db, queueEvent, type ImportMeta } from '../data/db'
import type { ImportPrepareSuccess, ImportSourceIdentity } from '../data/footballersImport'
import {
  normalizeProfileName,
  summarizeSavedRanking,
  type SavedRankingProfile,
  type SavedRankingSummary
} from '../data/savedRankings'
import type { KeeperAssignment, LeagueSettings } from '../types'

export interface ImportCommitOptions {
  profileName: string
  overwriteProfileId?: string
}

export interface ActiveImportState {
  players: ImportPrepareSuccess['players']
  importIdentity: ImportSourceIdentity
  activeSavedProfileId?: string
  savedRankings: SavedRankingSummary[]
}

export function identityWithProfile(
  identity: ImportSourceIdentity,
  profile: Pick<SavedRankingProfile, 'id' | 'displayName'>
): ImportSourceIdentity {
  return {
    ...identity,
    savedProfileId: profile.id,
    savedProfileName: profile.displayName
  }
}

export function buildImportMeta(
  prepared: ImportPrepareSuccess,
  profile: Pick<SavedRankingProfile, 'id' | 'displayName'>
): ImportMeta {
  const identity = identityWithProfile(prepared.identity, profile)
  return {
    id: 'import',
    fingerprint: identity.fingerprint,
    season: identity.season,
    asOfDate: identity.asOfDate,
    rankingType: identity.rankingType,
    scoringProfile: identity.scoringProfile,
    leagueSize: identity.leagueSize,
    sourceCheatsheetId: identity.sourceCheatsheetId,
    sourceUrl: identity.sourceUrl,
    importedAt: Date.now(),
    playerCount: prepared.players.length,
    positionCounts: identity.positionCounts,
    savedProfileId: profile.id,
    savedProfileName: profile.displayName
  }
}

export function buildSavedProfileRecord(
  prepared: ImportPrepareSuccess,
  options: ImportCommitOptions,
  existing?: SavedRankingProfile
): SavedRankingProfile {
  const now = Date.now()
  const displayName = options.profileName.trim()
  return {
    id: existing?.id ?? crypto.randomUUID(),
    displayName,
    normalizedName: normalizeProfileName(displayName),
    dataset: prepared.dataset,
    createdAt: existing?.createdAt ?? now,
    updatedAt: now
  }
}

export async function commitActiveImportTransaction(
  prepared: ImportPrepareSuccess,
  profile: SavedRankingProfile,
  settings?: LeagueSettings,
  validKeepers?: KeeperAssignment[]
): Promise<void> {
  const importMeta = buildImportMeta(prepared, profile)
  const identity = identityWithProfile(prepared.identity, profile)
  const players = prepared.players.map((player) => ({
    ...player,
    importSource: player.importSource
      ? { ...player.importSource, fingerprint: identity.fingerprint }
      : undefined
  }))

  await db.transaction(
    'rw',
    [db.players, db.evaluationRecords, db.importMeta, db.savedRankings, db.settings, db.keepers, db.events],
    async () => {
      await db.savedRankings.put(profile)
      await db.players.clear()
      await db.players.bulkPut(players)
      await db.evaluationRecords.clear()
      await db.importMeta.put(importMeta)
      if (settings) {
        await db.settings.put({ ...settings, id: 'active' })
        if (validKeepers) {
          await db.keepers.clear()
          await db.keepers.bulkPut(validKeepers)
        }
      }
      await queueEvent('CSV_IMPORTED', {
        count: prepared.players.length,
        fingerprint: identity.fingerprint,
        sourceCheatsheetId: identity.sourceCheatsheetId,
        savedProfileId: profile.id,
        savedProfileName: profile.displayName
      })
      if (settings) {
        await queueEvent('SETTINGS_UPDATED', settings)
      }
    }
  )
}

export async function loadSavedRankingSummaries(): Promise<SavedRankingSummary[]> {
  const profiles = await db.savedRankings.orderBy('updatedAt').reverse().toArray()
  return profiles.map(summarizeSavedRanking)
}

export function importIdentityFromMeta(meta: ImportMeta): ImportSourceIdentity {
  return {
    fingerprint: meta.fingerprint,
    season: meta.season,
    asOfDate: meta.asOfDate,
    rankingType: meta.rankingType,
    scoringProfile: meta.scoringProfile,
    leagueSize: meta.leagueSize,
    sourceCheatsheetId: meta.sourceCheatsheetId,
    sourceUrl: meta.sourceUrl,
    positionCounts: meta.positionCounts,
    savedProfileId: meta.savedProfileId,
    savedProfileName: meta.savedProfileName
  }
}

export function normalizeLeagueSettings(settings: LeagueSettings): LeagueSettings {
  const teamCount = Math.max(4, Math.min(20, settings.teamCount))
  return {
    ...settings,
    teamCount,
    userTeam: Math.max(1, Math.min(teamCount, settings.userTeam)),
    rosterSlots: { ...settings.rosterSlots }
  }
}
