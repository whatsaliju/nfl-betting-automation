import { X } from "lucide-react";
import { teamLogos } from "../data/nflData";
import { cleanOpponent, flagEmoji, internationalCode, isDivisionGame, isSignificantTravel } from "../lib/schedule";
import type { EngineTeamCell, TeamExpectation, TeamProfile } from "../types";
import { EngineBadge } from "./EngineBadge";

interface Props {
  team: TeamProfile;
  engineCells: Map<string, EngineTeamCell>;
  expectation?: TeamExpectation;
  metricLabel: string;
  onClose: () => void;
  onNavigateToGame?: (matchupKey: string) => void;
}

function format(value?: number | null) {
  return typeof value === "number" ? value.toFixed(1) : "n/a";
}

export function TeamModal({ team, engineCells, expectation, metricLabel, onClose, onNavigateToGame }: Props) {
  const homeGames = team.weeks.filter((game) => game.opponent && game.opponent !== "BYE" && !game.opponent.startsWith("@")).length;
  const awayGames = team.weeks.filter((game) => game.opponent.startsWith("@")).length;

  return (
    <div className="modal-overlay active" onClick={onClose}>
      <div className="modal-content" onClick={(event) => event.stopPropagation()}>
        <div className="modal-close">
          <button className="icon-button" onClick={onClose} aria-label="Close modal"><X size={18} /></button>
        </div>
        <div className="modal-body">
          <div className="modal-heading">
            <img src={teamLogos[team.name]} alt="" />
            <div>
              <h2>{team.name}</h2>
              <p>{team.division} · SoS {team.sos} · {metricLabel} {format(team.projectedWins)}</p>
            </div>
          </div>
          <div className="metric-grid">
            <div><strong>{homeGames}</strong><span>Home</span></div>
            <div><strong>{awayGames}</strong><span>Away</span></div>
            <div><strong>{team.restAdvantages}</strong><span>Rest+</span></div>
            <div><strong>{team.significantTravel}</strong><span>Travel</span></div>
          </div>
          {expectation && (
            <div className="metric-grid compact-metrics">
              <div><strong>{format(expectation.pythagorean_wins_17_game_pace)}</strong><span>Pyth</span></div>
              <div><strong>{format(expectation.vegas_win_total)}</strong><span>Vegas</span></div>
              <div><strong>{format(expectation.pythagorean_pace_vs_vegas)}</strong><span>Py-Vegas</span></div>
              <div><strong>{format(expectation.actual_vs_pythagorean)}</strong><span>Act-Py</span></div>
            </div>
          )}
          <div className="modal-schedule">
            {team.weeks.map((game) => {
              const engine = engineCells.get(`${team.name}:W${game.week}`);
              const opponent = cleanOpponent(game.opponent);
              const flag = flagEmoji(internationalCode(team.name, game.week, game.opponent));
              const isBye = game.opponent === "BYE";
              const matchupKey = isBye ? null : game.opponent.startsWith("@")
                ? `${team.name}@${opponent}`
                : `${opponent}@${team.name}`;
              const canNavigate = !isBye && !!onNavigateToGame && !!matchupKey;
              return (
                <div
                  className={`modal-game${canNavigate ? " modal-game-clickable" : ""}`}
                  key={game.week}
                  onClick={canNavigate ? () => { onNavigateToGame!(matchupKey!); onClose(); } : undefined}
                  role={canNavigate ? "button" : undefined}
                  tabIndex={canNavigate ? 0 : undefined}
                  onKeyDown={canNavigate ? (e) => e.key === "Enter" && (onNavigateToGame!(matchupKey!), onClose()) : undefined}
                >
                  <div className="modal-game-top">
                    <strong>W{game.week}</strong>
                    <span>{game.opponent}</span>
                  </div>
                  {!isBye && (
                    <div className="mini-flags">
                      {game.dayOfWeek !== "Sun" && <span>{game.dayOfWeek}</span>}
                      {game.daysRest !== null && game.daysRest !== 7 && <span>{game.daysRest}d</span>}
                      {flag && <span>{flag}</span>}
                      {game.opponent.startsWith("@") && isSignificantTravel(team.name, opponent, game.week) && <span>Travel</span>}
                      {isDivisionGame(team.name, game.opponent) && <span>Div</span>}
                    </div>
                  )}
                  <EngineBadge cell={engine} />
                  {canNavigate && <span className="modal-game-cta">View matchup →</span>}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
