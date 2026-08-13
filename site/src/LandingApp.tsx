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
            <a href="warps.html">WARPS</a>
            <a href="https://lijuvarughese.com/ytts/">YTTS</a>
          </div>
        </nav>
        <div className="landing-hero">
          <div className="landing-hero-copy">
            <p className="landing-kicker">2026 NFL Season</p>
            <h1 className="landing-name">NFL picks, win probabilities, and schedule analysis.</h1>
            <p className="landing-tagline">
              Weekly picks and schedule intelligence for the 2026 NFL season.
              Win-probability model built on 26 seasons of data.
            </p>
            <div className="landing-actions">
              <a href="matrix.html" className="landing-button primary">Open NFL Edge Hub</a>
              <a href="warps.html" className="landing-button secondary">WARPS Model</a>
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
            <a className="snapshot-row" href="https://lijuvarughese.com/ytts/">
              <TrendingUp size={19} />
              <div>
                <strong>YTTS Screener</strong>
                <span>Model-driven equity screener with research overlays and position monitoring.</span>
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
              <h2 className="landing-project-title">YTTS Financials</h2>
            </div>
            <p className="landing-project-desc">
              Equity screener and position tracker — research screens, long-hold monitoring,
              and a live trading desk.
            </p>
            <div className="landing-ytts-links">
              <a href="https://lijuvarughese.com/ytts/internal_research_dashboard_app.html" target="_blank" rel="noreferrer" className="landing-link">
                <BarChart3 size={12} /> Research <ExternalLink size={11} />
              </a>
              <a href="https://lijuvarughese.com/ytts/longhold_dashboard.html" target="_blank" rel="noreferrer" className="landing-link">
                <TrendingUp size={12} /> Long Hold <ExternalLink size={11} />
              </a>
              <a href="https://lijuvarughese.com/ytts/trading_dashboard.html" target="_blank" rel="noreferrer" className="landing-link">
                <Activity size={12} /> Trading Desk <ExternalLink size={11} />
              </a>
            </div>
          </div>

        </section>

        <section className="landing-method">
          <div className="method-card">
            <Grid3X3 size={18} />
            <strong>26 seasons of NFL data</strong>
            <span>Models trained and validated on 2000–2025 regular season results.</span>
          </div>
          <div className="method-card">
            <FlaskConical size={18} />
            <strong>Beats the Vegas baseline</strong>
            <span>WARPS win-total model outperforms the statistical baseline in 25 of 26 seasons.</span>
          </div>
          <div className="method-card">
            <BarChart3 size={18} />
            <strong>Every pick tracked</strong>
            <span>Results, edge scores, and model accuracy logged week by week.</span>
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
