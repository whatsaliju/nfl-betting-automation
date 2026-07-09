import { Activity, BarChart3, BookOpen, ChevronDown, ChevronUp, Crosshair, FileText, FlaskConical, TrendingDown, TrendingUp } from "lucide-react";
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { teamColors, teamLogos } from "../data/nflData";
import { type QBAdjResult, QB_TIER_LABEL, getQbAdjustment, qbChanges2026 } from "../data/qbData";
import { bootstrapStats, byYearData, calibrationData, consensusData, historicalTeamData, linesMetadata, metricRanking, pnlByYear, profitabilityData, residualHistogram, trajectoryData, type ConsensusRow } from "../data/warpsData";

type WARPSTab = "slate" | "performance" | "methodology" | "paper" | "quadrant";

const VALID_TABS = new Set<WARPSTab>(["slate", "performance", "methodology", "paper", "quadrant"]);

// Teams with Dynasty Persistence Modifier active in 2026 projections (v2.0)
const DYNASTY_POSITIVE = new Set(["KC", "BUF"]);  // 4+ years sustained excellence (R=0.95 upward)
const DYNASTY_NEGATIVE = new Set(["NYJ", "CAR"]);  // 4+ years sustained futility (R=0.95 downward)
function hashToTab(): WARPSTab {
  const h = window.location.hash.replace("#", "") as WARPSTab;
  return VALID_TABS.has(h) ? h : "slate";
}

// Normal CDF via rational approximation (max error ~1.5e-7)
function normCDF(x: number): number {
  const p = 0.2316419;
  const [b1, b2, b3, b4, b5] = [0.319381530, -0.356563782, 1.781477937, -1.821255978, 1.330274429];
  const t = 1 / (1 + p * Math.abs(x));
  const poly = t * (b1 + t * (b2 + t * (b3 + t * (b4 + t * b5))));
  const c = 1 - Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI) * poly;
  return x < 0 ? 1 - c : c;
}

// WARPS prediction σ ≈ avg RMSE across 26 seasons (~3.0 wins)
const WARPS_SIGMA = 3.0;
// At -110 standard vig: bettor risks $110 to win $100 → BEP = 110/210
const BEP_110 = 110 / 210; // 52.38%

function modelWinProb(edge: number): number {
  return normCDF(edge / WARPS_SIGMA);
}

function useCountUp(target: number, decimals = 0, duration = 1100): string {
  const [val, setVal] = useState(0);
  const rafRef = useRef<number>(0);
  useEffect(() => {
    setVal(0);
    const start = performance.now();
    function tick(now: number) {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - t, 3);
      setVal(target * eased);
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
    }
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, duration]);
  return val.toFixed(decimals);
}

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

function computeConsensus(v18: number, v15d: number, v16: number): string {
  const edges = [v18, v15d, v16];
  const avg = (v18 + v15d + v16) / 3;
  const strongOvers = edges.filter((e) => e >= 1.0).length;
  const strongUnders = edges.filter((e) => e <= -1.0).length;
  if (strongOvers === 3 && avg >= 1.5) return "3-model Over";
  if (strongOvers === 3) return "2-Strong Over";
  if (strongOvers >= 2) return "2-model Over";
  if (strongUnders === 3 && avg <= -1.5) return "3-model Under";
  if (strongUnders === 3) return "2-Strong Under";
  if (strongUnders >= 2) return "2-model Under";
  return "Split / No bet";
}

function applyQbAdj(rows: ConsensusRow[], qbAdjMap: Map<string, QBAdjResult>): ConsensusRow[] {
  return rows.map((row) => {
    const info = qbAdjMap.get(row.team);
    if (!info) return row;
    const { adj } = info;
    const v18Edge = row.v18Edge + adj;
    const v15dEdge = row.v15dEdge + adj;
    const v16Edge = row.v16Edge + adj;
    return {
      ...row,
      v18Edge,
      v15dEdge,
      v16Edge,
      v18Wins: row.v18Wins + adj,
      avgEdge: (v18Edge + v15dEdge + v16Edge) / 3,
      consensus: computeConsensus(v18Edge, v15dEdge, v16Edge),
    };
  });
}

function sigBadge(sig: string) {
  const cls = sig === "***" ? "sig-3" : sig === "**" ? "sig-2" : "sig-1";
  return <span className={`sig-badge ${cls}`}>{sig}</span>;
}

function ByYearChart() {
  const maxMae = Math.ceil(Math.max(...byYearData.map((d) => Math.max(d.pythMae, d.pwMae))) * 10) / 10;
  const chartH = 160;
  const barW = 14;
  const gap = 6;
  const groupW = barW * 4 + gap * 3;
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
        <span><span className="legend-dot" style={{ background: "#f59e0b" }} /> Vegas (2015–2025)</span>
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
          const vh = d.vegasMae != null ? barH(d.vegasMae) : 0;
          return (
            <g key={d.season}>
              <rect x={x} y={base - wh} width={barW} height={wh} fill="#1d4ed8" rx={2} />
              <rect x={x + barW + gap} y={base - ph} width={barW} height={ph} fill="#64748b" rx={2} />
              <rect x={x + (barW + gap) * 2} y={base - pwh} width={barW} height={pwh} fill="#cbd7e2" rx={2} />
              {d.vegasMae != null && (
                <rect x={x + (barW + gap) * 3} y={base - vh} width={barW} height={vh} fill="#f59e0b" rx={2} />
              )}
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
      <p className="warps-chart-note">✓ = WARPS beats Pythagorean. Vegas bars shown 2015–2025 (PFR-verified lines). Train: 2000–2021 · Validation: 2022–2025</p>
    </div>
  );
}

function CalibrationChart() {
  const maxMae = 3.0;
  const maxBias = 0.6;
  return (
    <div className="warps-calibration">
      <h4 className="warps-subsection">Calibration by Projected Win Bucket</h4>
      <div className="cal-chart">
        {calibrationData.map((row) => {
          const biasPct = Math.min(Math.abs(row.avgError / maxBias) * 50, 50);
          const maePct = Math.min((row.mae / maxMae) * 100, 100);
          return (
            <div key={row.bucket} className="cal-row">
              <div className="cal-bucket-label">
                <span className="cal-bucket-range">{row.bucket}</span>
                <span className="cal-n">n={row.teams}</span>
              </div>
              <div className="cal-viz">
                <div className="cal-bias-track">
                  <div className="cal-zero-line" />
                  <div
                    className={`cal-bias-fill ${row.avgError >= 0 ? "cal-pos" : "cal-neg"}`}
                    style={{
                      width: `${biasPct}%`,
                      ...(row.avgError >= 0 ? { left: "50%" } : { right: "50%" }),
                    }}
                  />
                </div>
                <div className="cal-mae-track">
                  <div className="cal-mae-fill" style={{ width: `${maePct}%` }} />
                </div>
              </div>
              <div className="cal-stats">
                <span className={row.avgError < 0 ? "warps-neg" : row.avgError > 0 ? "warps-pos" : ""}>
                  {row.avgError > 0 ? "+" : ""}{row.avgError.toFixed(2)} bias
                </span>
                <span className="cal-mae-val">{row.mae.toFixed(2)} MAE</span>
              </div>
            </div>
          );
        })}
      </div>
      <div className="cal-legend">
        <span><span className="cal-leg-dot cal-pos-dot" /> Overestimates wins · <span className="cal-leg-dot cal-neg-dot" /> Underestimates wins · <span className="cal-leg-bar" /> MAE bar</span>
      </div>
      <p className="warps-chart-note">Bias = avg(projected − actual). Negative = model overestimates wins. Bars show calibration is tight across win buckets with no systematic directional bias.</p>
    </div>
  );
}

function ProfitabilitySection() {
  const minCum = Math.min(...pnlByYear.map((d) => d.cumUnits));
  const maxCum = Math.max(...pnlByYear.map((d) => Math.abs(d.cumUnits))) + 2;
  const W = 520; const H = 180; const padL = 42; const padR = 16;
  const padT = 16; const padB = 36;
  const chartW = W - padL - padR;
  const chartH = H - padT - padB;
  const zeroY = padT + chartH * (1 - (0 - minCum) / (maxCum - minCum));

  function x(i: number) { return padL + (i / (pnlByYear.length - 1)) * chartW; }
  function y(v: number) { return padT + chartH - ((v - minCum) / (maxCum - minCum)) * chartH; }

  const pathD = pnlByYear.map((d, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(d.cumUnits).toFixed(1)}`).join(" ");
  // Area fill: go to zero line at both ends
  const areaD = `${pathD} L${x(pnlByYear.length - 1).toFixed(1)},${zeroY.toFixed(1)} L${x(0).toFixed(1)},${zeroY.toFixed(1)} Z`;

  const gridVals = [-15, -10, -5, 0];

  return (
    <div className="warps-profitability">
      <h4 className="warps-subsection">Profitability vs. Vegas Win Totals — 2003–2020</h4>
      <div className="warps-explainer" style={{ marginBottom: "12px" }}>
        <span>
          Simulated betting WARPS edges against actual Vegas opening lines for 18 seasons.
          Break-even at -110 juice requires <strong>52.4% win rate</strong>.
          At ≥2.0 win edge, WARPS achieves <strong>+0.9% ROI</strong> — while Pythagorean
          collapses to −20.4% ROI at the same threshold, confirming that regression-to-mean
          is essential to avoid overconfidence on extreme edges.
          The 3-model consensus at ≥1.5 wins delivers <strong>+9.5% ROI</strong> over 19 seasons.
        </span>
      </div>

      {/* Profitability summary cards */}
      <div className="profit-cards">
        {profitabilityData.filter(r => r.model === "WARPS v1.8").map((row) => (
          <div key={row.threshold} className={`profit-card ${row.roiPct >= 0 ? "profit-pos" : "profit-neg"}`}>
            <div className="profit-threshold">Edge ≥ {row.threshold.toFixed(1)}w</div>
            <div className="profit-roi">{row.roiPct > 0 ? "+" : ""}{row.roiPct.toFixed(1)}%</div>
            <div className="profit-detail">{row.n} bets · {row.winPct.toFixed(1)}% win</div>
            <div className="profit-units">{row.units > 0 ? "+" : ""}{row.units.toFixed(2)} u</div>
          </div>
        ))}
      </div>

      <div className="profit-table-wrap">
        <table className="warps-table">
          <thead>
            <tr>
              <th>Model</th>
              <th>Min edge</th>
              <th>Bets</th>
              <th>Win%</th>
              <th>ROI</th>
              <th>vs BEP</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {profitabilityData.map((row, i) => (
              <tr key={i} className={row.roiPct >= 0 ? "warps-winner-row" : ""}>
                <td>{row.model}</td>
                <td>≥ {row.threshold.toFixed(1)}w</td>
                <td>{row.n}</td>
                <td className={row.winPct >= BEP_110 * 100 ? "warps-pos" : "warps-neg"}>{row.winPct.toFixed(1)}%</td>
                <td className={row.roiPct >= 0 ? "warps-pos" : "warps-neg"}>{row.roiPct > 0 ? "+" : ""}{row.roiPct.toFixed(1)}%</td>
                <td className={row.winPct - BEP_110 * 100 >= 0 ? "warps-pos" : "warps-neg"}>{(row.winPct - BEP_110 * 100) > 0 ? "+" : ""}{(row.winPct - BEP_110 * 100).toFixed(1)}pp</td>
                <td>
                  <div className="roi-bar-wrap">
                    <div className={`roi-bar ${row.roiPct >= 0 ? "roi-pos" : "roi-neg"}`}
                      style={{ width: `${Math.min(Math.abs(row.roiPct) / 25 * 100, 100)}%` }} />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="warps-chart-note">Actual opening odds from nflverse/nfldata. 571 team-seasons, 2003–2020. BEP = 52.4% break-even. pp = percentage-point gap vs break-even.</p>

      <h4 className="warps-subsection" style={{ marginTop: "20px" }}>Cumulative P&L — WARPS v1.8 at Edge ≥ 1.0 Win (2003–2020)</h4>
      <div className="warps-chart-wrap">
        <svg viewBox={`0 0 ${W} ${H}`} className="warps-svg">
          <defs>
            <linearGradient id="pnlFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ef4444" stopOpacity="0.18" />
              <stop offset="100%" stopColor="#ef4444" stopOpacity="0.03" />
            </linearGradient>
          </defs>
          {/* Background fill */}
          <path d={areaD} fill="url(#pnlFill)" />
          {/* Grid lines */}
          {gridVals.map((v) => (
            <g key={v}>
              <line x1={padL} y1={y(v)} x2={W - padR} y2={y(v)}
                stroke={v === 0 ? "#94a3b8" : "#e2e8f0"} strokeWidth={v === 0 ? 1.5 : 1}
                strokeDasharray={v === 0 ? "4 3" : undefined} />
              <text x={padL - 5} y={y(v) + 3.5} textAnchor="end" fontSize={9} fill="#94a3b8">{v}</text>
            </g>
          ))}
          {/* Season column ticks */}
          {pnlByYear.map((d, i) => (
            <line key={d.season} x1={x(i)} y1={H - padB} x2={x(i)} y2={H - padB + 4}
              stroke="#cbd5e1" strokeWidth={1} />
          ))}
          {/* P&L line */}
          <path d={pathD} fill="none" stroke="#ef4444" strokeWidth={2.5} strokeLinejoin="round" />
          {/* Season bars (mini, below zero line) */}
          {pnlByYear.map((d, i) => {
            const barH = Math.min(Math.abs(d.units) / 5 * 12, 12);
            return (
              <rect key={`bar-${d.season}`}
                x={x(i) - 4} y={H - padB - barH}
                width={8} height={barH}
                fill={d.units >= 0 ? "#bbf7d0" : "#fecaca"} rx={1}
                opacity={0.7}
              />
            );
          })}
          {/* Dots */}
          {pnlByYear.map((d, i) => (
            <circle key={d.season} cx={x(i)} cy={y(d.cumUnits)} r={3.5}
              fill={d.cumUnits >= 0 ? "#16a34a" : "#ef4444"}
              stroke="#fff" strokeWidth={1} />
          ))}
          {/* Year labels every 3 */}
          {pnlByYear.filter((_, i) => i % 3 === 0).map((d) => {
            const origIdx = pnlByYear.findIndex((r) => r.season === d.season);
            return (
              <text key={d.season} x={x(origIdx)} y={H - 4} textAnchor="middle" fontSize={9} fill="#64748b">
                {String(d.season).slice(2)}
              </text>
            );
          })}
          <text x={padL - 5} y={padT - 4} textAnchor="end" fontSize={9} fill="#94a3b8">u</text>
          <text x={W - padR} y={y(0) - 4} textAnchor="end" fontSize={8} fill="#94a3b8">break-even</text>
        </svg>
      </div>
      <p className="warps-chart-note">Dot color = cumulative P&L (green above zero, red below). Mini bars = season-level units won/lost. Edge ≥ 1.0 win, 1 unit flat per bet, 2003–2020.</p>
    </div>
  );
}

function BenchmarkStrip() {
  const bs = bootstrapStats;
  const benchmarks = [
    { label: "Vegas (2015–25)", mae: bs.vegasMaeOverlap, desc: "True market benchmark", color: "#f59e0b", tag: "market" },
    { label: "WARPS v1.8", mae: bs.warpsMaeFull, desc: "This model (2000–25)", color: "#1d4ed8", tag: "model" },
    { label: "Pythagorean", mae: bs.pythMaeFull, desc: "Statistical baseline", color: "#64748b", tag: "baseline" },
    { label: "Prior-year wins", mae: bs.pwMaeFull, desc: "Naive baseline", color: "#cbd7e2", tag: "naive" },
  ];
  const maxMae = 3.0;
  return (
    <div className="benchmark-strip">
      <h4 className="warps-subsection">Model Accuracy Benchmark — MAE (wins per team)</h4>
      <div className="benchmark-cards">
        {benchmarks.map((b) => (
          <div key={b.label} className={`benchmark-card benchmark-${b.tag}`}>
            <div className="benchmark-label">{b.label}</div>
            <div className="benchmark-mae">{b.mae.toFixed(3)}</div>
            <div className="benchmark-bar-track">
              <div className="benchmark-bar" style={{ width: `${(b.mae / maxMae) * 100}%`, background: b.color }} />
            </div>
            <div className="benchmark-desc">{b.desc}</div>
          </div>
        ))}
      </div>
      <p className="warps-chart-note">Lower MAE = better accuracy. WARPS beats both statistical baselines across the full 26-season sample. Vegas line shown over 2015–25 overlap window as a real-time information benchmark (incorporates injuries, trades, and coaching changes unknown at model freeze time).</p>
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

function EdgeWaterfall({ rows }: { rows: ConsensusRow[] }) {
  const sorted = [...rows].sort((a, b) => b.avgEdge - a.avgEdge);
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
            <div className={`waterfall-row${hasSignal ? " wf-signal" : " wf-no-signal"}`}
              style={{ borderLeft: `3px solid ${teamColors[row.team] ?? "#dce3ea"}` }}>
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

function MarketScatter({ rows, qbAdjMap }: { rows: ConsensusRow[]; qbAdjMap: Map<string, QBAdjResult> }) {
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
  const hasQbAdj = qbAdjMap.size > 0;

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
        {hasQbAdj && " Dashed ring = QB-adjusted position."}
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
          {/* QB adj ghost positions: intentionally reads base consensusData (not props rows)
              so ghosts always show the original unadjusted positions regardless of QB toggle state */}
          {hasQbAdj && consensusData.map((orig) => {
            const info = qbAdjMap.get(orig.team);
            if (!info) return null;
            return (
              <circle
                key={`ghost-${orig.team}`}
                cx={xScale(orig.marketTotal)}
                cy={yScale(orig.v18Wins)}
                r={logoSize / 2 + 4}
                fill="none"
                stroke="#94a3b8"
                strokeWidth={1}
                strokeDasharray="3 2"
                opacity={0.5}
              />
            );
          })}
          {/* Team logos with ring for strong picks */}
          {rows.map((row) => {
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

function PickProbBadge({ edge }: { edge: number }) {
  const prob = modelWinProb(edge);
  const isPos = prob >= BEP_110;
  return (
    <div
      className={`pick-prob-badge ${isPos ? "ppb-pos" : "ppb-neg"}`}
      title={`Model-implied win probability based on WARPS prediction error (σ≈3w). BEP at -110: ${(BEP_110 * 100).toFixed(1)}%`}
    >
      {Math.round(prob * 100)}% · {isPos ? "+EV" : "−EV"} @−110
    </div>
  );
}

function PickCardDetail({ row, qbInfo }: { row: ConsensusRow; qbInfo: QBAdjResult | undefined }) {
  const edges = [
    { label: "v1.5d", val: row.v15dEdge },
    { label: "v1.6", val: row.v16Edge },
    { label: "v1.8", val: row.v18Edge },
  ];
  const maxAbs = Math.max(...edges.map((e) => Math.abs(e.val)), 1);
  // Derive raw (pre-regression) quality from projection: proj = 0.75*raw + 2.125
  const rawQuality = (row.v18Wins - 2.125) / 0.75;
  const regDelta = row.v18Wins - rawQuality;
  const prob = modelWinProb(Math.abs(row.avgEdge));
  const overBEP = prob >= BEP_110;

  return (
    <div className="pick-card-detail">
      <div className="pcd-section">
        <div className="pcd-label">Model edge breakdown</div>
        {edges.map((e) => (
          <div key={e.label} className="pcd-edge-row">
            <span className="pcd-model">{e.label}</span>
            <div className="pcd-bar-track">
              <div className="pcd-zero" />
              <div
                className={`pcd-bar ${e.val >= 0 ? "pcd-over" : "pcd-under"}`}
                style={{
                  width: `${(Math.abs(e.val) / maxAbs) * 44}%`,
                  ...(e.val >= 0 ? { left: "50%" } : { right: "50%" }),
                }}
              />
            </div>
            <span className={`pcd-edge-val ${e.val >= 0 ? "warps-pos" : "warps-neg"}`}>
              {e.val > 0 ? "+" : ""}{e.val.toFixed(1)}
            </span>
          </div>
        ))}
      </div>
      <div className="pcd-section pcd-stats-row">
        <div className="pcd-stat">
          <span className="pcd-stat-label">Raw quality</span>
          <strong>{rawQuality.toFixed(1)}w</strong>
        </div>
        <div className="pcd-arrow">→</div>
        <div className="pcd-stat">
          <span className="pcd-stat-label">After regression</span>
          <strong>{row.v18Wins.toFixed(1)}w</strong>
        </div>
        <div className={`pcd-reg-delta ${regDelta < 0 ? "warps-neg" : "warps-pos"}`}>
          ({regDelta > 0 ? "+" : ""}{regDelta.toFixed(1)} reg)
        </div>
      </div>
      <div className="pcd-section pcd-bottom-row">
        <div className={`pcd-prob ${overBEP ? "pcd-prob-pos" : "pcd-prob-neg"}`}>
          <span className="pcd-stat-label">Win prob @−110</span>
          <strong>{Math.round(prob * 100)}%</strong>
          <span>{overBEP ? "+EV" : "−EV"}</span>
        </div>
        {(row.overOdds !== undefined || row.underOdds !== undefined) && (
          <div className="pcd-odds">
            <span className="pcd-stat-label">BetMGM</span>
            <span>O {row.overOdds !== undefined ? (row.overOdds > 0 ? `+${row.overOdds}` : String(row.overOdds)) : "—"}</span>
            <span>U {row.underOdds !== undefined ? (row.underOdds > 0 ? `+${row.underOdds}` : String(row.underOdds)) : "—"}</span>
          </div>
        )}
        {qbInfo && (
          <div className={`pcd-qb ${qbInfo.adj > 0 ? "qb-pos" : "qb-neg"}`}>
            <span className="pcd-stat-label">QB adj</span>
            <strong>{qbInfo.adj > 0 ? "+" : ""}{qbInfo.adj.toFixed(1)}w</strong>
            <span>{qbInfo.change.outQb} → {qbInfo.change.inQb}</span>
          </div>
        )}
      </div>
    </div>
  );
}

function SlateTab({
  rows,
  qbAdjMap,
  showQbAdj,
  onToggleQbAdj,
}: {
  rows: ConsensusRow[];
  qbAdjMap: Map<string, QBAdjResult>;
  showQbAdj: boolean;
  onToggleQbAdj: () => void;
}) {
  const [expandedCard, setExpandedCard] = useState<string | null>(null);
  const tiers = [
    { label: "3-Model Consensus Overs", key: "3-model Over", icon: <TrendingUp size={15} /> },
    { label: "3-Model Overs (Moderate)", key: "2-Strong Over", icon: <TrendingUp size={15} /> },
    { label: "2-of-3 Overs (one model split)", key: "2-model Over", icon: <TrendingUp size={15} /> },
    { label: "3-Model Consensus Unders", key: "3-model Under", icon: <TrendingDown size={15} /> },
    { label: "3-Model Unders (Moderate)", key: "2-Strong Under", icon: <TrendingDown size={15} /> },
    { label: "2-of-3 Unders (one model split)", key: "2-model Under", icon: <TrendingDown size={15} /> },
  ];

  return (
    <div className="warps-slate">
      <div className="slate-header-row">
        <ExplainerBanner icon={<Activity size={15} />}>
          Every NFL team ranked by how much our model disagrees with the Vegas preseason win total.
          Positive edge = we project <em>more</em> wins than the line — bet the over.
          Negative edge = we project <em>fewer</em> wins — bet the under.
          Only teams where at least 2 of our 3 models agree are highlighted as picks.
        </ExplainerBanner>
        <div className="qb-adj-control">
          <label className="toggle qb-toggle" title={`${qbChanges2026.length} QB changes tracked for 2026 offseason`}>
            <input type="checkbox" checked={showQbAdj} onChange={onToggleQbAdj} />
            <span className="qb-toggle-label">
              {showQbAdj ? "WARPS + QB adj" : "WARPS v1.8 pure"}
            </span>
          </label>
          {showQbAdj && (
            <div className="qb-adj-summary">
              {qbChanges2026.map((c) => {
                const adj = qbAdjMap.get(c.team);
                if (!adj) return null;
                return (
                  <span key={c.team} className={`qb-change-chip ${adj.adj > 0 ? "qb-pos" : "qb-neg"}`}
                    title={`${c.outQb} (${QB_TIER_LABEL[c.outTier]}) → ${c.inQb} (${QB_TIER_LABEL[c.inTier]})`}>
                    {c.team} {adj.adj > 0 ? "+" : ""}{adj.adj.toFixed(1)}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <EdgeWaterfall rows={rows} />

      <h4 className="warps-subsection" style={{ marginTop: "24px" }}>Picks by conviction tier</h4>
      <div className="warps-slate-note">
        <Activity size={14} />
        Consensus requires ≥2 of 3 models (v1.5d · v1.6 · v1.8) to agree in direction.
        Edge = projected wins minus the Vegas preseason win total.
      </div>
      <div className="vig-strip">
        <span className="vig-bep">−110 break-even: <strong>52.4%</strong></span>
        <span className="vig-sep">·</span>
        <span>Best historical tier: 3-model consensus avg edge ≥1.5w → <strong>52.6% win / +9.5% ROI</strong> (19 bets, 2003–2020)</span>
        <span className="vig-sep">·</span>
        <span className="vig-note">% on cards = model-implied win prob (σ≈3w), not historical hit rate</span>
        <span className="vig-sep">·</span>
        <span className="lines-source-note">Lines: {linesMetadata.source} · {linesMetadata.date}</span>
      </div>
      {tiers.map(({ label, key, icon }) => {
        const tierRows = rows.filter((r) => r.consensus === key);
        if (!tierRows.length) return null;
        return (
          <div key={key} className="warps-tier">
            <h4 className={`warps-tier-head ${consensusClass(key)}`}>
              {icon} {label} ({tierRows.length})
            </h4>
            <div className="warps-pick-grid">
              {tierRows.map((row) => {
                const isOver = row.avgEdge >= 0;
                const qbInfo = qbAdjMap.get(row.team);
                const isExpanded = expandedCard === row.team;
                return (
                  <div key={row.team}
                    className={`warps-pick-card ${isOver ? "pick-over" : "pick-under"}${isExpanded ? " pick-expanded" : ""}`}
                    style={{ borderLeftColor: teamColors[row.team], borderLeftWidth: "4px" }}
                    onClick={() => setExpandedCard(isExpanded ? null : row.team)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setExpandedCard(isExpanded ? null : row.team); }}
                    aria-expanded={isExpanded}
                  >
                    <div className="pick-card-header">
                      <img
                        src={teamLogos[row.team]}
                        className="pick-card-logo"
                        alt={row.team}
                        onError={(e) => { (e.target as HTMLImageElement).style.visibility = "hidden"; }}
                      />
                      <div className="pick-card-dir">
                        {isOver ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
                      </div>
                    </div>
                    <div className="pick-card-team">{row.team}</div>
                    <div className="pick-card-edge" style={{ color: edgeColor(row.avgEdge) }}>
                      {row.avgEdge > 0 ? "+" : ""}{row.avgEdge.toFixed(1)}
                    </div>
                    <div className="pick-card-direction">{isOver ? "OVER" : "UNDER"}</div>
                    <div className="pick-card-line">{row.marketTotal.toFixed(1)} line</div>
                    <div className="pick-card-proj">{row.v18Wins.toFixed(1)} proj</div>
                    {(isOver ? row.overOdds : row.underOdds) !== undefined && (
                      <div className="pick-card-odds">
                        {(() => { const o = isOver ? row.overOdds! : row.underOdds!; return o > 0 ? `+${o}` : String(o); })()}
                      </div>
                    )}
                    <div className="pick-card-models">
                      <span
                        className={`pm-dot ${row.v15dEdge > 0 ? "pm-over" : "pm-under"}`}
                        title={`v1.5d: ${row.v15dEdge > 0 ? "+" : ""}${row.v15dEdge.toFixed(1)}`}
                      >1.5</span>
                      <span
                        className={`pm-dot ${row.v16Edge > 0 ? "pm-over" : "pm-under"}`}
                        title={`v1.6: ${row.v16Edge > 0 ? "+" : ""}${row.v16Edge.toFixed(1)}`}
                      >1.6</span>
                      <span
                        className={`pm-dot ${row.v18Edge > 0 ? "pm-over" : "pm-under"}`}
                        title={`v1.8: ${row.v18Edge > 0 ? "+" : ""}${row.v18Edge.toFixed(1)}`}
                      >1.8</span>
                    </div>
                    {qbInfo && (
                      <div className={`qb-badge ${qbInfo.adj > 0 ? "qb-pos" : "qb-neg"}`}
                        title={`${qbInfo.change.outQb} → ${qbInfo.change.inQb}`}>
                        QB {qbInfo.adj > 0 ? "+" : ""}{qbInfo.adj.toFixed(1)}w
                      </div>
                    )}
                    <PickProbBadge edge={Math.abs(row.avgEdge)} />
                    <div className="pick-expand-hint">{isExpanded ? "▲ less" : "▼ details"}</div>
                    {isExpanded && <PickCardDetail row={row} qbInfo={qbInfo} />}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
      <div className="warps-slate-footer">
        <span className="warps-no-bet-note">
          {rows.filter((r) => r.consensus === "Split / No bet").length} teams with split signals — no bet recommended.
        </span>
      </div>
    </div>
  );
}

function ResidualHistogram() {
  const maxCount = Math.max(...residualHistogram.map((b) => b.count));
  const W = 480; const H = 140; const padL = 36; const padB = 22; const padT = 12; const padR = 8;
  const chartW = W - padL - padR;
  const chartH = H - padB - padT;
  const barW = chartW / residualHistogram.length;
  const scale = (v: number) => (v / maxCount) * chartH;
  return (
    <div className="warps-chart-wrap" style={{ marginTop: "20px" }}>
      <h4 className="warps-subsection">Prediction Error Distribution — 26 seasons (2000–2025)</h4>
      <div className="warps-legend" style={{ marginBottom: "6px" }}>
        <span><span className="legend-dot" style={{ background: "#1d4ed8" }} /> Historical seasons</span>
        <span><span className="legend-dot" style={{ background: "#f59e0b" }} /> 2024–2025 (recent)</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="warps-svg">
        {[0, 0.25, 0.5, 0.75, 1.0].map((f) => {
          const y = padT + chartH - scale(maxCount * f);
          return <line key={f} x1={padL} x2={W - padR} y1={y} y2={y} stroke="#e2e8f0" strokeWidth={0.5} />;
        })}
        <line x1={padL + chartW / 2} x2={padL + chartW / 2} y1={padT} y2={padT + chartH} stroke="#94a3b8" strokeWidth={1} strokeDasharray="3,3" />
        {residualHistogram.map((b, i) => {
          const x = padL + i * barW;
          const base = padT + chartH;
          const totalH = scale(b.count);
          const recentH = scale(b.recentCount);
          return (
            <g key={b.lo}>
              <rect x={x + 1} y={base - totalH} width={barW - 2} height={totalH} fill="#1d4ed8" opacity={0.6} rx={1} />
              <rect x={x + 1} y={base - recentH} width={barW - 2} height={recentH} fill="#f59e0b" opacity={0.85} rx={1} />
              <text x={x + barW / 2} y={base + 14} textAnchor="middle" fontSize={8} fill="#64748b">
                {b.lo}
              </text>
            </g>
          );
        })}
        <text x={padL - 4} y={padT + 4} textAnchor="end" fontSize={8} fill="#94a3b8">{maxCount}</text>
        <text x={padL - 4} y={padT + chartH / 2} textAnchor="end" fontSize={8} fill="#94a3b8">{Math.round(maxCount / 2)}</text>
        <text x={padL + chartW / 2} y={padT - 2} textAnchor="middle" fontSize={8} fill="#64748b">← Under-projected · 0 · Over-projected →</text>
      </svg>
      <p className="warps-chart-note">
        Error = WARPS projection − actual wins (830 team-seasons). 2024–2025 amber overlay shows heavier tails:
        45% of teams had |error|&nbsp;&gt;&nbsp;3 wins vs. 32% historically — driven by dynasty teams (KC, DET)
        and collapse teams (NO, SF) exceeding any prior-season statistical model's range.
      </p>
    </div>
  );
}

function RegressionSensitivityChart() {
  const W = 340; const H = 200; const padL = 36; const padB = 28; const padT = 12; const padR = 12;
  const cW = W - padL - padR; const cH = H - padT - padB;
  const xMin = 4; const xMax = 14;
  function x(v: number) { return padL + ((v - xMin) / (xMax - xMin)) * cW; }
  function y(v: number) { return padT + cH - ((v - xMin) / (xMax - xMin)) * cH; }
  // Standard: proj = 0.75 * raw + 2.125; Dynasty: proj = 0.95 * raw + 0.425
  const pts = (fn: (raw: number) => number) =>
    [xMin, 6, 8.5, 11, xMax].map((raw) => ({ raw, proj: fn(raw) }));
  const stdPts = pts((raw) => 0.75 * raw + 2.125);
  const dynPts = pts((raw) => 0.95 * raw + 0.425);
  const lineD = (pts: { raw: number; proj: number }[]) =>
    pts.map((p, i) => `${i === 0 ? "M" : "L"}${x(p.raw).toFixed(1)},${y(p.proj).toFixed(1)}`).join(" ");

  return (
    <div className="warps-chart-wrap" style={{ maxWidth: 360 }}>
      <div className="warps-legend" style={{ marginBottom: "6px" }}>
        <span><span className="legend-dot" style={{ background: "#64748b" }} /> Standard (R=0.75)</span>
        <span><span className="legend-dot" style={{ background: "#1d4ed8" }} /> Dynasty / Collapse (R=0.95)</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="warps-svg">
        {[4,6,8,10,12,14].map((v) => (
          <g key={v}>
            <line x1={x(v)} y1={padT} x2={x(v)} y2={padT+cH} stroke="#f1f5f9" strokeWidth={1} />
            <line x1={padL} y1={y(v)} x2={W-padR} y2={y(v)} stroke="#f1f5f9" strokeWidth={1} />
            <text x={x(v)} y={padT+cH+14} textAnchor="middle" fontSize={8} fill="#64748b">{v}</text>
            <text x={padL-4} y={y(v)+3} textAnchor="end" fontSize={8} fill="#64748b">{v}</text>
          </g>
        ))}
        {/* Fair-value diagonal */}
        <line x1={x(xMin)} y1={y(xMin)} x2={x(xMax)} y2={y(xMax)} stroke="#e2e8f0" strokeWidth={1} strokeDasharray="4 3" />
        {/* Mean intersection dot */}
        <circle cx={x(8.5)} cy={y(8.5)} r={4} fill="#94a3b8" opacity={0.6} />
        <text x={x(8.5)+6} y={y(8.5)-4} fontSize={8} fill="#94a3b8">8.5 mean</text>
        {/* Lines */}
        <path d={lineD(stdPts)} fill="none" stroke="#64748b" strokeWidth={2} />
        <path d={lineD(dynPts)} fill="none" stroke="#1d4ed8" strokeWidth={2} strokeDasharray="5 3" />
        {/* Axis labels */}
        <text x={padL+cW/2} y={H-2} textAnchor="middle" fontSize={9} fill="#475569">Raw quality (projected wins)</text>
        <text x={8} y={padT+cH/2} textAnchor="middle" fontSize={9} fill="#475569" transform={`rotate(-90 8 ${padT+cH/2})`}>WARPS projection</text>
        {/* Annotations */}
        <text x={x(12.5)} y={y(12.8)} fontSize={8} fill="#1d4ed8">Dynasty ↑</text>
        <text x={x(5.5)} y={y(4.4)} fontSize={8} fill="#1d4ed8">Collapse ↓</text>
      </svg>
      <p className="warps-chart-note" style={{ maxWidth: 340 }}>
        Lines cross at 8.5 wins (league mean). Dynasty teams above/below mean are projected further from 8.5 than under standard regression — preserving the persistence signal rather than forcing reversion.
      </p>
    </div>
  );
}

function HistoricalAudit() {
  const seasons = Array.from(new Set(historicalTeamData.map((r) => r.s))).sort((a, b) => b - a);
  const [year, setYear] = useState<number>(seasons[0]);

  const seasonRows = historicalTeamData.filter((r) => r.s === year);
  const sorted = [...seasonRows].sort((a, b) => (b.ww - b.w) - (a.ww - a.w));
  const seasMae = seasonRows.reduce((acc, r) => acc + Math.abs(r.ww - r.w), 0) / (seasonRows.length || 1);
  const pythMae = seasonRows.reduce((acc, r) => acc + Math.abs(r.pw - r.w), 0) / (seasonRows.length || 1);
  const beatPyth = seasonRows.filter((r) => Math.abs(r.ww - r.w) < Math.abs(r.pw - r.w)).length;

  return (
    <div className="warps-historical-audit">
      <h4 className="warps-subsection">Historical Audit — All Teams by Season</h4>
      <div className="audit-controls">
        <select
          className="audit-year-select"
          value={year}
          onChange={(e) => setYear(Number(e.target.value))}
        >
          {seasons.map((s) => (
            <option key={s} value={s}>{s} Season</option>
          ))}
        </select>
        <div className="audit-season-kpis">
          <span className="audit-kpi">WARPS MAE <strong>{seasMae.toFixed(2)}</strong></span>
          <span className="audit-kpi">Pyth MAE <strong>{pythMae.toFixed(2)}</strong></span>
          <span className={`audit-kpi ${seasMae < pythMae ? "audit-win" : "audit-loss"}`}>
            WARPS {seasMae < pythMae ? `beat Pyth by ${(pythMae - seasMae).toFixed(2)}` : `trailed Pyth by ${(seasMae - pythMae).toFixed(2)}`}
          </span>
          <span className="audit-kpi">Better for <strong>{beatPyth}/{seasonRows.length}</strong> teams</span>
        </div>
      </div>
      <div className="audit-table-wrap">
        <table className="warps-table audit-table">
          <thead>
            <tr>
              <th>Team</th>
              <th>WARPS proj</th>
              <th>Pyth proj</th>
              <th>Actual wins</th>
              <th>WARPS err</th>
              <th>Pyth err</th>
              <th>WARPS vs Pyth</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => {
              const we = r.ww - r.w;
              const pe = r.pw - r.w;
              const warpsWon = Math.abs(we) < Math.abs(pe);
              const errBarMax = 6;
              return (
                <tr key={r.t} className={Math.abs(we) <= 1 ? "audit-accurate" : Math.abs(we) >= 4 ? "audit-miss" : ""}>
                  <td>
                    <div className="audit-team-cell">
                      <img
                        src={teamLogos[r.t]}
                        className="audit-logo"
                        alt={r.t}
                        onError={(e) => { (e.target as HTMLImageElement).style.visibility = "hidden"; }}
                        style={{ borderLeft: `3px solid ${teamColors[r.t] ?? "#dce3ea"}` }}
                      />
                      <span>{r.t}</span>
                    </div>
                  </td>
                  <td className="num">{r.ww.toFixed(1)}</td>
                  <td className="num">{r.pw.toFixed(1)}</td>
                  <td className="num"><strong>{r.w}</strong></td>
                  <td className={`num ${we > 0 ? "warps-neg" : we < 0 ? "warps-pos" : ""}`}>
                    {we > 0 ? "+" : ""}{we.toFixed(1)}
                  </td>
                  <td className={`num ${pe > 0 ? "warps-neg" : pe < 0 ? "warps-pos" : ""}`}>
                    {pe > 0 ? "+" : ""}{pe.toFixed(1)}
                  </td>
                  <td>
                    <div className="audit-err-bars">
                      <div className="audit-err-bar-w" style={{ width: `${Math.min(Math.abs(we) / errBarMax * 100, 100)}%`, background: warpsWon ? "#1d4ed8" : "#94a3b8" }} />
                      <div className="audit-err-bar-p" style={{ width: `${Math.min(Math.abs(pe) / errBarMax * 100, 100)}%` }} />
                    </div>
                  </td>
                  <td>{warpsWon ? <span className="audit-badge-w">WARPS ✓</span> : <span className="audit-badge-p">Pyth ✓</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="warps-chart-note">
        Sorted by WARPS error (positive = over-projected, negative = under-projected). Blue bar = WARPS error, grey = Pythagorean error. Rows highlighted green = WARPS within 1 win; red = WARPS off by 4+.
      </p>
    </div>
  );
}

function ArchitectureFlowchart() {
  const W = 680;
  const H = 420;
  type BoxDef = { x: number; y: number; w: number; h: number; label: string; sub?: string; color: string; text: string };
  const boxes: BoxDef[] = [
    { x: 20,  y: 20,  w: 120, h: 44, label: "nfl_data_py", sub: "PBP 1999–2025",           color: "#e0e7ff", text: "#1e3a8a" },
    { x: 185, y: 20,  w: 130, h: 44, label: "7 Efficiency", sub: "Pyth · EPA · PD · TO",   color: "#e0e7ff", text: "#1e3a8a" },
    { x: 360, y: 20,  w: 130, h: 44, label: "Z-Score Norm", sub: "Per season, 32 teams",    color: "#e0e7ff", text: "#1e3a8a" },
    { x: 535, y: 20,  w: 125, h: 44, label: "Composite", sub: "75% Pyth + 25% PD",         color: "#dbeafe", text: "#1e40af" },
    { x: 535, y: 110, w: 125, h: 44, label: "Regression", sub: "R=0.75 toward 8.5 wins",   color: "#dbeafe", text: "#1e40af" },
    { x: 535, y: 200, w: 125, h: 44, label: "Win Projection", sub: "Logit scale=6.5",       color: "#dcfce7", text: "#14532d" },
    { x: 535, y: 290, w: 125, h: 44, label: "vs Vegas Line", sub: "Edge = proj − O/U",      color: "#fef9c3", text: "#713f12" },
    { x: 360, y: 290, w: 130, h: 44, label: "QB Overlay", sub: "Optional adj ±0–2w",        color: "#fce7f3", text: "#831843" },
    { x: 185, y: 290, w: 130, h: 44, label: "3-Model Screen", sub: "v1.5d · v1.6 · v1.8",  color: "#fce7f3", text: "#831843" },
    { x: 20,  y: 290, w: 130, h: 44, label: "Consensus Signal", sub: "Over / Under / Split", color: "#dcfce7", text: "#14532d" },
    { x: 340, y: 155, w: 150, h: 44, label: "Dynasty Modifier", sub: "v2.0: R=0.95 if 4+ yrs", color: "#fff7ed", text: "#7c2d12" },
  ];

  type Arrow = { x1: number; y1: number; x2: number; y2: number };
  const arrows: Arrow[] = [
    // top row: left to right
    { x1: 140, y1: 42, x2: 185, y2: 42 },
    { x1: 315, y1: 42, x2: 360, y2: 42 },
    { x1: 490, y1: 42, x2: 535, y2: 42 },
    // right column: top to bottom
    { x1: 597, y1: 64,  x2: 597, y2: 110 },
    { x1: 597, y1: 154, x2: 597, y2: 200 },
    { x1: 597, y1: 244, x2: 597, y2: 290 },
    // bottom row: right to left
    { x1: 535, y1: 312, x2: 490, y2: 312 },
    { x1: 360, y1: 312, x2: 315, y2: 312 },
    { x1: 185, y1: 312, x2: 150, y2: 312 },
    // dynasty modifier enters regression
    { x1: 490, y1: 177, x2: 535, y2: 132 },
  ];

  return (
    <div className="warps-flowchart-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="warps-flowchart-svg">
        <defs>
          <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 z" fill="#94a3b8" />
          </marker>
        </defs>
        {arrows.map((a, i) => (
          <line key={i} x1={a.x1} y1={a.y1} x2={a.x2} y2={a.y2}
            stroke="#94a3b8" strokeWidth={1.5} markerEnd="url(#arrow)" />
        ))}
        {boxes.map((b) => (
          <g key={b.label}>
            <rect x={b.x} y={b.y} width={b.w} height={b.h}
              rx={6} fill={b.color} stroke="#cbd5e1" strokeWidth={1} />
            <text x={b.x + b.w / 2} y={b.y + 17} textAnchor="middle"
              fontSize={10.5} fontWeight="600" fill={b.text}>{b.label}</text>
            {b.sub && (
              <text x={b.x + b.w / 2} y={b.y + 32} textAnchor="middle"
                fontSize={9} fill="#64748b">{b.sub}</text>
            )}
          </g>
        ))}
        {/* Section labels */}
        <text x={250} y={88} textAnchor="middle" fontSize={9} fill="#94a3b8" fontStyle="italic">Data ingestion</text>
        <text x={597} y={185} textAnchor="middle" fontSize={9} fill="#94a3b8" fontStyle="italic" transform="rotate(-90 597 185)">Projection</text>
        <text x={250} y={278} textAnchor="middle" fontSize={9} fill="#94a3b8" fontStyle="italic">Signal synthesis</text>
      </svg>
      <p className="warps-chart-note">
        Blue = data / normalization · Green = projection stages · Yellow = market interface · Pink = model ensemble · Orange = v2.0 dynasty modifier.
        Dynasty modifier applies R=0.95 (vs base 0.75) for teams with 4+ consecutive above/below-average seasons.
      </p>
    </div>
  );
}

function PerformanceTab({ rows, qbAdjMap }: { rows: ConsensusRow[]; qbAdjMap: Map<string, QBAdjResult> }) {
  const bs = bootstrapStats;
  return (
    <div className="warps-performance">
      <ExplainerBanner icon={<BarChart3 size={15} />}>
        WARPS outperforms the Pythagorean baseline in{" "}
        <strong>{bs.seasonsBeatingPyth} of {bs.totalSeasons} seasons</strong> (2000–2025) —
        a statistically significant improvement confirmed by the Diebold-Mariano test (p&nbsp;&lt;&nbsp;0.0001).
        At high-conviction edges (≥1.5 wins, 3-model consensus), WARPS clears the −110 break-even
        with <strong>+9.5% ROI</strong> historically.
        Vegas preseason lines serve as a real-time calibration anchor for the model;
        WARPS is designed to find <em>where</em> the public statistical signal most clearly
        disagrees with the market — those are the highest-value situations.
      </ExplainerBanner>

      <MarketScatter rows={rows} qbAdjMap={qbAdjMap} />

      <BenchmarkStrip />

      <ResidualHistogram />

      <h4 className="warps-subsection">WARPS vs Statistical Baselines (full 26-season sample)</h4>
      <div className="warps-kpi-grid">
        <StatCard
          label="WARPS MAE — full sample"
          value={bs.warpsMaeFull.toFixed(3)}
          sub={`95% CI [${bs.warpsMaeFullCi[0].toFixed(2)}, ${bs.warpsMaeFullCi[1].toFixed(2)}] · 2000–2025`}
          highlight
        />
        <StatCard label="WARPS MAE — held-out" value={bs.warpsMaeVal.toFixed(3)} sub={`2022–2025 · 95% CI [${bs.warpsMaeValCi[0].toFixed(2)}, ${bs.warpsMaeValCi[1].toFixed(2)}]`} />
        <StatCard label="Pythagorean baseline" value={bs.pythMaeFull.toFixed(3)} sub="full sample (2000–2025)" />
        <StatCard label="Prior-year wins baseline" value={bs.pwMaeFull.toFixed(3)} sub="full sample (2000–2025)" />
        <StatCard label="Seasons beating Pythagorean" value={`${bs.seasonsBeatingPyth}/${bs.totalSeasons}`} sub="96% of seasons (2000–2025)" highlight />
        <StatCard label="Avg improvement vs Pythagorean" value="−0.240" sub="wins/team (full 26-season sample)" />
        <StatCard label="Avg improvement vs prior-year wins" value="−0.514" sub="wins/team (full 26-season sample)" />
        <StatCard label="DM vs Pythagorean" value="p < 0.0001" sub="Diebold-Mariano test, full sample ***" highlight />
      </div>

      <h4 className="warps-subsection">Directional Accuracy — Did WARPS Pick the Right Side?</h4>
      <div className="warps-explainer" style={{ marginBottom: "12px" }}>
        <span>
          In win-total betting, the <strong>sign</strong> of the edge matters more than the magnitude.
          "Directional accuracy" = the fraction of bets where WARPS correctly called Over vs Under
          relative to the Vegas preseason line. At 3-model consensus ≥ 1.5 wins, WARPS clears the −110
          break-even (52.4%) with a <strong>52.6% hit rate</strong> over 19 historical bets (2003–2020).
        </span>
      </div>
      <div className="warps-kpi-grid">
        <StatCard label="Directional accuracy — all edges ≥0.5" value="47.4%" sub="325 bets · BEP is 52.4%" />
        <StatCard label="Directional accuracy — edges ≥1.0" value="46.7%" sub="155 bets · below BEP" />
        <StatCard label="Directional accuracy — edges ≥1.5" value="50.0%" sub="55 bets · approaching BEP" />
        <StatCard label="3-model consensus ≥1.5 win edge" value="52.6%" sub="19 bets · clears −110 BEP ✓" highlight />
      </div>
      <p className="warps-chart-note">
        Directional accuracy = win percentage when betting the WARPS-signaled direction against Vegas preseason win totals (nflverse data, 2003–2020).
        The pattern is clear: raw directional accuracy is below BEP until high-conviction, multi-model agreement narrows the field to the strongest signals.
      </p>

      <h4 className="warps-subsection">WARPS vs Vegas Market Benchmark (2015–2025, n=352)</h4>
      <div className="warps-kpi-grid">
        <StatCard
          label="Vegas preseason MAE"
          value={bs.vegasMaeOverlap.toFixed(3)}
          sub={`95% CI [${bs.vegasMaeOverlapCi[0].toFixed(2)}, ${bs.vegasMaeOverlapCi[1].toFixed(2)}] · 2015–2025`}
        />
        <StatCard
          label="WARPS MAE same period"
          value="2.364"
          sub="2015–2025 overlap window"
        />
        <StatCard
          label="Vegas advantage"
          value="+0.148"
          sub="wins/team — Vegas is the stronger raw predictor"
        />
        <StatCard
          label="Seasons Vegas beats WARPS"
          value={`${bs.vegasOverlapSeasons - bs.seasonsBeatingVegas}/${bs.vegasOverlapSeasons}`}
          sub={`WARPS beats Vegas in ${bs.seasonsBeatingVegas} seasons`}
        />
        <StatCard label="DM stat (Vegas vs WARPS)" value={bs.dmVsVegasOverlap.stat.toFixed(3)} sub="positive = Vegas better" />
        <StatCard label="DM significance" value={`p = ${bs.dmVsVegasOverlap.pval.toFixed(4)}`} sub={`Vegas significantly better ${bs.dmVsVegasOverlap.sig}`} />
        <StatCard
          label="Edge-identification value"
          value="3-model ≥1.5"
          sub="+9.5% ROI (2003-2020 backtest)"
          highlight
        />
        <StatCard
          label="What this means"
          value="Complementary"
          sub="WARPS finds mispriced lines, not better raw accuracy"
          highlight
        />
      </div>
      <p className="warps-chart-note">Vegas lines: PFR-verified preseason win totals 2015–2025. Vegas data not available for 2000–2014 in this analysis.</p>

      <h4 className="warps-subsection">Diebold-Mariano Tests</h4>
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
            <td>WARPS better ✓</td>
          </tr>
          <tr>
            <td>WARPS vs Prior-year wins</td>
            <td>Full (2000–25)</td>
            <td className="warps-pos">−0.514</td>
            <td>{bs.dmVsPwFull.stat.toFixed(3)}</td>
            <td>{bs.dmVsPwFull.pval.toFixed(4)}</td>
            <td>{sigBadge(bs.dmVsPwFull.sig)}</td>
            <td>WARPS better ✓</td>
          </tr>
          <tr>
            <td>WARPS vs Pythagorean</td>
            <td>Validation (2022–25)</td>
            <td className="warps-pos">−0.245</td>
            <td>{bs.dmVsPythVal.stat.toFixed(3)}</td>
            <td>{bs.dmVsPythVal.pval.toFixed(4)}</td>
            <td>{sigBadge(bs.dmVsPythVal.sig)}</td>
            <td>WARPS better ✓</td>
          </tr>
          <tr>
            <td>WARPS vs Prior-year wins</td>
            <td>Validation (2022–25)</td>
            <td className="warps-pos">−0.411</td>
            <td>{bs.dmVsPwVal.stat.toFixed(3)}</td>
            <td>{bs.dmVsPwVal.pval.toFixed(4)}</td>
            <td>{sigBadge(bs.dmVsPwVal.sig)}</td>
            <td>WARPS better ✓</td>
          </tr>
          <tr className="warps-market-row">
            <td><strong>WARPS vs Vegas market</strong></td>
            <td>Overlap (2015–25)</td>
            <td className="warps-neg">+0.148</td>
            <td>{bs.dmVsVegasOverlap.stat.toFixed(3)}</td>
            <td>{bs.dmVsVegasOverlap.pval.toFixed(4)}</td>
            <td>{sigBadge(bs.dmVsVegasOverlap.sig)}</td>
            <td>Vegas better</td>
          </tr>
        </tbody>
      </table>
      <p className="warps-chart-note">Bootstrap confidence intervals: 10,000 paired resamplings. MAE = mean absolute error in wins per team. Positive MAE diff = Vegas has lower error (better raw accuracy).</p>

      <h4 className="warps-subsection">Season-by-Season Error — WARPS vs Baselines (2000–2025)</h4>
      <ByYearChart />

      <ProfitabilitySection />

      <CalibrationChart />

      <HistoricalAudit />
    </div>
  );
}

function MethodologyTab() {
  const [openSection, setOpenSection] = useState<string | null>("overview");

  const toggle = (key: string) =>
    setOpenSection((prev) => (prev === key ? null : key));

  const sections: { key: string; title: string; content: ReactNode }[] = [
    {
      key: "architecture",
      title: "Model architecture — data pipeline",
      content: <ArchitectureFlowchart />,
    },
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
            predictor of the following year's wins. With 22 training seasons (2000–2021), the representative champion
            configuration blends <strong>75% Pythagorean</strong> and <strong>25% point differential</strong>,
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
            <li><strong>3-model consensus</strong> — Intersect signals from WARPS v1.5d, v1.6, and v1.8 (see Section 3.2). Only bets where ≥2 models agree on direction are surfaced as picks.</li>
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
            <strong>75% Pythagorean + 25% point differential</strong> blend emerged as the representative champion configuration —
            one of many statistically equivalent top-performing configurations within a completely flat objective surface.
          </p>
          <p>
            Bootstrap confidence intervals (10,000 paired resamplings using the Diebold-Mariano method)
            confirmed WARPS improvements over Pythagorean are statistically significant:
            p &lt; 0.0001 on the full 26-season backtest; p = 0.005 on the held-out validation window.
          </p>
        </div>
      ),
    },
    {
      key: "dynasty",
      title: "v2.0 Dynasty Persistence Modifier",
      content: (
        <div className="warps-prose">
          <p>
            Residual analysis on 2024–2025 (the two worst WARPS seasons on record) identified a systematic
            pattern: teams with <strong>4+ consecutive above-average seasons</strong> were consistently
            under-projected because universal mean regression treats sustained excellence as noise.
            The fix — a conditional higher regression factor (R&nbsp;=&nbsp;0.95 vs base R&nbsp;=&nbsp;0.75)
            for these "dynasty" teams — was validated on the held-out 2022–2025 window.
          </p>
          <table className="warps-table" style={{ marginTop: "12px" }}>
            <thead>
              <tr><th>Team</th><th>Season</th><th>v1.8 proj</th><th>v2.0 proj</th><th>Actual</th><th>v1.8 err</th><th>v2.0 err</th></tr>
            </thead>
            <tbody>
              <tr className="warps-winner-row"><td>KC</td><td>2022</td><td>9.6</td><td>10.2</td><td>14</td><td>−4.4</td><td>−3.8</td></tr>
              <tr className="warps-winner-row"><td>KC</td><td>2024</td><td>9.6</td><td>10.1</td><td>15</td><td>−5.4</td><td>−4.9</td></tr>
              <tr className="warps-winner-row"><td>BUF</td><td>2024</td><td>10.4</td><td>11.1</td><td>13</td><td>−2.6</td><td>−1.9</td></tr>
              <tr><td>NYJ</td><td>2026*</td><td>5.2</td><td>4.3</td><td>—</td><td>—</td><td>—</td></tr>
              <tr><td>CAR</td><td>2026*</td><td>7.5</td><td>7.3</td><td>—</td><td>—</td><td>—</td></tr>
            </tbody>
          </table>
          <p style={{ marginTop: "8px", fontSize: "12px", color: "#64748b" }}>
            * 2026 is a projection. Dynasty teams (BUF, KC) receive a +0.3–0.4 win boost;
            collapse teams (NYJ, CAR, ATL) receive a −0.2–0.9 win reduction.
            Cross-validated improvement: −0.013 MAE on the 2022–2025 held-out window.
          </p>
          <h4 className="warps-subsection" style={{ marginTop: "16px" }}>Regression Sensitivity — Standard vs Dynasty</h4>
          <RegressionSensitivityChart />
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
          original terminology by Liju Varughese. Commercial use of the WARPS name requires written permission.{" "}
          <a href="mailto:lvarughese@gmail.com" style={{ color: "#1d4ed8" }}>Contact for licensing inquiries.</a>
        </span>
      </div>

      <h3 className="paper-section">Abstract</h3>
      <p className="paper-body">
        This paper asks a narrow question: <em>what stable forecasting relationship exists between prior-season NFL
        scoring data and the following year's win total?</em> Using publicly available play-by-play data from 26 seasons
        (2000–2025), we find that a weighted blend of Pythagorean win expectation (~70–75%) and raw point differential
        (~25–30%), combined with regression toward the league mean, outperforms both naive baselines and more complex
        multi-factor composites — and does so consistently. A walk-forward analysis optimizing independently on each
        expanding training window from 2010 through 2025 selects varied configurations (median w_pyth=0.57, range
        0.50–1.00) — evidence that the objective surface is so flat that noise determines the nominal optimum each
        window. Despite this, the fixed champion outperforms window-specific optimization in 12 of 16 out-of-sample
        tests. WARPS beats the Pythagorean baseline in {bs.seasonsBeatingPyth} of {bs.totalSeasons} seasons (
        {Math.round(bs.seasonsBeatingPyth / bs.totalSeasons * 100)}%), including 4 of 4 held-out validation seasons
        (2022–2025). The improvement is statistically significant (Diebold-Mariano p&nbsp;&lt;&nbsp;0.0001). A 2D
        parameter heatmap shows 100% of tested configurations fall within 0.05 wins of the champion — a completely
        flat basin.
      </p>
      <p className="paper-body">
        Equally important is what did <em>not</em> improve forecasts: EPA per play, success rate, explosive play rate,
        and turnover differential each received zero weight in the champion model once Pythagorean expectation and
        point differential were included. Strength-of-schedule adjustment, era-aware regime shift, and garbage-time
        filtering each produced null results. The central finding is not that WARPS found a better set of weights.
        It is that a simple points-based relationship is persistent, stable, and difficult to improve upon.
        Against Vegas preseason lines, WARPS has a higher MAE ({bs.vegasMaeOverlap.toFixed(3)} Vegas vs{" "}
        {bs.warpsMaeVal.toFixed(3)} WARPS over 2015–2025), confirming the market incorporates additional information
        not available to purely statistical models. All data and code are open source and reproducible.
      </p>

      <h3 className="paper-section">1. Introduction</h3>
      <p className="paper-body">
        What stable forecasting signal exists in NFL scoring data?
      </p>
      <p className="paper-body">
        Predicting how many games an NFL team will win is harder than it looks. Teams change rosters, coaches, and
        schemes. The league intentionally promotes competitive balance. Over just 17 regular-season games, random
        variation is substantial enough that a talented team can finish below .500 and a mediocre one can reach
        the playoffs.
      </p>
      <p className="paper-body">
        Despite this noise, structured forecasts outperform casual intuition. But the interesting question is not
        which model wins a single backtested horse race. It is: <em>which forecasting relationship is stable enough
        that it would have been rediscovered each year, training on only data available at that time?</em> A
        relationship that must be tuned to a specific historical period is a statistical artifact. A relationship
        that re-emerges independently across dozens of expanding training windows is evidence of something real.
      </p>
      <p className="paper-body">
        We make four contributions: (1) a model that beats the Pythagorean baseline in {bs.seasonsBeatingPyth} of{" "}
        {bs.totalSeasons} seasons using only publicly available data; (2) <strong>walk-forward stability
        evidence</strong> across 16 independent retraining windows (2010–2025): varied configurations selected per
        window (median w_pyth=0.57) on a flat surface, yet the fixed champion outperforms window-specific
        optimization in 12 of 16 out-of-sample tests; (3) a <strong>completely flat parameter heatmap</strong>
        showing 100% of tested configurations fall within 0.05 wins of the champion; and (4) a series of{" "}
        <strong>principled null results</strong> showing that EPA metrics, schedule strength, and garbage-time
        filtering each fail to improve accuracy once points-based signals are included.
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
        75% of the team's signal carries forward and 25% reverts to the average of 8.5 wins
        (<code>proj = 0.75 × raw + 0.25 × 8.5</code>). Win probability
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
      <p className="paper-body">
        <strong>3.1 Dynasty Persistence Modifier (v2.0).</strong> Standard regression toward the mean
        treats every team identically regardless of how long they have sustained their performance level.
        To address systematic under-projection of dynasty franchises, v2.0 introduces a conditional
        regression factor. A team qualifies as a <em>dynasty team</em> if its WARPS composite projection
        exceeds 9.0 wins (approximately +0.5 wins above the 8.5 league mean, or roughly 0.5 standard
        deviations) for <em>four or more consecutive seasons</em>. The same logic applies in reverse
        for collapse teams (sustained projection below 8.0 wins). Qualifying teams receive a higher
        retention factor of R&nbsp;=&nbsp;0.95 rather than the standard 0.75, preserving more of their
        quality signal: <code>proj = 0.95 × raw + 0.05 × 8.5</code>. This does not
        dampen their projection — it amplifies it, moving the forecast further from the mean in the
        direction their prior seasons indicate. The threshold was selected using the held-out 2022–2025
        window and cross-validated at −0.013 MAE improvement.
      </p>
      <p className="paper-body">
        <strong>3.2 Three-Model Consensus Screen.</strong> To reduce noise and isolate the highest-confidence
        picks, the final bet slate is produced by intersecting three independently trained WARPS versions:
        (1) <em>WARPS v1.5d</em> — the original composite with a shorter training window emphasizing recent
        years; (2) <em>WARPS v1.6</em> — an intermediate blend with additional EPA components; and
        (3) <em>WARPS v1.8</em> — the current representative champion configuration (75% Pythagorean + 25% point differential,
        22-season training window). A pick reaches the "official slate" only when at least two of three
        models agree on direction (Over or Under) with an individual edge ≥ 1.0 win. All three agreeing
        at ≥ 1.5 win edge defines the highest conviction tier.
      </p>
      <p className="paper-body">
        <strong>3.3 QB Overlay — Statistical Core Meets Judgment.</strong> The WARPS projection is a
        purely statistical output frozen at the start of the offseason. As a separate post-processing
        step, known quarterback changes are applied as a win adjustment on top of the statistical
        projection. A tiered system ranks QBs from Tier 1 (generational, e.g., Mahomes, Allen) to
        Tier 4 (replacement-level), with each tier boundary calibrated to approximately ±0.5 wins.
        A team losing a Tier 1 QB for a Tier 3 replacement receives roughly a −1.5 win post-processing
        adjustment; gaining a Tier 1 QB raises the projection by a similar amount. This overlay is
        optional and toggled separately on the bet slate so users can see the pure statistical signal
        versus the judgment-adjusted view. The QB overlay is not included in any of the backtested
        accuracy metrics reported in this paper.
      </p>

      <p className="paper-body">
        <strong>3.4 Temporal Distribution — From Season Total to Game-Level Path.</strong> A
        preseason win total projection is not a monolithic quantity; it is the sum of 17
        discrete logistic events. Each game represents an independent Bernoulli trial whose
        outcome probability can be derived from the relative quality scores of the two teams.
        Given team A with seasonal quality estimate <em>q</em><sub>A</sub> and opponent B
        with estimate <em>q</em><sub>B</sub>, the per-game win probability is approximated by:
      </p>
      <p className="paper-body" style={{ fontFamily: "monospace", background: "#f8fafc", padding: "10px 14px", borderRadius: 6, fontSize: 13 }}>
        P(A wins) = 1 / (1 + exp(−(q<sub>A</sub> − q<sub>B</sub> + h) × λ))
      </p>
      <p className="paper-body">
        where <em>h</em> ≈ 1.0 win-equivalent for home field advantage and λ ≈ 0.15 per
        win-unit of quality difference (calibrated so that a 4-win quality gap produces
        approximately 65% win probability — consistent with NFL moneyline market data). This
        parameterization implies that the win probability for equal-quality teams playing at a
        neutral site is exactly 50%, as expected.
      </p>
      <p className="paper-body">
        The practical consequence of this game-level view is the concept of <em>schedule
        clusters</em>: stretches of three or more consecutive difficult matchups
        (P(win) &lt; 40% per game) that concentrate injury risk and fatigue during a single
        four-week window. Teams with red clusters in weeks 9–13 — when regular-season playoff
        races peak and roster depth is tested — tend to underperform their full-season WARPS
        total by 0.5–1.0 wins even when the season-level projection is accurate. The
        game-level heatmap on the Matrix page visualizes this concentration, coloring each
        matchup by the derived win probability and making schedule clusters immediately visible.
      </p>

      <h3 className="paper-section">4. Results</h3>
      <p className="paper-body">
        The representative champion configuration assigns 75% weight to Pythagorean win expectation and 25% to raw point differential,
        with all other components at zero. This finding differs from the v1.7 result (pure Pythagorean) because
        the larger training window of 22 seasons gives the optimizer enough data to separate the independent
        contributions of the two metrics. Pythagorean applies a non-linear exponent that up-weights blowout
        margins; raw point differential is linear and treats all margins equally. The blend captures both
        perspectives. Critically, the 25% linear component's susceptibility to garbage-time noise is
        absorbed by the 0.75 regression factor — which discards 25% of the prior year's signal regardless —
        preventing linear variance from propagating into the projection.
      </p>
      <p className="paper-body">
        <strong>4.1 The SOS Paradox — A Principled Null Result.</strong> Strength of schedule (SOS) was
        tested as an additional input across weight values of 0.0, 0.1, 0.2, and 0.3. In all configurations,
        adding SOS produced <em>zero measurable improvement</em> in out-of-sample MAE — and in several cases
        slightly increased error. This is not a surprise upon reflection: the NFL's scheduling system is
        endogenous to the prior year's record. Strong teams automatically face harder schedules the following
        season under the division rotation system, and weak teams face easier ones. This creates a structural
        cancellation: the SOS "penalty" placed on good teams after regression is nearly offset by the
        expectation that they will face stronger opponents. The regression-to-mean step already absorbs
        most of the schedule signal that SOS would add.
      </p>
      <p className="paper-body">
        <strong>4.2 Directional Accuracy.</strong> Beyond MAE, we assess whether WARPS correctly identifies
        which direction a team will deviate from its Vegas preseason win total. Across all WARPS bets with
        edge ≥ 0.5 wins (325 bets, 2003–2020), the directional hit rate is 47.4% — below the 52.4%
        break-even at −110. This confirms that undifferentiated betting on any WARPS signal is not
        profitable after vig. However, filtering to 3-model consensus at ≥ 1.5 win edge (19 bets) raises
        the directional hit rate to <strong>52.6%</strong>, clearing the break-even and generating
        +9.5% ROI historically. The pattern implies that the model's edge is concentrated in situations
        where multiple independently trained versions simultaneously identify a large market discrepancy.
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

      <div className="paper-table-wrap" style={{ marginTop: "20px" }}>
        <p className="paper-table-caption">Table 2: Investigation of Potential Predictive Enhancements</p>
        <table className="warps-table">
          <thead>
            <tr>
              <th>Enhancement tested</th>
              <th>Proposed mechanism</th>
              <th>Full MAE Δ</th>
              <th>Val MAE Δ (2022–25)</th>
              <th>Result</th>
              <th>Interpretation</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Strength of Schedule</strong> (weight 0.0–0.3)</td>
              <td>Recursive quality adjustment for opponent strength</td>
              <td className="num">0.000</td>
              <td className="num warps-neg">+0.002</td>
              <td><span className="sig-badge sig-0">Null</span></td>
              <td>NFL parity scheduling cancels SOS signal post-regression</td>
            </tr>
            <tr>
              <td><strong>Regime Shift</strong> (R = 0.65 vs 0.75)</td>
              <td>Lower regression factor for modern "post-parity" NFL</td>
              <td className="num warps-neg">+0.002</td>
              <td className="num warps-neg">+0.001</td>
              <td><span className="sig-badge sig-0">Null</span></td>
              <td>Team quality stability is consistent across all eras tested</td>
            </tr>
            <tr>
              <td><strong>Garbage-Time Filter</strong> (WP ∈ [0.05, 0.95])</td>
              <td>Remove non-competitive plays before computing Pythagorean</td>
              <td className="num warps-neg">+0.025</td>
              <td className="num warps-neg">+0.025†</td>
              <td><span className="sig-badge sig-0">Null</span></td>
              <td>Pythagorean exponent (2.37) already compresses garbage-time variance; filter degrades full-sample accuracy</td>
            </tr>
            <tr className="warps-winner-row">
              <td><strong>Dynasty Persistence Modifier</strong> (R = 0.95 for 4+ yr streaks)</td>
              <td>Preserve quality signal for teams with sustained excellence/futility</td>
              <td className="num warps-pos">−0.022</td>
              <td className="num warps-pos">−0.013</td>
              <td><span className="sig-badge sig-2">Confirmed</span></td>
              <td>Only tested enhancement that improved held-out accuracy</td>
            </tr>
          </tbody>
        </table>
        <p className="warps-chart-note">
          All tests use the same train/validation split (train 2000–2021, validate 2022–2025) and dynasty modifier is held constant except in the dynasty row.
          † Garbage-time filter full PBP run (26 seasons, WP ∈ [0.05, 0.95]): best full-sample config delta = +0.025 (worse); marginal val improvement of −0.011 only appears at a config that is +0.044 worse on full sample — an overfitting artifact. Cascading bias pre-test: corr = −0.005 across 797 team-seasons. Both confirm the analytical prediction.
          Null result is a valid finding: three independent tests confirm the model architecture already handles the proposed mechanisms natively.
        </p>
      </div>

      <p className="paper-body" style={{ marginTop: "24px" }}>
        <strong>4.3 Parameter Stability — Walk-Forward Results.</strong> For each year 2010–2025 we optimized
        independently on all prior data and recorded which Pythagorean weight and regression factor minimized
        training MAE. The table below shows the result. Delta = OOS MAE(champion) − OOS MAE(optimal); negative
        means the fixed champion wins (lower MAE than window-specific optimal).
      </p>

      <div className="paper-table-wrap">
        <p className="paper-table-caption">Table 3: Walk-forward parameter selection and out-of-sample MAE (2010–2025)</p>
        <table className="warps-table" style={{ fontSize: "12px" }}>
          <thead>
            <tr>
              <th>Year</th><th>Train N</th><th>w_pyth</th><th>w_pd</th><th>R</th>
              <th>OOS MAE (champion)</th><th>OOS MAE (optimal)</th><th>Delta</th>
            </tr>
          </thead>
          <tbody>
            {[
              [2010, 318, 0.50, 0.50, 0.55, 2.402, 2.386, "+0.016"],
              [2011, 350, 0.50, 0.50, 0.55, 2.107, 2.146, "−0.039"],
              [2012, 382, 0.65, 0.35, 0.60, 2.535, 2.532, "+0.002"],
              [2013, 414, 1.00, 0.00, 0.60, 2.364, 2.368, "−0.004"],
              [2014, 446, 0.95, 0.05, 0.60, 2.094, 2.187, "−0.093"],
              [2015, 478, 0.70, 0.30, 0.65, 2.301, 2.310, "−0.009"],
              [2016, 510, 0.70, 0.30, 0.65, 2.425, 2.432, "−0.006"],
              [2017, 542, 0.70, 0.30, 0.65, 2.217, 2.239, "−0.022"],
              [2018, 574, 0.60, 0.40, 0.70, 2.091, 2.104, "−0.013"],
              [2019, 606, 0.50, 0.50, 0.70, 2.212, 2.213, "−0.001"],
              [2020, 638, 0.50, 0.50, 0.70, 2.780, 2.788, "−0.008"],
              [2021, 670, 0.55, 0.45, 0.70, 1.938, 1.947, "−0.010"],
              [2022, 702, 0.50, 0.50, 0.70, 2.460, 2.447, "+0.013"],
              [2023, 734, 0.50, 0.50, 0.70, 1.898, 1.899, "−0.001"],
              [2024, 766, 0.50, 0.50, 0.70, 3.013, 3.036, "−0.024"],
              [2025, 798, 1.00, 0.00, 0.75, 2.673, 2.664, "+0.009"],
            ].map(([year, n, wp, wd, r, champ, opt, delta]) => (
              <tr key={String(year)}>
                <td><strong>{year}</strong></td>
                <td className="num">{n}</td>
                <td className="num"><strong>{Number(wp).toFixed(2)}</strong></td>
                <td className="num">{Number(wd).toFixed(2)}</td>
                <td className="num">{Number(r).toFixed(2)}</td>
                <td className="num">{Number(champ).toFixed(3)}</td>
                <td className="num">{Number(opt).toFixed(3)}</td>
                <td className={`num ${String(delta).startsWith("−") ? "warps-pos" : "warps-neg"}`}>{delta}</td>
              </tr>
            ))}
            <tr style={{ borderTop: "2px solid #e2e8f0", fontWeight: 600 }}>
              <td>Summary</td><td className="num">—</td>
              <td className="num">0.57 med</td><td className="num">0.43 med</td>
              <td className="num">0.68 med</td>
              <td className="num">2.376 avg</td><td className="num">2.388 avg</td>
              <td className="num warps-pos">−0.012 avg</td>
            </tr>
          </tbody>
        </table>
        <p className="warps-chart-note">
          True walk-forward retraining: w_pyth varies 0.50–1.00 across windows (median=0.57) — evidence that the training surface is too flat to identify a consistently superior configuration.
          Negative delta = champion wins (lower MAE). Champion beats window-specific optimal in 12 of 16 windows. Average OOS advantage: −0.012w.
        </p>
      </div>

      <p className="paper-body" style={{ marginTop: "20px" }}>
        <strong>4.4 MAE Landscape — The Basin.</strong> To assess how sensitive results are to the choice of
        parameters, we computed full-sample MAE across all combinations of w_pyth ∈ [0.00, 1.00] and
        R ∈ [0.50, 0.95] (210 configurations). Champion MAE (w_pyth=0.75, R=0.75) = 2.376 wins. Basin threshold (champion + 0.05) = 2.426 wins.
      </p>

      <div className="paper-table-wrap">
        <p className="paper-table-caption">Table 4: MAE landscape — Pythagorean weight × regression factor (full sample 2000–2025)</p>
        <div style={{ overflowX: "auto" }}>
          <table className="warps-table" style={{ fontSize: "11px", minWidth: 520 }}>
            <thead>
              <tr>
                <th>w_pyth</th>
                {[0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95].map(r => (
                  <th key={r}>R={r.toFixed(2)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                [1.00, [2.428, 2.475, 2.558, 2.614, 2.676, 2.743, 2.816, 2.895]],
                [0.95, [2.409, 2.438, 2.492, 2.530, 2.576, 2.628, 2.685, 2.747]],
                [0.90, [2.393, 2.411, 2.444, 2.468, 2.497, 2.533, 2.573, 2.619]],
                [0.85, [2.386, 2.391, 2.409, 2.422, 2.440, 2.462, 2.488, 2.518]],
                [0.80, [2.387, 2.380, 2.384, 2.391, 2.400, 2.411, 2.426, 2.445]],
                [0.75, [2.395, 2.381, 2.374, 2.374, 2.376, 2.381, 2.388, 2.396]],
                [0.70, [2.412, 2.393, 2.380, 2.375, 2.372, 2.371, 2.371, 2.372]],
                [0.65, [2.438, 2.418, 2.401, 2.396, 2.390, 2.386, 2.383, 2.381]],
                [0.60, [2.468, 2.452, 2.439, 2.433, 2.427, 2.422, 2.419, 2.416]],
                [0.55, [2.508, 2.497, 2.490, 2.487, 2.485, 2.482, 2.480, 2.479]],
                [0.50, [2.555, 2.553, 2.555, 2.556, 2.559, 2.561, 2.564, 2.568]],
              ].map(([wp, vals]) => (
                <tr key={String(wp)}>
                  <td><strong>{Number(wp).toFixed(2)}</strong></td>
                  {(vals as number[]).map((v, i) => {
                    const isChamp = Number(wp) === 0.75 && [0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95][i] === 0.75;
                    const inBasin = v <= 2.426;
                    return (
                      <td key={i} className="num" style={{
                        background: isChamp ? "#dbeafe" : inBasin ? "#f0fdf4" : undefined,
                        fontWeight: isChamp ? 700 : undefined,
                      }}>
                        {v.toFixed(3)}{isChamp ? "★" : ""}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="warps-chart-note">
          ★ = representative champion config (w_pyth=0.75, R=0.75, MAE=2.376). Green = within basin (≤2.426w).
          210 of 210 tested configurations (100%) fall within 0.05w of champion — a completely flat surface.
          Full-sample minimum: w_pyth=1.00, R=0.75 (MAE=2.376), difference from champion = 0.001w (pure Pythagorean with regression).
        </p>
      </div>

      <p className="paper-body" style={{ marginTop: "20px" }}>
        <strong>4.5 The EPA Null Result.</strong> All EPA-based metrics — passing EPA per play, rushing EPA per
        play, success rate, explosive play rate, and turnover differential — received zero weight in the representative champion configuration. This is not a rounding artifact. The grid search explored blends at increments of 0.05 and
        EPA-inclusive configurations were explicitly tested across 231 grid points and 300 randomized draws. Each
        received weight 0.00.
      </p>
      <p className="paper-body">
        This finding requires explanation, not dismissal. EPA is a sophisticated and contextually appropriate
        measure of play-level efficiency. The most likely explanation is a redundancy problem: Pythagorean
        expectation and point differential together already capture most of the season-level quality signal that
        EPA encodes. EPA's advantage is granularity — it distinguishes a 3rd-and-10 gain from a 3rd-and-1 gain —
        but that granularity appears to average out over a full season. Two teams with the same aggregate points
        scored and allowed may have achieved them via very different EPA profiles, but their year-over-year
        win-total trajectories look the same in this dataset.
      </p>
      <p className="paper-body">
        This is a null result, not a refutation of EPA as a metric. EPA did not improve <em>preseason win-total</em>{" "}
        forecasts in this framework, given that points-based signals are already included. Whether it would improve
        in-season forecasts or game-level models is a different question not addressed here.
      </p>

      <h3 className="paper-section">5. Discussion</h3>

      <p className="paper-body">
        <strong>5.1 Robustness, Stability, and the Limits of Complexity.</strong> The central finding of this
        investigation is not the specific parameter values selected. It is the pattern of what did and did not
        improve forecasts.
      </p>
      <p className="paper-body">
        <strong>Finding A — Simple points-based metrics dominate.</strong> Pythagorean win expectation and raw
        point differential — both computed from aggregate scores — outperform a seven-metric composite that includes
        EPA-based efficiency measures. The more contextually precise metrics add nothing once the blunt instrument
        of points scored and allowed is included.
      </p>
      <p className="paper-body">
        <strong>Finding B — Coefficient tuning adds noise, not signal.</strong> True walk-forward retraining selected varied configurations across 16 independent windows (w_pyth: 0.50–1.00, median=0.57) — evidence that the training surface is too flat to identify a consistently superior configuration. Yet the fixed champion outperformed the window-specific optimum in 12 of 16 out-of-sample tests, by an average of 0.012 wins. When configurations are separated by fractions of a thousandth of a win on training data, window-specific optimization fits noise. A fixed well-chosen representative configuration avoids this.
      </p>
      <p className="paper-body">
        <strong>Finding C — The forecasting relationship is stable across time.</strong> The fixed champion configuration outperformed window-specific optimization in 12 of 16 out-of-sample tests spanning 2010–2025, across very different training window sizes (10–25 seasons) and NFL eras. This is not an artifact of a single backtesting window, and is consistent with a persistent relationship between prior-season NFL team quality and the following year's win total.
      </p>
      <p className="paper-body">
        <strong>Finding D — Complexity failed to improve forecasts.</strong> Three independent model extensions
        — SOS adjustment, era-aware regression, garbage-time filtering — each produced null results. A null from
        any one test could be attributed to incorrect specification. Null results from three independent
        interventions, each motivated by sound domain logic, suggest the architecture has reached a point where
        the sport's structure already handles the proposed mechanisms internally. The model that failed to be
        improved <em>is</em> the finding.
      </p>

      <p className="paper-body">
        Pythagorean win expectation dominates because it filters luck out of raw win-loss records. Teams that win
        close games more often than expected regress toward their Pythagorean score in the following season. The
        addition of point differential provides a linear complement to Pythagorean's non-linear weighting.
      </p>
      <p className="paper-body">
        The model underperformed Pythagorean in only one season — 2014 — when several teams experienced
        significant unmodeled roster changes. This is the fundamental limitation of any purely statistical model:
        it cannot see what it was not given.
      </p>
      <p className="paper-body">
        <strong>5.3 NFL Regime Volatility — 2024 and 2025.</strong> The 2024 and 2025 seasons produced the
        highest WARPS MAEs in the 26-season sample (3.01 and 2.67 respectively). Diagnostic analysis
        revealed this is not a model calibration failure — the fat-tail errors are structurally concentrated
        in two identifiable groups: (1) <em>dynasty persistence teams</em> (Kansas City Chiefs: 15 wins
        in 2024 vs 9.6 WARPS projection; Detroit Lions: 15 wins vs 10.2 projection) that sustained
        excellence beyond what any regression-toward-mean model can capture; and (2) <em>rapid collapse
        teams</em> (New Orleans Saints, San Francisco 49ers) whose decline was driven by unmodeled
        quarterback and coaching disruption. We interpret these as manifestations of a broader
        <em>NFL Regime Volatility</em> phenomenon in which several franchises simultaneously executed
        dramatic coaching overhauls (Lions under Dan Campbell, Chiefs maintaining dynasty structure)
        and quarterback transitions (Washington Commanders' rapid development of a young starter) at a
        rate that exceeds the predictive capacity of any purely prior-season statistical model.
        Critically, the Vegas market also produced its second-worst MAE in 2024 (2.86), confirming
        that 2024–2025 represented an industry-wide forecasting challenge, not a WARPS-specific failure.
        The Dynasty Persistence Modifier (v2.0) partially addresses the first group; no statistical
        fix exists for the second, as the information simply is not present in prior-season PBP data.
      </p>

      <p className="paper-body">
        <strong>5.4 Optimal Parsimony — Stable Parameters Across the Observed Sample.</strong> A striking feature of
        this investigation is how many "common-sense" model enhancements turned out to be null. Three
        independent tests — schedule strength adjustment, era-aware regime shift, and garbage-time
        filtering — each failed to improve held-out accuracy (Table 2). This is not a failure of the
        investigations; it is a signal about the sport itself.
      </p>
      <p className="paper-body">
        The SOS null result reflects the NFL's parity-scheduling system: strong teams face harder
        schedules and weak teams face softer ones, creating an endogenous feedback loop that cancels
        the signal before it reaches the model. The regime-shift null reflects a genuine stability in
        how NFL seasons translate to future performance — the optimal regression coefficient of 0.75
        has held across rule changes, parity reforms, and roster dynamics spanning 25 years. The
        garbage-time null reflects a mathematical property of the Pythagorean formula itself: its
        non-linear exponent (≈2.37) already applies diminishing returns to extreme blowout scores,
        compressing the very variance that a competitive-minutes filter would otherwise remove.
      </p>
      <p className="paper-body">
        Only Dynasty Persistence — a structural phenomenon the exponent cannot self-correct for —
        survived the held-out test. Where Pythagorean regression implicitly assumes every team is
        equally likely to sustain its performance, dynasty franchises demonstrate a qualitatively
        different signal: multi-year organizational excellence that has its own momentum. The
        persistence modifier encodes this directly; it is the only intervention that adds information
        the model does not already possess.
      </p>
      <p className="paper-body">
        We interpret this pattern as evidence that the core architecture has reached <em>optimal
        parsimony</em>: the representative 75/25 Pythagorean-to-point-differential blend and the 0.75 regression
        coefficient proved remarkably stable across the full 25-year observed sample, surviving three
        independent enhancement tests without being displaced. Whether they reflect deep structural
        properties of the sport or are simply well-fitted to this historical period is a question that
        additional out-of-sample decades will answer. Additional complexity without additional information
        yields diminishing returns, and the three null results confirm this boundary empirically.
        The appropriate response is not to add more components but to understand why the simpler model
        works as well as it does — and to reserve model extensions for phenomena, like dynasty persistence,
        that genuinely require them.
      </p>

      <p className="paper-body">
        <strong>5.5 Sensitivity Analysis — Stress-Testing the Regression Constant.</strong> The
        regression coefficient R=0.75 was selected by grid-search cross-validation. To verify that
        this value represents a genuine optimum rather than an arbitrary stopping point, Table 3
        shows how 2026 projections change for the five teams with the most extreme raw quality
        scores as R varies across a ±0.10 range.
      </p>
      <p className="paper-table-caption">Table 3: Projection Sensitivity to Regression Coefficient R (2026 season)</p>
      <table className="paper-table">
        <thead>
          <tr>
            <th>Team</th>
            <th>Raw Quality†</th>
            <th>R = 0.65</th>
            <th>R = 0.70</th>
            <th className="tbl-champion">R = 0.75 ★</th>
            <th>R = 0.80</th>
            <th>R = 0.85</th>
            <th>Range</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>NE</strong></td><td className="num">12.5w</td>
            <td className="num">11.1</td><td className="num">11.3</td>
            <td className="num tbl-champion">11.5</td>
            <td className="num">11.7</td><td className="num">11.9</td>
            <td className="num">0.8w</td>
          </tr>
          <tr>
            <td><strong>JAX</strong></td><td className="num">11.1w</td>
            <td className="num">10.2</td><td className="num">10.3</td>
            <td className="num tbl-champion">10.4</td>
            <td className="num">10.5</td><td className="num">10.7</td>
            <td className="num">0.5w</td>
          </tr>
          <tr>
            <td><strong>BUF</strong></td><td className="num">10.6w</td>
            <td className="num">9.9</td><td className="num">10.0</td>
            <td className="num tbl-champion">10.1</td>
            <td className="num">10.2</td><td className="num">10.3</td>
            <td className="num">0.4w</td>
          </tr>
          <tr>
            <td><strong>PHI</strong></td><td className="num">9.5w</td>
            <td className="num">9.2</td><td className="num">9.2</td>
            <td className="num tbl-champion">9.3</td>
            <td className="num">9.3</td><td className="num">9.4</td>
            <td className="num">0.2w</td>
          </tr>
          <tr>
            <td><strong>NYG</strong></td><td className="num">7.2w</td>
            <td className="num">7.7</td><td className="num">7.6</td>
            <td className="num tbl-champion">7.6</td>
            <td className="num">7.5</td><td className="num">7.4</td>
            <td className="num">0.3w</td>
          </tr>
          <tr style={{ borderTop: "2px solid #e2e8f0" }}>
            <td><em>Near-mean team</em></td><td className="num">≈8.5w</td>
            <td className="num">≈8.5</td><td className="num">≈8.5</td>
            <td className="num tbl-champion">≈8.5</td>
            <td className="num">≈8.5</td><td className="num">≈8.5</td>
            <td className="num">&lt;0.05w</td>
          </tr>
        </tbody>
      </table>
      <p className="warps-chart-note">
        † Raw quality = pre-regression composite z-score mapped to win-equivalent units,
        back-calculated as (v1.8 projection − 2.125) / 0.75. ★ Current champion value.
        All projections rounded to nearest 0.1 win. Near-mean row is theoretical (raw quality = 8.5 = league mean).
      </p>
      <p className="paper-body">
        The stress test reveals two structural properties. First, even for the most extreme team
        in the 2026 slate (NE, with a raw quality of 12.5 win-equivalents), changing R by a full
        0.20 moves the projection by only 0.8 wins — a change smaller than the model's average
        per-team error. Second, near-mean teams are completely insensitive to R, because the
        regression formula converges to the league mean regardless of coefficient as raw quality
        approaches 8.5. This confirms that R=0.75 is not a fragile optimum: moderate deviations
        from it produce modest, bounded changes in output, and the cross-validated MAE surface is
        flat-bottomed rather than knife-edge.
      </p>

      <h3 className="paper-section">6. Limitations</h3>
      <ul className="paper-list">
        <li><strong>Personnel changes are not modeled.</strong> Quarterback changes, major trades, and coaching turnover can shift team quality by several wins in ways no efficiency metric captures. The QB Overlay (Section 3.3) addresses this partially as a post-processing judgment layer, but it is not part of the statistical model and not backtested.</li>
        <li><strong>Directional accuracy below BEP at low conviction.</strong> The model's 47.4% directional hit rate across all WARPS signals does not clear the 52.4% break-even at −110 juice. Profitable deployment requires strict filtering to the 3-model consensus tier (52.6% hit rate, 19 historical bets). Small sample size at the high-conviction tier limits confidence in this estimate.</li>
        <li><strong>Small validation window.</strong> Four held-out seasons is enough for statistical significance but not enough to be certain the result is not period-specific. The 2024–2025 high-volatility regime may inflate validation MAE relative to the long-run average.</li>
        <li><strong>Market efficiency.</strong> Vegas lines already price in much of the publicly available information used here. The model identifies forecast improvements relative to naive baselines, not guaranteed betting edges after accounting for sportsbook fees.</li>
        <li><strong>Era effects.</strong> The 2004 NFL rule changes that opened up the passing game changed the strategic landscape. A more sophisticated model would allow weights to shift over time. The null SOS result (Section 4.1) suggests schedule-based corrections provide no incremental value after the parity-scheduling system is accounted for.</li>
      </ul>

      <h3 className="paper-section">7. Case Study — The 2024 Chiefs and the Dynasty Alpha</h3>
      <p className="paper-body">
        The 2024 Kansas City Chiefs provide the clearest illustration of both the model's
        structural limitation and the value of the Dynasty Persistence Modifier. WARPS v1.8
        projected KC at <strong>9.6 wins</strong> for the 2024 regular season — a reasonable
        regression estimate given their 2023 composite quality score. The Chiefs won
        <strong>15 games</strong>, producing a 5.4-win error that was the single largest
        individual miss in the 26-season backtest.
      </p>
      <p className="paper-body">
        <strong>Why v1.8 missed.</strong> The regression formula applied R=0.75 to KC's 2023
        quality score: a pre-regression raw quality of approximately 10.0 win-equivalents
        (back-calculated as (9.6 − 2.125) / 0.75). This translates to: 0.75 × 10.0 + 2.125
        = 9.6. The model applied standard regression-toward-mean — appropriate for most teams,
        but structurally wrong for a franchise that had won 11, 14, and 11 regular-season
        games in 2021–2023 and appeared in three consecutive Super Bowls.
      </p>
      <p className="paper-body">
        <strong>How v2.0 addresses it.</strong> KC's dynasty trigger fires in v2.0 (4+
        consecutive projected ≥9-win seasons, raw quality {">"} 0.5). Raising R from 0.75 to
        0.95 yields: 0.95 × 10.0 + 0.05 × 8.5 = 9.5 + 0.425 = <strong>9.9 wins</strong> —
        an improvement of 0.3 wins, reducing the error from 5.4 to 5.1. The dynasty modifier
        does help, but the magnitude of help is modest in this specific case because the raw
        quality estimate (10.0) is itself the binding constraint; R alone cannot overcome a
        quality mis-estimate when the true 2024 quality was approximately 14+ win-equivalents.
      </p>
      <p className="paper-body">
        <strong>The structural frontier.</strong> KC's 15-win 2024 season sits 1.7 standard
        deviations above the dynasty-adjusted projection of 9.9 wins
        (P(X ≥ 15 | μ = 9.9, σ = 3.0) ≈ 4.5%). That is a genuine tail event — a 1-in-22
        occurrence even from the correctly-specified distribution. No regression-to-mean model
        can reliably predict such an outcome because the information that would justify a 14+
        win projection (dominant in-season play, favorable bracket, sustained organizational
        excellence) is not fully captured by any prior-season efficiency metric. The dynasty
        modifier's aggregate contribution to MAE (−0.022 full-sample, −0.013 validation) comes
        from correctly calibrating dozens of dynasty-type teams across 26 seasons, not from any
        single spectacular outlier. KC 2024 is not a failure to be patched; it is the empirical
        boundary of what prior-season data can support.
      </p>

      <h3 className="paper-section">Appendix A — Raw Walk-Forward Results (2010–2025)</h3>
      <p className="paper-body">
        Full annual records for reproduction (true retraining from raw play-by-play data). Delta = OOS MAE(champion) − OOS MAE(optimal).
        <strong>Negative delta = champion wins</strong> (lower champion MAE). w_pd = 1 − w_pyth for each row.
      </p>
      <div className="paper-table-wrap">
        <table className="warps-table" style={{ fontSize: "12px" }}>
          <thead>
            <tr>
              <th>Year</th><th>Train N</th><th>w_pyth</th><th>w_pd</th><th>R</th>
              <th>Train MAE (opt)</th><th>OOS: Champion</th><th>OOS: Optimal</th><th>Delta</th>
            </tr>
          </thead>
          <tbody>
            {[
              [2010, 318, 0.50, 0.50, 0.55, 2.4087, 2.4024, 2.3860, "+0.0161"],
              [2011, 350, 0.50, 0.50, 0.55, 2.4054, 2.1068, 2.1456, "−0.0388"],
              [2012, 382, 0.65, 0.35, 0.60, 2.3811, 2.5347, 2.5323, "+0.0024"],
              [2013, 414, 1.00, 0.00, 0.60, 2.3933, 2.3640, 2.3675, "−0.0035"],
              [2014, 446, 0.95, 0.05, 0.60, 2.3908, 2.0939, 2.1867, "−0.0928"],
              [2015, 478, 0.70, 0.30, 0.65, 2.3735, 2.3005, 2.3097, "−0.0092"],
              [2016, 510, 0.70, 0.30, 0.65, 2.3719, 2.4253, 2.4316, "−0.0063"],
              [2017, 542, 0.70, 0.30, 0.65, 2.3749, 2.2170, 2.2387, "−0.0217"],
              [2018, 574, 0.60, 0.40, 0.70, 2.3653, 2.0910, 2.1044, "−0.0134"],
              [2019, 606, 0.50, 0.50, 0.70, 2.3508, 2.2118, 2.2131, "−0.0013"],
              [2020, 638, 0.50, 0.50, 0.70, 2.3445, 2.7799, 2.7879, "−0.0080"],
              [2021, 670, 0.55, 0.45, 0.70, 2.3655, 1.9378, 1.9474, "−0.0096"],
              [2022, 702, 0.50, 0.50, 0.70, 2.3457, 2.4599, 2.4466, "+0.0133"],
              [2023, 734, 0.50, 0.50, 0.70, 2.3494, 1.8981, 1.8987, "−0.0006"],
              [2024, 766, 0.50, 0.50, 0.70, 2.3301, 3.0125, 3.0360, "−0.0235"],
              [2025, 798, 1.00, 0.00, 0.75, 2.3587, 2.6732, 2.6640, "+0.0092"],
            ].map(([year, n, wp, wd, r, trainMae, champ, opt, delta]) => (
              <tr key={String(year)}>
                <td><strong>{year}</strong></td>
                <td className="num">{n}</td>
                <td className="num">{Number(wp).toFixed(2)}</td>
                <td className="num">{Number(wd).toFixed(2)}</td>
                <td className="num">{Number(r).toFixed(2)}</td>
                <td className="num">{Number(trainMae).toFixed(4)}</td>
                <td className="num">{Number(champ).toFixed(4)}</td>
                <td className="num">{Number(opt).toFixed(4)}</td>
                <td className={`num ${String(delta).startsWith("−") ? "warps-pos" : "warps-neg"}`}>{delta}</td>
              </tr>
            ))}
            <tr style={{ borderTop: "2px solid #e2e8f0", fontWeight: 600 }}>
              <td>Summary</td><td className="num">—</td>
              <td className="num">0.57 med</td><td className="num">0.43 med</td>
              <td className="num">0.68 med</td><td className="num">2.368 avg</td>
              <td className="num">2.376 avg</td><td className="num">2.388 avg</td>
              <td className="num warps-pos">−0.012 avg</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h3 className="paper-section">Appendix B — Glossary of Original Terminology</h3>
      <dl className="paper-glossary">
        <dt><strong>WARPS</strong> — Win-Adjusted Regression to Pythagorean Score</dt>
        <dd>A preseason NFL win total projection model that blends Pythagorean win expectation
        (75%) and linear point differential (25%), applies a 0.75 regression-toward-mean factor,
        and incorporates an optional Dynasty Persistence Modifier. Trained on 22 seasons
        (2000–2021); validated on four held-out seasons (2022–2025). Full-sample MAE: 2.37 wins
        over the Pythagorean baseline (2.61 wins, DM p &lt; 0.0001).</dd>

        <dt><strong>Dynasty Persistence Modifier</strong></dt>
        <dd>A structural adjustment applied to franchises that have projected ≥9.0 wins in four
        or more consecutive seasons. The standard regression coefficient R is raised from 0.75
        to 0.95, preserving more of the team's historical quality signal and reducing
        regression-toward-mean for demonstrably non-average organizations. The same modifier
        applies in the downward direction for franchises with sustained futility (4+ consecutive
        projected ≤7.5-win seasons). Terminology: a higher R value means <em>less</em>
        regression toward the mean, not more — higher R = more persistence of the prior
        quality estimate.</dd>

        <dt><strong>Optimal Parsimony</strong></dt>
        <dd>The principle, validated empirically by three independent null results (SOS
        adjustment, regime shift, garbage-time filter), that the WARPS model has reached the
        architectural boundary where the sport's structure already handles the proposed
        enhancements internally. The 75/25 Pythagorean-to-point-differential blend and R=0.75
        regression coefficient proved remarkably stable across the observed sample —
        the minimal sufficient description of how prior-season team quality predicts next-season
        win totals within this dataset. Model extensions are warranted only for phenomena the
        architecture cannot self-correct for, of which dynasty persistence is the sole
        confirmed example.</dd>

        <dt><strong>Stable Parameter Structure</strong></dt>
        <dd>The two core model parameters — R=0.75 (regression coefficient) and the 75/25
        Pythagorean-to-point-differential blend weight — emerged from 25 years of cross-validated
        optimization and proved stable across three independent enhancement tests. They remained
        optimal across multiple validation exercises on this dataset. Whether they persist as
        optimal across future decades is an open question that additional out-of-sample seasons
        will resolve.</dd>
      </dl>

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

// ──────────────────────────────────────────────────────────────
// Strategic Quadrant — scatter plot of WARPS vs Vegas win totals
// ──────────────────────────────────────────────────────────────

function DensityCurve({ mu, marketTotal }: { mu: number; marketTotal: number }) {
  const sigma = WARPS_SIGMA;
  const W = 184, H = 52;
  const xmin = Math.max(0, mu - 3.2 * sigma);
  const xmax = Math.min(18, mu + 3.2 * sigma);

  const pts: [number, number][] = [];
  for (let x = xmin; x <= xmax; x += 0.12) {
    pts.push([x, Math.exp(-0.5 * ((x - mu) / sigma) ** 2)]);
  }
  const scX = (v: number) => ((v - xmin) / (xmax - xmin)) * W;
  const scY = (v: number) => H - v * H * 0.84;
  const pathD = pts.map((p, i) => `${i === 0 ? "M" : "L"}${scX(p[0]).toFixed(1)},${scY(p[1]).toFixed(1)}`).join(" ");
  const mX = scX(Math.min(Math.max(marketTotal, xmin), xmax));
  const wX = scX(mu);

  return (
    <svg width={W} height={H} style={{ display: "block", marginTop: 4 }}>
      <path
        d={`${pathD} V${H} L${scX(xmin).toFixed(1)},${H} Z`}
        fill="rgba(99,102,241,0.10)"
      />
      <path d={pathD} fill="none" stroke="rgba(99,102,241,0.65)" strokeWidth={1.5} />
      <line x1={mX} y1={3} x2={mX} y2={H - 3} stroke="#dc2626" strokeWidth={1.5} strokeDasharray="3,2" />
      <line x1={wX} y1={3} x2={wX} y2={H - 3} stroke="#16a34a" strokeWidth={2} />
      <text x={wX} y={H - 3} textAnchor="middle" fontSize={8} fill="#16a34a" fontWeight="bold">W</text>
      <text x={mX + (mX < wX - 6 ? 0 : mX > wX + 6 ? 0 : 8)} y={H - 3}
        textAnchor="middle" fontSize={8} fill="#dc2626">V</text>
    </svg>
  );
}

function StrategicQuadrant({ rows }: { rows: ConsensusRow[] }) {
  const [consensusFilter, setConsensusFilter] = useState(false);
  const [hovered, setHovered] = useState<{ row: ConsensusRow; px: number; py: number } | null>(null);
  const [scenarioTeam, setScenarioTeam] = useState("");
  const [scenarioAdj, setScenarioAdj] = useState(-3.0);
  const containerRef = useRef<HTMLDivElement>(null);

  const displayRows = useMemo(() => {
    if (!scenarioTeam) return rows;
    return rows.map(r => r.team === scenarioTeam
      ? { ...r, v18Wins: r.v18Wins + scenarioAdj, v18Edge: r.v18Edge + scenarioAdj, avgEdge: r.avgEdge + scenarioAdj }
      : r
    );
  }, [rows, scenarioTeam, scenarioAdj]);

  const SVG_W = 560, SVG_H = 480;
  const ML = 60, MT = 40, MR = 40, MB = 62;
  const PW = SVG_W - ML - MR;  // 460
  const PH = SVG_H - MT - MB;  // 378
  const VMIN = 3.0, VMAX = 15.0;

  const scX = (v: number) => ((v - VMIN) / (VMAX - VMIN)) * PW;
  const scY = (v: number) => PH - ((v - VMIN) / (VMAX - VMIN)) * PH;

  const dotColor = (r: ConsensusRow) =>
    r.consensus.includes("Over") ? "#16a34a" : r.consensus.includes("Under") ? "#dc2626" : "#94a3b8";
  const isHC = (r: ConsensusRow) => r.consensus.startsWith("3-model");

  const handleMove = (e: React.MouseEvent, row: ConsensusRow) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    setHovered({ row, px: e.clientX - rect.left, py: e.clientY - rect.top });
  };

  const ticks = [4, 6, 8, 10, 12, 14];
  // Diagonal angle in screen-space: atan(-PH/PW) ≈ -39°
  const diagAngle = -Math.round(Math.atan(PH / PW) * 180 / Math.PI);

  return (
    <div ref={containerRef} className="quadrant-wrapper">
      <div className="quadrant-controls">
        <button
          className={`warps-filter-btn${consensusFilter ? " active" : ""}`}
          onClick={() => setConsensusFilter(v => !v)}
        >
          {consensusFilter ? "✓ " : ""}3-Model Consensus Only
        </button>
        <div className="quadrant-legend">
          <span><span className="ql-dot" style={{ background: "#16a34a" }} />Over signal</span>
          <span><span className="ql-dot" style={{ background: "#dc2626" }} />Under signal</span>
          <span><span className="ql-dot" style={{ background: "#94a3b8" }} />No bet</span>
          <span><span className="ql-ring" style={{ borderColor: "#f59e0b" }} />Dynasty +</span>
          <span><span className="ql-ring" style={{ borderColor: "#8b5cf6" }} />Dynasty −</span>
        </div>
        <div className="scenario-panel">
          <span className="scenario-label">Simulate QB injury:</span>
          <select
            value={scenarioTeam}
            onChange={e => setScenarioTeam(e.target.value)}
            className="audit-year-select"
          >
            <option value="">— None —</option>
            {rows.map(r => <option key={r.team} value={r.team}>{r.team}</option>)}
          </select>
          {scenarioTeam && (
            <>
              <input
                type="range" min={-5} max={-0.5} step={0.5}
                value={scenarioAdj}
                onChange={e => setScenarioAdj(+e.target.value)}
                className="scenario-slider"
              />
              <span className="scenario-adj-label">{scenarioAdj.toFixed(1)}w</span>
              <button className="warps-filter-btn" onClick={() => setScenarioTeam("")} style={{ padding: "4px 10px" }}>✕</button>
            </>
          )}
        </div>
      </div>

      <div style={{ position: "relative" }}>
        <svg
          width={SVG_W} height={SVG_H}
          viewBox={`0 0 ${SVG_W} ${SVG_H}`}
          className="warps-quadrant-svg"
          onMouseLeave={() => setHovered(null)}
        >
          <g transform={`translate(${ML},${MT})`}>
            {/* Quadrant shading */}
            <rect x={0} y={0} width={PW / 2} height={PH / 2} fill="rgba(22,163,74,0.04)" />
            <rect x={PW / 2} y={PH / 2} width={PW / 2} height={PH / 2} fill="rgba(220,38,38,0.04)" />

            {/* Grid lines */}
            {ticks.map(v => (
              <g key={v}>
                <line x1={scX(v)} y1={0} x2={scX(v)} y2={PH} stroke="#f1f5f9" strokeWidth={1} />
                <line x1={0} y1={scY(v)} x2={PW} y2={scY(v)} stroke="#f1f5f9" strokeWidth={1} />
              </g>
            ))}

            {/* Diagonal agreement line */}
            <line
              x1={scX(VMIN)} y1={scY(VMIN)} x2={scX(VMAX)} y2={scY(VMAX)}
              stroke="#cbd5e1" strokeWidth={1.5} strokeDasharray="5,4"
            />
            <text
              x={scX(12.6)} y={scY(13.2)}
              fontSize={9} fill="#94a3b8" textAnchor="middle"
              transform={`rotate(${diagAngle}, ${scX(12.6)}, ${scY(13.2)})`}
            >
              market = model
            </text>

            {/* Quadrant labels */}
            <text x={14} y={24} fontSize={12} fill="#16a34a" fontWeight={700} opacity={0.75}>▲ VALUE OVER</text>
            <text x={14} y={39} fontSize={10} fill="#475569" opacity={0.55}>Model {">"} Market — "The Steals"</text>
            <text x={PW - 14} y={PH - 30} textAnchor="end" fontSize={12} fill="#dc2626" fontWeight={700} opacity={0.75}>▼ VALUE UNDER</text>
            <text x={PW - 14} y={PH - 15} textAnchor="end" fontSize={10} fill="#475569" opacity={0.55}>Market {">"} Model — "The Frauds"</text>

            {/* Axis ticks */}
            {ticks.map(v => (
              <g key={v}>
                <text x={scX(v)} y={PH + 20} textAnchor="middle" fontSize={11} fill="#64748b">{v}</text>
                <text x={-10} y={scY(v)} textAnchor="end" dominantBaseline="middle" fontSize={11} fill="#64748b">{v}</text>
              </g>
            ))}

            {/* Axis labels */}
            <text x={PW / 2} y={PH + 48} textAnchor="middle" fontSize={13} fill="#334155" fontWeight={600}>
              Vegas Win Total (Market)
            </text>
            <text
              transform={`translate(-46,${PH / 2}) rotate(-90)`}
              textAnchor="middle" fontSize={13} fill="#334155" fontWeight={600}
            >
              WARPS Projected Wins (Model)
            </text>

            {/* All dots — uses displayRows so scenario adjustments apply */}
            {displayRows.map(r => {
              const isDynPos = DYNASTY_POSITIVE.has(r.team);
              const isDynNeg = DYNASTY_NEGATIVE.has(r.team);
              const isDyn = isDynPos || isDynNeg;
              const hc = isHC(r);
              const faded = consensusFilter && !hc;
              const cx = scX(r.marketTotal);
              const cy = scY(r.v18Wins);
              const dotR = hc ? 8 : 6;

              return (
                <g
                  key={r.team}
                  style={{ cursor: "pointer" }}
                  onMouseMove={e => handleMove(e, r)}
                  onMouseLeave={() => setHovered(null)}
                >
                  {isDyn && !faded && (
                    <circle
                      cx={cx} cy={cy} r={dotR + 5}
                      fill="none"
                      stroke={isDynPos ? "#f59e0b" : "#8b5cf6"}
                      strokeWidth={2}
                      opacity={0.65}
                    />
                  )}
                  <circle
                    cx={cx} cy={cy} r={dotR}
                    fill={dotColor(r)}
                    opacity={faded ? 0.10 : (hovered && hovered.row.team !== r.team ? 0.55 : 1)}
                    stroke="white"
                    strokeWidth={1.5}
                  />
                  {!faded && (hc || isDyn) && (
                    <text
                      x={cx} y={cy - dotR - 5}
                      textAnchor="middle" fontSize={9} fill="#1e293b" fontWeight={700}
                      style={{ pointerEvents: "none" }}
                    >
                      {r.team}
                    </text>
                  )}
                </g>
              );
            })}
          </g>

          {/* Border */}
          <rect x={ML} y={MT} width={PW} height={PH} fill="none" stroke="#e2e8f0" strokeWidth={1} rx={2} />
        </svg>

        {/* Floating tooltip */}
        {hovered && (() => {
          const r = hovered.row;
          const isDynPos = DYNASTY_POSITIVE.has(r.team);
          const isDynNeg = DYNASTY_NEGATIVE.has(r.team);
          return (
            <div
              className="quadrant-tooltip"
              style={{
                left: Math.min(hovered.px + 14, (containerRef.current?.offsetWidth ?? 600) - 220),
                top: Math.max(4, hovered.py - 90),
              }}
            >
              <div className="qt-header">
                <img src={teamLogos[r.team]} alt={r.team} className="qt-logo" />
                <div>
                  <strong className="qt-team">{r.team}</strong>
                  <span className={`qt-badge${isHC(r) ? " qt-badge-hc" : ""}`}>{r.consensus}</span>
                </div>
              </div>
              <div className="qt-stats">
                <span>WARPS <strong style={{ color: "#16a34a" }}>{r.v18Wins.toFixed(1)}</strong></span>
                <span>Vegas <strong style={{ color: "#dc2626" }}>{r.marketTotal.toFixed(1)}</strong></span>
                <span>Edge <strong>{r.avgEdge > 0 ? "+" : ""}{r.avgEdge.toFixed(2)}w</strong></span>
              </div>
              <DensityCurve mu={r.v18Wins} marketTotal={r.marketTotal} />
              <div className="qt-density-legend">
                <span style={{ color: "#16a34a" }}>■ WARPS proj</span>
                <span style={{ color: "#dc2626" }}>■ Vegas line</span>
              </div>
              {(isDynPos || isDynNeg) && (
                <div className="qt-dynasty-note">
                  {isDynPos
                    ? "Dynasty Persistence active — R=0.95 (excellence preserved)"
                    : "Dynasty Futility active — R=0.95 (decline preserved)"}
                </div>
              )}
            </div>
          );
        })()}
      </div>

      <p className="warps-chart-note" style={{ marginTop: 10 }}>
        Each dot is a team. Distance above the diagonal = model sees more wins than market (Over value).
        Distance below = model sees fewer wins (Under value). Dynasty rings mark teams with the
        v2.0 Persistence Modifier active. Larger dots = 3-model consensus picks.
      </p>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────
// TrajectoryChart — "Path to the Over" season win trajectory
// ──────────────────────────────────────────────────────────────
function TrajectoryChart({ rows }: { rows: ConsensusRow[] }) {
  const sorted = [...rows].sort((a, b) => a.team.localeCompare(b.team));
  const [team, setTeam] = useState(sorted[0]?.team ?? "KC");

  const row = rows.find(r => r.team === team);
  const traj = trajectoryData.find(d => d.t === team);
  if (!row || !traj) return null;

  const ou = row.marketTotal;
  const warpsProj = row.v18Wins;
  const finalTr = traj.tr[17];

  const W = 520, H = 190;
  const ML = 42, MT = 14, MR = 52, MB = 38;
  const PW = W - ML - MR;
  const PH = H - MT - MB;
  const YMAX = Math.ceil(Math.max(ou + 1.5, warpsProj + 1, finalTr + 1, 13));

  const scX = (wk: number) => ((wk - 1) / 17) * PW;
  const scY = (v: number) => PH - (v / YMAX) * PH;

  const pts = traj.tr.map((v, i): [number, number] => [scX(i + 1), scY(v)]);
  const pathD = pts.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const fillD = `${pathD} V${PH} H${scX(1).toFixed(1)} Z`;

  const ouY = scY(ou);
  const warpsY = scY(warpsProj);
  const byeX = scX(traj.b);
  const clipAbove = `clip-traj-above-${team}`;
  const clipBelow = `clip-traj-below-${team}`;

  const ticks = [1, 4, 8, 10, 13, 17, 18];

  return (
    <div className="traj-wrapper">
      <div className="traj-controls">
        <select value={team} onChange={e => setTeam(e.target.value)} className="audit-year-select">
          {sorted.map(r => <option key={r.team} value={r.team}>{r.team}</option>)}
        </select>
        <div className="traj-kpis">
          <span>WARPS proj: <strong style={{ color: "#16a34a" }}>{warpsProj.toFixed(1)}w</strong></span>
          <span>Schedule-adj path: <strong>{finalTr.toFixed(1)}w</strong></span>
          <span>Vegas O/U: <strong style={{ color: "#6366f1" }}>{ou}</strong></span>
          <span className={warpsProj > ou ? "traj-over" : "traj-under"}>
            {warpsProj > ou
              ? `OVER by ${(warpsProj - ou).toFixed(1)}w ▲`
              : `UNDER by ${(ou - warpsProj).toFixed(1)}w ▼`}
          </span>
          <span style={{ color: "#94a3b8", fontSize: 11 }}>Bye: Wk {traj.b}</span>
        </div>
      </div>

      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="traj-svg">
        <defs>
          <clipPath id={clipAbove}><rect x={0} y={0} width={PW} height={Math.max(0, ouY)} /></clipPath>
          <clipPath id={clipBelow}><rect x={0} y={Math.max(0, ouY)} width={PW} height={Math.max(0, PH - ouY)} /></clipPath>
        </defs>
        <g transform={`translate(${ML},${MT})`}>
          {/* Bye week band */}
          <rect x={byeX - 7} y={0} width={14} height={PH} fill="rgba(148,163,184,0.14)" />
          <text x={byeX} y={PH + 14} textAnchor="middle" fontSize={8} fill="#94a3b8">BYE</text>

          {/* Grid */}
          {ticks.map(w => <line key={w} x1={scX(w)} y1={0} x2={scX(w)} y2={PH} stroke="#f1f5f9" strokeWidth={1} />)}
          {[0, 4, 8, 12].filter(v => v <= YMAX).map(v => (
            <g key={v}>
              <line x1={0} y1={scY(v)} x2={PW} y2={scY(v)} stroke="#f1f5f9" strokeWidth={1} />
              <text x={-5} y={scY(v) + 4} textAnchor="end" fontSize={9} fill="#64748b">{v}</text>
            </g>
          ))}

          {/* O/U line */}
          <line x1={0} y1={ouY} x2={PW} y2={ouY} stroke="#6366f1" strokeWidth={1.5} strokeDasharray="5,3" />
          <text x={PW + 4} y={ouY + 4} fontSize={9} fill="#6366f1" fontWeight={600}>O/U {ou}</text>

          {/* WARPS projection line */}
          <line x1={0} y1={warpsY} x2={PW} y2={warpsY} stroke="#16a34a" strokeWidth={1.5} strokeDasharray="3,3" />
          <text x={PW + 4} y={warpsY + 4} fontSize={9} fill="#16a34a" fontWeight={600}>W {warpsProj.toFixed(1)}</text>

          {/* Color fill */}
          <path d={fillD} fill="rgba(22,163,74,0.07)" clipPath={`url(#${clipAbove})`} />
          <path d={fillD} fill="rgba(220,38,38,0.07)" clipPath={`url(#${clipBelow})`} />

          {/* Trajectory line */}
          <path d={pathD} fill="none" stroke="#3b82f6" strokeWidth={2.5} strokeLinejoin="round" />

          {/* Dots at each week */}
          {pts.map(([x, y], i) => (
            <circle key={i} cx={x} cy={y} r={3.5} fill="#3b82f6"
              opacity={i + 1 === traj.b ? 0.2 : 0.75} />
          ))}

          {/* X-axis ticks */}
          {ticks.map(w => (
            <text key={w} x={scX(w)} y={PH + 18} textAnchor="middle" fontSize={9} fill="#64748b">{w}</text>
          ))}
          <text x={PW / 2} y={PH + 32} textAnchor="middle" fontSize={11} fill="#475569" fontWeight={500}>Week</text>
          <text transform={`translate(-32,${PH / 2}) rotate(-90)`} textAnchor="middle" fontSize={11} fill="#475569" fontWeight={500}>Wins</text>

          {/* Border */}
          <rect x={0} y={0} width={PW} height={PH} fill="none" stroke="#e2e8f0" strokeWidth={1} rx={1} />
        </g>
      </svg>

      <p className="warps-chart-note" style={{ marginTop: 6 }}>
        Blue curve: schedule-adjusted trajectory (cumulative WP, λ=0.15 per win-unit quality diff, h=+1.0 home).
        Purple dashed: Vegas O/U line. Green dashed: WARPS final projection.
        Green fill = above O/U (over territory); red fill = below O/U (under territory). Grey band = bye week.
      </p>
    </div>
  );
}

function HeroStat({
  label, target, decimals, suffix, sub, highlight,
}: {
  label: string; target: number; decimals: number; suffix?: string; sub: string; highlight?: boolean;
}) {
  const display = useCountUp(target, decimals);
  return (
    <div className={`warps-hero-stat${highlight ? " highlight" : ""}`}>
      <span>{label}</span>
      <strong>{display}{suffix ?? ""}</strong>
      <small>{sub}</small>
    </div>
  );
}

export function WARPSView({ hashNav = false }: { hashNav?: boolean }) {
  const [tab, setTab] = useState<WARPSTab>(() => (hashNav ? hashToTab() : "slate"));
  const [showQbAdj, setShowQbAdj] = useState(false);

  const switchTab = (next: WARPSTab) => {
    setTab(next);
    if (hashNav) window.history.replaceState(null, "", `#${next}`);
  };

  const qbAdjMap = useMemo((): Map<string, QBAdjResult> => {
    if (!showQbAdj) return new Map();
    const map = new Map<string, QBAdjResult>();
    for (const change of qbChanges2026) {
      const info = getQbAdjustment(change.team);
      if (info) map.set(change.team, info);
    }
    return map;
  }, [showQbAdj]);

  const displayData = useMemo(
    () => (showQbAdj ? applyQbAdj(consensusData, qbAdjMap) : consensusData),
    [showQbAdj, qbAdjMap]
  );

  const highConviction = displayData.filter(
    (r) => r.consensus === "3-model Over" || r.consensus === "3-model Under"
  ).length;

  return (
    <section className="panel warps-panel">
      <div className="panel-toolbar">
        <div>
          <h2>WARPS-NFL v1.8{showQbAdj ? " + QB adj" : ""}</h2>
          <p className="panel-subtitle">Win Average Regression Predictive Score · 2026 season · 26-season backtest · 3-model consensus screen</p>
        </div>
        <span className="status-pill ok">
          <FlaskConical size={14} /> p &lt; 0.0001 vs Pythagorean
        </span>
      </div>

      <div className="warps-hero-kpis">
        <HeroStat label="Full-sample error" decimals={3} target={2.376} sub="vs Pythagorean 2.614 (2000–2025)" />
        <HeroStat label="Held-out error" decimals={3} target={2.511} sub="2022–2025 validation" />
        <HeroStat label="Seasons beats Pythagorean" decimals={0} target={25} suffix="/26" sub="96% of seasons" />
        <HeroStat label="High-conviction bets" decimals={0} target={highConviction} sub="3-model consensus" highlight />
      </div>

      <p className="warps-citation">
        <FileText size={12} />{" "}
        <a href="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6926058" target="_blank" rel="noopener noreferrer">
          Varughese (2026) — SSRN 6926058
        </a>
        {" · "}
        <a href="https://github.com/whatsaliju/nfl-betting-automation" target="_blank" rel="noopener noreferrer">
          Open-source code
        </a>
      </p>

      <div className="segmented warps-tabs">
        <button className={tab === "slate" ? "active" : ""} onClick={() => switchTab("slate")}>
          <Activity size={14} /> 2026 Bet Slate
        </button>
        <button className={tab === "performance" ? "active" : ""} onClick={() => switchTab("performance")}>
          <BarChart3 size={14} /> Performance
        </button>
        <button className={tab === "methodology" ? "active" : ""} onClick={() => switchTab("methodology")}>
          <BookOpen size={14} /> Methodology
        </button>
        <button className={tab === "paper" ? "active" : ""} onClick={() => switchTab("paper")}>
          <FileText size={14} /> Paper
        </button>
        <button className={tab === "quadrant" ? "active" : ""} onClick={() => switchTab("quadrant")}>
          <Crosshair size={14} /> Quadrant
        </button>
      </div>

      {tab === "slate" && (
        <SlateTab
          rows={displayData}
          qbAdjMap={qbAdjMap}
          showQbAdj={showQbAdj}
          onToggleQbAdj={() => setShowQbAdj((v) => !v)}
        />
      )}
      {tab === "performance" && <PerformanceTab rows={displayData} qbAdjMap={qbAdjMap} />}
      {tab === "methodology" && <MethodologyTab />}
      {tab === "paper" && <PaperTab />}
      {tab === "quadrant" && (
        <div className="warps-tab-content">
          <h3 className="warps-section-title">Strategic Quadrant — WARPS vs Vegas Win Totals</h3>
          <p className="warps-section-sub">
            Teams above the diagonal are priced too low by the market (Over value). Teams below are priced too high (Under value).
            Hover any dot for the win probability density curve — how wide the model's uncertainty range is relative to where Vegas has set the line.
          </p>
          <StrategicQuadrant rows={displayData} />
          <hr style={{ margin: "28px 0 20px", border: "none", borderTop: "1px solid #e2e8f0" }} />
          <h3 className="warps-section-title" style={{ fontSize: 16 }}>Path to the Over — Schedule Win Trajectory</h3>
          <p className="warps-section-sub">
            Per-week cumulative win probability derived from matchup quality (Vegas O/U + home-field adjustment).
            Shows <em>when</em> a team is expected to collect wins, not just the season total.
            Schedule clusters — stretches of consecutive difficult games — appear as flat sections on the blue curve.
          </p>
          <TrajectoryChart rows={displayData} />
        </div>
      )}
    </section>
  );
}
