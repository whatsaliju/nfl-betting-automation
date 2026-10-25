import { useEffect, useState } from "react";
import topPicksData from "../data/topPicks.json";

interface Pick {
  matchup: string;
  market: string;
  pick: string;
  contest_line: number;
  market_line: number;
  line_value: number;
  line_source: string;
  basis: string;
  history: string | null;
  also: string[];
  expected: number;
  low: number | null;
  high: number | null;
}
interface ContestPicks {
  season: number;
  week: number;
  budget: number;
  weeks_left: number;
  max_per_week: number;
  picks: Pick[];
}

const data = topPicksData as ContestPicks;
const USED_KEY = `contest-picks-used-${data.season}`;

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const signedPts = (v: number) => `${v > 0 ? "+" : ""}${v.toFixed(1)}`;

function readUsed(): number {
  try {
    const v = Number(localStorage.getItem(USED_KEY));
    return Number.isFinite(v) && v >= 0 ? v : 0;
  } catch {
    return 0;
  }
}

function lineNote(p: Pick) {
  const source = p.line_source === "provisional" ? "Contest line (provisional until the contest posts Thu 4pm ET)"
    : p.line_source === "contest" ? "Posted contest line" : "Contest line (our Thursday snapshot)";
  if (p.line_value === 0) return `${source} matches the market`;
  return `${source} is ${signedPts(p.line_value)} pts ${p.line_value > 0 ? "better" : "worse"} than the market now`;
}

export function TopPicksPanel({ week }: { week: number }) {
  const [used, setUsed] = useState<number>(readUsed);
  useEffect(() => {
    try {
      localStorage.setItem(USED_KEY, String(used));
    } catch {
      /* storage unavailable: keep the value for this visit only */
    }
  }, [used]);

  if (data.week !== week) return null;
  const left = Math.max(0, data.budget - used);
  const target = Math.min(data.max_per_week, Math.ceil(left / Math.max(1, data.weeks_left)), data.picks.length);

  return (
    <section className="tp">
      <div className="tp-head">
        <h3>Contest picks · Week {data.week}</h3>
        <span>Ranked by expected points (win 1, push ½). Re-check Sunday morning: line moves change the order.</span>
      </div>

      <div className="tp-budget">
        <label htmlFor="contest-used">
          Picks used so far
          <input
            id="contest-used"
            type="number"
            min={0}
            max={data.budget}
            value={used}
            onChange={(e) => setUsed(Math.max(0, Math.min(data.budget, Number(e.target.value) || 0)))}
          />
        </label>
        <div><b>{left}</b><span>left of {data.budget}</span></div>
        <div><b>{data.weeks_left}</b><span>weeks left</span></div>
        <div className="tp-target"><b>{target}</b><span>to make this week</span></div>
      </div>

      <ol className="tp-list">
        {data.picks.map((p, i) => (
          <li key={`${p.matchup}-${p.market}`} className={`tp-row${i < target ? " tp-take" : ""}`}>
            <div className="tp-main">
              <strong>{p.pick}</strong>
              <span className="tp-matchup">{p.matchup} · {p.market === "spread" ? "Side" : "Total"}</span>
              <span className="tp-signal">
                {p.basis}{p.history ? ` · history ${p.history}` : ""}
                {p.also.length > 0 ? ` · also: ${p.also.join(", ")}` : ""}
              </span>
              <span className="tp-signal">{lineNote(p)}</span>
            </div>
            <div className="tp-conf">
              <b>{pct(p.expected)}</b>
              <span className="tp-range-text">
                {p.low !== null && p.high !== null ? `${Math.round(p.low * 100)}–${Math.round(p.high * 100)}%` : "expected pts"}
              </span>
              <span className={`tp-tag${i < target ? " on" : ""}`}>{i < target ? "Take" : "Bench"}</span>
            </div>
          </li>
        ))}
      </ol>
      <p className="tp-note">
        Every side and total is priced from 2015–2025 results against the closing line, so a contest line better than
        the market is worth about 4 points of win rate per point of line. Pattern picks (under-start Overs, engine
        plays) add their graded edge, pulled toward 50% so short records can't look stronger than they are. Any pick
        over 50% adds expected points; with {left} picks for {data.weeks_left} weeks, take the top {target}.
      </p>
    </section>
  );
}
