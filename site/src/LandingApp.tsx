import {
  Activity,
  BarChart3,
  ExternalLink,
  FlaskConical,
  Grid3X3,
  TrendingUp,
} from "lucide-react";

export default function LandingApp() {
  return (
    <div className="landing-shell">
      <header className="landing-header">
        <nav className="landing-nav" aria-label="Project navigation">
          <span className="landing-brand">Liju Varughese</span>
          <div className="landing-nav-links">
            <a href="matrix.html">NFL Edge Hub</a>
            <a href="warps.html">WARPS-NFL</a>
            <a href="https://lijuvarughese.com/ytts/" target="_blank" rel="noreferrer">YTTS</a>
          </div>
        </nav>
        <div className="landing-hero">
          <div className="landing-hero-copy">
            <p className="landing-kicker">Project Lab</p>
            <h1 className="landing-name">Quantitative research tools for sports and markets.</h1>
            <p className="landing-tagline">
              NFL picks and schedule analysis. Win-total forecasting built on 26 seasons of data.
              Weekly equity screener with model rankings and company research.
            </p>
            <div className="landing-actions">
              <a href="matrix.html" className="landing-button primary">Open NFL Edge Hub</a>
              <a href="warps.html" className="landing-button secondary">Open WARPS-NFL</a>
              <a href="https://lijuvarughese.com/ytts/" target="_blank" rel="noreferrer" className="landing-button secondary">Open YTTS</a>
            </div>
          </div>
          <div className="landing-snapshot" aria-label="Project snapshot">
            <a className="snapshot-row" href="matrix.html">
              <Grid3X3 size={19} />
              <div>
                <strong>NFL Edge Hub</strong>
                <span>Weekly picks, schedule spots, win-prob model, and matchup comparisons.</span>
              </div>
            </a>
            <a className="snapshot-row" href="warps.html">
              <FlaskConical size={19} />
              <div>
                <strong>WARPS-NFL</strong>
                <span>Preseason win-total model · beats Vegas baseline in 25 of 26 seasons.</span>
              </div>
            </a>
            <a className="snapshot-row" href="https://lijuvarughese.com/ytts/" target="_blank" rel="noreferrer">
              <TrendingUp size={19} />
              <div>
                <strong>YTTS</strong>
                <span>Weekly stock research — equity screener, model rankings, and risk checks.</span>
              </div>
            </a>
          </div>
        </div>
      </header>

      <main className="landing-main">
        <section className="landing-projects" id="projects">

          <div className="landing-project">
            <div className="landing-project-head">
              <div className="landing-project-icon lp-matrix"><Grid3X3 size={18} /></div>
              <h2 className="landing-project-title">NFL Edge Hub</h2>
            </div>
            <p className="landing-project-desc">
              Full-season schedule matrix with engine overlays, weekly edge board with play/watch/pass
              decisions, team win-probability signals, schedule scout, matchup comparisons, and model research.
              Live during the 2026 NFL season.
            </p>
            <a href="matrix.html" className="landing-link">
              Open NFL Edge Hub <ExternalLink size={12} />
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
              The 2026 slate identifies where Vegas lines are mispriced vs. the model.
            </p>
            <a href="warps.html" className="landing-link">
              Open WARPS-NFL™ <ExternalLink size={12} />
            </a>
          </div>

          <div className="landing-project">
            <div className="landing-project-head">
              <div className="landing-project-icon lp-ytts"><TrendingUp size={18} /></div>
              <h2 className="landing-project-title">YTTS</h2>
            </div>
            <p className="landing-project-desc">
              A weekly stock research system: an equity screener with model rankings, valuation work,
              company research, and risk checks. Tracks long-hold positions and surfaces new
              opportunities through a structured, repeatable process each week.
            </p>
            <a href="https://lijuvarughese.com/ytts/" target="_blank" rel="noreferrer" className="landing-link">
              Open YTTS <ExternalLink size={12} />
            </a>
          </div>

        </section>

        <section className="landing-method">
          <div className="method-card">
            <Grid3X3 size={18} />
            <strong>Weekly NFL analysis</strong>
            <span>Sharp-money signals, injury context, referee trends, and schedule factors — every game, every week.</span>
          </div>
          <div className="method-card">
            <FlaskConical size={18} />
            <strong>Beats the Vegas baseline</strong>
            <span>WARPS win-total model outperforms the statistical baseline in 25 of 26 seasons.</span>
          </div>
          <div className="method-card">
            <BarChart3 size={18} />
            <strong>Structured equity research</strong>
            <span>Model-ranked screener with valuation, risk checks, and position monitoring — updated weekly.</span>
          </div>
        </section>
      </main>

      <footer className="landing-footer">
        <span>© 2026 Liju Varughese</span>
        <span className="landing-footer-sep">·</span>
        <a href="https://github.com/whatsaliju/nfl-betting-automation" target="_blank" rel="noreferrer">
          github.com/whatsaliju
        </a>
      </footer>
    </div>
  );
}
