import { useState, useMemo } from "react";
import { historicalVegasLines, teamLogos } from "../data/nflData";
import { historicalTeamData, consensusData } from "../data/warpsData";

// ─── Types ────────────────────────────────────────────────────────────────────
interface TeamAuditRow {
  team: string;
  vegasLine: number;
  actualWins: number | null;   // null = season not played yet
  warpsProj: number;
  ouResult: "over" | "under" | "push" | null;
  warpsEdge: number;            // warpsProj − vegasLine
  warpsPick: "over" | "under" | "push";
  warpsHit: boolean | null;
}

interface SeasonSummary {
  season: number;
  rows: TeamAuditRow[];
  overs: number;
  unders: number;
  pushes: number;
  vegasMAE: number;
  warpsMAE: number | null;
  warpsPickAcc: number | null; // % of WARPS directional picks that were correct
  warpsPickCount: number;
  complete: boolean;           // false = 2026 / future
}

// ─── Data build ───────────────────────────────────────────────────────────────
function buildSeasonSummary(season: number): SeasonSummary {
  const vl = historicalVegasLines[String(season)] ?? {};
  const complete = season <= 2025;
  const rows: TeamAuditRow[] = [];

  for (const [team, line] of Object.entries(vl)) {
    // Actual wins: from historicalTeamData (completed) or null (2026)
    const hist = historicalTeamData.find(r => r.s === season && r.t === team);
    // WARPS projection: from historicalTeamData (past) or consensusData (2026)
    const warpsProj = hist
      ? hist.ww
      : (consensusData.find(r => r.team === team)?.v18Wins ?? line);

    const actualWins = hist ? hist.w : null;
    const ouResult: TeamAuditRow["ouResult"] =
      actualWins === null ? null :
      actualWins > line ? "over" :
      actualWins < line ? "under" : "push";

    const warpsEdge = warpsProj - line;
    const warpsPick: TeamAuditRow["warpsPick"] =
      warpsEdge > 0.05 ? "over" : warpsEdge < -0.05 ? "under" : "push";

    const warpsHit: boolean | null =
      ouResult === null || warpsPick === "push" ? null :
      (warpsPick === "over" && ouResult === "over") ||
      (warpsPick === "under" && ouResult === "under");

    rows.push({ team, vegasLine: line, actualWins, warpsProj, ouResult, warpsEdge, warpsPick, warpsHit });
  }

  rows.sort((a, b) => a.team.localeCompare(b.team));

  const done = rows.filter(r => r.ouResult !== null);
  const overs = done.filter(r => r.ouResult === "over").length;
  const unders = done.filter(r => r.ouResult === "under").length;
  const pushes = done.filter(r => r.ouResult === "push").length;

  const vegasMAE = done.length
    ? done.reduce((s, r) => s + Math.abs(r.actualWins! - r.vegasLine), 0) / done.length
    : 0;
  const warpsMAE = done.length && rows.some(r => r.warpsProj !== r.vegasLine)
    ? done.reduce((s, r) => s + Math.abs(r.actualWins! - r.warpsProj), 0) / done.length
    : null;

  const pickRows = rows.filter(r => r.warpsPick !== "push" && r.warpsHit !== null);
  const warpsPickAcc = pickRows.length
    ? pickRows.filter(r => r.warpsHit).length / pickRows.length
    : null;

  return { season, rows, overs, unders, pushes, vegasMAE, warpsMAE, warpsPickAcc, warpsPickCount: pickRows.length, complete };
}

const SEASONS = [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015];

// ─── Helper components ────────────────────────────────────────────────────────
function OUBadge({ result }: { result: TeamAuditRow["ouResult"] }) {
  if (!result) return <span className="ou-tbd">TBD</span>;
  if (result === "push") return <span className="ou-push">PUSH</span>;
  return result === "over"
    ? <span className="ou-over">✓ OVER</span>
    : <span className="ou-under">✗ UNDER</span>;
}

function WarpsPick({ pick, hit }: { pick: TeamAuditRow["warpsPick"]; hit: boolean | null }) {
  const label = pick === "push" ? "—" : pick === "over" ? "↑ O" : "↓ U";
  const cls = hit === null ? "warps-pick-neutral"
    : hit ? "warps-pick-hit" : "warps-pick-miss";
  return <span className={cls}>{label}</span>;
}

// ─── Season detail table ──────────────────────────────────────────────────────
function SeasonDetail({ summary, onBack }: { summary: SeasonSummary; onBack: () => void }) {
  const [sortKey, setSortKey] = useState<"team" | "edge" | "actual" | "vegas">("edge");
  const [sortDir, setSortDir] = useState<1 | -1>(-1);

  const sorted = useMemo(() => {
    return [...summary.rows].sort((a, b) => {
      let diff = 0;
      if (sortKey === "team") diff = a.team.localeCompare(b.team);
      else if (sortKey === "vegas") diff = a.vegasLine - b.vegasLine;
      else if (sortKey === "actual") diff = (a.actualWins ?? -1) - (b.actualWins ?? -1);
      else diff = a.warpsEdge - b.warpsEdge;
      return diff * sortDir;
    });
  }, [summary.rows, sortKey, sortDir]);

  function toggleSort(key: typeof sortKey) {
    if (sortKey === key) setSortDir(d => d === 1 ? -1 : 1);
    else { setSortKey(key); setSortDir(-1); }
  }

  const SortTh = ({ k, children }: { k: typeof sortKey; children: React.ReactNode }) => (
    <th onClick={() => toggleSort(k)} style={{ cursor: "pointer", userSelect: "none" }}>
      {children}{sortKey === k ? (sortDir === -1 ? " ↓" : " ↑") : ""}
    </th>
  );

  const correctPicks = summary.rows.filter(r => r.warpsHit === true).length;
  const totalPicks = summary.rows.filter(r => r.warpsHit !== null).length;

  return (
    <div className="track-detail">
      <div className="track-detail-header">
        <button className="track-back-btn" onClick={onBack}>← All Seasons</button>
        <div className="track-detail-kpis">
          <span>
            <strong>{summary.overs}</strong> Overs &nbsp;
            <strong>{summary.unders}</strong> Unders &nbsp;
            <strong>{summary.pushes}</strong> Pushes
          </span>
          {summary.vegasMAE > 0 && <span>Vegas MAE <strong>{summary.vegasMAE.toFixed(2)}w</strong></span>}
          {summary.warpsMAE !== null && <span>WARPS MAE <strong>{summary.warpsMAE.toFixed(2)}w</strong></span>}
          {totalPicks > 0 && (
            <span>WARPS picks <strong>{correctPicks}/{totalPicks}</strong> ({(correctPicks/totalPicks*100).toFixed(0)}%)</span>
          )}
        </div>
      </div>

      <div className="track-table-wrap">
        <table className="track-table">
          <thead>
            <tr>
              <SortTh k="team">Team</SortTh>
              <SortTh k="vegas">Vegas O/U</SortTh>
              <SortTh k="actual">Actual W</SortTh>
              <th>Record</th>
              <th>Result</th>
              <SortTh k="edge">WARPS Proj</SortTh>
              <th>WARPS Edge</th>
              <th>Pick / Hit</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(row => {
              const rowCls = row.ouResult === "over" ? "tr-over" : row.ouResult === "under" ? "tr-under" : row.ouResult === "push" ? "tr-push" : "";
              return (
                <tr key={row.team} className={rowCls}>
                  <td className="track-team-cell">
                    <img src={teamLogos[row.team]} alt="" className="track-logo" />
                    <span>{row.team}</span>
                  </td>
                  <td className="track-num">{row.vegasLine}</td>
                  <td className="track-num">{row.actualWins ?? "—"}</td>
                  <td className="track-num" style={{ color: "#64748b", fontSize: 11 }}>
                    {row.actualWins !== null ? `Δ${(row.actualWins - row.vegasLine) > 0 ? "+" : ""}${(row.actualWins - row.vegasLine).toFixed(1)}` : "—"}
                  </td>
                  <td><OUBadge result={row.ouResult} /></td>
                  <td className="track-num">{row.warpsProj.toFixed(1)}</td>
                  <td className="track-num" style={{ color: row.warpsEdge > 0 ? "#16a34a" : row.warpsEdge < 0 ? "#dc2626" : "#94a3b8", fontWeight: 700 }}>
                    {row.warpsEdge > 0 ? "+" : ""}{row.warpsEdge.toFixed(1)}
                  </td>
                  <td><WarpsPick pick={row.warpsPick} hit={row.warpsHit} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── All-seasons summary table ────────────────────────────────────────────────
function AllSeasonsSummary({ summaries, onSelect }: { summaries: SeasonSummary[]; onSelect: (s: number) => void }) {
  const totals = useMemo(() => {
    const complete = summaries.filter(s => s.complete);
    const allRows = complete.flatMap(s => s.rows.filter(r => r.ouResult !== null));
    const pickRows = complete.flatMap(s => s.rows.filter(r => r.warpsHit !== null));
    return {
      seasons: complete.length,
      overs: complete.reduce((n, s) => n + s.overs, 0),
      unders: complete.reduce((n, s) => n + s.unders, 0),
      pushes: complete.reduce((n, s) => n + s.pushes, 0),
      vegasMAE: allRows.length ? allRows.reduce((n, r) => n + Math.abs(r.actualWins! - r.vegasLine), 0) / allRows.length : 0,
      warpsMAE: allRows.length ? allRows.reduce((n, r) => n + Math.abs(r.actualWins! - r.warpsProj), 0) / allRows.length : 0,
      warpsAcc: pickRows.length ? pickRows.filter(r => r.warpsHit).length / pickRows.length : 0,
      warpsPicks: pickRows.length,
    };
  }, [summaries]);

  return (
    <div>
      <div className="track-aggregate-kpis">
        <div className="track-kpi">
          <strong>{totals.seasons}</strong>
          <span>Seasons audited</span>
        </div>
        <div className="track-kpi">
          <strong>{totals.overs}</strong>
          <span>Total overs hit</span>
        </div>
        <div className="track-kpi">
          <strong>{totals.unders}</strong>
          <span>Total unders hit</span>
        </div>
        <div className="track-kpi">
          <strong>{totals.vegasMAE.toFixed(2)}w</strong>
          <span>Vegas avg error</span>
        </div>
        <div className="track-kpi">
          <strong>{totals.warpsMAE.toFixed(2)}w</strong>
          <span>WARPS avg error</span>
        </div>
        <div className="track-kpi highlight">
          <strong>{(totals.warpsAcc * 100).toFixed(0)}%</strong>
          <span>WARPS pick acc ({totals.warpsPicks} picks)</span>
        </div>
      </div>

      <div className="track-table-wrap">
        <table className="track-table">
          <thead>
            <tr>
              <th>Season</th>
              <th>Overs</th>
              <th>Unders</th>
              <th>Pushes</th>
              <th>Over%</th>
              <th>Vegas MAE</th>
              <th>WARPS MAE</th>
              <th>WARPS Pick Acc</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {summaries.map(s => {
              const total = s.overs + s.unders + s.pushes;
              const overPct = total ? (s.overs / total * 100).toFixed(0) : "—";
              const pickAcc = s.warpsPickAcc !== null ? `${(s.warpsPickAcc * 100).toFixed(0)}% (${s.warpsPickCount}pk)` : "—";
              return (
                <tr key={s.season} className={!s.complete ? "tr-future" : ""}>
                  <td><strong>{s.season}</strong>{!s.complete && <span className="track-live-badge">LIVE</span>}</td>
                  <td className="track-num">{s.complete ? s.overs : "—"}</td>
                  <td className="track-num">{s.complete ? s.unders : "—"}</td>
                  <td className="track-num">{s.complete ? s.pushes : "—"}</td>
                  <td className="track-num">{s.complete ? `${overPct}%` : "—"}</td>
                  <td className="track-num">{s.complete ? s.vegasMAE.toFixed(2) : "—"}</td>
                  <td className="track-num">{s.warpsMAE !== null ? s.warpsMAE.toFixed(2) : "—"}</td>
                  <td className="track-num">{s.complete ? pickAcc : "—"}</td>
                  <td>
                    <button className="track-drill-btn" onClick={() => onSelect(s.season)}>
                      {s.complete ? "Details →" : "2026 Slate →"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Main component ────────────────────────────────────────────────────────────
export function TrackRecordView() {
  const [drillSeason, setDrillSeason] = useState<number | null>(null);

  const summaries = useMemo(() => SEASONS.map(buildSeasonSummary), []);

  const current = drillSeason !== null ? summaries.find(s => s.season === drillSeason) : null;

  return (
    <div className="track-wrapper">
      <div className="track-header">
        <div>
          <h2 className="track-title">Track Record — WARPS vs Vegas O/U (2015–2026)</h2>
          <p className="track-subtitle">
            Preseason Vegas win totals vs final regular-season standings.
            WARPS projections (v1.8, {"λ"}=0.15) shown alongside for model accountability.
            Click any season for the full team-by-team breakdown.
          </p>
        </div>
        {drillSeason !== null && (
          <button className="track-back-btn" onClick={() => setDrillSeason(null)}>← All Seasons</button>
        )}
      </div>

      {current
        ? <SeasonDetail summary={current} onBack={() => setDrillSeason(null)} />
        : <AllSeasonsSummary summaries={summaries} onSelect={setDrillSeason} />
      }
    </div>
  );
}
