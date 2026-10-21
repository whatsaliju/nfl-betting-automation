import modelViewData from "../data/modelView.json";

interface Rec { w: number; l: number; pct: number | null }
interface ModelGame {
  matchup: string;
  side_pick: string;
  side_conf: number;
  total_pick: string;
  total_conf: number;
}
interface ModelView {
  week: number | null;
  lean_threshold: number;
  history: { sides_lean?: Rec | null; totals_lean?: Rec | null };
  live: { sides?: { with_2026_layer_walk_forward: Rec }; totals?: { with_2026_layer_walk_forward: Rec } };
  games: ModelGame[];
}

const data = modelViewData as unknown as ModelView;
const pct = (v: number) => `${Math.round(v * 100)}%`;
const rec = (r?: Rec | null) => (r && r.pct !== null ? `${r.w}-${r.l} (${(r.pct * 100).toFixed(1)}%)` : "—");

// Learning model: 2015-2025 lean model plus the 2026 layer (sharp splits, line movement).
// Shown beside the engine as a second opinion; it does not change the betting card.
export function ModelViewPanel({ week }: { week: number }) {
  if (data.week !== week) return null;
  const leans = data.games
    .flatMap((g) => [
      { key: `${g.matchup}-s`, matchup: g.matchup, pick: g.side_pick, conf: g.side_conf },
      { key: `${g.matchup}-t`, matchup: g.matchup, pick: g.total_pick, conf: g.total_conf },
    ])
    .filter((x) => x.conf >= data.lean_threshold)
    .sort((a, b) => b.conf - a.conf);

  return (
    <div className="track-record-strip model-view">
      <div className="track-record-head">
        <strong>Model view · Week {week}</strong>
        <span>Learning model leans at {pct(data.lean_threshold)}+, a second opinion beside the engine</span>
      </div>
      {leans.length ? (
        <ul className="model-view-list">
          {leans.map((x) => (
            <li key={x.key}>
              <b>{x.pick}</b>
              <span>{x.matchup}</span>
              <em>{pct(x.conf)}</em>
            </li>
          ))}
        </ul>
      ) : (
        <p className="track-record-note">No game clears {pct(data.lean_threshold)} this week.</p>
      )}
      <p className="track-record-note">
        At {pct(data.lean_threshold)}+, past seasons went sides {rec(data.history.sides_lean)} and totals{" "}
        {rec(data.history.totals_lean)} (2018–2025, each season tested on earlier ones). 2026 so far: sides{" "}
        {rec(data.live.sides?.with_2026_layer_walk_forward)}, totals {rec(data.live.totals?.with_2026_layer_walk_forward)}.
        Break-even is 52.4%. These are weak leans, graded at the closing line.
      </p>
    </div>
  );
}
