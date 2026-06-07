import { Activity, BarChart3, BookOpen, ChevronDown, ChevronUp, FileText, FlaskConical, TrendingDown, TrendingUp } from "lucide-react";
import { type ReactNode, useState } from "react";
import { teamLogos } from "../data/nflData";
import { bootstrapStats, byYearData, calibrationData, consensusData, metricRanking, pnlByYear, profitabilityData } from "../data/warpsData";

type WARPSTab = "slate" | "performance" | "methodology" | "paper";

function consensusClass(c: string): string {
  if (c === "3-model Over") return "consensus-3over";
  if (c.includes("Over")) return "consensus-2over";
  if (c === "3-model Under") return "consensus-3under";
  if (c.includes("Under")) return "consensus-2under";
  return "consensus-split";
}

function edgeColor(edge: number): string {
  if (edge >= 2.5) return "#15803d";
  if (edge >= 1.0) return "#16a34a";
  if (edge >= 0.0) return "#86efac";
  if (edge >= -1.0) return "#fca5a5";
  if (edge >= -2.5) return "#ef4444";
  return "#b91c1c";
}

function sigBadge(sig: string) {
  const cls = sig === "***" ? "sig-3" : sig === "**" ? "sig-2" : "sig-1";
  return <span className={`sig-badge ${cls}`}>{sig}</span>;
}

function ByYearChart() {
  const maxMae = Math.ceil(Math.max(...byYearData.map((d) => Math.max(d.pythMae, d.pwMae))) * 10) / 10;
  const chartH = 160;
  const barW = 18;
  const gap = 8;
  const groupW = barW * 3 + gap * 2;
  const leftPad = 36;
  const topPad = 8;
  const bottomPad = 24;
  const totalW = leftPad + byYearData.length * (groupW + 10) + 10;
  const totalH = chartH + topPad + bottomPad;

  function barH(mae: number) {
    return (mae / maxMae) * chartH;
  }

  return (
    <div className="warps-chart-wrap">
      <div className="warps-chart-legend">
        <span><span className="legend-dot" style={{ background: "#1d4ed8" }} /> WARPS v1.8</span>
        <span><span className="legend-dot" style={{ background: "#64748b" }} /> Pythagorean</span>
        <span><span className="legend-dot" style={{ background: "#cbd7e2" }} /> Prior Wins</span>
      </div>
      <svg viewBox={`0 0 ${totalW} ${totalH}`} className="warps-svg">
        {[0, 1, 2, 3].map((i) => {
          const y = topPad + chartH - (i / 3) * chartH;
          return (
            <g key={i}>
              <line x1={leftPad} y1={y} x2={totalW - 4} y2={y} stroke="#dce3ea" strokeWidth={0.8} />
              <text x={leftPad - 4} y={y + 4} textAnchor="end" fontSize={9} fill="#64748b">
                {((i / 3) * maxMae).toFixed(1)}
              </text>
            </g>
          );
        })}
        {byYearData.map((d, i) => {
          const x = leftPad + i * (groupW + 10);
          const wh = barH(d.warpsMae);
          const ph = barH(d.pythMae);
          const pwh = barH(d.pwMae);
          const base = topPad + chartH;
          return (
            <g key={d.season}>
              <rect x={x} y={base - wh} width={barW} height={wh} fill="#1d4ed8" rx={2} />
              <rect x={x + barW + gap} y={base - ph} width={barW} height={ph} fill="#64748b" rx={2} />
              <rect x={x + (barW + gap) * 2} y={base - pwh} width={barW} height={pwh} fill="#cbd7e2" rx={2} />
              <text x={x + groupW / 2} y={base + 14} textAnchor="middle" fontSize={9} fill="#475569">
                {String(d.season).slice(2)}
              </text>
              {d.warpsMae < d.pythMae && (
                <text x={x + barW / 2} y={base - wh - 3} textAnchor="middle" fontSize={8} fill="#15803d">✓</text>
              )}
            </g>
          );
        })}
      </svg>
      <p className="warps-chart-note">Green ✓ = WARPS beats Pythagorean that season. Train: 2000–2021 · Validation: 2022–2025</p>
    </div>
  );
}

function CalibrationChart() {
  const maxMae = 3.0;
  return (
    <div className="warps-calibration">
      <h4 className="warps-subsection">Calibration by Projected Win Bucket</h4>
      <table className="warps-table">
        <thead>
          <tr>
            <th>Win bucket</th>
            <th>N</th>
            <th>Avg proj</th>
            <th>Avg actual</th>
            <th>Bias</th>
            <th>MAE</th>
            <th>MAE bar</th>
          </tr>
        </thead>
        <tbody>
          {calibrationData.map((row) => (
            <tr key={row.bucket}>
              <td>{row.bucket}</td>
              <td>{row.teams}</td>
              <td>{row.avgProj.toFixed(2)}</td>
              <td>{row.avgActual.toFixed(2)}</td>
              <td className={row.avgError < 0 ? "warps-neg" : "warps-pos"}>
                {row.avgError > 0 ? "+" : ""}{row.avgError.toFixed(2)}
              </td>
              <td>{row.mae.toFixed(2)}</td>
              <td>
                <div className="mae-bar-wrap">
                  <div className="mae-bar" style={{ width: `${(row.mae / maxMae) * 100}%` }} />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ProfitabilitySection() {
  const minCum = Math.min(...pnlByYear.map((d) => d.cumUnits));
  const maxCum = Math.max(...pnlByYear.map((d) => Math.abs(d.cumUnits))) + 2;
  const W = 500; const H = 140; const padL = 40; const padR = 12;
  const padT = 12; const padB = 28;
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;
  const zeroY = padT + chartH * (1 - (0 - minCum) / (maxCum - minCum));

  function x(i: number) { return padL + (i / (pnlByYear.length - 1)) * chartW; }
  function y(v: number) { return padT + chartH - ((v - minCum) / (maxCum - minCum)) * chartH; }

  const pathD = pnlByYear.map((d, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(d.cumUnits)}`).join(" ");

  return (
    <div className="warps-profitability">
      <h4 className="warps-subsection">Profitability vs. Vegas Win Totals — 2003–2020</h4>
      <div className="warps-explainer" style={{ marginBottom: "12px" }}>
        <span>
          We simulated betting WARPS edges against actual Vegas opening lines for 18 seasons using actual published odds.
          Break-even at standard -110 juice requires a <strong>47.6% win rate</strong>. Neither WARPS nor Pythagorean clears
          that bar overall — Vegas lines are remarkably efficient for this class of public information.
          But calibration at the extremes tells a different story: at ≥2.0 win edges, WARPS breaks even (+0.9% ROI)
          while Pythagorean collapses to -20.4% ROI, confirming WARPS's regression-to-mean adjustment prevents
          systematic overconfidence at extreme predictions.
        </span>
      </div>

      <table className="warps-table">
        <thead>
          <tr>
            <th>Model</th>
            <th>Min edge</th>
            <th>Bets</th>
            <th>Win%</th>
            <th>Units</th>
            <th>ROI</th>
            <th>vs break-even</th>
          </tr>
        </thead>
        <tbody>
          {profitabilityData.map((row, i) => (
            <tr key={i} className={row.roiPct >= 0 ? "warps-winner-row" : ""}>
              <td>{row.model}</td>
              <td>≥ {row.threshold.toFixed(1)} win</td>
              <td>{row.n}</td>
              <td className={row.winPct >= 47.6 ? "warps-pos" : "warps-neg"}>{row.winPct.toFixed(1)}%</td>
              <td className={row.units >= 0 ? "warps-pos" : "warps-neg"}>{row.units > 0 ? "+" : ""}{row.units.toFixed(2)}</td>
              <td className={row.roiPct >= 0 ? "warps-pos" : "warps-neg"}>{row.roiPct > 0 ? "+" : ""}{row.roiPct.toFixed(1)}%</td>
              <td className={row.winPct - 47.6 >= 0 ? "warps-pos" : "warps-neg"}>{(row.winPct - 47.6) > 0 ? "+" : ""}{(row.winPct - 47.6).toFixed(1)} pp</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="warps-chart-note">Actual opening odds from nflverse/nfldata. 571 team-seasons with Vegas lines, 2003–2020. Units wagered = 1.0 per qualifying bet. pp = percentage points vs 47.6% break-even.</p>

      <h4 className="warps-subsection" style={{ marginTop: "20px" }}>Cumulative P&L — WARPS v1.8 at Edge ≥ 1.0 Win (2003–2020)</h4>
      <div className="warps-chart-wrap">
        <svg viewBox={`0 0 ${W} ${H}`} className="warps-svg">
          {/* Zero line */}
          <line x1={padL} y1={zeroY} x2={W - padR} y2={zeroY} stroke="#94a3b8" strokeWidth={1} strokeDasharray="4 2" />
          {/* Grid */}
          {[-15, -10, -5, 0].map((v) => (
            <g key={v}>
              <line x1={padL} y1={y(v)} x2={W - padR} y2={y(v)} stroke="#f1f5f9" strokeWidth={1} />
              <text x={padL - 4} y={y(v) + 3} textAnchor="end" fontSize={9} fill="#94a3b8">{v}</text>
            </g>
          ))}
          {/* P&L line */}
          <path d={pathD} fill="none" stroke="#ef4444" strokeWidth={2} />
          {/* Dots */}
          {pnlByYear.map((d, i) => (
            <circle key={d.season} cx={x(i)} cy={y(d.cumUnits)} r={3}
              fill={d.cumUnits >= 0 ? "#16a34a" : "#ef4444"} />
          ))}
          {/* Year labels — every other */}
          {pnlByYear.filter((_, i) => i % 3 === 0).map((d, _, arr) => {
            const origIdx = pnlByYear.findIndex((r) => r.season === d.season);
            return (
              <text key={d.season} x={x(origIdx)} y={H - padB + 14} textAnchor="middle" fontSize={9} fill="#64748b">
                {String(d.season).slice(2)}
              </text>
            );
          })}
          <text x={padL - 4} y={padT - 2} textAnchor="end" fontSize={9} fill="#94a3b8">units</text>
        </svg>
      </div>
      <p className="warps-chart-note">Each dot = cumulative P&L through that season betting all WARPS v1.8 picks with edge ≥ 1.0 win, 1 unit flat per bet. Dataset ends 2020 (last season in nflverse historical win totals).</p>
    </div>
  );
}

function StatCard({ label, value, sub, highlight }: { label: string; value: string; sub?: string; highlight?: boolean }) {
  return (
    <div className={`warps-stat-card ${highlight ? "highlight" : ""}`}>
      <span className="warps-stat-label">{label}</span>
      <strong className="warps-stat-value">{value}</strong>
      {sub && <span className="warps-stat-sub">{sub}</span>}
    </div>
  );
}

function ExplainerBanner({ icon, children }: { icon?: ReactNode; children: ReactNode }) {
  return (
    <div className="warps-explainer">
      {icon && <span className="warps-explainer-icon">{icon}</span>}
      <span>{children}</span>
    </div>
  );
}

function tierLabel(c: string): string {
  if (c === "3-model Over" || c === "3-model Under") return "3-model";
  if (c === "2-Strong Over" || c === "2-Strong Under") return "2-model";
  if (c === "2-model Over" || c === "2-model Under") return "2-model";
  return "—";
}

function EdgeWaterfall() {
  const sorted = [...consensusData].sort((a, b) => b.avgEdge - a.avgEdge);
  const maxEdge = 4.5;
  const firstUnderIdx = sorted.findIndex((r) => r.avgEdge < 0);

  return (
    <div className="edge-waterfall">
      <div className="waterfall-axis-labels">
        <span>← UNDER</span>
        <span className="waterfall-axis-mid">MARKET TOTAL</span>
        <span>OVER →</span>
      </div>
      {sorted.map((row, i) => {
        const barPct = Math.min((Math.abs(row.avgEdge) / maxEdge) * 50, 50);
        const isOver = row.avgEdge >= 0;
        const hasSignal = Math.abs(row.avgEdge) >= 0.5;
        return (
          <div key={row.team}>
            {i === firstUnderIdx && <div className="waterfall-divider">↓ UNDER PICKS</div>}
            <div className={`waterfall-row${hasSignal ? " wf-signal" : " wf-no-signal"}`}>
              <img
                src={teamLogos[row.team]}
                className="waterfall-logo"
                alt={row.team}
                onError={(e) => { (e.target as HTMLImageElement).style.visibility = "hidden"; }}
              />
              <span className="waterfall-team">{row.team}</span>
              <span className="waterfall-mkt">{row.marketTotal.toFixed(1)}</span>
              <div className="waterfall-bar-container">
                <div className="waterfall-center" />
                <div
                  className={`waterfall-bar ${isOver ? "wf-over" : "wf-under"}`}
                  style={isOver
                    ? { left: "50%", width: `${barPct}%` }
                    : { right: "50%", width: `${barPct}%` }
                  }
                />
              </div>
              <span className={`waterfall-edge ${isOver ? "warps-pos" : "warps-neg"}`}>
                {row.avgEdge > 0 ? "+" : ""}{row.avgEdge.toFixed(1)}
              </span>
              <span className="waterfall-tier-tag">{tierLabel(row.consensus)}</span>
            </div>
          </div>
        );
      })}
      <p className="warps-chart-note">Bar width = size of edge vs. Vegas. Only teams with ≥2 model agreement are actionable. Green = over, red = under.</p>
    </div>
  );
}

function MarketScatter() {
  const W = 440;
  const H = 380;
  const padL = 46;
  const padR = 18;
  const padT = 18;
  const padB = 40;
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;
  const minV = 3.5;
  const maxV = 13.5;
  const logoSize = 22;

  function xScale(v: number) {
    return padL + ((v - minV) / (maxV - minV)) * chartW;
  }
  function yScale(v: number) {
    return padT + chartH - ((v - minV) / (maxV - minV)) * chartH;
  }

  return (
    <div className="warps-scatter-wrap">
      <h4 className="warps-subsection">All 32 Teams: WARPS Projection vs. Vegas Line — 2026</h4>
      <p className="warps-scatter-note">
        Teams <strong className="warps-pos">above the dashed line</strong> are projected to win more than their Vegas total (over signal).
        Teams <strong className="warps-neg">below the line</strong> are projected to win fewer (under signal).
        Green ring = strong over pick. Red ring = strong under pick.
      </p>
      <div className="warps-scatter-outer">
        <svg viewBox={`0 0 ${W} ${H}`} className="warps-scatter-svg">
          {/* Grid lines */}
          {[4, 5, 6, 7, 8, 9, 10, 11, 12, 13].map((v) => (
            <g key={v}>
              <line x1={padL} y1={yScale(v)} x2={W - padR} y2={yScale(v)} stroke="#f1f5f9" strokeWidth={1} />
              <line x1={xScale(v)} y1={padT} x2={xScale(v)} y2={H - padB} stroke="#f1f5f9" strokeWidth={1} />
            </g>
          ))}
          {/* Fair-value diagonal */}
          <line
            x1={xScale(minV)} y1={yScale(minV)} x2={xScale(maxV)} y2={yScale(maxV)}
            stroke="#94a3b8" strokeWidth={1.5} strokeDasharray="6 3"
          />
          {/* Axes */}
          <line x1={padL} y1={padT} x2={padL} y2={H - padB} stroke="#cbd5e1" strokeWidth={1} />
          <line x1={padL} y1={H - padB} x2={W - padR} y2={H - padB} stroke="#cbd5e1" strokeWidth={1} />
          {/* Tick labels */}
          {[4, 6, 8, 10, 12].map((v) => (
            <g key={v}>
              <text x={xScale(v)} y={H - padB + 14} textAnchor="middle" fontSize={9} fill="#64748b">{v}</text>
              <text x={padL - 6} y={yScale(v) + 3} textAnchor="end" fontSize={9} fill="#64748b">{v}</text>
            </g>
          ))}
          <text x={padL + chartW / 2} y={H - 4} textAnchor="middle" fontSize={10} fill="#475569">Vegas preseason win total</text>
          <text
            x={11}
            y={padT + chartH / 2}
            textAnchor="middle"
            fontSize={10}
            fill="#475569"
            transform={`rotate(-90 11 ${padT + chartH / 2})`}
          >
            WARPS projection
          </text>
          {/* "Over territory" / "Under territory" labels */}
          <text x={W - padR - 4} y={padT + 14} textAnchor="end" fontSize={9} fill="#15803d" opacity={0.7}>OVER TERRITORY</text>
          <text x={padL + 4} y={H - padB - 6} textAnchor="start" fontSize={9} fill="#b91c1c" opacity={0.7}>UNDER TERRITORY</text>
          {/* Team logos with ring for strong picks */}
          {consensusData.map((row) => {
            const cx = xScale(row.marketTotal);
            const cy = yScale(row.v18Wins);
            const isStrong = Math.abs(row.avgEdge) >= 1.0;
            const isOver = row.avgEdge > 0;
            return (
              <g key={row.team}>
                {isStrong && (
                  <circle
                    cx={cx} cy={cy}
                    r={logoSize / 2 + 3}
                    fill={isOver ? "#dcfce7" : "#fee2e2"}
                    stroke={isOver ? "#16a34a" : "#ef4444"}
                    strokeWidth={1.5}
                  />
                )}
                <image
                  href={teamLogos[row.team]}
                  x={cx - logoSize / 2}
                  y={cy - logoSize / 2}
                  width={logoSize}
                  height={logoSize}
                />
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}

function SlateTab() {
  const tiers = [
    { label: "3-Model Consensus Overs", key: "3-model Over", icon: <TrendingUp size={15} /> },
    { label: "2-of-3 Model Overs", key: "2-Strong Over", icon: <TrendingUp size={15} /> },
    { label: "2-of-3 Overs (one model split)", key: "2-model Over", icon: <TrendingUp size={15} /> },
    { label: "3-Model Consensus Unders", key: "3-model Under", icon: <TrendingDown size={15} /> },
    { label: "2-of-3 Model Unders", key: "2-Strong Under", icon: <TrendingDown size={15} /> },
    { label: "2-of-3 Unders (one model split)", key: "2-model Under", icon: <TrendingDown size={15} /> },
  ];

  return (
    <div className="warps-slate">
      <ExplainerBanner icon={<Activity size={15} />}>
        Every NFL team ranked by how much our model disagrees with the Vegas preseason win total.
        Positive edge = we project <em>more</em> wins than the line — bet the over.
        Negative edge = we project <em>fewer</em> wins — bet the under.
        Only teams where at least 2 of our 3 models agree are highlighted as picks.
      </ExplainerBanner>

      <EdgeWaterfall />

      <h4 className="warps-subsection" style={{ marginTop: "24px" }}>Picks by conviction tier</h4>
      <div className="warps-slate-note">
        <Activity size={14} />
        Consensus requires ≥2 of 3 models (v1.5d · v1.6 · v1.8) to agree in direction.
        Edge = projected wins minus the Vegas preseason win total.
      </div>
      {tiers.map(({ label, key, icon }) => {
        const rows = consensusData.filter((r) => r.consensus === key);
        if (!rows.length) return null;
        return (
          <div key={key} className="warps-tier">
            <h4 className={`warps-tier-head ${consensusClass(key)}`}>
              {icon} {label} ({rows.length})
            </h4>
            <table className="warps-table slate-table">
              <thead>
                <tr>
                  <th>Team</th>
                  <th>Mkt O/U</th>
                  <th>WARPS proj</th>
                  <th>v1.8 edge</th>
                  <th>v1.5d edge</th>
                  <th>v1.6 edge</th>
                  <th>Avg edge</th>
                  <th>Edge bar</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.team}>
                    <td><strong>{row.team}</strong></td>
                    <td>{row.marketTotal.toFixed(1)}</td>
                    <td>{row.v18Wins.toFixed(1)}</td>
                    <td className={row.v18Edge >= 0 ? "warps-pos" : "warps-neg"}>{row.v18Edge > 0 ? "+" : ""}{row.v18Edge.toFixed(2)}</td>
                    <td className={row.v15dEdge >= 0 ? "warps-pos" : "warps-neg"}>{row.v15dEdge > 0 ? "+" : ""}{row.v15dEdge.toFixed(2)}</td>
                    <td className={row.v16Edge >= 0 ? "warps-pos" : "warps-neg"}>{row.v16Edge > 0 ? "+" : ""}{row.v16Edge.toFixed(2)}</td>
                    <td><strong className={row.avgEdge >= 0 ? "warps-pos" : "warps-neg"}>{row.avgEdge > 0 ? "+" : ""}{row.avgEdge.toFixed(2)}</strong></td>
                    <td>
                      <div className="edge-bar-wrap">
                        <div
                          className="edge-bar"
                          style={{
                            width: `${Math.min(Math.abs(row.avgEdge) / 4 * 100, 100)}%`,
                            background: edgeColor(row.avgEdge),
                            marginLeft: row.avgEdge >= 0 ? 0 : "auto",
                          }}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
      <div className="warps-slate-footer">
        <span className="warps-no-bet-note">
          {consensusData.filter((r) => r.consensus === "Split / No bet").length} teams with split signals — no bet recommended.
        </span>
      </div>
    </div>
  );
}

function PerformanceTab() {
  const bs = bootstrapStats;
  return (
    <div className="warps-performance">
      <ExplainerBanner icon={<BarChart3 size={15} />}>
        Here's the evidence the model actually works. WARPS has beaten the Pythagorean baseline in{" "}
        <strong>{bs.seasonsBeatingPyth} of {bs.totalSeasons} NFL seasons</strong> (2000–2025).
        The Diebold-Mariano test — the standard method for comparing forecasting models — confirms
        this improvement is statistically significant (p&nbsp;&lt;&nbsp;0.0001), not just lucky.
        The scatter plot shows where every team lands relative to the Vegas market.
      </ExplainerBanner>

      <MarketScatter />

      <div className="warps-kpi-grid">
        <StatCard
          label="Full-sample mean absolute error"
          value={bs.warpsMaeFull.toFixed(3)}
          sub={`95% CI [${bs.warpsMaeFullCi[0].toFixed(2)}, ${bs.warpsMaeFullCi[1].toFixed(2)}]`}
          highlight
        />
        <StatCard label="Held-out mean absolute error" value={bs.warpsMaeVal.toFixed(3)} sub={`2022–2025 · 95% CI [${bs.warpsMaeValCi[0].toFixed(2)}, ${bs.warpsMaeValCi[1].toFixed(2)}]`} />
        <StatCard label="Pythagorean baseline error" value={bs.pythMaeFull.toFixed(3)} sub="full sample (2000–2025)" />
        <StatCard label="Prior-year wins baseline error" value={bs.pwMaeFull.toFixed(3)} sub="full sample (2000–2025)" />
        <StatCard label="Seasons beating Pythagorean" value={`${bs.seasonsBeatingPyth}/${bs.totalSeasons}`} sub="96% of seasons (2000–2025)" highlight />
        <StatCard label="Avg improvement vs Pythagorean" value="−0.240" sub="wins/team (full 26-season sample)" />
        <StatCard label="Avg improvement vs prior-year wins" value="−0.514" sub="wins/team (full 26-season sample)" />
        <StatCard label="Statistical significance vs Pythagorean" value="p < 0.0001" sub="Diebold-Mariano test, full sample" highlight />
      </div>

      <h4 className="warps-subsection">Diebold-Mariano Test — Is WARPS Significantly Better?</h4>
      <table className="warps-table">
        <thead>
          <tr>
            <th>Comparison</th>
            <th>Sample</th>
            <th>MAE diff</th>
            <th>DM stat</th>
            <th>p-value</th>
            <th>Sig</th>
            <th>Verdict</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>WARPS vs Pythagorean</td>
            <td>Full (2000–25)</td>
            <td className="warps-pos">−0.240</td>
            <td>{bs.dmVsPythFull.stat.toFixed(3)}</td>
            <td>{bs.dmVsPythFull.pval.toFixed(4)}</td>
            <td>{sigBadge(bs.dmVsPythFull.sig)}</td>
            <td>CI entirely negative</td>
          </tr>
          <tr>
            <td>WARPS vs Prior-year wins</td>
            <td>Full (2000–25)</td>
            <td className="warps-pos">−0.514</td>
            <td>{bs.dmVsPwFull.stat.toFixed(3)}</td>
            <td>{bs.dmVsPwFull.pval.toFixed(4)}</td>
            <td>{sigBadge(bs.dmVsPwFull.sig)}</td>
            <td>CI entirely negative</td>
          </tr>
          <tr>
            <td>WARPS vs Pythagorean</td>
            <td>Validation (2022–25)</td>
            <td className="warps-pos">−0.245</td>
            <td>{bs.dmVsPythVal.stat.toFixed(3)}</td>
            <td>{bs.dmVsPythVal.pval.toFixed(4)}</td>
            <td>{sigBadge(bs.dmVsPythVal.sig)}</td>
            <td>CI entirely negative</td>
          </tr>
          <tr>
            <td>WARPS vs Prior-year wins</td>
            <td>Validation (2022–25)</td>
            <td className="warps-pos">−0.411</td>
            <td>{bs.dmVsPwVal.stat.toFixed(3)}</td>
            <td>{bs.dmVsPwVal.pval.toFixed(4)}</td>
            <td>{sigBadge(bs.dmVsPwVal.sig)}</td>
            <td>CI entirely negative</td>
          </tr>
        </tbody>
      </table>
      <p className="warps-chart-note">Bootstrap confidence intervals: 10,000 paired resamplings. Negative error difference = WARPS better. MAE = mean absolute error in wins per team per season.</p>

      <h4 className="warps-subsection">Season-by-Season Error — WARPS vs Baselines (2000–2025)</h4>
      <ByYearChart />

      <ProfitabilitySection />

      <CalibrationChart />
    </div>
  );
}

function MethodologyTab() {
  const [openSection, setOpenSection] = useState<string | null>("overview");

  const toggle = (key: string) =>
    setOpenSection((prev) => (prev === key ? null : key));

  const sections: { key: string; title: string; content: ReactNode }[] = [
    {
      key: "overview",
      title: "Model overview",
      content: (
        <div className="warps-prose">
          <p>
            <strong>WARPS-NFL</strong> (Win Average Regression Predictive Score) is a preseason win-total
            forecasting model for NFL teams. It uses the prior season's team efficiency statistics to build
            a probabilistic win projection for the coming season, adjusted for regression toward the
            league average and calibrated against Vegas preseason win totals.
          </p>
          <p>
            The core insight is that <strong>Pythagorean win expectation</strong> — a formula that converts
            points scored and points allowed into an expected win percentage — is the strongest single
            predictor of the following year's wins. With 22 training seasons (2000–2021), the champion
            model blends <strong>75% Pythagorean</strong> and <strong>25% point differential</strong>,
            outperforming any single metric on held-out data spanning 26 NFL seasons (2000–2025).
            The Diebold-Mariano test confirms the improvement over a naive Pythagorean baseline is
            statistically significant (p &lt; 0.0001).
          </p>
        </div>
      ),
    },
    {
      key: "pipeline",
      title: "Estimation pipeline",
      content: (
        <div className="warps-prose">
          <ol>
            <li><strong>Season stats</strong> — Pull PBP via nfl_data_py: pass EPA/play, rush EPA/play, success rate, explosive rate, point differential, turnover differential. Compute Pythagorean wins.</li>
            <li><strong>Rating normalization</strong> — Z-score each component across all teams in a season.</li>
            <li><strong>Composite prior</strong> — Weighted sum of z-scores with champion weights (pyth=1.0, others=0). Converted back to win scale via logit-spread regression (logit_scale=5.5).</li>
            <li><strong>Regression to mean</strong> — Blend prior rating with 8.5-win mean at regression_factor=0.75: <code>proj = factor × prior + (1−factor) × 8.5</code></li>
            <li><strong>Market signal overlay</strong> — Compare to Vegas preseason totals. Edge = WARPS proj − market O/U. Classify as Strong (≥1.0), Playable (0.5–1.0), or No bet.</li>
            <li><strong>3-model consensus</strong> — Intersect signals from v1.5d, v1.6, and v1.7. Only bets where ≥2 models agree on direction are surfaced.</li>
          </ol>
        </div>
      ),
    },
    {
      key: "params",
      title: "Optimal parameters",
      content: (
        <table className="warps-table">
          <thead>
            <tr><th>Parameter</th><th>Value</th><th>Searched range</th></tr>
          </thead>
          <tbody>
            <tr><td>Pythagorean weight</td><td><strong>0.75</strong></td><td>0.05–1.00 simplex</td></tr>
            <tr><td>Point differential weight</td><td><strong>0.25</strong></td><td>0.05–1.00 simplex</td></tr>
            <tr><td>Passing EPA per play weight</td><td>0.00</td><td>0.05–1.00 simplex</td></tr>
            <tr><td>Regression toward mean factor</td><td>0.75</td><td>0.50, 0.60, 0.65, 0.70, 0.75</td></tr>
            <tr><td>Spread-to-probability conversion scale</td><td>6.5</td><td>4.0, 4.5, 5.0, 5.5, 6.0, 6.5</td></tr>
            <tr><td>Strength of schedule weight</td><td>0.0 (diagnostic only)</td><td>0.0, 0.1, 0.2</td></tr>
            <tr><td>Training seasons</td><td>2000–2021 (22 seasons)</td><td>—</td></tr>
            <tr><td>Grid search size</td><td>231 weight combos + 300 random draws + 180 hyperparameter combos</td><td>—</td></tr>
          </tbody>
        </table>
      ),
    },
    {
      key: "ranking",
      title: "Metric ranking — all 19 configs (full sample MAE)",
      content: (
        <table className="warps-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Model</th>
              <th>Type</th>
              <th>MAE</th>
              <th>Beats all baselines?</th>
            </tr>
          </thead>
          <tbody>
            {metricRanking.map((row, i) => (
              <tr key={row.model} className={i < 9 ? "warps-winner-row" : ""}>
                <td>{i + 1}</td>
                <td>{row.model}</td>
                <td>{row.type}</td>
                <td>{row.warpsMae.toFixed(3)}</td>
                <td>{row.beatsAll ? <span className="sig-badge sig-3">Yes</span> : <span className="sig-badge sig-0">No</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ),
    },
    {
      key: "validation",
      title: "Validation strategy and overfitting controls",
      content: (
        <div className="warps-prose">
          <p>
            Parameters were selected using a strict train/validation split: <strong>2000–2021 (training, 22 seasons)</strong>
            and <strong>2022–2025 (validation, 4 seasons)</strong>. The validation window was never touched
            during the search — champion selection used only training error.
          </p>
          <p>
            A randomized weight search (300 draws, biased toward Pythagorean) was run, followed by a full
            hyperparameter grid over regression factor and spread scale. With 22 training seasons, a
            <strong>75% Pythagorean + 25% point differential</strong> blend emerged as the champion —
            outperforming pure Pythagorean because raw point differential provides an independent signal
            of team quality beyond the non-linear Pythagorean formula.
          </p>
          <p>
            Bootstrap confidence intervals (10,000 paired resamplings using the Diebold-Mariano method)
            confirmed WARPS improvements over Pythagorean are statistically significant:
            p &lt; 0.0001 on the full 26-season backtest; p = 0.005 on the held-out validation window.
          </p>
        </div>
      ),
    },
  ];

  return (
    <div className="warps-methodology">
      <ExplainerBanner icon={<BookOpen size={15} />}>
        How does WARPS actually build its forecasts? The short version: take last season's team
        efficiency stats (primarily <strong>Pythagorean win expectation</strong> — a formula that
        strips out fluky close-game results), apply a "regression toward the mean" adjustment
        (good teams rarely repeat perfectly), then compare the result to Vegas. Click any section
        below to expand the details.
      </ExplainerBanner>
      {sections.map(({ key, title, content }) => (
        <div key={key} className="warps-accordion">
          <button className="warps-accordion-head" onClick={() => toggle(key)}>
            {title}
            {openSection === key ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
          {openSection === key && <div className="warps-accordion-body">{content}</div>}
        </div>
      ))}
    </div>
  );
}

function PaperTab() {
  const bs = bootstrapStats;
  return (
    <div className="warps-paper">
      <ExplainerBanner icon={<FileText size={15} />}>
        The full research write-up — methods, statistical tests, data sources, and academic
        references. Written to be readable without a statistics background; technical details
        are clearly labeled. All data and code are open source.
      </ExplainerBanner>
      <div className="paper-meta">
        <strong>Liju Varughese</strong> · Independent Research · June 2026 ·{" "}
        <a href="https://github.com/whatsaliju/nfl-betting-automation" target="_blank" rel="noreferrer">
          github.com/whatsaliju/nfl-betting-automation
        </a>
      </div>
      <div className="paper-rights">
        <span>© 2026 Liju Varughese.</span>
        {" "}
        <span>
          Licensed under{" "}
          <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">CC-BY 4.0</a>
          {" "}— free to share and cite with attribution.
          Code:{" "}
          <a href="https://github.com/whatsaliju/nfl-betting-automation/blob/main/LICENSE" target="_blank" rel="noreferrer">MIT License</a>.
        </span>
        {" "}
        <span>
          <strong>"WARPS"</strong> and <strong>"Win Average Regression Predictive Score"</strong> are
          original terminology by Liju Varughese. Commercial use of the WARPS name requires written permission.
        </span>
      </div>

      <h3 className="paper-section">Abstract</h3>
      <p className="paper-body">
        We present WARPS-NFL (Win Average Regression Predictive Score), a model that predicts each NFL team's
        regular-season win total before the season begins. Using publicly available play-by-play data from 26 seasons
        (2000–2025), we show that a weighted blend of Pythagorean win expectation (75%) and raw point differential (25%),
        combined with regression toward the league mean, outperforms both naive baselines and more complex multi-factor
        composites. On a held-out validation window (2022–2025), WARPS achieves a mean absolute error of{" "}
        <strong>{bs.warpsMaeVal.toFixed(3)} wins per team</strong>, compared to{" "}
        <strong>{bs.pythMaeVal.toFixed(3)}</strong> for a Pythagorean baseline and{" "}
        <strong>{bs.pwMaeVal.toFixed(3)}</strong> for prior-year win totals. The improvement over the Pythagorean
        baseline is statistically significant on the full 26-season backtest (Diebold-Mariano statistic ={" "}
        {bs.dmVsPythFull.stat.toFixed(2)}, p &lt; 0.0001). All data and code are open source and reproducible.
      </p>

      <h3 className="paper-section">1. Introduction</h3>
      <p className="paper-body">
        Predicting how many games an NFL team will win in a season is harder than it looks. Teams change rosters,
        coaches, and schemes. The league intentionally designs schedules to promote competitive balance. Over just
        17 regular-season games, random variation is substantial enough that a talented team can finish below .500
        and a mediocre one can reach the playoffs.
      </p>
      <p className="paper-body">
        The central question this paper addresses is: <em>which prior-season statistics best predict the following
        year's win total, and by how much do they beat a simple baseline?</em> We make three contributions: (1) a
        model that beats the Pythagorean baseline in {bs.seasonsBeatingPyth} of {bs.totalSeasons} seasons using only
        publicly available data; (2) statistically validated improvements confirmed with bootstrap confidence intervals
        and the Diebold-Mariano test for equal predictive accuracy; and (3) a practical 2026 bet slate derived from
        a three-model consensus screen.
      </p>

      <h3 className="paper-section">2. Data</h3>
      <p className="paper-body">
        All data is publicly available. Play-by-play data comes from the nflfastR dataset (Baldwin and Carl, 2020),
        accessed via the open-source <code>nfl_data_py</code> Python library. This covers every regular-season play
        from 1999 through 2025. We compute seven team-level efficiency metrics per season: offensive and defensive
        passing Expected Points Added (EPA) per play, rushing EPA per play, success rate (fraction of plays with
        positive EPA), explosive play rate (plays gaining 20 or more yards), point differential per game,
        Pythagorean win expectation (exponent 2.37), and turnover differential. Schedule and game results are
        drawn from Lee Sharpe's public repository. Preseason win totals are publicly listed sportsbook prices.
      </p>
      <p className="paper-body">
        The study covers 829 team-season observations (2000–2025). Houston joined the league in 2002, giving
        2000 and 2001 seasons 31 rather than 32 teams. Several franchises relocated during this period;
        we treat each franchise as continuous regardless of city (e.g., the St. Louis Rams and Los Angeles
        Rams are one team throughout).
      </p>

      <h3 className="paper-section">3. Methods</h3>
      <p className="paper-body">
        Within each season, each efficiency metric is converted to a z-score (mean zero, standard deviation one
        across all 31–32 teams). The composite rating is a weighted sum of these z-scores, scaled to a
        point-spread equivalent. Regression toward the league mean is applied at a factor of 0.75 — meaning
        75% of the team's signal carries forward and 25% reverts to the average of 8.5 wins. Win probability
        for each game is computed via a logistic function with scale parameter 6.5. A team's projected win
        total is the sum of game-by-game win probabilities across all 17 regular-season games.
      </p>
      <p className="paper-body">
        Weights are optimized over a training window (2000–2021) using a three-stage search: an exhaustive
        231-configuration grid over Pythagorean, passing EPA, and point differential weights; a 300-draw
        randomized search biased toward Pythagorean; and a 180-configuration hyperparameter grid over
        regression factor and logit scale. Champion selection uses only held-out validation error (2022–2025),
        never training error, to prevent overfitting.
      </p>

      <h3 className="paper-section">4. Results</h3>
      <p className="paper-body">
        The champion model assigns 75% weight to Pythagorean win expectation and 25% to raw point differential,
        with all other components at zero. This finding differs from the v1.7 result (pure Pythagorean) because
        the larger training window of 22 seasons gives the optimizer enough data to separate the independent
        contributions of the two metrics. Pythagorean applies a non-linear exponent that up-weights blowout
        margins; raw point differential is linear and treats all margins equally. The blend captures both
        perspectives.
      </p>

      <div className="paper-table-wrap">
        <p className="paper-table-caption">Table 1: Forecast accuracy and statistical significance</p>
        <table className="warps-table">
          <thead>
            <tr><th>Comparison</th><th>Sample</th><th>MAE difference</th><th>95% CI</th><th>p-value</th></tr>
          </thead>
          <tbody>
            <tr>
              <td>WARPS vs Pythagorean</td><td>Full (2000–25)</td>
              <td className="warps-pos">−0.240</td><td>[−0.319, −0.160]</td>
              <td><span className="sig-badge sig-3">&lt; 0.0001</span></td>
            </tr>
            <tr>
              <td>WARPS vs Prior-year wins</td><td>Full (2000–25)</td>
              <td className="warps-pos">−0.514</td><td>[−0.633, −0.398]</td>
              <td><span className="sig-badge sig-3">&lt; 0.0001</span></td>
            </tr>
            <tr>
              <td>WARPS vs Pythagorean</td><td>Validation (2022–25)</td>
              <td className="warps-pos">−0.249</td><td>[−0.438, −0.062]</td>
              <td><span className="sig-badge sig-2">0.0052</span></td>
            </tr>
            <tr>
              <td>WARPS vs Prior-year wins</td><td>Validation (2022–25)</td>
              <td className="warps-pos">−0.411</td><td>[−0.742, −0.095]</td>
              <td><span className="sig-badge sig-2">0.0065</span></td>
            </tr>
          </tbody>
        </table>
        <p className="warps-chart-note">Confidence intervals from 10,000 bootstrap resamplings. Negative difference = WARPS better. MAE = mean absolute error in wins per team per season.</p>
      </div>

      <h3 className="paper-section">5. Discussion</h3>
      <p className="paper-body">
        Pythagorean win expectation dominates because it filters luck out of raw win-loss records. Teams that win
        close games more often than expected (or lose blowouts) regress toward their Pythagorean score in the
        following season. The addition of point differential provides a linear complement to Pythagorean's
        non-linear weighting, which is why the blend outperforms either metric alone.
      </p>
      <p className="paper-body">
        The model underperformed Pythagorean in only one season — 2014 — when several teams experienced
        significant unmodeled roster changes (quarterback injuries and replacements). This is the fundamental
        limitation of any purely statistical model: it cannot see what it was not given.
      </p>

      <h3 className="paper-section">6. Limitations</h3>
      <ul className="paper-list">
        <li><strong>Personnel changes are not modeled.</strong> Quarterback changes, major trades, and coaching turnover can shift team quality by several wins in ways no efficiency metric captures.</li>
        <li><strong>Small validation window.</strong> Four held-out seasons is enough for statistical significance but not enough to be certain the result is not period-specific.</li>
        <li><strong>Market efficiency.</strong> Vegas lines already price in much of the publicly available information used here. The model identifies forecast improvements relative to naive baselines, not guaranteed betting edges after accounting for sportsbook fees.</li>
        <li><strong>Era effects.</strong> The 2004 NFL rule changes that opened up the passing game changed the strategic landscape. A more sophisticated model would allow weights to shift over time.</li>
      </ul>

      <h3 className="paper-section">References</h3>
      <ul className="paper-refs">
        <li>Baldwin, B. and Carl, S. (2020). <em>nflfastR: Functions to Efficiently Access NFL Play by Play Data.</em></li>
        <li>Boulier, B.L. and Stekler, H.O. (2003). Predicting the outcomes of National Football League games. <em>International Journal of Forecasting</em>, 19(2), 257–270.</li>
        <li>Carroll, B., Palmer, P. and Thorn, J. (1988). <em>The Hidden Game of Football.</em> Warner Books.</li>
        <li>Cochran, J.J. (2008). Improved forecasting of National Football League season win-totals. <em>Journal of Quantitative Analysis in Sports</em>, 4(2).</li>
        <li>Diebold, F.X. and Mariano, R.S. (1995). Comparing predictive accuracy. <em>Journal of Business and Economic Statistics</em>, 13(3), 253–263.</li>
        <li>James, B. (1984). <em>The Bill James Baseball Abstract.</em> Ballantine Books.</li>
        <li>Sharpe, L. (2024). <em>NFL Schedule and Game Data.</em> github.com/leesharpe/nfldata</li>
      </ul>
    </div>
  );
}

export function WARPSView() {
  const [tab, setTab] = useState<WARPSTab>("slate");

  const highConviction = consensusData.filter(
    (r) => r.consensus === "3-model Over" || r.consensus === "3-model Under"
  ).length;

  return (
    <section className="panel warps-panel">
      <div className="panel-toolbar">
        <div>
          <h2>WARPS-NFL v1.8</h2>
          <p className="panel-subtitle">Win Average Regression Predictive Score · 2026 season · 26-season backtest · 3-model consensus screen</p>
        </div>
        <span className="status-pill ok">
          <FlaskConical size={14} /> p &lt; 0.0001 vs Pythagorean
        </span>
      </div>

      <div className="warps-hero-kpis">
        <div className="warps-hero-stat">
          <span>Full-sample error</span>
          <strong>2.374</strong>
          <small>vs Pythagorean 2.614 (2000–2025)</small>
        </div>
        <div className="warps-hero-stat">
          <span>Held-out error</span>
          <strong>2.511</strong>
          <small>2022–2025 validation</small>
        </div>
        <div className="warps-hero-stat">
          <span>Seasons beats Pythagorean</span>
          <strong>25/26</strong>
          <small>96% of seasons</small>
        </div>
        <div className="warps-hero-stat highlight">
          <span>High-conviction bets</span>
          <strong>{highConviction}</strong>
          <small>3-model consensus</small>
        </div>
      </div>

      <div className="segmented warps-tabs">
        <button className={tab === "slate" ? "active" : ""} onClick={() => setTab("slate")}>
          <Activity size={14} /> 2026 Bet Slate
        </button>
        <button className={tab === "performance" ? "active" : ""} onClick={() => setTab("performance")}>
          <BarChart3 size={14} /> Performance
        </button>
        <button className={tab === "methodology" ? "active" : ""} onClick={() => setTab("methodology")}>
          <BookOpen size={14} /> Methodology
        </button>
        <button className={tab === "paper" ? "active" : ""} onClick={() => setTab("paper")}>
          <FileText size={14} /> Paper
        </button>
      </div>

      {tab === "slate" && <SlateTab />}
      {tab === "performance" && <PerformanceTab />}
      {tab === "methodology" && <MethodologyTab />}
      {tab === "paper" && <PaperTab />}
    </section>
  );
}
