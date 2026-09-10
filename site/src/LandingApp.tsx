import { BarChart3, ExternalLink, FlaskConical, ShieldCheck, Target } from "lucide-react";

export default function LandingApp() {
  return (
    <div className="landing-shell">
      <header className="landing-header">
        <nav className="landing-nav" aria-label="Site navigation">
          <span className="landing-brand">NFL Signal</span>
          <div className="landing-nav-links">
            <a href="matrix.html">Edge Board</a>
            <a href="matrix.html#pickem">Pick'em</a>
            <a href="warps.html">WARPS</a>
          </div>
        </nav>
        <div className="landing-hero">
          <div className="landing-hero-copy">
            <p className="landing-kicker">2026 NFL Season</p>
            <h1 className="landing-name">The edge your picks are missing.</h1>
            <p className="landing-tagline">
              Weekly spread, total, and moneyline analysis powered by 26 seasons of NFL data.
              Model-backed picks, WARPS fair value, survivor tools — all in one board.
            </p>
            <div className="landing-actions">
              <a href="matrix.html" className="landing-button primary">Open the Board</a>
              <a href="warps.html" className="landing-button secondary">WARPS Model</a>
            </div>
          </div>
          <div className="landing-snapshot" aria-label="Feature overview">
            <a className="snapshot-row" href="matrix.html#edges">
              <BarChart3 size={19} />
              <div>
                <strong>Weekly Edge Board</strong>
                <span>Play/watch/pass decisions with scores — spread, total, and moneyline every week.</span>
              </div>
            </a>
            <a className="snapshot-row" href="matrix.html#pickem">
              <Target size={19} />
              <div>
                <strong>Pick'em Tool</strong>
                <span>SU picks powered by WARPS fair value, implied totals, and tiebreaker rankings.</span>
              </div>
            </a>
            <a className="snapshot-row" href="warps.html">
              <FlaskConical size={19} />
              <div>
                <strong>WARPS-NFL™</strong>
                <span>Preseason win-total model · outperforms the Vegas baseline in 25 of 26 seasons.</span>
              </div>
            </a>
          </div>
        </div>
      </header>

      <main className="landing-main">
        <section className="landing-projects" id="features">

          <div className="landing-project">
            <div className="landing-project-head">
              <div className="landing-project-icon lp-matrix"><BarChart3 size={18} /></div>
              <h2 className="landing-project-title">Weekly Edge Board</h2>
            </div>
            <p className="landing-project-desc">
              Every game rated across spread, total, and moneyline. Edge scores, referee trends,
              schedule context, and WARPS fair-value overlays — updated weekly during the season.
              Play / watch / pass with a reason why.
            </p>
            <a href="matrix.html" className="landing-link">
              Open the Board <ExternalLink size={12} />
            </a>
          </div>

          <div className="landing-project">
            <div className="landing-project-head">
              <div className="landing-project-icon lp-matrix"><Target size={18} /></div>
              <h2 className="landing-project-title">Pick'em &amp; Survivor</h2>
            </div>
            <p className="landing-project-desc">
              Straight-up picks for office pools — ranked by WARPS win probability and implied scoring.
              Survivor manager tracks multiple pools, highlights already-used teams, and suggests
              season paths that maximize survival probability.
            </p>
            <a href="matrix.html#pickem" className="landing-link">
              Open Pick'em <ExternalLink size={12} />
            </a>
          </div>

          <div className="landing-project">
            <div className="landing-project-head">
              <div className="landing-project-icon lp-warps"><FlaskConical size={18} /></div>
              <h2 className="landing-project-title">WARPS-NFL™</h2>
            </div>
            <p className="landing-project-desc">
              Preseason win-total forecasting model built on 26 seasons of NFL data.
              A 75% Pythagorean + 25% point differential blend beats the statistical baseline
              in 25 of 26 seasons (MAE 2.374, p&nbsp;&lt;&nbsp;0.0001 vs baseline).
            </p>
            <a href="warps.html" className="landing-link">
              Open WARPS-NFL™ <ExternalLink size={12} />
            </a>
          </div>

        </section>

        <section className="landing-method">
          <div className="method-card">
            <BarChart3 size={18} />
            <strong>Weekly NFL analysis</strong>
            <span>Sharp-money signals, referee trends, schedule context, and WARPS fair value — every game, every week.</span>
          </div>
          <div className="method-card">
            <FlaskConical size={18} />
            <strong>Beats the Vegas baseline</strong>
            <span>WARPS win-total model outperforms the statistical baseline in 25 of 26 seasons.</span>
          </div>
          <div className="method-card">
            <ShieldCheck size={18} />
            <strong>Survivor-optimized</strong>
            <span>Pool-aware pick strategy that balances survival probability against public chalk to maximize pool EV.</span>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <span>© 2026 NFL Signal</span>
      </footer>
    </div>
  );
}
