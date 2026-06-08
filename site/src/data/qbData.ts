// WARPS-NFL QB Adjustment Overlay — 2026 offseason
// Versioned separately from warpsData.ts so the base model stays frozen.
// Apply on top of WARPS v1.8 edges to account for QB changes the model cannot see.

export type QBTier = "elite" | "good" | "average" | "below" | "journeyman" | "rookie";

// Win adjustment relative to a league-average QB starter
export const QB_TIER_ADJ: Record<QBTier, number> = {
  elite:      2.5,   // Mahomes / Allen tier — carries a team
  good:       0.5,   // Reliable above-average starter
  average:    0.0,   // League-average starter
  below:     -1.0,   // Below-average starter, costs wins
  journeyman: -2.0,  // Career backup starting
  rookie:    -1.0,   // Unknown upside, real downside risk
};

export const QB_TIER_LABEL: Record<QBTier, string> = {
  elite: "Elite",
  good: "Good",
  average: "Average",
  below: "Below Avg",
  journeyman: "Journeyman",
  rookie: "Rookie",
};

export interface QBChange {
  team: string;
  outQb: string;
  outTier: QBTier;
  inQb: string;
  inTier: QBTier;
  confidence: number; // 0–1: certainty this person starts week 1
}

// Only teams where the 2025 starter (used in WARPS v1.8 inputs) changed materially.
// Teams with same-tier replacements (e.g. journeyman → journeyman) are omitted.
export const qbChanges2026: QBChange[] = [
  {
    team: "ARI",
    outQb: "K. Murray", outTier: "good",
    inQb: "J. Brissett", inTier: "journeyman",
    confidence: 0.85,
  },
  {
    team: "MIN",
    outQb: "J.J. McCarthy", outTier: "rookie",
    inQb: "K. Murray", inTier: "good",
    confidence: 0.90,
  },
  {
    team: "MIA",
    outQb: "Tua Tagovailoa", outTier: "good",
    inQb: "M. Willis", inTier: "below",
    confidence: 0.80,
  },
  {
    team: "ATL",
    outQb: "K. Cousins", outTier: "average",
    inQb: "Tua Tagovailoa", inTier: "good",
    confidence: 0.90,
  },
  {
    team: "LV",
    outQb: "A. O'Connell", outTier: "journeyman",
    inQb: "E. Mendoza", inTier: "rookie",
    confidence: 0.75,
  },
];

export interface QBAdjResult {
  adj: number;
  change: QBChange;
}

const adjCache = new Map<string, QBAdjResult | null>();
for (const change of qbChanges2026) {
  const adj = QB_TIER_ADJ[change.inTier] - QB_TIER_ADJ[change.outTier];
  adjCache.set(change.team, adj !== 0 ? { adj, change } : null);
}

export function getQbAdjustment(team: string): QBAdjResult | null {
  return adjCache.get(team) ?? null;
}
