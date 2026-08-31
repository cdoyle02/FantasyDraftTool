import type { DraftPick, LeagueSettings, Player, Recommendation, UserAdjustment } from '../types'

const replacements: Record<Player['position'], number> = {
  QB: 285, RB: 155, WR: 165, TE: 125, K: 120, DST: 110
}

/**
 * DEVELOPMENT FALLBACK ONLY. Production recommendations should come from the
 * FastAPI service or packaged dvs_engine Python wheel in the Pyodide worker.
 */
export function developmentFallbackScore(
  players: Player[],
  picks: DraftPick[],
  settings: LeagueSettings,
  adjustments: UserAdjustment[] = []
): Recommendation[] {
  const drafted = new Set(picks.map((pick) => pick.playerId))
  const round = Math.floor(picks.length / settings.teamCount) + 1
  const roster = picks.filter((pick) => pick.teamId === settings.userTeam)
  const opinions = new Map(adjustments.map((item) => [item.playerId, item]))
  const counts = roster.reduce<Partial<Record<Player['position'], number>>>((all, pick) => {
    all[pick.position] = (all[pick.position] ?? 0) + 1
    return all
  }, {})

  return players.filter((player) => !drafted.has(player.id)).map((player) => {
    const opinion = opinions.get(player.id)
    const vorp = Math.max(0, player.projectedPoints - replacements[player.position])
    const tierUrgency = Math.max(0, 24 - player.tier * 4)
    const survivalProbability = Math.max(0.08, Math.min(0.94, 1 - (picks.length + settings.teamCount - player.adp) / 35))
    const target = settings.rosterSlots[player.position] ?? 1
    const needMultiplier = Math.max(0.72, 1.22 - (counts[player.position] ?? 0) / Math.max(1, target) * 0.28)
    const guardrailAdjustment = ['K', 'DST'].includes(player.position) && round < 13 ? -80 : 0
    const opponentDemandFactor = 1
    const tagAdjustment = opinion?.tag === 'myGuy' ? 6 : opinion?.tag === 'avoid' ? -1000 : 0
    const dvsScore = vorp * needMultiplier + tierUrgency * (1 - survivalProbability) + (opinion?.pointsDelta ?? 0) + tagAdjustment + guardrailAdjustment
    return {
      playerId: player.id,
      dvsScore: Number(dvsScore.toFixed(1)),
      tierLabel: survivalProbability < 0.3 && dvsScore > 80 ? "CAN'T PASS" : survivalProbability > 0.7 ? 'SAFE TO WAIT' : 'BEST PICK',
      breakdown: {
        vorp,
        marginalValue: vorp,
        waitLoss: 0,
        tierUrgency,
        survivalProbability,
        needMultiplier,
        opponentDemandFactor,
        guardrailAdjustment
      },
      explanation: survivalProbability < 0.4
        ? `Strong value with only a ${Math.round(survivalProbability * 100)}% chance to reach your next pick.`
        : `${Math.round(survivalProbability * 100)}% chance to survive; balance value against positional need.`
    } satisfies Recommendation
  }).sort((a, b) => b.dvsScore - a.dvsScore).slice(0, 8)
}
