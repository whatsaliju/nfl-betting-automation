import { Activity, BarChart3, BookOpen, ChevronDown, ChevronUp, FlaskConical, TrendingDown, TrendingUp } from "lucide-react";
import { type ReactNode, useState } from "react";
import { bootstrapStats, byYearData, calibrationData, consensusData, metricRanking } from "../data/warpsData";

type WARPSTab = "slate" | "performance" | "methodology";

function consensusClass(c: string): string {
  if (c === "3-model Over") return "consensus-3over";
  if (c === "2-Strong Over") return "consensus-2over";
  if (c === "3-model Under") return "consensus-3under";
  if (c === "2-Strong Under") return "consensus-2under";
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
        <span><span className="legend-dot" style={{ background: "#1d4ed8" }} /> WARPS v1.7</span>
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
      <p className="warps-chart-note">Green ✓ = WARPS beats Pythagorean that season. Train: 2015–2021 · Validation: 2022–2025</p>
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

function StatCard({ label, value, sub, highlight }: { label: string; value: string; sub?: string; highlight?: boolean }) {
  return (
    <div className={`warps-stat-card ${highlight ? "highlight" : ""}`}>
      <span className="warps-stat-label">{label}</span>
      <strong className="warps-stat-value">{value}</strong>
      {sub && <span className="warps-stat-sub">{sub}</span>}
    </div>
  );
}

function SlateTab() {
  const tiers = [
    { label: "3-Model Consensus Overs", key: "3-model Over", icon: <TrendingUp size={15} /> },
    { label: "2-Strong Overs", key: "2-Strong Over", icon: <TrendingUp size={15} /> },
    { label: "3-Model Consensus Unders", key: "3-model Under", icon: <TrendingDown size={15} /> },
    { label: "2-Strong Unders", key: "2-Strong Under", icon: <TrendingDown size={15} /> },
  ];

  return (
    <div className="warps-slate">
      <div className="warps-slate-note">
        <Activity size={14} />
        Consensus requires ≥2 of 3 models (v1.5d · v1.6 · v1.7) to agree in direction.
        Strong Over/Under = edge ≥ 1 win. Bet-worthy = consensus tier only.
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
                  <th>v1.7 edge</th>
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
                    <td>{row.v17Wins.toFixed(1)}</td>
                    <td className={row.v17Edge >= 0 ? "warps-pos" : "warps-neg"}>{row.v17Edge > 0 ? "+" : ""}{row.v17Edge.toFixed(2)}</td>
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
      <div className="warps-kpi-grid">
        <StatCard
          label="Full-sample MAE"
          value={bs.warpsMaeFull.toFixed(3)}
          sub={`95% CI [${bs.warpsMaeFullCi[0].toFixed(2)}, ${bs.warpsMaeFullCi[1].toFixed(2)}]`}
          highlight
        />
        <StatCard label="Validation MAE (2022–25)" value={bs.warpsMaeVal.toFixed(3)} sub={`95% CI [${bs.warpsMaeValCi[0].toFixed(2)}, ${bs.warpsMaeValCi[1].toFixed(2)}]`} />
        <StatCard label="Pythagorean MAE (baseline)" value={bs.pythMaeFull.toFixed(3)} sub="full sample" />
        <StatCard label="Prior wins MAE (baseline)" value={bs.pwMaeFull.toFixed(3)} sub="full sample" />
        <StatCard label="WARPS beats Pythagorean" value={`${bs.seasonsBeatingPyth}/${bs.totalSeasons}`} sub="seasons (100%)" highlight />
        <StatCard label="Avg improvement vs Pythagorean" value="−0.169" sub="wins/team (full sample)" />
        <StatCard label="Avg improvement vs prior wins" value="−0.437" sub="wins/team (full sample)" />
        <StatCard label="DM test vs Pythagorean" value="p = 0.0002" sub="Diebold-Mariano, full sample" highlight />
      </div>

      <h4 className="warps-subsection">Diebold-Mariano Statistical Tests</h4>
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
            <td>Full (2015–25)</td>
            <td className="warps-pos">−0.169</td>
            <td>{bs.dmVsPythFull.stat.toFixed(3)}</td>
            <td>{bs.dmVsPythFull.pval.toFixed(4)}</td>
            <td>{sigBadge(bs.dmVsPythFull.sig)}</td>
            <td>CI entirely negative</td>
          </tr>
          <tr>
            <td>WARPS vs Prior wins</td>
            <td>Full (2015–25)</td>
            <td className="warps-pos">−0.437</td>
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
            <td>WARPS vs Prior wins</td>
            <td>Validation (2022–25)</td>
            <td className="warps-pos">−0.408</td>
            <td>{bs.dmVsPwVal.stat.toFixed(3)}</td>
            <td>{bs.dmVsPwVal.pval.toFixed(4)}</td>
            <td>{sigBadge(bs.dmVsPwVal.sig)}</td>
            <td>CI entirely negative</td>
          </tr>
        </tbody>
      </table>
      <p className="warps-chart-note">Bootstrap CIs: 10,000 paired resamplings. Negative MAE diff = WARPS better.</p>

      <h4 className="warps-subsection">Season-by-Season MAE — WARPS vs Baselines</h4>
      <ByYearChart />

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
            forecasting model for NFL teams. It converts season-level efficiency statistics from the prior
            season into a probabilistic win projection adjusted for regression to the mean and market spread signals.
          </p>
          <p>
            The core insight is that <strong>Pythagorean win expectation</strong> (exponent 2.37) is the
            single strongest predictor of future wins, and that a principled composite of passing EPA,
            point differential, and Pythagorean — weighted heavily toward Pythagorean — outperforms any
            single metric on held-out validation data spanning 11 NFL seasons (2015–2025).
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
            <tr><td>Pythagorean weight</td><td>1.00 (solo)</td><td>0.05–1.00 simplex</td></tr>
            <tr><td>Point diff weight</td><td>0.00</td><td>0.05–1.00 simplex</td></tr>
            <tr><td>Pass EPA weight</td><td>0.00</td><td>0.05–1.00 simplex</td></tr>
            <tr><td>Regression factor</td><td>0.75</td><td>0.50, 0.60, 0.65, 0.70, 0.75</td></tr>
            <tr><td>Logit scale</td><td>5.5</td><td>4.0, 4.5, 5.0, 5.5, 6.0, 6.5</td></tr>
            <tr><td>SOS weight</td><td>0.0 (diagnostic only)</td><td>0.0, 0.1, 0.2</td></tr>
            <tr><td>Grid search size</td><td>180 hyperparameter combos + 231 simplex + 300 biased Dirichlet</td><td>—</td></tr>
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
            Parameters were selected using a strict train/validation split: <strong>2015–2021 (train)</strong>
            and <strong>2022–2025 (validation)</strong>. Champion selection used validation MAE, not training MAE,
            to prevent overfitting.
          </p>
          <p>
            A random Dirichlet weight search (n=300, α biased toward Pythagorean) was run on training data,
            then the best candidates were re-evaluated on the held-out validation window. The champion
            (solo Pythagorean, pyth=1.0) was robust: it reached identical validation MAE as all composite
            configs, with zero additional complexity.
          </p>
          <p>
            Bootstrap confidence intervals (10,000 paired resamplings) confirmed WARPS improvements over
            Pythagorean are statistically significant (DM p=0.0002 full-sample; p=0.0016 validation-only).
          </p>
        </div>
      ),
    },
  ];

  return (
    <div className="warps-methodology">
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

export function WARPSView() {
  const [tab, setTab] = useState<WARPSTab>("slate");

  const highConviction = consensusData.filter(
    (r) => r.consensus === "3-model Over" || r.consensus === "3-model Under"
  ).length;

  return (
    <section className="panel warps-panel">
      <div className="panel-toolbar">
        <div>
          <h2>WARPS-NFL v1.7</h2>
          <p className="panel-subtitle">Win Average Regression Predictive Score · 2026 season · 3-model consensus screen</p>
        </div>
        <span className="status-pill ok">
          <FlaskConical size={14} /> p = 0.0002 vs Pythagorean
        </span>
      </div>

      <div className="warps-hero-kpis">
        <div className="warps-hero-stat">
          <span>Full-sample MAE</span>
          <strong>2.365</strong>
          <small>vs Pyth 2.532</small>
        </div>
        <div className="warps-hero-stat">
          <span>Validation MAE</span>
          <strong>2.514</strong>
          <small>2022–2025</small>
        </div>
        <div className="warps-hero-stat">
          <span>Seasons beats Pyth</span>
          <strong>11/11</strong>
          <small>100% win rate</small>
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
      </div>

      {tab === "slate" && <SlateTab />}
      {tab === "performance" && <PerformanceTab />}
      {tab === "methodology" && <MethodologyTab />}
    </section>
  );
}
