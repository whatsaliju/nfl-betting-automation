import { teamLogos } from "../data/nflData";
import type { GameResult } from "../types";

interface Props {
  results: GameResult[];
  loading: boolean;
  error: string | null;
}

export function ResultsView({ results, loading, error }: Props) {
  return (
    <section className="panel">
      <div className="panel-toolbar">
        <h2>Results</h2>
        {loading && <span className="status-pill">Loading ESPN scores</span>}
        {error && <span className="status-pill warning">{error}</span>}
      </div>
      <div className="results-grid">
        {results.map((game) => (
          <article className="result-card" key={`${game.week}-${game.awayTeam}-${game.homeTeam}`}>
            <span>W{game.week}</span>
            <div className={game.winner === game.awayTeam ? "winner" : ""}>
              <img src={teamLogos[game.awayTeam]} alt="" /> {game.awayTeam} <strong>{game.awayScore ?? "-"}</strong>
            </div>
            <div className={game.winner === game.homeTeam ? "winner" : ""}>
              <img src={teamLogos[game.homeTeam]} alt="" /> {game.homeTeam} <strong>{game.homeScore ?? "-"}</strong>
            </div>
            <small>{game.status}</small>
          </article>
        ))}
        {!loading && !results.length && <p className="empty-state">No results loaded yet.</p>}
      </div>
    </section>
  );
}
