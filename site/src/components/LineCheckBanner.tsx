import lineCheckData from "../data/lineCheck.json";

interface LineCheck {
  week: string | number | null;
  source: string;
  checked: number;
  flagged: { matchup_key: string; issues: { field: string; ours: number | null; consensus: number | null }[] }[];
  corrected?: { matchup_key: string; market: string; scraped: string; corrected: string; reason: string; source?: string }[];
  warnings?: string[];
}

const data = lineCheckData as unknown as LineCheck;
const fmt = (field: string, v: number | null) => (v === null ? "unreadable" : field === "spread" && v > 0 ? `+${v}` : `${v}`);

// Scraped lines are corrected against the books' consensus right after each scrape
// (scripts/verify_scraped_lines.py), then the published feed is cross-checked against
// nflverse (scripts/check_lines.py). Corrections are informational; flags need a look.
export function LineCheckBanner({ week }: { week: number }) {
  if (Number(data.week) !== week) return null;
  const corrected = data.corrected ?? [];
  const warnings = data.warnings ?? [];
  if (!data.flagged.length && !corrected.length && !warnings.length) return null;
  const urgent = data.flagged.length > 0 || warnings.length > 0;
  return (
    <div className={urgent ? "line-move-alert" : "line-move-alert line-check-info"}>
      <div>
        {data.flagged.length > 0 && (
          <>
            <strong>Line check: {data.flagged.length} game{data.flagged.length !== 1 ? "s" : ""} don't match the consensus line</strong>
            <ul className="line-check-list">
              {data.flagged.flatMap((g) =>
                g.issues.map((i) => (
                  <li key={`${g.matchup_key}-${i.field}`}>
                    {g.matchup_key} {i.field}: we read {fmt(i.field, i.ours)}, consensus {fmt(i.field, i.consensus)} (home team)
                  </li>
                )),
              )}
            </ul>
            <p className="line-move-note">Check your book before betting these games.</p>
          </>
        )}
        {warnings.length > 0 && (
          <>
            <strong>Data check</strong>
            <ul className="line-check-list">
              {warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          </>
        )}
        {corrected.length > 0 && (
          <>
            <strong>
              Corrected {corrected.length} scraped line{corrected.length !== 1 ? "s" : ""} to the books' consensus
            </strong>
            <ul className="line-check-list">
              {corrected.map((c) => (
                <li key={`${c.matchup_key}-${c.market}`}>
                  {c.matchup_key} {c.market.toLowerCase()}: scraped {c.scraped}, now {c.corrected} ({c.reason})
                </li>
              ))}
            </ul>
            <p className="line-move-note">Source: {corrected[0].source ?? "consensus"}. Picks and edges use the corrected number.</p>
          </>
        )}
      </div>
    </div>
  );
}
