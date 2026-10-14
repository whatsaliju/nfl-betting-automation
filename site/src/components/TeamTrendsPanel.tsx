import { useMemo, useState } from "react";
import { teamLogos } from "../data/nflData";
import trendsData from "../data/teamTrends.json";

interface Rec { w: number; l: number; pct: number | null }
interface TeamTrends {
  season: number;
  through_week: number;
  league: { ou: Rec; home_ats: Rec; fav_ats: Rec };
  teams: { team: string; ou: Rec; ats: Rec }[];
  under_start: {
    teams: string[];
    record: Rec;
    games: { week: number; matchup: string; teams: string[]; total: number; result: string }[];
    upcoming: { week: number; matchup: string; teams: string[]; total: number | null }[];
    history: {
      seasons: string;
      under_start_later_over: Rec;
      others_later_over: Rec;
      seasons_ahead: number;
      season_count: number;
    };
  };
}

const data = trendsData as TeamTrends;

function rec(r: Rec) {
  return `${r.w}–${r.l}`;
}

function pct(r: Rec) {
  return r.pct === null ? "—" : `${Math.round(r.pct * 100)}%`;
}

type SortKey = "ou" | "ats" | "team";

export function TeamTrendsPanel() {
  const [sort, setSort] = useState<SortKey>("ou");
  const flagged = new Set(data.under_start.teams);
  const rows = useMemo(() => {
    const r = [...data.teams];
    if (sort === "team") return r.sort((a, b) => a.team.localeCompare(b.team));
    return r.sort((a, b) => (b[sort].pct ?? 0) - (a[sort].pct ?? 0) || a.team.localeCompare(b.team));
  }, [sort]);
  const u = data.under_start;
  const h = u.history;

  return (
    <section className="trends">
      <div className="trends-head">
        <h3>Team Trends · {data.season} through Week {data.through_week}</h3>
        <p>Graded against closing lines. Overs {rec(data.league.ou)} ({pct(data.league.ou)}) · Home teams ATS {rec(data.league.home_ats)} · Favorites ATS {rec(data.league.fav_ats)}</p>
      </div>

      <div className="trends-angle">
        <div className="trends-angle-top">
          <strong>Tracked angle: Over on teams that started under</strong>
          <span className="trends-tag">Tracking only, not a pick</span>
        </div>
        <p>
          Teams that went over in at most 1 of their first 5 games went over{" "}
          <b>{pct(h.under_start_later_over)}</b> the rest of the season ({rec(h.under_start_later_over)}), against{" "}
          {pct(h.others_later_over)} for everyone else, ahead in {h.seasons_ahead} of {h.season_count} seasons ({h.seasons}).
          Streaks don't predict anything; this works because the market cuts these teams' totals too far.
          At standard odds it needs 52.4% to profit.
        </p>
        {u.teams.length > 0 ? (
          <>
            <div className="trends-chips">
              {u.teams.map((t) => (
                <span key={t} className="trends-chip"><img src={teamLogos[t]} alt="" />{t}</span>
              ))}
            </div>
            <div className="trends-angle-grid">
              <div>
                <span className="trends-label">This season</span>
                <b>{u.record.w + u.record.l > 0 ? `${rec(u.record)} (${pct(u.record)})` : "No graded games yet"}</b>
              </div>
              {u.upcoming.length > 0 && (
                <div>
                  <span className="trends-label">Week {u.upcoming[0].week}</span>
                  <ul>
                    {u.upcoming.map((g) => (
                      <li key={g.matchup}>{g.matchup}{g.total !== null ? ` · Over ${g.total}` : ""}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </>
        ) : (
          <p className="trends-muted">No team qualifies until Week 5 is graded.</p>
        )}
      </div>

      <div className="track-table-wrap">
        <table className="track-table trends-table">
          <thead>
            <tr>
              <th><button onClick={() => setSort("team")}>Team</button></th>
              <th><button onClick={() => setSort("ou")}>Over–Under{sort === "ou" ? " ↓" : ""}</button></th>
              <th><button onClick={() => setSort("ats")}>ATS{sort === "ats" ? " ↓" : ""}</button></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.team} className={flagged.has(r.team) ? "trends-flagged" : undefined}>
                <td><span className="trends-team"><img src={teamLogos[r.team]} alt="" />{r.team}</span></td>
                <td className="track-num">{rec(r.ou)} <span className="trends-pct">{pct(r.ou)}</span></td>
                <td className="track-num">{rec(r.ats)} <span className="trends-pct">{pct(r.ats)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
