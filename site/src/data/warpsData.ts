// WARPS-NFL v1.7 model outputs — embedded from Python run (2026-06-07)

export interface ByYearRow {
  season: number;
  teams: number;
  warpsMae: number;
  pythMae: number;
  pwMae: number;
  warpsRmse: number;
}

export interface CalibrationRow {
  bucket: string;
  avgProj: number;
  avgActual: number;
  avgError: number;
  mae: number;
  teams: number;
}

export interface MetricRow {
  model: string;
  type: string;
  warpsMae: number;
  beatsAll: boolean;
}

export interface ConsensusRow {
  team: string;
  marketTotal: number;
  v17Wins: number;
  v17Edge: number;
  v15dEdge: number;
  v16Edge: number;
  avgEdge: number;
  consensus: string;
}

export interface BootstrapStats {
  warpsMaeFull: number;
  warpsMaeFullCi: [number, number];
  pythMaeFull: number;
  pwMaeFull: number;
  warpsMaeVal: number;
  warpsMaeValCi: [number, number];
  pythMaeVal: number;
  pwMaeVal: number;
  dmVsPythFull: { stat: number; pval: number; sig: string };
  dmVsPwFull: { stat: number; pval: number; sig: string };
  dmVsPythVal: { stat: number; pval: number; sig: string };
  dmVsPwVal: { stat: number; pval: number; sig: string };
  seasonsBeatingPyth: number;
  totalSeasons: number;
}

export const byYearData: ByYearRow[] = [
  { season: 2015, teams: 31, warpsMae: 2.366, pythMae: 2.559, pwMae: 2.742, warpsRmse: 2.965 },
  { season: 2016, teams: 32, warpsMae: 2.455, pythMae: 2.602, pwMae: 2.839, warpsRmse: 2.967 },
  { season: 2017, teams: 32, warpsMae: 2.191, pythMae: 2.303, pwMae: 3.125, warpsRmse: 2.760 },
  { season: 2018, teams: 32, warpsMae: 2.055, pythMae: 2.198, pwMae: 2.719, warpsRmse: 2.512 },
  { season: 2019, teams: 32, warpsMae: 2.217, pythMae: 2.259, pwMae: 2.469, warpsRmse: 2.782 },
  { season: 2020, teams: 32, warpsMae: 2.778, pythMae: 2.896, pwMae: 2.906, warpsRmse: 3.114 },
  { season: 2021, teams: 32, warpsMae: 1.908, pythMae: 1.996, pwMae: 2.313, warpsRmse: 2.166 },
  { season: 2022, teams: 32, warpsMae: 2.501, pythMae: 2.853, pwMae: 3.000, warpsRmse: 2.895 },
  { season: 2023, teams: 32, warpsMae: 1.903, pythMae: 2.131, pwMae: 2.594, warpsRmse: 2.406 },
  { season: 2024, teams: 32, warpsMae: 2.985, pythMae: 3.076, pwMae: 2.938, warpsRmse: 3.534 },
  { season: 2025, teams: 32, warpsMae: 2.669, pythMae: 2.978, pwMae: 3.156, warpsRmse: 3.260 },
];

export const calibrationData: CalibrationRow[] = [
  { bucket: "4.5–6.6 wins", avgProj: 5.88, avgActual: 6.57, avgError: -0.69, mae: 2.40, teams: 59 },
  { bucket: "6.6–7.5 wins", avgProj: 7.08, avgActual: 6.49, avgError: 0.59, mae: 2.50, teams: 58 },
  { bucket: "7.5–8.2 wins", avgProj: 7.87, avgActual: 8.48, avgError: -0.61, mae: 2.32, teams: 59 },
  { bucket: "8.2–9.0 wins", avgProj: 8.58, avgActual: 8.32, avgError: 0.26, mae: 2.43, teams: 58 },
  { bucket: "9.0–9.9 wins", avgProj: 9.43, avgActual: 9.48, avgError: -0.06, mae: 2.31, teams: 58 },
  { bucket: "9.9–11.9 wins", avgProj: 10.52, avgActual: 10.02, avgError: 0.50, mae: 2.23, teams: 59 },
];

export const metricRanking: MetricRow[] = [
  { model: "WARPS v1.7 champion (solo Pythagorean)", type: "WARPS composite", warpsMae: 2.365, beatsAll: true },
  { model: "pyth_heavy", type: "WARPS composite", warpsMae: 2.377, beatsAll: true },
  { model: "solo_point_diff", type: "Single metric", warpsMae: 2.378, beatsAll: true },
  { model: "pdiff_heavy", type: "WARPS composite", warpsMae: 2.380, beatsAll: true },
  { model: "balanced", type: "WARPS composite", warpsMae: 2.382, beatsAll: true },
  { model: "pass_pyth", type: "WARPS composite", warpsMae: 2.382, beatsAll: true },
  { model: "v1.5d default", type: "WARPS composite", warpsMae: 2.385, beatsAll: true },
  { model: "solo_pass_epa", type: "Single metric", warpsMae: 2.438, beatsAll: true },
  { model: "solo_success", type: "Single metric", warpsMae: 2.452, beatsAll: true },
  { model: "Pythagorean (baseline)", type: "Baseline", warpsMae: 2.532, beatsAll: false },
  { model: "solo_explosive", type: "Single metric", warpsMae: 2.559, beatsAll: false },
  { model: "solo_turnover", type: "Single metric", warpsMae: 2.604, beatsAll: false },
  { model: "Prior-year wins", type: "Baseline", warpsMae: 2.800, beatsAll: false },
  { model: "solo_rush_epa", type: "Single metric", warpsMae: 2.630, beatsAll: false },
];

export const bootstrapStats: BootstrapStats = {
  warpsMaeFull: 2.365,
  warpsMaeFullCi: [2.135, 2.599],
  pythMaeFull: 2.532,
  pwMaeFull: 2.800,
  warpsMaeVal: 2.514,
  warpsMaeValCi: [2.225, 2.818],
  pythMaeVal: 2.759,
  pwMaeVal: 2.922,
  dmVsPythFull: { stat: 3.548, pval: 0.0002, sig: "***" },
  dmVsPwFull: { stat: 4.811, pval: 0.0000, sig: "***" },
  dmVsPythVal: { stat: 2.939, pval: 0.0016, sig: "**" },
  dmVsPwVal: { stat: 2.571, pval: 0.0051, sig: "**" },
  seasonsBeatingPyth: 11,
  totalSeasons: 11,
};

export const consensusData: ConsensusRow[] = [
  { team: "NO",  marketTotal: 4.5,  v17Wins: 8.27,  v17Edge: 3.77,  v15dEdge: 4.26,  v16Edge: 3.75,  avgEdge: 3.93,  consensus: "3-model Over" },
  { team: "NE",  marketTotal: 8.5,  v17Wins: 11.85, v17Edge: 3.35,  v15dEdge: 2.61,  v16Edge: 3.34,  avgEdge: 3.10,  consensus: "3-model Over" },
  { team: "JAX", marketTotal: 7.5,  v17Wins: 10.70, v17Edge: 3.20,  v15dEdge: 2.39,  v16Edge: 3.19,  avgEdge: 2.92,  consensus: "3-model Over" },
  { team: "NYG", marketTotal: 5.5,  v17Wins: 7.42,  v17Edge: 1.92,  v15dEdge: 2.12,  v16Edge: 1.92,  avgEdge: 1.98,  consensus: "3-model Over" },
  { team: "IND", marketTotal: 7.5,  v17Wins: 9.22,  v17Edge: 1.72,  v15dEdge: 1.44,  v16Edge: 1.71,  avgEdge: 1.62,  consensus: "3-model Over" },
  { team: "ARI", marketTotal: 4.5,  v17Wins: 5.52,  v17Edge: 1.02,  v15dEdge: 1.92,  v16Edge: 1.02,  avgEdge: 1.31,  consensus: "2-Strong Over" },
  { team: "ATL", marketTotal: 6.5,  v17Wins: 7.56,  v17Edge: 1.06,  v15dEdge: 1.49,  v16Edge: 1.06,  avgEdge: 1.20,  consensus: "2-Strong Over" },
  { team: "MIA", marketTotal: 4.5,  v17Wins: 5.49,  v17Edge: 0.99,  v15dEdge: 1.53,  v16Edge: 0.99,  avgEdge: 1.17,  consensus: "Split / No bet" },
  { team: "CLE", marketTotal: 5.5,  v17Wins: 5.97,  v17Edge: 0.47,  v15dEdge: 1.18,  v16Edge: 0.47,  avgEdge: 0.71,  consensus: "Split / No bet" },
  { team: "WAS", marketTotal: 7.5,  v17Wins: 7.89,  v17Edge: 0.39,  v15dEdge: 0.94,  v16Edge: 0.38,  avgEdge: 0.57,  consensus: "Split / No bet" },
  { team: "HOU", marketTotal: 9.5,  v17Wins: 10.23, v17Edge: 0.73,  v15dEdge: -0.11, v16Edge: 0.75,  avgEdge: 0.46,  consensus: "Split / No bet" },
  { team: "PIT", marketTotal: 8.5,  v17Wins: 8.61,  v17Edge: 0.11,  v15dEdge: 0.02,  v16Edge: 0.12,  avgEdge: 0.08,  consensus: "Split / No bet" },
  { team: "SEA", marketTotal: 10.5, v17Wins: 10.82, v17Edge: 0.32,  v15dEdge: -0.56, v16Edge: 0.32,  avgEdge: 0.03,  consensus: "Split / No bet" },
  { team: "CAR", marketTotal: 7.5,  v17Wins: 7.32,  v17Edge: -0.18, v15dEdge: 0.34,  v16Edge: -0.20, avgEdge: -0.01, consensus: "Split / No bet" },
  { team: "DEN", marketTotal: 9.5,  v17Wins: 9.53,  v17Edge: 0.03,  v15dEdge: -0.31, v16Edge: 0.05,  avgEdge: -0.08, consensus: "Split / No bet" },
  { team: "DET", marketTotal: 10.5, v17Wins: 10.43, v17Edge: -0.06, v15dEdge: -0.45, v16Edge: -0.07, avgEdge: -0.19, consensus: "Split / No bet" },
  { team: "TB",  marketTotal: 8.5,  v17Wins: 8.27,  v17Edge: -0.23, v15dEdge: -0.27, v16Edge: -0.23, avgEdge: -0.24, consensus: "Split / No bet" },
  { team: "TEN", marketTotal: 6.5,  v17Wins: 5.80,  v17Edge: -0.70, v15dEdge: 0.28,  v16Edge: -0.70, avgEdge: -0.37, consensus: "Split / No bet" },
  { team: "LAR", marketTotal: 11.5, v17Wins: 11.12, v17Edge: -0.38, v15dEdge: -0.72, v16Edge: -0.40, avgEdge: -0.50, consensus: "Split / No bet" },
  { team: "GB",  marketTotal: 9.5,  v17Wins: 8.94,  v17Edge: -0.56, v15dEdge: -0.41, v16Edge: -0.55, avgEdge: -0.51, consensus: "Split / No bet" },
  { team: "LAC", marketTotal: 9.5,  v17Wins: 8.65,  v17Edge: -0.85, v15dEdge: -0.69, v16Edge: -0.85, avgEdge: -0.80, consensus: "Split / No bet" },
  { team: "MIN", marketTotal: 9.5,  v17Wins: 8.77,  v17Edge: -0.73, v15dEdge: -0.99, v16Edge: -0.73, avgEdge: -0.82, consensus: "Split / No bet" },
  { team: "LV",  marketTotal: 6.5,  v17Wins: 5.28,  v17Edge: -1.22, v15dEdge: -0.01, v16Edge: -1.24, avgEdge: -0.82, consensus: "Split / No bet" },
  { team: "CIN", marketTotal: 9.5,  v17Wins: 8.42,  v17Edge: -1.08, v15dEdge: -1.21, v16Edge: -1.06, avgEdge: -1.11, consensus: "2-Strong Under" },
  { team: "CHI", marketTotal: 9.5,  v17Wins: 8.27,  v17Edge: -1.23, v15dEdge: -1.27, v16Edge: -1.23, avgEdge: -1.24, consensus: "2-Strong Under" },
  { team: "SF",  marketTotal: 10.5, v17Wins: 9.51,  v17Edge: -0.99, v15dEdge: -1.79, v16Edge: -0.99, avgEdge: -1.26, consensus: "Split / No bet" },
  { team: "DAL", marketTotal: 9.5,  v17Wins: 7.99,  v17Edge: -1.51, v15dEdge: -1.49, v16Edge: -1.50, avgEdge: -1.50, consensus: "3-model Under" },
  { team: "NYJ", marketTotal: 6.5,  v17Wins: 4.76,  v17Edge: -1.74, v15dEdge: -1.06, v16Edge: -1.72, avgEdge: -1.50, consensus: "3-model Under" },
  { team: "BAL", marketTotal: 11.5, v17Wins: 9.87,  v17Edge: -1.63, v15dEdge: -2.02, v16Edge: -1.63, avgEdge: -1.76, consensus: "3-model Under" },
  { team: "KC",  marketTotal: 11.5, v17Wins: 9.76,  v17Edge: -1.74, v15dEdge: -2.18, v16Edge: -1.72, avgEdge: -1.88, consensus: "3-model Under" },
  { team: "PHI", marketTotal: 11.5, v17Wins: 9.42,  v17Edge: -2.08, v15dEdge: -2.36, v16Edge: -2.07, avgEdge: -2.17, consensus: "3-model Under" },
  { team: "BUF", marketTotal: 12.5, v17Wins: 10.32, v17Edge: -2.18, v15dEdge: -2.63, v16Edge: -2.19, avgEdge: -2.33, consensus: "3-model Under" },
];
