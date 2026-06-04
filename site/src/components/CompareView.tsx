import { teamLogos } from "../data/nflData";
import type { TeamProfile } from "../types";

interface Props {
  teams: TeamProfile[];
  teamA: string;
  teamB: string;
  onTeamA: (team: string) => void;
  onTeamB: (team: string) => void;
}

export function CompareView({ teams, teamA, teamB, onTeamA, onTeamB }: Props) {
  const first = teams.find((team) => team.name === teamA) || teams[0];
  const second = teams.find((team) => team.name === teamB) || teams[1];
  const options = teams.map((team) => <option key={team.name} value={team.name}>{team.name}</option>);

  return (
    <section className="panel">
      <div className="panel-toolbar">
        <h2>Compare Teams</h2>
        <select value={first.name} onChange={(event) => onTeamA(event.target.value)}>{options}</select>
        <select value={second.name} onChange={(event) => onTeamB(event.target.value)}>{options}</select>
      </div>
      <div className="compare-grid">
        {[first, second].map((team) => (
          <div className="compare-card" key={team.name}>
            <div className="compare-head">
              <img src={teamLogos[team.name]} alt="" />
              <div><h3>{team.name}</h3><p>{team.division}</p></div>
            </div>
            <div className="metric-grid">
              <div><strong>{team.sos}</strong><span>SoS</span></div>
              <div><strong>{team.projectedWins}</strong><span>Wins</span></div>
              <div><strong>{team.restAdvantages}</strong><span>Rest+</span></div>
              <div><strong>{team.significantTravel}</strong><span>Travel</span></div>
            </div>
          </div>
        ))}
      </div>
      <table className="compare-table">
        <thead><tr><th>Week</th><th>{first.name}</th><th>{second.name}</th></tr></thead>
        <tbody>
          {first.weeks.map((game, index) => (
            <tr key={game.week}>
              <td>W{game.week}</td>
              <td>{game.opponent} <span>{game.daysRest !== null && game.daysRest !== 7 ? `${game.daysRest}d` : ""}</span></td>
              <td>{second.weeks[index]?.opponent} <span>{second.weeks[index]?.daysRest !== null && second.weeks[index]?.daysRest !== 7 ? `${second.weeks[index]?.daysRest}d` : ""}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
