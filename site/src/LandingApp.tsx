import { Activity, BarChart3, ExternalLink, FlaskConical, Grid3X3, TrendingUp } from "lucide-react";

export default function LandingApp() {
  return (
    <div className="landing-shell">
      <header className="landing-header">
        <h1 className="landing-name">Liju Varughese</h1>
        <p className="landing-tagline">NFL Analytics · Sports Betting · Trading</p>
      </header>

      <main className="landing-main">
        <section className="landing-about">
          <p>
            I build data-driven systems at the intersection of sports analytics and financial markets.
            On the NFL side, I run statistical models to find mispriced preseason win totals,
            track weekly betting edges, and backtest signals across 26 seasons of play-by-play data.
            On the trading side, I manage a systematic portfolio with research screens,
            long-hold position tracking, and an active trading desk.
          </p>
          <p>
            Everything here is built from scratch — custom models, live data pipelines,
            and dashboards I actually use every day.
          </p>
        </section>

        <div className="landing-divider" />

        <section className="landing-projects">

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
