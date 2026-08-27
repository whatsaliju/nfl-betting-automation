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
  if (!result) return null;
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

// ─── Season chart ─────────────────────────────────────────────────────────────
function SeasonChart({ summaries }: { summaries: SeasonSummary[] }) {
  const complete = summaries.filter(s => s.complete && s.warpsPickAcc !== null).reverse();
  if (complete.length < 2) return null;
  const barW = 30, barGap = 6, chartH = 90, labelH = 20, padL = 28, padTop = 16;
  const totalW = complete.length * (barW + barGap) - barGap;
  const svgW = totalW + padL + 8;
  const svgH = chartH + labelH + padTop;

  return (
    <div className="track-chart-wrap">
      <div className="track-chart-label">WARPS Pick Accuracy by Season</div>
      <div className="track-chart-scroll">
        <svg width={svgW} height={svgH} className="track-chart-svg">
          {/* Y-axis grid lines at 40%, 50%, 60% */}
          {[40, 50, 60].map(pct => {
            const y = padTop + chartH * (1 - pct / 100);
            return (
              <g key={pct}>
                <line x1={padL} y1={y} x2={svgW - 8} y2={y} stroke="#e2e8f0" strokeDasharray={pct === 50 ? "4 2" : "2 4"} />
                <text x={padL - 4} y={y + 4} textAnchor="end" fontSize={9} fill="#94a3b8">{pct}%</text>
              </g>
            );
          })}
          {complete.map((s, i) => {
            const acc = s.warpsPickAcc!;
            const barH = Math.max(2, acc * chartH);
            const x = padL + i * (barW + barGap);
            const y = padTop + chartH - barH;
            const color = acc >= 0.57 ? "#16a34a" : acc >= 0.5 ? "#3b82f6" : "#dc2626";
            return (
              <g key={s.season}>
                <rect x={x} y={y} width={barW} height={barH} rx={4} fill={color} opacity={0.82} />
                <text x={x + barW / 2} y={y - 3} textAnchor="middle" fontSize={9} fill={color} fontWeight="700">
                  {(acc * 100).toFixed(0)}%
                </text>
                <text x={x + barW / 2} y={svgH - 2} textAnchor="middle" fontSize={9} fill="#64748b">
                  {s.season}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
      <div className="track-chart-mae">
        <div className="track-chart-label">Vegas vs WARPS MAE by Season</div>
        <div className="track-chart-scroll">
          <svg width={svgW} height={svgH} className="track-chart-svg">
            {(() => {
              const maxMAE = Math.max(...complete.map(s => Math.max(s.vegasMAE, s.warpsMAE ?? 0)));
              const scale = maxMAE > 0 ? chartH / (maxMAE * 1.15) : 1;
              return (
                <>
                  {[1, 2, 3].filter(v => v <= maxMAE * 1.2).map(v => {
                    const y = padTop + chartH - v * scale;
                    return (
                      <g key={v}>
                        <line x1={padL} y1={y} x2={svgW - 8} y2={y} stroke="#e2e8f0" strokeDasharray="2 4" />
                        <text x={padL - 4} y={y + 4} textAnchor="end" fontSize={9} fill="#94a3b8">{v}w</text>
                      </g>
                    );
                  })}
                  {complete.map((s, i) => {
                    const x = padL + i * (barW + barGap);
                    const hV = s.vegasMAE * scale;
                    const hW = (s.warpsMAE ?? 0) * scale;
                    return (
                      <g key={s.season}>
                        <rect x={x} y={padTop + chartH - hV} width={barW / 2 - 1} height={hV} rx={3} fill="#94a3b8" opacity={0.75} />
                        {s.warpsMAE !== null && (
                          <rect x={x + barW / 2} y={padTop + chartH - hW} width={barW / 2 - 1} height={hW} rx={3} fill="#3b82f6" opacity={0.8} />
                        )}
                        <text x={x + barW / 2} y={svgH - 2} textAnchor="middle" fontSize={9} fill="#64748b">
                          {s.season}
                        </text>
                      </g>
                    );
                  })}
                </>
              );
            })()}
          </svg>
        </div>
        <div className="track-chart-legend">
          <span><span className="legend-dot" style={{ background: "#94a3b8" }} />Vegas</span>
          <span><span className="legend-dot" style={{ background: "#3b82f6" }} />WARPS</span>
        </div>
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
          <span>Seasons on record</span>
        </div>
        <div className="track-kpi">
          {(() => {
            const total = totals.overs + totals.unders + totals.pushes;
            return <>
              <strong>{total > 0 ? `${(totals.overs / total * 100).toFixed(0)}%` : "—"}</strong>
              <span>Hit over · {totals.overs}/{total}</span>
            </>;
          })()}
        </div>
        <div className="track-kpi">
          <strong>{totals.vegasMAE.toFixed(2)}w</strong>
          <span>Vegas avg miss</span>
        </div>
        <div className="track-kpi">
          <strong>{totals.warpsMAE.toFixed(2)}w</strong>
          <span>WARPS avg miss</span>
        </div>
        <div className="track-kpi highlight">
          <strong>{(totals.warpsAcc * 100).toFixed(0)}%</strong>
          <span>WARPS O/U accuracy · {totals.warpsPicks} picks</span>
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
          <h2 className="track-title">The Public Record — 11 Seasons of WARPS vs Vegas</h2>
          <p className="track-subtitle">
            Every year Vegas sets win total lines for all 32 teams. WARPS makes independent calls.
            This is the 11-year public record of both — no cherry-picks, no retroactive edits.
            Click any season for the full team-by-team breakdown.
          </p>
        </div>
        {drillSeason !== null && (
          <button className="track-back-btn" onClick={() => setDrillSeason(null)}>← All Seasons</button>
        )}
      </div>

      {current
        ? <SeasonDetail summary={current} onBack={() => setDrillSeason(null)} />
        : (
          <>
            <SeasonChart summaries={summaries} />
            <AllSeasonsSummary summaries={summaries} onSelect={setDrillSeason} />
          </>
        )
      }
    </div>
  );
}
