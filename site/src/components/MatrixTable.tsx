import { useState } from "react";
import { divisions, teamLogos } from "../data/nflData";
import { qbChanges2026 } from "../data/qbData";
import { classifyCell, cleanOpponent, flagEmoji, internationalCode, isDivisionGame, isSignificantTravel } from "../lib/schedule";
import type { EngineTeamCell, GameResult, TeamExpectation, TeamProfile, WarpsMarketOverlay } from "../types";
import { EngineBadge } from "./EngineBadge";
import { WarpsMarketBadge } from "./WarpsMarketBadge";

// Win probability from Vegas seasonal O/U lines.
// λ=0.15 calibrated so a 4-win quality gap → ~65% WP (consistent with NFL moneyline data).
// Home field advantage ≈ 1 win-equivalent per season.
function winProbClass(teamOV: number | null, oppOV: number | null, isHome: boolean): string {
  if (teamOV == null || oppOV == null) return "";
  const diff = (teamOV - oppOV) + (isHome ? 1.0 : 0);
  const wp = 1 / (1 + Math.exp(-diff * 0.15));
  if (wp > 0.68) return "wp-high";
  if (wp > 0.56) return "wp-med-high";
  if (wp > 0.44) return "wp-neutral-wp";
  if (wp > 0.32) return "wp-med-low";
  return "wp-low";
}

interface Props {
  teams: TeamProfile[];
  weeks: number[];
  teamStats: Record<string, { sos: number; wins: number | null }>;
  metricLabel: string;
  metricTitle: string;
  metricLegend: string;
  engineCells: Map<string, EngineTeamCell>;
  warpsMarketIndex: Map<string, WarpsMarketOverlay>;
  selectedTeam: string | null;
  showHeatmap: boolean;
  expectations: Record<string, TeamExpectation>;
  results: GameResult[];
  showCellResults: boolean;
  vegasLines: Record<string, number | null>;
  onSelectTeam: (team: string | null) => void;
  onOpenTeam: (team: TeamProfile) => void;
}

function oppConference(code: string): "AFC" | "NFC" | null {
  if (!code) return null;
  for (const [div, teams] of Object.entries(divisions)) {
    if (teams.includes(code)) return div.startsWith("AFC") ? "AFC" : "NFC";
  }
  return null;
}

function buildResultIndex(results: GameResult[]): Map<string, GameResult> {
  const map = new Map<string, GameResult>();
  for (const r of results) {
    map.set(`${r.homeTeam}:${r.week}`, r);
    map.set(`${r.awayTeam}:${r.week}`, r);
  }
  return map;
}

function buildRecordIndex(results: GameResult[]): Map<string, string> {
  const records = new Map<string, { wins: number; losses: number; ties: number }>();
  const ensure = (team: string) => {
    if (!records.has(team)) records.set(team, { wins: 0, losses: 0, ties: 0 });
    return records.get(team)!;
  };

  for (const result of results) {
    if (result.homeScore == null || result.awayScore == null) continue;
    const home = ensure(result.homeTeam);
    const away = ensure(result.awayTeam);
    if (!result.winner) {
      home.ties += 1;
      away.ties += 1;
    } else if (result.winner === result.homeTeam) {
      home.wins += 1;
      away.losses += 1;
    } else {
      away.wins += 1;
      home.losses += 1;
    }
  }

  return new Map(
    Array.from(records.entries()).map(([team, record]) => [
      team,
      record.ties ? `${record.wins}-${record.losses}-${record.ties}` : `${record.wins}-${record.losses}`,
    ])
  );
}

function divAbbr(division: string) {
  const parts = division.split(" ");
  return `${parts[0]} ${parts[1]?.[0] ?? ""}`;
}

function formatMetric(value: number | null) {
  return typeof value === "number" ? value : "-";
}

interface ModalGame {
  teamName: string; oppCode: string; week: number;
  isHome: boolean; daysRest: number | null; hasTravel: boolean;
  teamOV: number | null; oppOV: number | null;
  warpsOverlay?: WarpsMarketOverlay;
}

function MatchupModal({ game, onClose }: { game: ModalGame; onClose: () => void }) {
  const diff = (game.teamOV ?? 8.5) - (game.oppOV ?? 8.5) + (game.isHome ? 1.0 : 0);
  const wp = 1 / (1 + Math.exp(-diff * 0.15));
  const wpPct = (wp * 100).toFixed(0);
  const edge = (game.teamOV ?? 8.5) - (game.oppOV ?? 8.5);
  const teamQB = qbChanges2026.find(q => q.team === game.teamName);
  const oppQB = qbChanges2026.find(q => q.team === game.oppCode);

  return (
    <div className="mm-overlay" onClick={onClose}>
      <div className="mm-modal" onClick={e => e.stopPropagation()}>
        <button className="mm-close" onClick={onClose}>✕</button>
        <div className="mm-header">
          <div className="mm-team-side">
            <img src={teamLogos[game.teamName]} alt={game.teamName} className="mm-logo" />
            <strong>{game.teamName}</strong>
            {teamQB && <span className="mm-qb-change" title={`QB change: ${teamQB.outQb} → ${teamQB.inQb}`}>QB↕</span>}
          </div>
          <div className="mm-vs">{game.isHome ? "vs" : "@"}<br /><span className="mm-wk">Wk {game.week}</span></div>
          <div className="mm-team-side">
            <img src={teamLogos[game.oppCode]} alt={game.oppCode} className="mm-logo" />
            <strong>{game.oppCode}</strong>
            {oppQB && <span className="mm-qb-change" title={`QB change: ${oppQB.outQb} → ${oppQB.inQb}`}>QB↕</span>}
          </div>
        </div>

        <div className="mm-wp-bar">
          <div className="mm-wp-fill" style={{ width: `${wpPct}%`, background: wp > 0.55 ? "#16a34a" : wp < 0.45 ? "#dc2626" : "#94a3b8" }} />
          <span className="mm-wp-label" style={{ color: wp > 0.55 ? "#16a34a" : wp < 0.45 ? "#dc2626" : "#475569" }}>
            {wpPct}% WP
          </span>
        </div>

        <div className="mm-stats">
          <div className="mm-stat">
            <span>Vegas O/U</span>
            <strong>{game.teamOV ?? "—"}</strong>
          </div>
          <div className="mm-stat">
            <span>Opp O/U</span>
            <strong>{game.oppOV ?? "—"}</strong>
          </div>
          <div className="mm-stat">
            <span>Quality edge</span>
            <strong style={{ color: edge > 0 ? "#16a34a" : edge < 0 ? "#dc2626" : "#94a3b8" }}>
              {edge > 0 ? "+" : ""}{edge.toFixed(1)}w
            </strong>
          </div>
          <div className="mm-stat">
            <span>Location</span>
            <strong>{game.isHome ? "Home" : "Away"}</strong>
          </div>
          {game.warpsOverlay && (
            <>
              <div className="mm-stat">
                <span>WARPS spread</span>
                <strong>{game.teamName} {game.teamName === game.warpsOverlay.away_tla ? game.warpsOverlay.fair_away_spread.toFixed(1) : game.warpsOverlay.fair_home_spread.toFixed(1)}</strong>
              </div>
              <div className="mm-stat">
                <span>WARPS ML</span>
                <strong>{game.teamName === game.warpsOverlay.away_tla ? game.warpsOverlay.away_fair_moneyline : game.warpsOverlay.home_fair_moneyline}</strong>
              </div>
            </>
          )}
          {game.daysRest !== null && game.daysRest !== 7 && (
            <div className="mm-stat">
              <span>Days rest</span>
              <strong style={{ color: game.daysRest <= 5 ? "#dc2626" : game.daysRest >= 10 ? "#16a34a" : "#475569" }}>
                {game.daysRest}d
              </strong>
            </div>
          )}
          {game.hasTravel && (
            <div className="mm-stat">
              <span>Travel</span>
              <strong>✈️ 2+ TZ</strong>
            </div>
          )}
        </div>

        {(teamQB || oppQB) && (
          <div className="mm-qb-note">
            {teamQB && <span>{game.teamName}: {teamQB.outQb} → {teamQB.inQb}</span>}
            {oppQB && <span>{game.oppCode}: {oppQB.outQb} → {oppQB.inQb}</span>}
          </div>
        )}
      </div>
    </div>
  );
}

export function MatrixTable({ teams, weeks, teamStats, metricLabel, metricTitle, metricLegend, engineCells, warpsMarketIndex, selectedTeam, showHeatmap, expectations, results, showCellResults, vegasLines, onSelectTeam, onOpenTeam }: Props) {
  const [modalGame, setModalGame] = useState<ModalGame | null>(null);
  const resultIndex = showCellResults ? buildResultIndex(results) : new Map<string, GameResult>();
  const recordIndex = buildRecordIndex(results);

  return (
    <div className="table-shell">
      <div className="matrix-swipe-hint" aria-hidden="true">← swipe to explore all 18 weeks →</div>
      <div className="matrix-legend">
        <div className="legend-group">
          <div className="legend-group-title">Game Type</div>
          <div className="legend-item"><span className="legend-swatch" style={{background:"#f8fafc",border:"1px solid #e2e8f0"}} />Home</div>
          <div className="legend-item"><span className="legend-swatch" style={{background:"#dbeafe",border:"1px solid #93c5fd"}} />Away</div>
          <div className="legend-item"><span className="legend-swatch" style={{background:"#f8fafc",border:"2px solid #16a34a"}} />Home Div</div>
          <div className="legend-item"><span className="legend-swatch" style={{background:"#bfdbfe",border:"2px solid #2563eb"}} />Away Div</div>
          <div className="legend-item"><span className="legend-swatch" style={{background:"#e2e8f0"}} />Bye</div>
        </div>
        <div className="legend-group">
          <div className="legend-group-title">Opponent</div>
          <div className="legend-item"><span style={{color:"#b91c1c",fontWeight:800}}>AFC</span> opponent</div>
          <div className="legend-item"><span style={{color:"#1d4ed8",fontWeight:800}}>NFC</span> opponent</div>
          <div className="legend-item" style={{color:"#64748b"}}>Row tint = your conf</div>
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
          <div className="legend-item">{metricLegend}</div>
          <div className="legend-item">Rest+ = 10+ day rest</div>
          <div className="legend-item">✈️ significant travel</div>
          <div className="legend-item"><span className="legend-warps-pill">W</span> WARPS fair spread</div>
          <div className="legend-item" style={{color:"#16a34a"}}>🟩 &gt;68% WP (Gimme)</div>
          <div className="legend-item" style={{color:"#dc2626"}}>🟥 &lt;32% WP (Schedule loss)</div>
        </div>
      </div>
      <table className="matrix-table">
        <thead>
          <tr>
            <th className="sticky-col team-col">Team</th>
            <th>Div</th>
            <th>SoS</th>
            <th title={metricTitle}>{metricLabel}</th>
            <th>Rest+</th>
            <th>✈️</th>
            {weeks.map((week) => <th key={week}>{week}</th>)}
          </tr>
        </thead>
        <tbody>
          {teams.map((team) => {
            const exp = expectations[team.name];
            const record = recordIndex.get(team.name) || (exp ? `${exp.actual_wins}-${exp.actual_losses}` : null);
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
                <td className="subtle-cell">{divAbbr(team.division)}</td>
                <td>{team.sos}</td>
                <td className={(() => {
                  const vl = vegasLines[team.name] ?? null;
                  const aw: number | null = exp?.actual_wins ?? team.projectedWins ?? null;
                  if (vl === null || aw === null) return "";
                  return aw > vl ? "ou-hit" : aw < vl ? "ou-miss" : "";
                })()}>
                  {(() => {
                    const vl = vegasLines[team.name] ?? null;
                    const aw: number | null = exp?.actual_wins ?? team.projectedWins ?? null;
                    if (vl === null) return formatMetric(team.projectedWins);
                    const ouResult = aw !== null ? (aw > vl ? "over" : aw < vl ? "under" : "push") : null;
                    return (
                      <span className="ou-cell">
                        <span className="ou-line">{vl}</span>
                        {ouResult === "over" && <span className="ou-check">✓</span>}
                        {ouResult === "under" && <span className="ou-x">✗</span>}
                      </span>
                    );
                  })()}
                </td>
                <td>{team.restAdvantages}</td>
                <td>{team.significantTravel}</td>
                {weeks.map((week) => {
                  const game = team.weeks.find((item) => item.week === week);
                  const opponent = game?.opponent || "";
                  const opponentCode = cleanOpponent(opponent);
                  const engine = engineCells.get(`${team.name}:W${week}`);
                  const highlighted = selectedTeam && opponentCode === selectedTeam;
                  const isHome = opponent !== "BYE" && !opponent.startsWith("@");
                  const matchupKey = isHome ? `${opponentCode}@${team.name}` : `${team.name}@${opponentCode}`;
                  const warpsOverlay = opponentCode && opponent !== "BYE" ? warpsMarketIndex.get(matchupKey) : undefined;
                  const heatmap = showHeatmap && opponentCode && opponent !== "BYE"
                    ? winProbClass(vegasLines[team.name] ?? null, vegasLines[opponentCode] ?? null, isHome)
                    : "";
                  const b2b = team.backToBackInfo.find((item) => item.week === week);
                  const flag = flagEmoji(internationalCode(team.name, week, opponent));
                  const isDiv = isDivisionGame(team.name, opponent);
                  const dayTag = game?.dayOfWeek && game.dayOfWeek !== "Sun" ? game.dayOfWeek : null;
                  const isPrimetime = dayTag === "Thu" || dayTag === "Mon";
                  const hasTravel = opponent.startsWith("@") && isSignificantTravel(team.name, opponent, week);
                  const oppConf = opponentCode ? oppConference(opponentCode) : null;
                  const daysRest = game?.daysRest ?? null;
                  const showRest = daysRest !== null && daysRest !== 7 && (daysRest <= 5 || daysRest >= 10);

                  const result = opponent && opponent !== "BYE" ? resultIndex.get(`${team.name}:${week}`) ?? null : null;
                  const isWin = result?.winner === team.name;
                  const isLoss = result?.winner && result.winner !== team.name;
                  const isTie = result && !result.winner;
                  let resultScore: string | null = null;
                  if (result?.homeScore != null && result?.awayScore != null) {
                    const teamIsHome = result.homeTeam === team.name;
                    const teamScore = teamIsHome ? result.homeScore : result.awayScore;
                    const oppScore = teamIsHome ? result.awayScore : result.homeScore;
                    resultScore = `${teamScore}-${oppScore}`;
                  }
                  const resultLabel = isWin ? "W" : isLoss ? "L" : isTie ? "T" : null;

                  return (
                    <td key={week} className={`game-cell ${heatmap}`}>
                      <div
                        className={`game-chip ${classifyCell(team.name, opponent)}${isDiv ? " division-chip" : ""}${highlighted ? " highlight-opponent" : ""}`}
                        onClick={opponentCode && opponent !== "BYE" ? (e) => {
                          e.stopPropagation();
                          setModalGame({
                            teamName: team.name, oppCode: opponentCode, week,
                            isHome, daysRest: game?.daysRest ?? null, hasTravel,
                            teamOV: vegasLines[team.name] ?? null, oppOV: vegasLines[opponentCode] ?? null,
                            warpsOverlay,
                          });
                        } : undefined}
                        style={opponentCode && opponent !== "BYE" ? { cursor: "pointer" } : undefined}
                      >
                        <div className={`chip-name${oppConf ? ` opp-${oppConf.toLowerCase()}` : ""}`}>
                          {opponent}
                        </div>
                        {resultLabel && (
                          <div className={`game-result result-${resultLabel.toLowerCase()}`}>
                            {resultLabel}{resultScore ? ` ${resultScore}` : ""}
                          </div>
                        )}
                        <div className="cell-tags">
                          {dayTag && <span className={isPrimetime ? "primetime-tag" : ""}>{dayTag}</span>}
                          {showRest && (
                            <span className={daysRest <= 5 ? "short-rest-tag" : "long-rest-tag"}>{daysRest}d</span>
                          )}
                          {flag && <span>{flag}</span>}
                          {hasTravel && <span>✈️</span>}
                          {b2b && <span className={b2b.type === "b2b" ? "orange-tag" : "red-tag"}>{b2b.type}</span>}
                        </div>
                        <EngineBadge cell={engine} />
                        <WarpsMarketBadge overlay={warpsOverlay} team={team.name} compact />
                      </div>
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
      {modalGame && <MatchupModal game={modalGame} onClose={() => setModalGame(null)} />}
    </div>
  );
}
