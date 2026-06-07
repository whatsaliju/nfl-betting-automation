// WARPS-NFL v1.8 model outputs — embedded from Python run (2026-06-07)
// Extended training window: 2000-2021 (22 seasons, up from 7 in v1.7)

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
  v18Wins: number;
  v18Edge: number;
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
  { season: 2000, teams: 31, warpsMae: 2.456, pythMae: 2.587, pwMae: 2.774, warpsRmse: 2.800 },
  { season: 2001, teams: 31, warpsMae: 2.590, pythMae: 3.452, pwMae: 3.355, warpsRmse: 3.210 },
  { season: 2002, teams: 32, warpsMae: 1.935, pythMae: 2.121, pwMae: 2.548, warpsRmse: 2.423 },
  { season: 2003, teams: 32, warpsMae: 2.635, pythMae: 2.875, pwMae: 3.125, warpsRmse: 3.043 },
  { season: 2004, teams: 32, warpsMae: 2.346, pythMae: 2.792, pwMae: 2.750, warpsRmse: 3.050 },
  { season: 2005, teams: 32, warpsMae: 2.784, pythMae: 2.944, pwMae: 3.500, warpsRmse: 3.171 },
  { season: 2006, teams: 32, warpsMae: 2.152, pythMae: 2.803, pwMae: 3.250, warpsRmse: 2.649 },
  { season: 2007, teams: 32, warpsMae: 2.682, pythMae: 3.004, pwMae: 3.250, warpsRmse: 3.239 },
  { season: 2008, teams: 32, warpsMae: 2.590, pythMae: 3.015, pwMae: 3.219, warpsRmse: 3.232 },
  { season: 2009, teams: 32, warpsMae: 2.113, pythMae: 2.117, pwMae: 2.438, warpsRmse: 2.540 },
  { season: 2010, teams: 32, warpsMae: 2.402, pythMae: 2.896, pwMae: 3.313, warpsRmse: 2.836 },
  { season: 2011, teams: 32, warpsMae: 2.107, pythMae: 2.280, pwMae: 2.813, warpsRmse: 2.713 },
  { season: 2012, teams: 32, warpsMae: 2.535, pythMae: 2.698, pwMae: 3.094, warpsRmse: 2.937 },
  { season: 2013, teams: 32, warpsMae: 2.364, pythMae: 2.607, pwMae: 2.719, warpsRmse: 3.000 },
  { season: 2014, teams: 32, warpsMae: 2.094, pythMae: 2.018, pwMae: 2.188, warpsRmse: 2.500 },
  { season: 2015, teams: 32, warpsMae: 2.301, pythMae: 2.485, pwMae: 2.688, warpsRmse: 2.885 },
  { season: 2016, teams: 32, warpsMae: 2.425, pythMae: 2.597, pwMae: 2.844, warpsRmse: 2.922 },
  { season: 2017, teams: 32, warpsMae: 2.217, pythMae: 2.303, pwMae: 3.125, warpsRmse: 2.767 },
  { season: 2018, teams: 32, warpsMae: 2.091, pythMae: 2.198, pwMae: 2.719, warpsRmse: 2.505 },
  { season: 2019, teams: 32, warpsMae: 2.212, pythMae: 2.259, pwMae: 2.469, warpsRmse: 2.780 },
  { season: 2020, teams: 32, warpsMae: 2.780, pythMae: 2.896, pwMae: 2.906, warpsRmse: 3.118 },
  { season: 2021, teams: 32, warpsMae: 1.938, pythMae: 1.996, pwMae: 2.313, warpsRmse: 2.204 },
  { season: 2022, teams: 32, warpsMae: 2.460, pythMae: 2.853, pwMae: 3.000, warpsRmse: 2.864 },
  { season: 2023, teams: 32, warpsMae: 1.898, pythMae: 2.131, pwMae: 2.594, warpsRmse: 2.391 },
  { season: 2024, teams: 32, warpsMae: 3.013, pythMae: 3.076, pwMae: 2.938, warpsRmse: 3.521 },
  { season: 2025, teams: 32, warpsMae: 2.673, pythMae: 2.978, pwMae: 3.156, warpsRmse: 3.240 },
];

export const calibrationData: CalibrationRow[] = [
  { bucket: "4.8–6.7 wins", avgProj: 6.12, avgActual: 6.36, avgError: -0.24, mae: 2.35, teams: 139 },
  { bucket: "6.7–7.5 wins", avgProj: 7.09, avgActual: 6.99, avgError: 0.10, mae: 2.37, teams: 138 },
  { bucket: "7.5–8.1 wins", avgProj: 7.80, avgActual: 8.07, avgError: -0.27, mae: 2.47, teams: 138 },
  { bucket: "8.1–8.7 wins", avgProj: 8.41, avgActual: 8.07, avgError: 0.34, mae: 2.39, teams: 138 },
  { bucket: "8.7–9.5 wins", avgProj: 9.10, avgActual: 9.12, avgError: -0.02, mae: 2.47, teams: 138 },
  { bucket: "9.5–11.5 wins", avgProj: 10.06, avgActual: 9.96, avgError: 0.10, mae: 2.22, teams: 139 },
];

export const metricRanking: MetricRow[] = [
  { model: "WARPS v1.8 champion (75% Pythagorean + 25% Point Differential)", type: "WARPS composite", warpsMae: 2.352, beatsAll: true },
  { model: "pyth=0.70, point_diff=0.30 blend", type: "WARPS composite", warpsMae: 2.358, beatsAll: true },
  { model: "pyth=0.65, point_diff=0.35 blend", type: "WARPS composite", warpsMae: 2.358, beatsAll: true },
  { model: "pyth=0.75, pass=0.05, point_diff=0.20 blend", type: "WARPS composite", warpsMae: 2.358, beatsAll: true },
  { model: "v1.7 champion (pure Pythagorean)", type: "WARPS composite", warpsMae: 2.365, beatsAll: true },
  { model: "v1.5d default composite", type: "WARPS composite", warpsMae: 2.385, beatsAll: true },
  { model: "Pythagorean alone (baseline)", type: "Baseline", warpsMae: 2.588, beatsAll: false },
  { model: "Prior-year wins (baseline)", type: "Baseline", warpsMae: 2.882, beatsAll: false },
];

export const bootstrapStats: BootstrapStats = {
  warpsMaeFull: 2.374,
  warpsMaeFullCi: [2.261, 2.485],
  pythMaeFull: 2.614,
  pwMaeFull: 2.888,
  warpsMaeVal: 2.511,
  warpsMaeValCi: [2.225, 2.810],
  pythMaeVal: 2.759,
  pwMaeVal: 2.922,
  dmVsPythFull: { stat: 5.853, pval: 0.0000, sig: "***" },
  dmVsPwFull: { stat: 8.607, pval: 0.0000, sig: "***" },
  dmVsPythVal: { stat: 2.560, pval: 0.0052, sig: "**" },
  dmVsPwVal: { stat: 2.485, pval: 0.0065, sig: "**" },
  seasonsBeatingPyth: 25,
  totalSeasons: 26,
};

export const consensusData: ConsensusRow[] = [
  { team: "NO",  marketTotal: 4.5,  v18Wins: 8.32,  v18Edge: 3.82,  v15dEdge: 4.26,  v16Edge: 3.75,  avgEdge: 3.95,  consensus: "3-model Over" },
  { team: "NE",  marketTotal: 8.5,  v18Wins: 11.47, v18Edge: 2.97,  v15dEdge: 2.61,  v16Edge: 3.34,  avgEdge: 2.97,  consensus: "3-model Over" },
  { team: "JAX", marketTotal: 7.5,  v18Wins: 10.41, v18Edge: 2.91,  v15dEdge: 2.39,  v16Edge: 3.19,  avgEdge: 2.83,  consensus: "3-model Over" },
  { team: "NYG", marketTotal: 5.5,  v18Wins: 7.56,  v18Edge: 2.06,  v15dEdge: 2.12,  v16Edge: 1.92,  avgEdge: 2.03,  consensus: "3-model Over" },
  { team: "IND", marketTotal: 7.5,  v18Wins: 9.14,  v18Edge: 1.64,  v15dEdge: 1.44,  v16Edge: 1.71,  avgEdge: 1.59,  consensus: "3-model Over" },
  { team: "ARI", marketTotal: 4.5,  v18Wins: 5.88,  v18Edge: 1.38,  v15dEdge: 1.92,  v16Edge: 1.02,  avgEdge: 1.44,  consensus: "2-Strong Over" },
  { team: "MIA", marketTotal: 4.5,  v18Wins: 5.89,  v18Edge: 1.39,  v15dEdge: 1.53,  v16Edge: 0.99,  avgEdge: 1.30,  consensus: "2-model Over" },
  { team: "ATL", marketTotal: 6.5,  v18Wins: 7.70,  v18Edge: 1.20,  v15dEdge: 1.49,  v16Edge: 1.06,  avgEdge: 1.25,  consensus: "2-Strong Over" },
  { team: "CLE", marketTotal: 5.5,  v18Wins: 6.37,  v18Edge: 0.87,  v15dEdge: 1.18,  v16Edge: 0.47,  avgEdge: 0.84,  consensus: "Split / No bet" },
  { team: "WAS", marketTotal: 7.5,  v18Wins: 7.98,  v18Edge: 0.48,  v15dEdge: 0.94,  v16Edge: 0.38,  avgEdge: 0.60,  consensus: "Split / No bet" },
  { team: "HOU", marketTotal: 9.5,  v18Wins: 9.96,  v18Edge: 0.46,  v15dEdge: -0.11, v16Edge: 0.75,  avgEdge: 0.37,  consensus: "Split / No bet" },
  { team: "PIT", marketTotal: 8.5,  v18Wins: 8.59,  v18Edge: 0.09,  v15dEdge: 0.02,  v16Edge: 0.12,  avgEdge: 0.08,  consensus: "Split / No bet" },
  { team: "CAR", marketTotal: 7.5,  v18Wins: 7.51,  v18Edge: 0.01,  v15dEdge: 0.34,  v16Edge: -0.20, avgEdge: 0.05,  consensus: "Split / No bet" },
  { team: "SEA", marketTotal: 10.5, v18Wins: 10.52, v18Edge: 0.02,  v15dEdge: -0.56, v16Edge: 0.32,  avgEdge: -0.08, consensus: "Split / No bet" },
  { team: "DEN", marketTotal: 9.5,  v18Wins: 9.36,  v18Edge: -0.14, v15dEdge: -0.31, v16Edge: 0.05,  avgEdge: -0.13, consensus: "Split / No bet" },
  { team: "TB",  marketTotal: 8.5,  v18Wins: 8.30,  v18Edge: -0.20, v15dEdge: -0.27, v16Edge: -0.23, avgEdge: -0.23, consensus: "Split / No bet" },
  { team: "TEN", marketTotal: 6.5,  v18Wins: 6.15,  v18Edge: -0.35, v15dEdge: 0.28,  v16Edge: -0.70, avgEdge: -0.25, consensus: "Split / No bet" },
  { team: "DET", marketTotal: 10.5, v18Wins: 10.19, v18Edge: -0.31, v15dEdge: -0.45, v16Edge: -0.07, avgEdge: -0.28, consensus: "Split / No bet" },
  { team: "GB",  marketTotal: 9.5,  v18Wins: 8.87,  v18Edge: -0.63, v15dEdge: -0.41, v16Edge: -0.55, avgEdge: -0.53, consensus: "Split / No bet" },
  { team: "LAR", marketTotal: 11.5, v18Wins: 10.80, v18Edge: -0.70, v15dEdge: -0.72, v16Edge: -0.40, avgEdge: -0.61, consensus: "Split / No bet" },
  { team: "LV",  marketTotal: 6.5,  v18Wins: 5.72,  v18Edge: -0.78, v15dEdge: -0.01, v16Edge: -1.24, avgEdge: -0.68, consensus: "Split / No bet" },
  { team: "LAC", marketTotal: 9.5,  v18Wins: 8.63,  v18Edge: -0.87, v15dEdge: -0.69, v16Edge: -0.85, avgEdge: -0.80, consensus: "Split / No bet" },
  { team: "MIN", marketTotal: 9.5,  v18Wins: 8.72,  v18Edge: -0.78, v15dEdge: -0.99, v16Edge: -0.73, avgEdge: -0.83, consensus: "Split / No bet" },
  { team: "CIN", marketTotal: 9.5,  v18Wins: 8.41,  v18Edge: -1.09, v15dEdge: -1.21, v16Edge: -1.06, avgEdge: -1.12, consensus: "2-Strong Under" },
  { team: "CHI", marketTotal: 9.5,  v18Wins: 8.30,  v18Edge: -1.20, v15dEdge: -1.27, v16Edge: -1.23, avgEdge: -1.23, consensus: "2-Strong Under" },
  { team: "SF",  marketTotal: 10.5, v18Wins: 9.37,  v18Edge: -1.13, v15dEdge: -1.79, v16Edge: -0.99, avgEdge: -1.30, consensus: "2-model Under" },
  { team: "NYJ", marketTotal: 6.5,  v18Wins: 5.18,  v18Edge: -1.32, v15dEdge: -1.06, v16Edge: -1.72, avgEdge: -1.36, consensus: "2-Strong Under" },
  { team: "DAL", marketTotal: 9.5,  v18Wins: 8.05,  v18Edge: -1.45, v15dEdge: -1.49, v16Edge: -1.50, avgEdge: -1.48, consensus: "2-Strong Under" },
  { team: "BAL", marketTotal: 11.5, v18Wins: 9.67,  v18Edge: -1.83, v15dEdge: -2.02, v16Edge: -1.63, avgEdge: -1.82, consensus: "3-model Under" },
  { team: "KC",  marketTotal: 11.5, v18Wins: 9.59,  v18Edge: -1.91, v15dEdge: -2.18, v16Edge: -1.72, avgEdge: -1.94, consensus: "3-model Under" },
  { team: "PHI", marketTotal: 11.5, v18Wins: 9.27,  v18Edge: -2.23, v15dEdge: -2.36, v16Edge: -2.07, avgEdge: -2.22, consensus: "3-model Under" },
  { team: "BUF", marketTotal: 12.5, v18Wins: 10.10, v18Edge: -2.40, v15dEdge: -2.63, v16Edge: -2.19, avgEdge: -2.40, consensus: "3-model Under" },
];
