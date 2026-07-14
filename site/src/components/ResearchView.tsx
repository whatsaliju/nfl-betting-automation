import { AlertTriangle, Brain, CheckCircle2, FlaskConical, ShieldCheck, TrendingUp } from "lucide-react";
import type { FactorLeaderboardRow, PolicySimulation, PromotedFactor, PromotionOverlaySimulation, ResearchSummary } from "../types";

function pct(value?: number | null) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "n/a";
}

function signed(value?: number | null) {
  if (typeof value !== "number") return "n/a";
  return `${value > 0 ? "+" : ""}${(value * 100).toFixed(1)} pts`;
}

function signedRaw(value?: number | null) {
  if (typeof value !== "number") return "n/a";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

function record(row: Pick<PolicySimulation, "wins" | "losses">) {
  return `${row.wins ?? 0}-${row.losses ?? 0}`;
}

function factorRecord(row: Pick<FactorLeaderboardRow, "wins" | "losses">) {
  return `${row.wins ?? 0}-${row.losses ?? 0}`;
}

function promotedRecord(row: Pick<PromotedFactor, "wins" | "losses">) {
  return `${row.wins ?? 0}-${row.losses ?? 0}`;
}

function overlayRecord(row: Pick<PromotionOverlaySimulation, "wins" | "losses">) {
  return `${row.wins ?? 0}-${row.losses ?? 0}`;
}

const fallback: ResearchSummary = {
  available: false,
  status: "BUILDING_SAMPLE",
  sample_warning: true,
  feature_rows: 0,
  graded_bets: 0,
  wins: 0,
  losses: 0,
  win_rate: null,
  observations: ["Research summary is not available in the current engine feed."],
  candidate_policy: {
    status: "monitor_only",
    recommendation: "Keep the selector as the source of truth while feature evidence is still building."
  },
  top_policy_simulations: [],
  top_factor_leaderboard: [],
  promotion_summary: {
    production_ready: 0,
    candidate: 0,
    monitor: 0,
    research: 0
  },
  promoted_factors: [],
  promotion_overlay_simulations: [],
  source_reliability: null,
  warps_selector_alignment: null,
  market_router: null,
  clv_audit: null
};

export function ResearchView({ summary }: { summary?: ResearchSummary }) {
  const report = summary || fallback;
  const policies = report.top_policy_simulations || [];
  const baseline = policies.find((row) => row.policy === "baseline");
  const overlays = policies.filter((row) => row.policy !== "baseline");
  const factors = report.top_factor_leaderboard || [];
  const promoted = report.promoted_factors || [];
  const promotionOverlays = report.promotion_overlay_simulations || [];
  const promotionSummary = report.promotion_summary || {};
  const sourceReliability = report.source_reliability;
  const warpsAlignment = report.warps_selector_alignment;
  const marketRouter = report.market_router;
  const clvAudit = report.clv_audit;

  return (
    <section className="panel research-panel">
      <div className="panel-toolbar">
        <div>
          <h2>Model Research</h2>
          <p className="panel-subtitle">Feature learning, policy overlays, and sample discipline</p>
        </div>
        <span className={`research-status ${report.sample_warning ? "warning" : "ok"}`}>
          {report.sample_warning ? <AlertTriangle size={15} /> : <CheckCircle2 size={15} />}
          {report.status.replace(/_/g, " ")}
        </span>
      </div>

      <div className="research-kpis">
        <div>
          <span>Feature Rows</span>
          <strong>{report.feature_rows}</strong>
        </div>
        <div>
          <span>Graded Bets</span>
          <strong>{report.graded_bets}</strong>
        </div>
        <div>
          <span>Replay Record</span>
          <strong>{report.wins}-{report.losses}</strong>
        </div>
        <div>
          <span>Replay Win Rate</span>
          <strong>{pct(report.win_rate)}</strong>
        </div>
        <div>
          <span>Candidates</span>
          <strong>{promotionSummary.candidate ?? 0}</strong>
        </div>
      </div>

      <div className="research-grid">
        <article className="research-card">
          <h3><Brain size={16} /> Current Thesis</h3>
          <p>{report.candidate_policy.recommendation}</p>
          <span>{report.candidate_policy.status.replace(/_/g, " ")}</span>
        </article>
        <article className="research-card">
          <h3><FlaskConical size={16} /> Baseline</h3>
          {baseline ? (
            <p>{record(baseline)} over {baseline.plays} plays at {pct(baseline.win_rate)}.</p>
          ) : (
            <p>No baseline policy simulation is available yet.</p>
          )}
          <span>Selector source of truth</span>
        </article>
        <article className="research-card">
          <h3><TrendingUp size={16} /> WARPS Gate Test</h3>
          {warpsAlignment?.verdict ? (
            <p>{warpsAlignment.verdict.recommendation || "WARPS selector alignment is being monitored."}</p>
          ) : (
            <p>No WARPS selector alignment audit is available yet.</p>
          )}
          <span>{(warpsAlignment?.verdict?.status || "context_only").replace(/_/g, " ")}</span>
        </article>
        <article className="research-card">
          <h3><FlaskConical size={16} /> Market Router</h3>
          {marketRouter?.verdict ? (
            <p>{marketRouter.verdict.recommendation || "Market router evidence is still building."}</p>
          ) : (
            <p>No market router audit is available yet.</p>
          )}
          <span>{(marketRouter?.verdict?.status || "building_sample").replace(/_/g, " ")}</span>
        </article>
        <article className="research-card">
          <h3><ShieldCheck size={16} /> Price Discipline</h3>
          {clvAudit?.verdict ? (
            <p>{clvAudit.verdict.recommendation || "Closing-line value tracking is active."}</p>
          ) : (
            <p>No closing-line value audit is available yet.</p>
          )}
          <span>{pct(clvAudit?.overall?.beat_close_rate)} beat close</span>
        </article>
      </div>

      {report.observations.length > 0 && (
        <div className="research-observations">
          {report.observations.slice(0, 4).map((item) => (
            <p key={item}>{item}</p>
          ))}
        </div>
      )}

      {warpsAlignment && (
        <div className="policy-table-shell">
          <h3 className="table-heading">WARPS Selector Alignment</h3>
          <div className="source-reliability-head">
            <span className={`research-status ${warpsAlignment.verdict?.status === "MONITOR_ONLY" ? "warning" : "ok"}`}>
              {warpsAlignment.verdict?.status || "unknown"}
            </span>
            <span>{warpsAlignment.warps_joined ?? 0}/{warpsAlignment.graded_picks ?? 0} joined</span>
            <span>{warpsAlignment.graded_spread_picks ?? 0} spread picks</span>
            <span>{pct(warpsAlignment.verdict?.no_conflict_policy_delta)} no-conflict delta</span>
          </div>
          <table className="compare-table policy-table">
            <thead>
              <tr>
                <th>WARPS Bucket</th>
                <th>Plays</th>
                <th>Record</th>
                <th>Win Rate</th>
              </tr>
            </thead>
            <tbody>
              {(warpsAlignment.alignment_buckets || []).map((row) => (
                <tr key={row.value}>
                  <td>{row.value.replace(/_/g, " ")}</td>
                  <td>{row.plays ?? 0}</td>
                  <td>{row.wins ?? 0}-{row.losses ?? 0}</td>
                  <td>{pct(row.win_rate)}</td>
                </tr>
              ))}
              {!warpsAlignment.alignment_buckets?.length && (
                <tr>
                  <td colSpan={4}>No WARPS alignment buckets are available yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {marketRouter && (
        <div className="policy-table-shell">
          <h3 className="table-heading">Market Router Ledger</h3>
          <div className="source-reliability-head">
            <span className={`research-status ${marketRouter.verdict?.status === "BUILDING_SAMPLE" ? "warning" : "ok"}`}>
              {marketRouter.verdict?.status || "unknown"}
            </span>
            <span>{marketRouter.ledger_rows ?? 0} ledger rows</span>
            <span>{marketRouter.selected_bets ?? 0} selected bets</span>
            <span>{marketRouter.moneyline_research_rows ?? 0} ML research</span>
          </div>
          <table className="compare-table policy-table">
            <thead>
              <tr>
                <th>Section</th>
                <th>Bucket</th>
                <th>Plays</th>
                <th>Record</th>
                <th>Win Rate</th>
              </tr>
            </thead>
            <tbody>
              {(marketRouter.summary_rows || []).map((row) => (
                <tr key={`${row.section}-${row.bucket}`}>
                  <td>{row.section.replace(/_/g, " ")}</td>
                  <td>{row.bucket.replace(/_/g, " ")}</td>
                  <td>{row.plays ?? 0}</td>
                  <td>{row.wins ?? 0}-{row.losses ?? 0}</td>
                  <td>{pct(row.win_rate)}</td>
                </tr>
              ))}
              {!marketRouter.summary_rows?.length && (
                <tr>
                  <td colSpan={5}>No market router buckets are available yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {clvAudit && (
        <div className="policy-table-shell">
          <h3 className="table-heading">Price Discipline</h3>
          <div className="source-reliability-head">
            <span className={`research-status ${clvAudit.verdict?.status === "BUILDING_SAMPLE" ? "warning" : "ok"}`}>
              {clvAudit.verdict?.status || "unknown"}
            </span>
            <span>{clvAudit.selected_bets ?? 0} selected bets</span>
            <span>{signedRaw(clvAudit.overall?.avg_clv)} avg CLV</span>
            <span>{pct(clvAudit.overall?.beat_close_rate)} beat close</span>
          </div>
          <table className="compare-table policy-table">
            <thead>
              <tr>
                <th>Section</th>
                <th>Bucket</th>
                <th>Plays</th>
                <th>Record</th>
                <th>Avg CLV</th>
                <th>Beat Close</th>
              </tr>
            </thead>
            <tbody>
              {(clvAudit.buckets || []).map((row) => (
                <tr key={`${row.section}-${row.bucket}`}>
                  <td>{row.section.replace(/_/g, " ")}</td>
                  <td>{row.bucket.replace(/_/g, " ")}</td>
                  <td>{row.plays ?? 0}</td>
                  <td>{row.wins ?? 0}-{row.losses ?? 0}</td>
                  <td className={(row.avg_clv ?? 0) >= 0 ? "positive" : "negative"}>{signedRaw(row.avg_clv)}</td>
                  <td>{pct(row.beat_close_rate)}</td>
                </tr>
              ))}
              {!clvAudit.buckets?.length && (
                <tr>
                  <td colSpan={6}>No CLV buckets are available yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="policy-table-shell">
        <h3 className="table-heading">Promotion Rules</h3>
        <table className="compare-table policy-table">
          <thead>
            <tr>
              <th>Factor</th>
              <th>Status</th>
              <th>Allowed</th>
              <th>Plays</th>
              <th>Record</th>
              <th>Lift</th>
              <th>Rule Note</th>
            </tr>
          </thead>
          <tbody>
            {promoted.map((row) => (
              <tr key={row.factor}>
                <td>
                  <span className="policy-name">
                    <ShieldCheck size={14} />
                    {row.factor.replace(/_/g, " ")}
                  </span>
                </td>
                <td>
                  <span className={`promotion-pill ${(row.promotion_status || "research").replace(/_/g, "-")}`}>
                    {(row.promotion_status || "research").replace(/_/g, " ")}
                  </span>
                </td>
                <td>{row.selector_influence_allowed ? "yes" : "no"}</td>
                <td>{row.plays ?? 0}</td>
                <td>{promotedRecord(row)}</td>
                <td className={(row.win_rate_lift ?? 0) >= 0 ? "positive" : "negative"}>{signed(row.win_rate_lift)}</td>
                <td>{row.warnings?.[0] || row.blockers?.[0] || row.recommendation || "n/a"}</td>
              </tr>
            ))}
            {!promoted.length && (
              <tr>
                <td colSpan={7}>No factor promotion report is available yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="policy-table-shell">
        <h3 className="table-heading">Candidate Overlay Tests</h3>
        <table className="compare-table policy-table">
          <thead>
            <tr>
              <th>Overlay</th>
              <th>Plays</th>
              <th>Record</th>
              <th>Win Rate</th>
              <th>Removed</th>
              <th>Delta</th>
              <th>Read</th>
            </tr>
          </thead>
          <tbody>
            {promotionOverlays.map((row) => (
              <tr key={row.overlay}>
                <td>
                  <span className="policy-name">
                    <TrendingUp size={14} />
                    {row.overlay.replace(/_/g, " ")}
                  </span>
                </td>
                <td>{row.plays ?? 0}</td>
                <td>{overlayRecord(row)}</td>
                <td>{pct(row.win_rate)}</td>
                <td>{row.removed_wins ?? 0}-{row.removed_losses ?? 0}</td>
                <td className={(row.win_rate_delta ?? 0) >= 0 ? "positive" : "negative"}>{signed(row.win_rate_delta)}</td>
                <td>{row.recommendation || "n/a"}</td>
              </tr>
            ))}
            {!promotionOverlays.length && (
              <tr>
                <td colSpan={7}>No candidate overlay simulations are available yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="policy-table-shell">
        <h3 className="table-heading">Source Reliability</h3>
        <div className="source-reliability-head">
          <span className={`research-status ${sourceReliability?.overall_status === "OK" ? "ok" : "warning"}`}>
            {sourceReliability?.overall_status || "unknown"}
          </span>
          <span>{sourceReliability?.overall_score ?? "n/a"} score</span>
          <span>{sourceReliability?.weeks_audited ?? 0} weeks audited</span>
        </div>
        {sourceReliability?.recommendations?.length ? (
          <div className="research-observations source-notes">
            {sourceReliability.recommendations.slice(0, 3).map((item) => (
              <p key={item}>{item}</p>
            ))}
          </div>
        ) : null}
        <table className="compare-table policy-table">
          <thead>
            <tr>
              <th>Source</th>
              <th>Avg</th>
              <th>Min</th>
              <th>OK</th>
              <th>Degraded</th>
              <th>Missing</th>
              <th>Warnings</th>
            </tr>
          </thead>
          <tbody>
            {(sourceReliability?.by_source || []).map((row) => (
              <tr key={row.source}>
                <td>{row.source.replace(/_/g, " ")}</td>
                <td>{row.avg_score}</td>
                <td>{row.min_score}</td>
                <td>{row.ok_weeks}</td>
                <td>{row.degraded_weeks}</td>
                <td>{row.missing_weeks}</td>
                <td>{row.total_warnings + row.total_critical_warnings}</td>
              </tr>
            ))}
            {!sourceReliability?.by_source?.length && (
              <tr>
                <td colSpan={7}>No source reliability report is available yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="policy-table-shell">
        <h3 className="table-heading">Policy Simulations</h3>
        <table className="compare-table policy-table">
          <thead>
            <tr>
              <th>Overlay</th>
              <th>Plays</th>
              <th>Record</th>
              <th>Win Rate</th>
              <th>Removed</th>
              <th>Delta</th>
            </tr>
          </thead>
          <tbody>
            {overlays.map((row) => (
              <tr key={row.policy}>
                <td>
                  <span className="policy-name">
                    <TrendingUp size={14} />
                    {row.policy.replace(/_/g, " ")}
                  </span>
                </td>
                <td>{row.plays ?? 0}</td>
                <td>{record(row)}</td>
                <td>{pct(row.win_rate)}</td>
                <td>{row.removed_wins ?? 0}-{row.removed_losses ?? 0}</td>
                <td className={(row.win_rate_delta ?? 0) >= 0 ? "positive" : "negative"}>{signed(row.win_rate_delta)}</td>
              </tr>
            ))}
            {!overlays.length && (
              <tr>
                <td colSpan={6}>No policy simulations are available yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="policy-table-shell">
        <h3 className="table-heading">Factor Leaderboard</h3>
        <table className="compare-table policy-table">
          <thead>
            <tr>
              <th>Factor</th>
              <th>Type</th>
              <th>Plays</th>
              <th>Record</th>
              <th>Win Rate</th>
              <th>Lift</th>
              <th>Sample</th>
            </tr>
          </thead>
          <tbody>
            {factors.map((row) => (
              <tr key={`${row.feature}-${row.value}`}>
                <td>
                  <span className="policy-name">
                    <TrendingUp size={14} />
                    {row.feature.replace(/_/g, " ")}: {row.value.replace(/_/g, " ")}
                  </span>
                </td>
                <td>{(row.actionability || "research").replace(/_/g, " ")}</td>
                <td>{row.plays ?? 0}</td>
                <td>{factorRecord(row)}</td>
                <td>{pct(row.win_rate)}</td>
                <td className={(row.win_rate_lift ?? 0) >= 0 ? "positive" : "negative"}>{signed(row.win_rate_lift)}</td>
                <td>{row.sample_flag || "n/a"}</td>
              </tr>
            ))}
            {!factors.length && (
              <tr>
                <td colSpan={7}>No factor leaderboard is available yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
