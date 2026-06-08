// WARPS-NFL v1.8 model outputs — embedded from Python run (2026-06-07)
// Extended training window: 2000-2021 (22 seasons, up from 7 in v1.7)

export interface ByYearRow {
  season: number;
  teams: number;
  warpsMae: number;
  pythMae: number;
  pwMae: number;
  warpsRmse: number;
  vegasMae?: number; // available 2015-2025 only (PFR-verified lines)
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
  // Vegas market benchmark (PFR-verified lines, 2015-2025, n=352 team-seasons)
  vegasMaeOverlap: number;
  vegasMaeOverlapCi: [number, number];
  vegasOverlapSeasons: number;
  seasonsBeatingVegas: number;
  dmVsVegasOverlap: { stat: number; pval: number; sig: string };
}

// Profitability backtest: 2003-2020 vs nflverse historical Vegas win totals
export interface ProfitRow {
  model: string;
  threshold: number;
  n: number;
  winPct: number;
  units: number;
  roiPct: number;
}

export interface PnlByYearRow {
  season: number;
  n: number;
  units: number;
  cumUnits: number;
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
  { season: 2015, teams: 32, warpsMae: 2.301, pythMae: 2.485, pwMae: 2.688, warpsRmse: 2.885, vegasMae: 2.234 },
  { season: 2016, teams: 32, warpsMae: 2.425, pythMae: 2.597, pwMae: 2.844, warpsRmse: 2.922, vegasMae: 2.234 },
  { season: 2017, teams: 32, warpsMae: 2.217, pythMae: 2.303, pwMae: 3.125, warpsRmse: 2.767, vegasMae: 2.312 },
  { season: 2018, teams: 32, warpsMae: 2.091, pythMae: 2.198, pwMae: 2.719, warpsRmse: 2.505, vegasMae: 2.078 },
  { season: 2019, teams: 32, warpsMae: 2.212, pythMae: 2.259, pwMae: 2.469, warpsRmse: 2.780, vegasMae: 1.984 },
  { season: 2020, teams: 32, warpsMae: 2.780, pythMae: 2.896, pwMae: 2.906, warpsRmse: 3.118, vegasMae: 2.297 },
  { season: 2021, teams: 32, warpsMae: 1.938, pythMae: 1.996, pwMae: 2.313, warpsRmse: 2.204, vegasMae: 1.594 },
  { season: 2022, teams: 32, warpsMae: 2.460, pythMae: 2.853, pwMae: 3.000, warpsRmse: 2.864, vegasMae: 2.469 },
  { season: 2023, teams: 32, warpsMae: 1.898, pythMae: 2.131, pwMae: 2.594, warpsRmse: 2.391, vegasMae: 1.875 },
  { season: 2024, teams: 32, warpsMae: 3.013, pythMae: 3.076, pwMae: 2.938, warpsRmse: 3.521, vegasMae: 2.859 },
  { season: 2025, teams: 32, warpsMae: 2.673, pythMae: 2.978, pwMae: 3.156, warpsRmse: 3.240, vegasMae: 2.438 },
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
  // Vegas market benchmark: PFR-verified preseason lines, 2015-2025, n=352 team-seasons
  vegasMaeOverlap: 2.216,
  vegasMaeOverlapCi: [2.058, 2.375],
  vegasOverlapSeasons: 11,
  seasonsBeatingVegas: 2,
  dmVsVegasOverlap: { stat: 3.427, pval: 0.0006, sig: "***" },
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

// Profitability simulation against Vegas win totals (nflverse, 2003-2020)
// Actual opening odds used; break-even at -110 juice = 47.6% win rate
export const profitabilityData: ProfitRow[] = [
  { model: "WARPS v1.8",           threshold: 0.5, n: 325, winPct: 47.4, units: -29.934, roiPct: -9.6 },
  { model: "WARPS v1.8",           threshold: 1.0, n: 155, winPct: 46.7, units: -17.250, roiPct: -11.3 },
  { model: "WARPS v1.8",           threshold: 1.5, n:  55, winPct: 50.0, units:  -2.904, roiPct:  -5.4 },
  { model: "WARPS v1.8",           threshold: 2.0, n:   8, winPct: 50.0, units:  +0.069, roiPct:  +0.9 },
  { model: "Pythagorean",          threshold: 1.0, n: 302, winPct: 46.7, units: -27.394, roiPct:  -9.5 },
  { model: "Pythagorean",          threshold: 1.5, n: 179, winPct: 46.6, units: -16.847, roiPct:  -9.7 },
  { model: "Pythagorean",          threshold: 2.0, n:  95, winPct: 40.4, units: -19.197, roiPct: -20.4 },
  { model: "3-model consensus",    threshold: 1.0, n:  51, winPct: 47.1, units:  -3.070, roiPct:  -6.0 },
  { model: "3-model consensus",    threshold: 1.5, n:  19, winPct: 52.6, units:  +1.812, roiPct:  +9.5 },
];

// Residual histogram — prediction error distribution (2000-2025, 830 team-seasons)
// recentCount = 2024-2025 season team-seasons in that bucket
export interface ResidualBucket { lo: number; hi: number; count: number; recentCount: number; }
export const residualHistogram: ResidualBucket[] = [
  { lo: -6, hi: -5, count: 11, recentCount: 7 },
  { lo: -5, hi: -4, count: 47, recentCount: 0 },
  { lo: -4, hi: -3, count: 56, recentCount: 6 },
  { lo: -3, hi: -2, count: 80, recentCount: 3 },
  { lo: -2, hi: -1, count: 91, recentCount: 9 },
  { lo: -1, hi:  0, count: 101, recentCount: 5 },
  { lo:  0, hi:  1, count: 82, recentCount: 7 },
  { lo:  1, hi:  2, count: 96, recentCount: 5 },
  { lo:  2, hi:  3, count: 69, recentCount: 6 },
  { lo:  3, hi:  4, count: 56, recentCount: 3 },
  { lo:  4, hi:  5, count: 41, recentCount: 8 },
  { lo:  5, hi:  6, count: 16, recentCount: 3 },
];

// Cumulative P&L for WARPS v1.8 (edge ≥ 1.0 win) year by year, 2003-2020
export const pnlByYear: PnlByYearRow[] = [
  { season: 2003, n:  6, units: -4.333, cumUnits:  -4.333 },
  { season: 2004, n:  7, units: -1.131, cumUnits:  -5.464 },
  { season: 2005, n: 13, units:  3.775, cumUnits:  -1.689 },
  { season: 2006, n:  6, units: -2.466, cumUnits:  -4.155 },
  { season: 2007, n:  6, units: -0.507, cumUnits:  -4.662 },
  { season: 2008, n:  7, units: -1.083, cumUnits:  -5.746 },
  { season: 2009, n:  7, units:  0.153, cumUnits:  -5.593 },
  { season: 2010, n:  8, units: -4.200, cumUnits:  -9.793 },
  { season: 2011, n: 13, units:  2.216, cumUnits:  -7.577 },
  { season: 2012, n: 11, units: -3.161, cumUnits: -10.737 },
  { season: 2013, n: 11, units: -3.175, cumUnits: -13.912 },
  { season: 2014, n: 11, units:  0.032, cumUnits: -13.880 },
  { season: 2015, n:  3, units:  0.625, cumUnits: -13.255 },
  { season: 2016, n:  6, units:  0.123, cumUnits: -13.132 },
  { season: 2017, n: 10, units:  4.031, cumUnits:  -9.101 },
  { season: 2018, n:  9, units:  0.756, cumUnits:  -8.344 },
  { season: 2019, n: 12, units: -1.858, cumUnits: -10.202 },
  { season: 2020, n:  9, units: -7.048, cumUnits: -17.250 },
];
