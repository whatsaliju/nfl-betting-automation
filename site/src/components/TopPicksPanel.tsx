import topPicksData from "../data/topPicks.json";

interface Pick {
  matchup: string;
  market: string;
  pick: string;
  signal: string;
  also: string[];
  expected: number;
  low: number;
  high: number;
  history: string;
}
interface TopPicks {
  season: number;
  week: number;
  breakeven: number;
  picks: Pick[];
  below_breakeven: number;
  conflicts: { matchup: string; market: string }[];
}

const data = topPicksData as TopPicks;

// Bar spans 40%-70% so the 52.4% breakeven sits in view.
const MIN = 0.4;
const MAX = 0.7;
const pos = (v: number) => `${Math.min(100, Math.max(0, ((v - MIN) / (MAX - MIN)) * 100))}%`;
const pct = (v: number) => `${Math.round(v * 100)}%`;

export function TopPicksPanel({ week }: { week: number }) {
  if (data.week !== week) return null;
  const picks = data.picks;

  return (
    <section className="tp">
      <div className="tp-head">
        <h3>Top picks · Week {data.week}</h3>
        <span>
          {picks.length === 0
            ? "No spread or total pick clears breakeven this week."
            : picks.length < 10
              ? `Only ${picks.length} clear the ${(data.breakeven * 100).toFixed(1)}% breakeven this week`
              : `Top 10 by confidence`}
        </span>
      </div>
      {picks.length > 0 && (
        <ol className="tp-list">
          {picks.map((p) => (
            <li key={`${p.matchup}-${p.market}`} className="tp-row">
              <div className="tp-main">
                <strong>{p.pick}</strong>
                <span className="tp-matchup">{p.matchup}</span>
                <span className="tp-signal">
                  {p.signal} · history {p.history}
                  {p.also.length > 0 ? ` · also: ${p.also.join(", ")}` : ""}
                </span>
              </div>
              <div className="tp-conf" aria-label={`Expected ${pct(p.expected)}, 90% range ${pct(p.low)} to ${pct(p.high)}`}>
                <b>{pct(p.expected)}</b>
                <div className="tp-bar">
                  <span className="tp-range" style={{ left: pos(p.low), width: `calc(${pos(p.high)} - ${pos(p.low)})` }} />
                  <span className="tp-dot" style={{ left: pos(p.expected) }} />
                  <span className="tp-even" style={{ left: pos(data.breakeven) }} />
                </div>
                <span className="tp-range-text">{pct(p.low)}–{pct(p.high)}</span>
              </div>
            </li>
          ))}
        </ol>
      )}
      <p className="tp-note">
        Each pick's rate is its kind of pick's graded history, pulled toward 50% so short records can't look stronger
        than they are. The bar shows the 90% range; the tick marks the {(data.breakeven * 100).toFixed(1)}% needed to profit at −110.
        {data.conflicts.length > 0 ? ` ${data.conflicts.length} game(s) left out because signals disagree.` : ""}
      </p>
    </section>
  );
}
