export type Conference = "AFC" | "NFC";
export type Filter = "All" | Conference;
export type HomeAway = "home" | "away";
export type SeasonType = "REG" | "POST";

export interface ScheduleRow {
  Team: string;
  [weekKey: `W${number}`]: string;
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
  projectedWins: number;
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

export interface EngineFeed {
  feed_version: string;
  source: string;
  game_count: number;
  team_cell_count: number;
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
  games: EngineGame[];
  team_cells: Record<string, EngineTeamCell> | EngineTeamCell[];
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
