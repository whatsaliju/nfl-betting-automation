import seasonScheduleData from "../data/seasonSchedules.json";
import { getConference, getDivision, intlGames, teamStats as defaultSeasonTeamStats, teamTimeZones } from "../data/nflData";
import type { EdgeBoardGame, EngineFeed, EngineTeamCell, GameResult, ScheduleRow, SeasonSchedule, TeamProfile, TeamWeek } from "../types";

export const ENGINE_FEED_URL =
  import.meta.env.VITE_ENGINE_FEED_URL ||
  "https://raw.githubusercontent.com/whatsaliju/nfl-betting-automation/main/data/historical/matrix_engine_feed.json";

const schedulesBySeason = seasonScheduleData as Record<string, SeasonSchedule>;

export const availableSeasons = Object.keys(schedulesBySeason)
  .map(Number)
  .sort((a, b) => a - b);

export const DEFAULT_SEASON = 2025;

export function getSeasonSchedule(season: number): SeasonSchedule {
  return schedulesBySeason[String(season)] || schedulesBySeason[String(DEFAULT_SEASON)];
}

export function getDisplayTeamStats(schedule: SeasonSchedule) {
  return schedule.season === DEFAULT_SEASON ? defaultSeasonTeamStats : schedule.teamStats;
}

export function cleanOpponent(opponent: string) {
  return opponent.replace("@", "").trim();
}

export function getGameDay(team: string, week: number, schedule: SeasonSchedule) {
  return schedule.gameDays[String(week)]?.[team] || "Sun";
}

export function getGameDate(team: string, week: number, schedule: SeasonSchedule) {
  const raw = schedule.gameDates[String(week)]?.[team];
  return raw ? new Date(`${raw}T12:00:00Z`) : null;
}

export function calculateDaysRest(previous: Date | null, next: Date | null) {
  if (!previous || !next) return null;
  return Math.round((next.getTime() - previous.getTime()) / 86400000);
}

export function flagEmoji(code: string | null) {
  if (!code || code.length !== 2) return null;
  const base = 0x1f1e6;
  return String.fromCodePoint(base + code.charCodeAt(0) - 65, base + code.charCodeAt(1) - 65);
}

export function internationalCode(team: string, week: number, opponent: string) {
  const cleanTeam = cleanOpponent(team);
  const cleanOpp = cleanOpponent(opponent);
  const match = (intlGames[week] || []).find(([left, right]) => {
    const a = cleanOpponent(left);
    const b = cleanOpponent(right);
    return (cleanTeam === a && cleanOpp === b) || (cleanTeam === b && cleanOpp === a);
  });
  return match?.[2] || null;
}

export function isDivisionGame(team: string, opponent: string) {
  if (!opponent || opponent === "BYE") return false;
  return getDivision(team) === getDivision(cleanOpponent(opponent));
}

export function isSignificantTravel(team: string, opponent: string, week: number) {
  if (internationalCode(team, week, opponent)) return true;
  const from = teamTimeZones[team];
  const to = teamTimeZones[cleanOpponent(opponent)];
  if (!from || !to) return false;
  return (
    (from === "PST" && to === "EST") ||
    (from === "EST" && to === "PST") ||
    (from === "PST" && to === "CST") ||
    (from === "EST" && to === "MST")
  );
}

export function buildWeeks(row: ScheduleRow, schedule: SeasonSchedule): TeamWeek[] {
  const team = row.Team;
  const built = schedule.weeks.map((week) => {
    const opponent = row[`W${week}`] || "";
    return {
      week,
      opponent,
      dayOfWeek: getGameDay(team, week, schedule),
      gameDate: opponent && opponent !== "BYE" ? getGameDate(team, week, schedule) : null,
      daysRest: null
    };
  });

  return built.map((game, index) => {
    if (index === 0 || game.opponent === "BYE") return game;
    const previousGame = [...built.slice(0, index)].reverse().find((candidate) => candidate.opponent !== "BYE");
    if (!previousGame) return game;
    return {
      ...game,
      daysRest: calculateDaysRest(previousGame.gameDate, game.gameDate)
    };
  });
}

export function analyzeBackToBack(teamWeeks: TeamWeek[]) {
  const info: TeamProfile["backToBackInfo"] = [];
  for (let index = 1; index < teamWeeks.length; index += 1) {
    const game = teamWeeks[index];
    if (!game.opponent.startsWith("@")) continue;
    let streak = 1;
    let cursor = index - 1;
    while (cursor >= 0 && teamWeeks[cursor].opponent.startsWith("@")) {
      streak += 1;
      cursor -= 1;
    }
    if (streak >= 2) info.push({ week: game.week, type: streak === 2 ? "b2b" : "b2b2b" });
  }
  return info;
}

export function calculateRemainingSOS(team: string, schedule: SeasonSchedule, currentWeek = 1) {
  const row = schedule.scheduleRows.find((item) => item.Team === team);
  if (!row) return null;
  const opponents = schedule.weeks
    .filter((week) => week >= currentWeek)
    .map((week) => cleanOpponent(row[`W${week}`] || ""))
    .filter((opponent) => opponent && opponent !== "BYE");
  if (!opponents.length) return null;
  const displayStats = getDisplayTeamStats(schedule);
  return opponents.reduce((sum, opponent) => sum + (displayStats[opponent]?.sos || 16), 0) / opponents.length;
}

export function buildTeams(schedule = getSeasonSchedule(DEFAULT_SEASON)): TeamProfile[] {
  const displayStats = getDisplayTeamStats(schedule);
  return schedule.scheduleRows.map((row) => {
    const teamWeeks = buildWeeks(row, schedule);
    const team = row.Team;
    return {
      name: team,
      division: getDivision(team),
      conference: getConference(team),
      sos: displayStats[team]?.sos || 0,
      projectedWins: displayStats[team]?.wins ?? null,
      weeks: teamWeeks,
      backToBackInfo: analyzeBackToBack(teamWeeks),
      restAdvantages: teamWeeks.filter((game) => game.daysRest !== null && game.daysRest >= 10).length,
      significantTravel: teamWeeks.filter((game) => game.opponent.startsWith("@") && isSignificantTravel(team, game.opponent, game.week)).length,
      remainingSOS: calculateRemainingSOS(team, schedule)
    };
  });
}

export function getOpponentStrengthClass(sos?: number) {
  if (!sos) return "";
  if (sos <= 6) return "sos-very-hard";
  if (sos <= 12) return "sos-hard";
  if (sos <= 20) return "sos-medium";
  if (sos <= 26) return "sos-easy";
  return "sos-very-easy";
}

export function classifyCell(team: string, opponent: string) {
  if (!opponent) return "";
  if (opponent === "BYE") return "bye-cell";
  const away = opponent.startsWith("@");
  const division = isDivisionGame(team, opponent);
  if (division) return away ? "away-cell division-cell" : "home-cell division-cell";
  return away ? "away-cell" : "home-cell";
}

export async function loadEngineFeed(url = ENGINE_FEED_URL): Promise<EngineFeed> {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`Engine feed failed: ${response.status}`);
  return response.json();
}

function engineCellValues(feed: EngineFeed | null) {
  const cells = feed?.team_cells || [];
  return Array.isArray(cells) ? cells : Object.values(cells);
}

export function indexEngineCells(feed: EngineFeed | null, season = DEFAULT_SEASON) {
  const map = new Map<string, EngineTeamCell>();
  for (const cell of engineCellValues(feed)) {
    if (cell.season_type === "REG" && cell.season === season) map.set(cell.key, cell);
  }
  return map;
}

export function postseasonCells(feed: EngineFeed | null, season = DEFAULT_SEASON) {
  return engineCellValues(feed).filter((cell) => cell.season_type === "POST" && cell.season === season);
}

export function edgeBoardGames(feed: EngineFeed | null, season = DEFAULT_SEASON) {
  return (feed?.edge_board || []).filter((game) => game.season === season);
}

export function indexEdgeBoard(feed: EngineFeed | null, season = DEFAULT_SEASON) {
  const map = new Map<string, EdgeBoardGame>();
  for (const game of edgeBoardGames(feed, season)) {
    if (game.season_type === "REG") map.set(game.matchup_key, game);
  }
  return map;
}

export function getSeasonResults(schedule: SeasonSchedule): GameResult[] {
  return schedule.results || [];
}
