export type Conference = "AFC" | "NFC";
export type Filter = "All" | Conference;
export type HomeAway = "home" | "away";
export type SeasonType = "PRE" | "REG" | "POST";

export interface ScheduleRow {
  Team: string;
  [weekKey: `W${number}`]: string;
}

export interface SeasonSchedule {
  season: number;
  weeks: number[];
  hasResults: boolean;
  scheduleRows: ScheduleRow[];
  gameDays: Record<string, Record<string, string>>;
  gameDates: Record<string, Record<string, string | null>>;
  teamStats: Record<string, { sos: number; wins: number | null }>;
  results: GameResult[];
}

export interface TeamWeek {
  week: number;
  opponent: string;
  dayOfWeek: string;
  gameDate: Date | null;
  daysRest: number | null;
}

export interface TeamProfile {
  name: string;
  division: string;
  conference: Conference;
  sos: number;
  projectedWins: number | null;
  weeks: TeamWeek[];
  backToBackInfo: Array<{ week: number; type: "b2b" | "b2b2b" }>;
  restAdvantages: number;
  significantTravel: number;
  remainingSOS: number | null;
}

export interface EngineTeamCell {
  key: string;
  team: string;
  week: number;
  season: number;
  season_type: SeasonType;
  opponent: string;
  home_away: HomeAway;
  matchup_key: string;
  score_for: number | null;
  score_against: number | null;
  latest_stage: string | null;
  analysis_available: boolean;
  classification: string | null;
  pick_market: string | null;
  pick_side: string | null;
  pick_on_team: boolean;
  selector_score: number | string | null;
  data_quality_status: string | null;
  source_health_status: string | null;
}

export interface WarpsMarketOverlay {
  season: number;
  week: number;
  matchup_key: string;
  game_date: string;
  game_day: string;
  away_tla: string;
  home_tla: string;
  away_warps_wins: number;
  home_warps_wins: number;
  fair_home_spread: number;
  fair_away_spread: number;
  home_win_prob: number;
  away_win_prob: number;
  home_fair_moneyline: string;
  away_fair_moneyline: string;
  market_home_spread: number | "";
  market_away_spread: number | "";
  market_home_moneyline: number | "";
  market_away_moneyline: number | "";
  home_spread_edge: number | "";
  away_spread_edge: number | "";
  spread_overlay_side: "HOME" | "AWAY" | "";
  spread_overlay_team: string;
  spread_overlay_edge_points: number | "";
  home_ml_no_vig_prob: number | "";
  away_ml_no_vig_prob: number | "";
  moneyline_hold: number | "";
  home_ml_edge: number | "";
  away_ml_edge: number | "";
  ml_overlay_side: "HOME" | "AWAY" | "";
  ml_overlay_team: string;
  ml_overlay_edge_prob: number | "";
  ml_overlay_ev: number | "";
  status: "priced" | "fair_line_only";
  recommendation_policy: string;
  source: string;
}

export interface EdgeWarpsMarketOverlay {
  available: boolean;
  status: "priced" | "fair_line_only" | "unavailable" | string;
  source?: string | null;
  recommendation_policy?: string | null;
  historical_policy?: string | null;
  reason?: string | null;
  away_tla?: string | null;
  home_tla?: string | null;
  away_warps_wins?: number | null;
  home_warps_wins?: number | null;
  fair_home_spread?: number | null;
  fair_away_spread?: number | null;
  home_win_prob?: number | null;
  away_win_prob?: number | null;
  home_fair_moneyline?: string | null;
  away_fair_moneyline?: string | null;
  market_home_spread?: number | null;
  market_away_spread?: number | null;
  market_home_moneyline?: number | null;
  market_away_moneyline?: number | null;
  spread_side?: "HOME" | "AWAY" | "NEUTRAL" | null;
  fair_spread_side?: "HOME" | "AWAY" | "NEUTRAL" | null;
  spread_team?: string | null;
  spread_edge_points?: number | null;
  spread_pick_alignment?: "aligned" | "conflict" | "neutral" | "missing" | "no_pick" | "no_spread_pick" | string;
  ml_side?: "HOME" | "AWAY" | null;
  ml_team?: string | null;
  ml_edge_prob?: number | null;
  ml_ev?: number | null;
  ml_pick_alignment?: string | null;
}

export interface EngineGame {
  season: number;
  season_type: SeasonType;
  week: number;
  matchup_key: string;
  away_tla: string;
  home_tla: string;
  away_score: number | null;
  home_score: number | null;
  latest: {
    stage: string | null;
    available: boolean;
    classification?: string | null;
    recommendation?: string | null;
    pick_market?: string | null;
    pick_side?: string | null;
    selector_score?: number | string | null;
    recommendation_trace?: unknown;
    data_quality_status?: string | null;
    source_health_status?: string | null;
  };
}

export interface EdgeMarket {
  market: "spread" | "total" | "moneyline";
  side: string | null;
  score: number | null;
  threshold: number | null;
  cleared_threshold?: boolean;
  blocked?: boolean;
  blockers?: string[];
  signals?: Array<{
    source?: string;
    side?: string;
    score?: number;
    impact?: number;
    status?: string;
  }>;
  conflicts?: Array<{
    source?: string;
    side?: string;
    score?: number;
    impact?: number;
    status?: string;
  }>;
  reasons?: string[];
  status: "playable" | "lean" | "blocked" | "unavailable" | "not_priced";
  reason?: string;
}

export interface EdgeBoardGame {
  season: number;
  season_type: SeasonType;
  week: number;
  matchup_key: string;
  game: string;
  away_team: string;
  home_team: string;
  away_tla: string;
  home_tla: string;
  stage: string | null;
  analysis_available: boolean;
  best_edge: {
    market: "spread" | "total" | null;
    side: string | null;
    score: number | null;
    label: string | null;
    recommendation: string | null;
    status: "play" | "pass";
  };
  markets: {
    spread: EdgeMarket;
    total: EdgeMarket;
    moneyline: EdgeMarket;
  };
  factor_summary: Array<{
    market: string;
    source: string;
    side?: string;
    impact?: number;
    status?: string;
  }>;
  warps_market_overlay?: EdgeWarpsMarketOverlay;
  schedule_context: {
    division_game: boolean;
    conference_game: boolean;
    away_division: string;
    home_division: string;
  };
  expectation_context?: {
    away_team: string;
    home_team: string;
    away?: TeamExpectation;
    home?: TeamExpectation;
    games_tracked_min: number;
    pythagorean_wins_delta: number | null;
    vegas_win_total_delta: number | null;
    pythagorean_vs_vegas_delta: number | null;
    actual_vs_pythagorean_delta: number | null;
    pythagorean_side: "AWAY" | "HOME" | "NEUTRAL" | null;
    market_expectation_side: "AWAY" | "HOME" | "NEUTRAL" | null;
    value_gap_side: "AWAY" | "HOME" | "NEUTRAL" | null;
    overperformance_side: "AWAY" | "HOME" | "NEUTRAL" | null;
    sample_warning: boolean;
  };
  source_health_status: string | null;
  data_quality_status: string | null;
  result: {
    away_score: number | null;
    home_score: number | null;
    final_margin: number | null;
    final_total: number | null;
  };
  explanation?: PickExplanation | null;
}

export interface PickExplanation {
  key: string;
  raw_action: "play" | "lean" | "pass" | string;
  quality_action: "play" | "lean" | "watch" | "pass" | string;
  quality_gate: "clear" | "warn" | "blocked" | string;
  confidence: "high" | "standard" | "watch" | "blocked" | "none" | string;
  market?: string | null;
  side?: string | null;
  selector_score?: string | number | null;
  label?: string | null;
  recommendation?: string | null;
  source_health_status?: string | null;
  data_quality_status?: string | null;
  promoted_matches?: Array<{
    factor: string;
    status: string;
    allowed: boolean;
    plays?: number | null;
    wins?: number | null;
    losses?: number | null;
    lift?: number | null;
  }>;
  source_blockers?: string[];
  source_warnings?: string[];
  market_signals?: string[];
  market_conflicts?: string[];
  market_blockers?: string[];
  reasons?: string[];
}

export interface WeeklyBettingCardRow {
  key: string;
  season: number;
  season_type: SeasonType;
  week: number;
  matchup_key: string;
  away_tla: string;
  home_tla: string;
  action: "play" | "watch" | "lean" | "pass" | string;
  market?: "spread" | "total" | "moneyline" | null;
  side?: string | null;
  confidence?: string | null;
  selector_score?: number | null;
  classification?: string | null;
  recommendation?: string | null;
  required_line?: string | null;
  current_line?: string | null;
  warps_alignment?: string | null;
  warps_side?: string | null;
  source_health?: string | null;
  data_quality?: string | null;
  quality_gate?: string | null;
  main_reasons?: string[];
  risk_flags?: string[];
  market_status?: string | null;
  spread_status?: string | null;
  total_status?: string | null;
  moneyline_status?: string | null;
}

export interface WeeklyBettingCard {
  available?: boolean;
  feed_version?: string;
  source?: string;
  card_count: number;
  plays: number;
  watch: number;
  passes: number;
  cards: WeeklyBettingCardRow[];
}

export interface TeamExpectation {
  team: string;
  conference: string;
  division: string;
  games_tracked: number;
  actual_wins: number;
  actual_losses: number;
  actual_win_pct: number | null;
  points_for: number;
  points_against: number;
  vegas_win_total: number | null;
  pythagorean_exponent: number;
  pythagorean_win_pct: number | null;
  pythagorean_wins_tracked: number | null;
  pythagorean_wins_17_game_pace: number | null;
  actual_vs_pythagorean: number | null;
  pythagorean_pace_vs_vegas: number | null;
  actual_pace_vs_vegas: number | null;
  expectation_band: "overperforming" | "underperforming" | "in_line" | "unknown";
}

export interface PolicySimulation {
  policy: string;
  description?: string | null;
  plays?: number | null;
  wins?: number | null;
  losses?: number | null;
  win_rate?: number | null;
  removed_plays?: number | null;
  removed_wins?: number | null;
  removed_losses?: number | null;
  win_rate_delta?: number | null;
}

export interface FactorLeaderboardRow {
  feature: string;
  value: string;
  actionability?: string | null;
  plays?: number | null;
  wins?: number | null;
  losses?: number | null;
  win_rate?: number | null;
  win_rate_lift?: number | null;
  sample_flag?: string | null;
}

export interface PromotedFactor {
  factor: string;
  feature?: string | null;
  value?: string | null;
  actionability?: string | null;
  plays?: number | null;
  wins?: number | null;
  losses?: number | null;
  win_rate?: number | null;
  win_rate_lift?: number | null;
  promotion_status?: "production_ready" | "candidate" | "monitor" | "research" | string;
  selector_influence_allowed?: boolean | null;
  recommendation?: string | null;
  warnings?: string[];
  blockers?: string[];
}

export interface PromotionOverlaySimulation {
  overlay: string;
  factor?: string | null;
  description?: string | null;
  plays?: number | null;
  wins?: number | null;
  losses?: number | null;
  win_rate?: number | null;
  removed_plays?: number | null;
  removed_wins?: number | null;
  removed_losses?: number | null;
  win_rate_delta?: number | null;
  recommendation?: string | null;
}

export interface SourceReliability {
  overall_status?: string | null;
  overall_score?: number | null;
  weeks_audited?: number | null;
  recommendations?: string[];
  by_source?: Array<{
    source: string;
    weeks: number;
    avg_score: number;
    min_score: number;
    ok_weeks: number;
    degraded_weeks: number;
    unsafe_weeks: number;
    missing_weeks: number;
    total_warnings: number;
    total_critical_warnings: number;
  }>;
  feature_status_buckets?: Array<{
    dimension: string;
    bucket: string;
    games: number;
    graded_picks: number;
    wins: number;
    losses: number;
    pushes: number;
    win_rate: number | null;
  }>;
}

export interface WarpsSelectorAlignment {
  graded_picks?: number | null;
  graded_spread_picks?: number | null;
  warps_joined?: number | null;
  baseline?: {
    plays?: number | null;
    wins?: number | null;
    losses?: number | null;
    pushes?: number | null;
    win_rate?: number | null;
  };
  verdict?: {
    status?: string | null;
    recommendation?: string | null;
    baseline_win_rate?: number | null;
    aligned_win_rate?: number | null;
    conflict_win_rate?: number | null;
    no_conflict_policy_delta?: number | null;
  };
  alignment_buckets?: Array<{
    dimension: string;
    value: string;
    plays?: number | null;
    wins?: number | null;
    losses?: number | null;
    pushes?: number | null;
    win_rate?: number | null;
  }>;
  policy_simulations?: PolicySimulation[];
}

export interface MarketRouterAudit {
  ledger_rows?: number | null;
  selected_bets?: number | null;
  moneyline_research_rows?: number | null;
  verdict?: {
    status?: string | null;
    recommendation?: string | null;
    baseline_win_rate?: number | null;
    best_market?: {
      section?: string;
      bucket?: string;
      plays?: number | null;
      wins?: number | null;
      losses?: number | null;
      pushes?: number | null;
      win_rate?: number | null;
    } | null;
  };
  summary_rows?: Array<{
    section: string;
    bucket: string;
    plays?: number | null;
    wins?: number | null;
    losses?: number | null;
    pushes?: number | null;
    win_rate?: number | null;
  }>;
}

export interface ClvAudit {
  selected_bets?: number | null;
  market_reference_rows?: number | null;
  overall?: {
    plays?: number | null;
    wins?: number | null;
    losses?: number | null;
    pushes?: number | null;
    win_rate?: number | null;
    avg_clv?: number | null;
    beat_close?: number | null;
    lost_to_close?: number | null;
    push_close?: number | null;
    beat_close_rate?: number | null;
  };
  verdict?: {
    status?: string | null;
    recommendation?: string | null;
    best_market_by_clv?: {
      section?: string;
      bucket?: string;
      plays?: number | null;
      wins?: number | null;
      losses?: number | null;
      pushes?: number | null;
      win_rate?: number | null;
      avg_clv?: number | null;
      beat_close_rate?: number | null;
    } | null;
  };
  buckets?: Array<{
    section: string;
    bucket: string;
    plays?: number | null;
    wins?: number | null;
    losses?: number | null;
    pushes?: number | null;
    win_rate?: number | null;
    avg_clv?: number | null;
    beat_close_rate?: number | null;
  }>;
}

export interface BacktestCoverage {
  configured_replay?: {
    weeks?: Array<number | string>;
    week_count?: number | null;
    games?: number | null;
    plays?: number | null;
    graded?: number | null;
    wins?: number | null;
    losses?: number | null;
    pushes?: number | null;
    win_rate?: number | null;
    warnings?: Array<{ week?: number | string; warnings?: string[] }>;
  };
  full_2025_attempt?: {
    weeks_requested?: Array<number | string>;
    completed_weeks?: Array<number | string>;
    skipped_weeks?: Array<{ week?: number | string; reason?: string }>;
    failed_weeks?: Array<{ week?: number | string; reason?: string; source_status?: string }>;
  };
  verdict?: {
    status?: string | null;
    recommendation?: string | null;
    blockers?: string[];
  };
  next_steps?: string[];
}

export interface ResearchSummary {
  available: boolean;
  status: "BUILDING_SAMPLE" | "MONITORING" | "READY_FOR_MODELING" | string;
  sample_warning: boolean;
  feature_rows: number;
  graded_bets: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  observations: string[];
  candidate_policy: {
    status: string;
    recommendation: string;
  };
  top_policy_simulations: PolicySimulation[];
  top_factor_leaderboard?: FactorLeaderboardRow[];
  promotion_summary?: {
    production_ready?: number;
    candidate?: number;
    monitor?: number;
    research?: number;
    [key: string]: number | undefined;
  };
  promoted_factors?: PromotedFactor[];
  promotion_overlay_simulations?: PromotionOverlaySimulation[];
  source_reliability?: SourceReliability | null;
  warps_selector_alignment?: WarpsSelectorAlignment | null;
  market_router?: MarketRouterAudit | null;
  clv_audit?: ClvAudit | null;
  backtest_coverage?: BacktestCoverage | null;
}

export interface EngineFeed {
  feed_version: string;
  source: string;
  game_count: number;
  team_cell_count: number;
  edge_board_count?: number;
  model_readiness?: {
    available: boolean;
    status: string;
    reason?: string;
    replay?: {
      plays?: number;
      wins?: number;
      losses?: number;
      win_rate?: number;
    };
    active_walk_forward?: {
      plays?: number;
      wins?: number;
      losses?: number;
      win_rate?: number;
    };
    optimized_walk_forward?: {
      plays?: number;
      wins?: number;
      losses?: number;
      win_rate?: number;
    };
  };
  research_summary?: ResearchSummary;
  weekly_betting_card?: WeeklyBettingCard;
  games: EngineGame[];
  team_cells: Record<string, EngineTeamCell> | EngineTeamCell[];
  edge_board?: EdgeBoardGame[];
  team_expectations?: Record<string, TeamExpectation>;
}

export interface GameResult {
  week: number;
  homeTeam: string;
  awayTeam: string;
  homeScore: number | null;
  awayScore: number | null;
  status: string;
  winner: string | null;
  date: string | null;
}
