import { teamLogos, teamStats, weeks } from "../data/nflData";
import { classifyCell, cleanOpponent, flagEmoji, getOpponentStrengthClass, internationalCode, isDivisionGame, isSignificantTravel } from "../lib/schedule";
import type { EngineTeamCell, TeamExpectation, TeamProfile } from "../types";
import { EngineBadge } from "./EngineBadge";

interface Props {
  teams: TeamProfile[];
  engineCells: Map<string, EngineTeamCell>;
  selectedTeam: string | null;
  showHeatmap: boolean;
  expectations: Record<string, TeamExpectation>;
  onSelectTeam: (team: string | null) => void;
  onOpenTeam: (team: TeamProfile) => void;
}

export function MatrixTable({ teams, engineCells, selectedTeam, showHeatmap, expectations, onSelectTeam, onOpenTeam }: Props) {
  return (
    <div className="table-shell">
      <table className="matrix-table">
        <thead>
          <tr>
            <th className="sticky-col team-col">Team</th>
            <th>Div</th>
            <th>SoS</th>
            <th>Wins</th>
            <th>Rest+</th>
            <th>Travel</th>
            {weeks.map((week) => <th key={week}>W{week}</th>)}
          </tr>
        </thead>
        <tbody>
          {teams.map((team) => {
            const exp = expectations[team.name];
            const record = exp ? `${exp.actual_wins}-${exp.actual_losses}` : null;
            const [conf, ...regionParts] = team.division.split(" ");
            const region = regionParts.join(" ");
            return (
              <tr key={team.name} className={selectedTeam === team.name ? "selected-team" : ""} onClick={() => onSelectTeam(selectedTeam === team.name ? null : team.name)}>
                <td className="sticky-col team-col">
                  <button className="team-button" onClick={(event) => { event.stopPropagation(); onOpenTeam(team); }}>
                    <img src={teamLogos[team.name]} alt="" />
                    <div className="team-name-block">
                      <span>{team.name}</span>
                      {record && <span className="team-record">{record}</span>}
                    </div>
                  </button>
                </td>
                <td className="subtle-cell div-cell">
                  <span className="div-conf">{conf}</span>
                  <span>{region}</span>
                </td>
                <td>{team.sos}</td>
                <td>{team.projectedWins}</td>
                <td>{team.restAdvantages}</td>
                <td>{team.significantTravel}</td>
                {weeks.map((week) => {
                  const game = team.weeks.find((item) => item.week === week);
                  const opponent = game?.opponent || "";
                  const opponentCode = cleanOpponent(opponent);
                  const engine = engineCells.get(`${team.name}:W${week}`);
                  const highlighted = selectedTeam && opponentCode === selectedTeam;
                  const heatmap = showHeatmap ? getOpponentStrengthClass(teamStats[opponentCode]?.sos) : "";
                  const b2b = team.backToBackInfo.find((item) => item.week === week);
                  const flag = flagEmoji(internationalCode(team.name, week, opponent));
                  const isDiv = isDivisionGame(team.name, opponent);
                  const dayTag = game?.dayOfWeek && game.dayOfWeek !== "Sun" ? game.dayOfWeek : null;
                  const isPrimetime = dayTag === "Thu" || dayTag === "Mon";
                  return (
                    <td key={week} className={`game-cell ${heatmap}`}>
                      <div className={`game-chip ${classifyCell(team.name, opponent)}${isDiv ? " division-chip" : ""} ${highlighted ? "highlight-opponent" : ""}`}>
                        <strong>{opponent}</strong>
                        <div className="cell-tags">
                          {dayTag && <span className={isPrimetime ? "primetime-tag" : ""}>{dayTag}</span>}
                          {game?.daysRest !== null && game?.daysRest !== 7 && (
                            <span className={(game?.daysRest ?? 7) <= 4 ? "short-rest-tag" : "long-rest-tag"}>{game?.daysRest}d</span>
                          )}
                          {flag && <span>{flag}</span>}
                          {opponent.startsWith("@") && isSignificantTravel(team.name, opponent, week) && <span>Travel</span>}
                          {b2b && <span className={b2b.type === "b2b" ? "orange-tag" : "red-tag"}>{b2b.type}</span>}
                          {isDiv && <span className="div-tag">Div</span>}
                        </div>
                        <EngineBadge cell={engine} />
                        {engine?.score_for !== null && engine?.score_for !== undefined && (
                          <div className="score-line">{engine.score_for}-{engine.score_against}</div>
                        )}
                      </div>
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
