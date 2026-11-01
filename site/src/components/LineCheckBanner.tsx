import lineCheckData from "../data/lineCheck.json";

interface LineCheck {
  week: string | number | null;
  source: string;
  checked: number;
  flagged: { matchup_key: string; issues: { field: string; ours: number | null; consensus: number | null }[] }[];
}

const data = lineCheckData as unknown as LineCheck;
const fmt = (field: string, v: number | null) => (v === null ? "unreadable" : field === "spread" && v > 0 ? `+${v}` : `${v}`);

// Our lines are cross-checked against nflverse's consensus on every run (scripts/check_lines.py).
export function LineCheckBanner({ week }: { week: number }) {
  if (Number(data.week) !== week || !data.flagged.length) return null;
  return (
    <div className="line-move-alert">
      <div>
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
        <p className="line-move-note">Likely a scrape misread. Check your book before betting these games.</p>
      </div>
    </div>
  );
}
