import { teamColors, teamLogos } from "../data/nflData";
import { cleanOpponent, flagEmoji, internationalCode } from "../lib/schedule";
import type { EdgeBoardGame, EngineTeamCell, TeamProfile, WarpsMarketOverlay } from "../types";
import { EngineBadge } from "./EngineBadge";
import { WarpsMarketBadge } from "./WarpsMarketBadge";

const DAY_ORDER: Record<string, number> = { Wed: 0, Thu: 1, Fri: 2, Sat: 3, Sun: 4, Mon: 5 };

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
  const games = teams
    .flatMap((team) => {
      const game = team.weeks.find((item) => item.week === week);
      if (!game || game.opponent === "BYE" || game.opponent.startsWith("@")) return [];
      return [{ homeTeam: team.name, awayTeam: cleanOpponent(game.opponent), game }];
    })
    .filter((item) => dayFilter === "all" || item.game.dayOfWeek === dayFilter)
    .sort((a, b) => (DAY_ORDER[a.game.dayOfWeek] ?? 4) - (DAY_ORDER[b.game.dayOfWeek] ?? 4));

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
          <option value="Thu">Thursday</option>
          <option value="Fri">Friday</option>
          <option value="Sat">Saturday</option>
          <option value="Sun">Sunday</option>
          <option value="Mon">Monday</option>
        </select>
      </div>
      <div className="week-grid">
        {games.map(({ awayTeam, homeTeam, game }) => {
          const awayEngine = engineCells.get(`${awayTeam}:W${week}`);
          const homeEngine = engineCells.get(`${homeTeam}:W${week}`);
          const edge = edgeIndex.get(`${awayTeam}@${homeTeam}`);
          const warpsOverlay = warpsMarketIndex.get(`${awayTeam}@${homeTeam}`);
          const flag = flagEmoji(internationalCode(homeTeam, week, game.opponent));
          const homeColor = teamColors[homeTeam] || "#003594";
          const awayColor = teamColors[awayTeam] || "#64748b";
          return (
            <article className="game-card" key={`${awayTeam}@${homeTeam}`} style={{ "--home-color": homeColor, "--away-color": awayColor } as React.CSSProperties}>
              <div className="game-card-stripe" />
              <div className="game-card-top">
                <span className="game-card-day">{game.dayOfWeek}</span>
                {game.gameDate && <span className="game-card-date">{game.gameDate.toLocaleDateString("en-US", { month: "short", day: "numeric" })}</span>}
                {flag && <span>{flag}</span>}
              </div>
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
