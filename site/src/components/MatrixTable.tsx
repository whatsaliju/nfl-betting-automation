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
      <div className="matrix-legend">
        <div className="legend-group">
          <div className="legend-group-title">Game Type</div>
          <div className="legend-item"><span className="legend-swatch" style={{background:"#bbf7d0",border:"1px solid #86efac"}} />Home</div>
          <div className="legend-item"><span className="legend-swatch" style={{background:"#bfdbfe",border:"1px solid #93c5fd"}} />Away</div>
          <div className="legend-item"><span className="legend-swatch" style={{background:"#86efac",border:"2px solid #16a34a"}} />Home Div</div>
          <div className="legend-item"><span className="legend-swatch" style={{background:"#93c5fd",border:"2px solid #2563eb"}} />Away Div</div>
          <div className="legend-item"><span className="legend-swatch" style={{background:"#d9dee6"}} />Bye</div>
        </div>
        <div className="legend-group">
          <div className="legend-group-title">Conference</div>
          <div className="legend-item"><span className="legend-swatch" style={{background:"#fee2e2",border:"1px solid #fca5a5"}} /><span style={{color:"#991b1b",fontWeight:700}}>AFC</span> row</div>
          <div className="legend-item"><span className="legend-swatch" style={{background:"#dbeafe",border:"1px solid #93c5fd"}} /><span style={{color:"#1e40af",fontWeight:700}}>NFC</span> row</div>
        </div>
        <div className="legend-group">
          <div className="legend-group-title">Indicators</div>
          <div className="legend-item"><span style={{color:"#4338ca",fontWeight:800}}>Thu/Mon</span> primetime</div>
          <div className="legend-item"><span style={{color:"#7c3aed",fontWeight:800}}>4d</span> short rest</div>
          <div className="legend-item"><span style={{color:"#15803d",fontWeight:700}}>14d</span> post-bye</div>
          <div className="legend-item"><span style={{color:"#9a4b05",fontWeight:800}}>b2b</span> 2nd consec. away</div>
          <div className="legend-item"><span style={{color:"#a41414",fontWeight:800}}>b2b2b</span> 3rd+ away</div>
        </div>
        <div className="legend-group">
          <div className="legend-group-title">Analytics</div>
          <div className="legend-item">SoS rank (1=hardest)</div>
          <div className="legend-item">Rest+ = 10+ day rest</div>
          <div className="legend-item">✈️ significant travel</div>
          <div className="legend-item" style={{color:"#64748b"}}>Heatmap = opp strength</div>
        </div>
      </div>
      <table className="matrix-table">
        <thead>
          <tr>
            <th className="sticky-col team-col">Team</th>
            <th>Div</th>
            <th>SoS</th>
            <th>Wins</th>
            <th>Rest+</th>
            <th>✈️</th>
            {weeks.map((week) => <th key={week}>{week}</th>)}
          </tr>
        </thead>
        <tbody>
          {teams.map((team) => {
            const exp = expectations[team.name];
            const record = exp ? `${exp.actual_wins}-${exp.actual_losses}` : null;
            const [conf, ...regionParts] = team.division.split(" ");
            const region = regionParts.join(" ");
            const isAfc = team.conference === "AFC";
            const rowClass = [
              isAfc ? "afc-row" : "nfc-row",
              selectedTeam === team.name ? "selected-team" : "",
            ].join(" ");
            return (
              <tr key={team.name} className={rowClass} onClick={() => onSelectTeam(selectedTeam === team.name ? null : team.name)}>
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
                  const hasTravel = opponent.startsWith("@") && isSignificantTravel(team.name, opponent, week);
                  return (
                    <td key={week} className={`game-cell ${heatmap}`}>
                      <div className={`game-chip ${classifyCell(team.name, opponent)}${isDiv ? " division-chip" : ""}${highlighted ? " highlight-opponent" : ""}`}>
                        <div className="chip-name">{opponent}</div>
                        <div className="cell-tags">
                          {dayTag && <span className={isPrimetime ? "primetime-tag" : ""}>{dayTag}</span>}
                          {game?.daysRest !== null && game?.daysRest !== 7 && (
                            <span className={(game?.daysRest ?? 7) <= 4 ? "short-rest-tag" : "long-rest-tag"}>{game?.daysRest}d</span>
                          )}
                          {flag && <span>{flag}</span>}
                          {hasTravel && <span>✈️</span>}
                          {b2b && <span className={b2b.type === "b2b" ? "orange-tag" : "red-tag"}>{b2b.type}</span>}
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
