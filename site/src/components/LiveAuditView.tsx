import { useMemo } from "react";
import { teamLogos } from "../data/nflData";
import type { TeamExpectation } from "../types";

interface Props {
  expectations: Record<string, TeamExpectation>;
  vegasLines: Record<string, number | null>;
  season: number;
}

function BandBadge({ band }: { band: TeamExpectation["expectation_band"] }) {
  const map: Record<string, { label: string; cls: string }> = {
    overperforming: { label: "↑ Over pace", cls: "band-over" },
    underperforming: { label: "↓ Under pace", cls: "band-under" },
    in_line: { label: "On track", cls: "band-inline" },
    unknown: { label: "—", cls: "band-unknown" },
  };
  const { label, cls } = map[band] ?? map.unknown;
  return <span className={`band-badge ${cls}`}>{label}</span>;
}

function WinBar({ actual, pace, total }: { actual: number; pace: number | null; total: number | null }) {
  if (!total) return null;
  const max = Math.max(total * 1.2, actual, pace ?? 0) + 1;
  const actualW = `${Math.min((actual / max) * 100, 100).toFixed(1)}%`;
  const paceW = pace !== null ? `${Math.min((pace / max) * 100, 100).toFixed(1)}%` : null;
  const lineL = `${((total / max) * 100).toFixed(1)}%`;
  return (
    <div className="audit-bar-wrap" title={`${actual}W actual · ${pace?.toFixed(1) ?? "—"} Pyth pace · ${total} Vegas`}>
      <div className="audit-bar-track">
        {paceW && <div className="audit-bar-pace" style={{ width: paceW }} />}
        <div className="audit-bar-actual" style={{ width: actualW }} />
        <div className="audit-bar-line" style={{ left: lineL }} />
      </div>
    </div>
  );
}

export function LiveAuditView({ expectations, vegasLines, season }: Props) {
  const rows = useMemo(() => {
    return Object.values(expectations)
      .map(e => ({ ...e, vegasLine: vegasLines[e.team] ?? e.vegas_win_total }))
      .sort((a, b) => Math.abs(b.pythagorean_pace_vs_vegas ?? 0) - Math.abs(a.pythagorean_pace_vs_vegas ?? 0));
  }, [expectations, vegasLines]);

  if (!rows.length) {
    return (
      <div className="audit-empty">
        <div className="audit-empty-icon">📊</div>
        <h3>Live Season Audit — {season}</h3>
        <p>
          No in-season data yet. Once the {season} season kicks off, this view tracks
          WARPS Pythagorean projections against real standings each week.
        </p>
      </div>
    );
  }

  const week = rows[0]?.games_tracked ?? 0;
  const over = rows.filter(r => r.expectation_band === "overperforming").length;
  const under = rows.filter(r => r.expectation_band === "underperforming").length;

  return (
    <div className="audit-wrapper">
      <div className="audit-header">
        <div>
          <h2 className="audit-title">Live Season Audit — {season}</h2>
          <p className="audit-subtitle">
            Pythagorean win pace vs preseason Vegas O/U · through {week} game{week !== 1 ? "s" : ""} ·
            {" "}<span style={{ color: "#16a34a" }}>{over} over pace</span> ·{" "}
            <span style={{ color: "#dc2626" }}>{under} under pace</span>
          </p>
        </div>
      </div>
      <div className="audit-table-wrap">
        <table className="audit-table">
          <thead>
            <tr>
              <th>Team</th>
              <th>W-L</th>
              <th>Gms</th>
              <th>Vegas O/U</th>
              <th>Pyth Pace</th>
              <th>vs Vegas</th>
              <th>Status</th>
              <th>Pace bar</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => {
              const delta = r.pythagorean_pace_vs_vegas;
              const deltaStr = delta !== null ? (delta > 0 ? `+${delta.toFixed(1)}` : delta.toFixed(1)) : "—";
              const deltaCls = delta !== null ? (delta > 0.5 ? "audit-pos" : delta < -0.5 ? "audit-neg" : "") : "";
              return (
                <tr key={r.team}>
                  <td>
                    <div className="audit-team-cell">
                      <img src={teamLogos[r.team]} alt="" className="audit-logo" />
                      <span>{r.team}</span>
                    </div>
                  </td>
                  <td className="audit-num">{r.actual_wins}-{r.actual_losses}</td>
                  <td className="audit-num">{r.games_tracked}</td>
                  <td className="audit-num">{r.vegasLine ?? "—"}</td>
                  <td className="audit-num">{r.pythagorean_wins_17_game_pace?.toFixed(1) ?? "—"}</td>
                  <td className={`audit-num ${deltaCls}`}>{deltaStr}</td>
                  <td><BandBadge band={r.expectation_band} /></td>
                  <td><WinBar actual={r.actual_wins} pace={r.pythagorean_wins_17_game_pace} total={r.vegasLine} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
