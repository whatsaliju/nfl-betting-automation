import {
  Activity,
  BarChart3,
  ExternalLink,
  FlaskConical,
  Grid3X3,
  LineChart,
  Search,
  TrendingUp,
} from "lucide-react";

export default function LandingApp() {
  return (
    <div className="landing-shell">
      <header className="landing-header">
        <nav className="landing-nav" aria-label="Project navigation">
          <span className="landing-brand">Liju Varughese</span>
          <div className="landing-nav-links">
            <a href="matrix.html">Matrix</a>
            <a href="warps.html">WARPS</a>
            <a href="https://lijuvarughese.com/ytts/">YTTS</a>
          </div>
        </nav>
        <div className="landing-hero">
          <div className="landing-hero-copy">
            <p className="landing-kicker">Project Lab</p>
            <h1 className="landing-name">Sports models and market screens.</h1>
            <p className="landing-tagline">
              A personal project lab built to compare assumptions, surface edges, and keep score over time.
            </p>
            <div className="landing-actions">
              <a href="#projects" className="landing-button primary">View Projects</a>
              <a href="matrix.html" className="landing-button secondary">NFL Edge Hub</a>
              <a href="warps.html" className="landing-button secondary">WARPS</a>
              <a href="https://lijuvarughese.com/ytts/" className="landing-button secondary">YTTS</a>
            </div>
          </div>
          <div className="landing-snapshot" aria-label="Project snapshot">
            <a className="snapshot-row" href="matrix.html">
              <Grid3X3 size={19} />
              <div>
                <strong>NFL Edge Hub</strong>
                <span>Matchup grid, weekly edges, scorecards, and comparison views.</span>
              </div>
            </a>
            <a className="snapshot-row" href="warps.html">
              <FlaskConical size={19} />
              <div>
                <strong>WARPS-NFL</strong>
                <span>Win-total research model with historical validation context.</span>
              </div>
            </a>
            <a className="snapshot-row" href="https://lijuvarughese.com/ytts/">
              <TrendingUp size={19} />
              <div>
                <strong>YTTS Screener</strong>
                <span>Equity screen with research notes, risk checks, and PM dashboards.</span>
              </div>
            </a>
          </div>
        </div>
      </header>

      <main className="landing-main">
        <section className="landing-about">
          <h2>Small systems for testing ideas.</h2>
          <p>
            Each project starts with a question, turns it into a model or dashboard, and then keeps score.
            The goal is not to make every answer automatic; it is to make the logic visible enough to improve.
          </p>
        </section>

        <section className="landing-projects" id="projects">

          <div className="landing-project">
            <div className="landing-project-head">
              <div className="landing-project-icon lp-matrix"><Grid3X3 size={18} /></div>
              <h2 className="landing-project-title">NFL Edge Hub</h2>
            </div>
            <p className="landing-project-desc">
              Full-season schedule matrix with engine overlays, weekly edge board with play/watch/pass
              decisions, team expectation signals, matchup comparisons, and model factor research.
            </p>
            <a href="matrix.html" className="landing-link">
              Open Matrix <ExternalLink size={12} />
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
              The 2026 bet slate identifies where Vegas lines are mispriced vs. the model consensus.
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
              My personal trading account dashboard — systematic research screens,
              long-hold position tracking, and a live trading desk. Built to replace
              spreadsheets with a purpose-built interface I can actually navigate quickly.
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
            <Search size={18} />
            <strong>Compare assumptions</strong>
            <span>Put schedules, lines, projections, and screens in one place.</span>
          </div>
          <div className="method-card">
            <LineChart size={18} />
            <strong>Surface edges</strong>
            <span>Highlight model disagreements, quality flags, and research gaps.</span>
          </div>
          <div className="method-card">
            <BarChart3 size={18} />
            <strong>Keep score</strong>
            <span>Track validation, results, and what should change next.</span>
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
