import modelViewData from "../data/modelView.json";
import recordData from "../data/modelViewRecord.json";

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
  games: ModelGame[];
}
interface LiveRecord {
  markets?: Record<string, Record<string, { late?: Rec; early?: Rec }>>;
}

const data = modelViewData as unknown as ModelView;
const record = recordData as unknown as LiveRecord;
const pct = (v: number) => `${Math.round(v * 100)}%`;
const rec = (r?: Rec | null) => (r && r.pct !== null && r.w + r.l > 0 ? `${r.w}-${r.l} (${(r.pct * 100).toFixed(1)}%)` : "—");

// Learning model: 2015-2025 lean model plus the 2026 layer (sharp splits, line movement).
// Totals are its working market (live record graded by scripts/grade_model_view.py);
// sides are shown as coin-flip information only.
export function ModelViewPanel({ week }: { week: number }) {
  if (data.week !== week) return null;
  const thr = data.lean_threshold;
  const totals = data.games
    .filter((g) => g.total_conf >= thr)
    .map((g) => ({ key: `${g.matchup}-t`, matchup: g.matchup, pick: g.total_pick, conf: g.total_conf }))
    .sort((a, b) => b.conf - a.conf);
  const sides = data.games
    .filter((g) => g.side_conf >= thr)
    .map((g) => ({ key: `${g.matchup}-s`, matchup: g.matchup, pick: g.side_pick, conf: g.side_conf }))
    .sort((a, b) => b.conf - a.conf);
  const tot = record.markets?.totals?.["53"];
  const sid = record.markets?.sides?.["53"];

  return (
    <div className="track-record-strip model-view">
      <div className="track-record-head">
        <strong>Totals leans · Week {week}</strong>
        <span>Model view at {pct(thr)}+, its strongest market</span>
      </div>
      {totals.length ? (
        <ul className="model-view-list">
          {totals.map((x) => (
            <li key={x.key}>
              <b>{x.pick}</b>
              <span>{x.matchup}</span>
              <em className={x.conf >= 0.55 ? "model-view-strong" : undefined}>{pct(x.conf)}</em>
            </li>
          ))}
        </ul>
      ) : (
        <p className="track-record-note">No total clears {pct(thr)} this week.</p>
      )}
      <p className="track-record-note">
        2026 live at {pct(thr)}+: <b>{rec(tot?.late)}</b> at game-day lines, {rec(tot?.early)} at the early-week
        line. Past seasons: {rec(data.history.totals_lean)}. Early numbers have been better, so bet these when they
        first show up. Break-even is 52.4%.
      </p>
      {sides.length > 0 && (
        <p className="track-record-note">
          <b>Sides (coin flip, info only):</b>{" "}
          {sides.map((x) => `${x.pick} (${pct(x.conf)})`).join(", ")}. Past seasons {rec(data.history.sides_lean)}; 2026{" "}
          {rec(sid?.late)}.
        </p>
      )}
    </div>
  );
}
