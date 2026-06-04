import { teamLogos } from "../data/nflData";
import { cleanOpponent, flagEmoji, internationalCode } from "../lib/schedule";
import type { EngineTeamCell, TeamProfile } from "../types";
import { EngineBadge } from "./EngineBadge";

interface Props {
  teams: TeamProfile[];
  week: number;
  dayFilter: string;
  engineCells: Map<string, EngineTeamCell>;
  onWeekChange: (week: number) => void;
  onDayChange: (day: string) => void;
}

export function WeekView({ teams, week, dayFilter, engineCells, onWeekChange, onDayChange }: Props) {
  const games = teams
    .flatMap((team) => {
      const game = team.weeks.find((item) => item.week === week);
      if (!game || game.opponent === "BYE" || game.opponent.startsWith("@")) return [];
      return [{ homeTeam: team.name, awayTeam: cleanOpponent(game.opponent), game }];
    })
    .filter((item) => dayFilter === "all" || item.game.dayOfWeek === dayFilter);

  return (
    <section className="panel">
      <div className="panel-toolbar">
        <h2>Week View</h2>
        <div className="segmented compact">
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18].map((item) => (
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
          const flag = flagEmoji(internationalCode(homeTeam, week, game.opponent));
          return (
            <article className="game-card" key={`${awayTeam}@${homeTeam}`}>
              <div className="game-card-top">
                <span>{game.dayOfWeek}</span>
                {flag && <span>{flag}</span>}
              </div>
              <div className="matchup-row">
                <img src={teamLogos[awayTeam]} alt="" />
                <strong>{awayTeam}</strong>
                <span>@</span>
                <img src={teamLogos[homeTeam]} alt="" />
                <strong>{homeTeam}</strong>
              </div>
              <EngineBadge cell={awayEngine || homeEngine} />
            </article>
          );
        })}
      </div>
    </section>
  );
}
