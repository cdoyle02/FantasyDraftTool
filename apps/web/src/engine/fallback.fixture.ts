import type { Player } from '../types'

const rows: Array<[string, Player['position'], string, number, number, number]> = [
  ['Christian McCaffrey', 'RB', 'SF', 315, 1.2, 1],
  ['CeeDee Lamb', 'WR', 'DAL', 302, 2.1, 1],
  ['Tyreek Hill', 'WR', 'MIA', 296, 3.2, 1],
  ['Ja’Marr Chase', 'WR', 'CIN', 290, 4.4, 1],
  ['Breece Hall', 'RB', 'NYJ', 278, 5.1, 1],
  ['Bijan Robinson', 'RB', 'ATL', 274, 6.3, 1],
  ['Amon-Ra St. Brown', 'WR', 'DET', 283, 7.5, 2],
  ['Justin Jefferson', 'WR', 'MIN', 281, 8.4, 2],
  ['A.J. Brown', 'WR', 'PHI', 266, 10.2, 2],
  ['Jahmyr Gibbs', 'RB', 'DET', 260, 11.1, 2],
  ['Puka Nacua', 'WR', 'LAR', 257, 12.8, 2],
  ['Jonathan Taylor', 'RB', 'IND', 252, 13.5, 2],
  ['Saquon Barkley', 'RB', 'PHI', 248, 15.2, 2],
  ['Garrett Wilson', 'WR', 'NYJ', 255, 16.1, 2],
  ['Travis Etienne', 'RB', 'JAX', 235, 18.2, 3],
  ['Sam LaPorta', 'TE', 'DET', 218, 20.4, 1],
  ['Josh Allen', 'QB', 'BUF', 386, 22.1, 1],
  ['Marvin Harrison Jr.', 'WR', 'ARI', 231, 23.6, 3],
  ['De’Von Achane', 'RB', 'MIA', 226, 25.8, 3],
  ['Patrick Mahomes', 'QB', 'KC', 371, 28.4, 1],
  ['Travis Kelce', 'TE', 'KC', 207, 30.2, 1],
  ['Lamar Jackson', 'QB', 'BAL', 365, 31.8, 1],
  ['Mark Andrews', 'TE', 'BAL', 192, 42.5, 2],
  ['Justin Tucker', 'K', 'BAL', 151, 170, 1],
  ['49ers DST', 'DST', 'SF', 145, 165, 1]
]

export const fallbackFixturePlayers: Player[] = rows.map(
  ([name, position, team, projectedPoints, adp, tier], index) => ({
    id: `seed-${index + 1}`,
    name,
    position,
    team,
    projectedPoints,
    adp,
    tier
  })
)
