import { intlVenue, teamColors, teamLogos } from "../data/nflData";
import gameTimesData from "../data/gameTimes2026.json";
import { cleanOpponent, flagEmoji, internationalCode } from "../lib/schedule";
import type { EdgeBoardGame, EngineTeamCell, TeamProfile, WarpsMarketOverlay } from "../types";
import { EngineBadge } from "./EngineBadge";
import { WarpsMarketBadge } from "./WarpsMarketBadge";

const gameTimesByWeek = (gameTimesData as { weeks: Record<string, Record<string, string>> }).weeks;

function kickoffET(utcIso: string): string {
  const dt = new Date(utcIso);
  // EDT = UTC-4 (Mar–Nov), EST = UTC-5 (Nov–Mar). NFL season is mostly EDT.
  const month = dt.getUTCMonth() + 1;
  const offsetH = month >= 3 && month <= 10 ? 4 : 5;
  let h = dt.getUTCHours() - offsetH;
  if (h < 0) h += 24;
  const m = dt.getUTCMinutes();
  const ampm = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 || 12;
  return m === 0 ? `${h12} ${ampm} ET` : `${h12}:${String(m).padStart(2, "0")} ${ampm} ET`;
}

interface Props {
  teams: TeamProfile[];
  weeks: number[];
  week: number;
  dayFilter: string;
  engineCells: Map<string, EngineTeamCell>;
  edgeIndex: Map<string, EdgeBoardGame>;
  warpsMarketIndex: Map<string, WarpsMarketOverlay>;
  onWeekChange: (week: number) => void;
  onDayChange: (day: string) => void;
}

function edgeSummary(edge?: EdgeBoardGame) {
  if (!edge) return null;
  if (edge.best_edge.status === "play" && edge.best_edge.market) {
    return `${edge.best_edge.market.toUpperCase()} ${edge.best_edge.side || ""} (${edge.best_edge.score ?? "n/a"})`;
  }
  return "PASS";
}

export function WeekView({ teams, weeks, week, dayFilter, engineCells, edgeIndex, warpsMarketIndex, onWeekChange, onDayChange }: Props) {
  const weekTimes = gameTimesByWeek[String(week)] || {};

  const games = teams
    .flatMap((team) => {
      const game = team.weeks.find((item) => item.week === week);
      if (!game || game.opponent === "BYE" || game.opponent.startsWith("@")) return [];
      const matchupKey = `${cleanOpponent(game.opponent)}@${team.name}`;
      const commence = weekTimes[matchupKey] || null;
      return [{ homeTeam: team.name, awayTeam: cleanOpponent(game.opponent), game, commence }];
    })
    .filter((item) => dayFilter === "all" || item.game.dayOfWeek === dayFilter)
    .sort((a, b) => {
      if (a.commence && b.commence) return a.commence.localeCompare(b.commence);
      if (a.commence) return -1;
      if (b.commence) return 1;
      return 0;
    });

  return (
    <section className="panel">
      <div className="panel-toolbar">
        <h2>Week View</h2>
        <div className="segmented compact">
          {weeks.map((item) => (
            <button key={item} className={item === week ? "active" : ""} onClick={() => onWeekChange(item)}>W{item}</button>
          ))}
        </div>
        <select value={dayFilter} onChange={(event) => onDayChange(event.target.value)}>
          <option value="all">All days</option>
          <option value="Wed">Wednesday</option>
          <option value="Thu">Thursday</option>
          <option value="Fri">Friday</option>
          <option value="Sat">Saturday</option>
          <option value="Sun">Sunday</option>
          <option value="Mon">Monday</option>
        </select>
      </div>
      <div className="week-grid">
        {games.map(({ awayTeam, homeTeam, game, commence }) => {
          const awayEngine = engineCells.get(`${awayTeam}:W${week}`);
          const homeEngine = engineCells.get(`${homeTeam}:W${week}`);
          const edge = edgeIndex.get(`${awayTeam}@${homeTeam}`);
          const warpsOverlay = warpsMarketIndex.get(`${awayTeam}@${homeTeam}`);
          const intlCode = internationalCode(homeTeam, week, game.opponent);
          const flag = flagEmoji(intlCode);
          const venue = intlCode ? intlVenue[intlCode] : null;
          const homeColor = teamColors[homeTeam] || "#003594";
          const awayColor = teamColors[awayTeam] || "#64748b";
          return (
            <article className={`game-card${venue ? " game-card-intl" : ""}`} key={`${awayTeam}@${homeTeam}`} style={{ "--home-color": homeColor, "--away-color": awayColor } as React.CSSProperties}>
              <div className="game-card-stripe" />
              <div className="game-card-top">
                <span className="game-card-day">{game.dayOfWeek}</span>
                {game.gameDate && <span className="game-card-date">{game.gameDate.toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>}
                {commence && <span className="game-card-time">{kickoffET(commence)}</span>}
              </div>
              {venue && (
                <div className="game-card-intl-badge">
                  <span>{flag}</span>
                  <span>{venue.city}</span>
                </div>
              )}
              <div className="matchup-teams">
                <div className="matchup-team away">
                  <img src={teamLogos[awayTeam]} alt={awayTeam} />
                  <span className="team-tla" style={{ color: awayColor }}>{awayTeam}</span>
                </div>
                <span className="matchup-at">@</span>
                <div className="matchup-team home">
                  <img src={teamLogos[homeTeam]} alt={homeTeam} />
                  <span className="team-tla" style={{ color: homeColor }}>{homeTeam}</span>
                </div>
              </div>
              <EngineBadge cell={awayEngine || homeEngine} />
              <WarpsMarketBadge overlay={warpsOverlay} team={homeTeam} />
              {edge && (
                <div className={`week-edge-summary ${edge.best_edge.status}`}>
                  <strong>{edgeSummary(edge)}</strong>
                  <span>
                    Spread {edge.markets.spread.status} · Total {edge.markets.total.status} · ML {edge.markets.moneyline.status.replace("_", " ")}
                  </span>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
