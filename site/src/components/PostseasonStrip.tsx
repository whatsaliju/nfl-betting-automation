import type { EngineTeamCell } from "../types";

export function PostseasonStrip({ cells }: { cells: EngineTeamCell[] }) {
  if (!cells.length) return null;
  const games = new Map<string, EngineTeamCell[]>();
  for (const cell of cells) {
    if (!games.has(cell.matchup_key)) games.set(cell.matchup_key, []);
    games.get(cell.matchup_key)?.push(cell);
  }

  return (
    <section className="postseason-strip">
      <div>
        <h2>Postseason Feed</h2>
        <p>Playoff rows are available from the engine feed without changing the regular season matrix.</p>
      </div>
      <div className="postseason-list">
        {[...games.entries()].map(([key, group]) => (
          <div className="postseason-game" key={key}>
            <strong>W{group[0].week}</strong>
            <span>{key}</span>
            <small>{group[0].classification || "analysis pending"}</small>
          </div>
        ))}
      </div>
    </section>
  );
}
