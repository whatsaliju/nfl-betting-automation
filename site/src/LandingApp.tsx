import { Activity, BarChart3, ExternalLink, FlaskConical, Grid3X3, TrendingUp } from "lucide-react";

export default function LandingApp() {
  return (
    <div className="landing-shell">
      <header className="landing-header">
        <div className="landing-brand-row">
          <div className="landing-brand-mark">
            <Grid3X3 size={36} strokeWidth={1.5} />
          </div>
          <div>
            <h1 className="landing-name">Liju Varughese</h1>
            <p className="landing-tagline">NFL Analytics · Win Forecasting · Trading</p>
          </div>
        </div>
        <p className="landing-hero-text">
          Data-driven tools for NFL edge identification, preseason win-total forecasting,
          and portfolio management.
        </p>
      </header>

      <main className="landing-main">
        <div className="landing-grid">

          {/* NFL Matrix */}
          <a href="matrix.html" className="landing-card">
            <div className="landing-card-top">
              <div className="landing-card-icon landing-icon-matrix">
                <Grid3X3 size={22} />
              </div>
              <ExternalLink size={13} className="landing-card-ext" />
            </div>
            <h2 className="landing-card-title">NFL Matrix</h2>
            <p className="landing-card-desc">
              Full-season schedule matrix, weekly edge board, team expectations,
              matchup analysis, and factor research surface.
            </p>
            <div className="landing-card-tags">
              <span>Schedule</span>
              <span>Edges</span>
              <span>Expectations</span>
              <span>Research</span>
            </div>
            <span className="landing-card-cta">Open Matrix →</span>
          </a>

          {/* WARPS */}
          <a href="warps.html" className="landing-card landing-card-warps">
            <div className="landing-card-top">
              <div className="landing-card-icon landing-icon-warps">
                <FlaskConical size={22} />
              </div>
              <ExternalLink size={13} className="landing-card-ext" />
            </div>
            <h2 className="landing-card-title">WARPS-NFL™</h2>
            <p className="landing-card-desc">
              Preseason win-total forecasting model. 26-season backtest,
              3-model consensus screen, and 2026 bet slate vs Vegas.
            </p>
            <div className="landing-warps-kpis">
              <div className="landing-kpi">
                <strong>2.374</strong>
                <span>MAE wins</span>
              </div>
              <div className="landing-kpi">
                <strong>25/26</strong>
                <span>beats baseline</span>
              </div>
              <div className="landing-kpi">
                <strong>p&lt;0.0001</strong>
                <span>DM stat</span>
              </div>
            </div>
            <span className="landing-card-cta">Open WARPS →</span>
          </a>

          {/* YTTS Financials */}
          <div className="landing-card landing-card-financials">
            <div className="landing-card-top">
              <div className="landing-card-icon landing-icon-financials">
                <TrendingUp size={22} />
              </div>
            </div>
            <h2 className="landing-card-title">YTTS Financials</h2>
            <p className="landing-card-desc">
              Trading account dashboard — research signals, long-hold positions,
              and active trading desk.
            </p>
            <div className="ytts-link-grid">
              <a
                href="https://lijuvarughese.com/ytts/internal_research_dashboard_app.html"
                target="_blank"
                rel="noreferrer"
                className="ytts-dest"
              >
                <BarChart3 size={15} />
                <span>Research</span>
                <ExternalLink size={11} className="ytts-ext" />
              </a>
              <a
                href="https://lijuvarughese.com/ytts/longhold_dashboard.html"
                target="_blank"
                rel="noreferrer"
                className="ytts-dest"
              >
                <TrendingUp size={15} />
                <span>Long Hold</span>
                <ExternalLink size={11} className="ytts-ext" />
              </a>
              <a
                href="https://lijuvarughese.com/ytts/trading_dashboard.html"
                target="_blank"
                rel="noreferrer"
                className="ytts-dest"
              >
                <Activity size={15} />
                <span>Trading Desk</span>
                <ExternalLink size={11} className="ytts-ext" />
              </a>
            </div>
          </div>

        </div>
      </main>

      <footer className="landing-footer">
        <span>© 2026 Liju Varughese</span>
        <span className="landing-footer-sep">·</span>
        <a
          href="https://github.com/whatsaliju/nfl-betting-automation"
          target="_blank"
          rel="noreferrer"
        >
          github.com/whatsaliju
        </a>
      </footer>
    </div>
  );
}
