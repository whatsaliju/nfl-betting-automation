import { Gauge, TrendingDown, TrendingUp } from "lucide-react";
import { teamLogos } from "../data/nflData";
import type { TeamExpectation } from "../types";

function format(value: number | null | undefined, digits = 1) {
  return typeof value === "number" ? value.toFixed(digits) : "n/a";
}

function signed(value: number | null | undefined) {
  if (typeof value !== "number") return "n/a";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}

function bandIcon(band: TeamExpectation["expectation_band"]) {
  if (band === "overperforming") return <TrendingUp size={15} />;
  if (band === "underperforming") return <TrendingDown size={15} />;
  return <Gauge size={15} />;
}

export function ExpectationsView({ expectations }: { expectations: Record<string, TeamExpectation> }) {
  const rows = Object.values(expectations).sort((a, b) => {
    const left = Math.abs(a.pythagorean_pace_vs_vegas ?? 0);
    const right = Math.abs(b.pythagorean_pace_vs_vegas ?? 0);
    return right - left || a.team.localeCompare(b.team);
  });
  const tracked = rows.filter((row) => row.games_tracked > 0);

  return (
    <section className="panel expectations-panel">
      <div className="panel-toolbar">
        <div>
          <h2>Team Expectations</h2>
          <p className="panel-subtitle">Vegas totals vs NFL Pythagorean wins using exponent 2.37</p>
        </div>
        <div className="edge-board-stats">
          <span>{tracked.length} tracked teams</span>
          <span>{rows.length} win totals</span>
        </div>
      </div>

      <div className="expectations-table-shell">
        <table className="compare-table expectations-table">
          <thead>
            <tr>
              <th>Team</th>
              <th>Games</th>
              <th>Actual</th>
              <th>PF</th>
              <th>PA</th>
              <th>Pyth Wins</th>
              <th>Vegas</th>
              <th>Py vs Vegas</th>
              <th>Actual vs Py</th>
              <th>Band</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((team) => (
              <tr key={team.team}>
                <td>
                  <span className="expectation-team">
                    <img src={teamLogos[team.team]} alt="" />
                    <strong>{team.team}</strong>
                  </span>
                </td>
                <td>{team.games_tracked}</td>
                <td>{team.actual_wins}-{team.actual_losses}</td>
                <td>{format(team.points_for, 0)}</td>
                <td>{format(team.points_against, 0)}</td>
                <td>{format(team.pythagorean_wins_17_game_pace)}</td>
                <td>{format(team.vegas_win_total)}</td>
                <td className={team.pythagorean_pace_vs_vegas && team.pythagorean_pace_vs_vegas > 0 ? "positive" : "negative"}>
                  {signed(team.pythagorean_pace_vs_vegas)}
                </td>
                <td className={team.actual_vs_pythagorean && team.actual_vs_pythagorean > 0 ? "positive" : "negative"}>
                  {signed(team.actual_vs_pythagorean)}
                </td>
                <td>
                  <span className={`expectation-band ${team.expectation_band}`}>
                    {bandIcon(team.expectation_band)}
                    {team.expectation_band.replace("_", " ")}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
