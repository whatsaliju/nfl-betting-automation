import { BarChart3, ExternalLink, FlaskConical, Trophy } from "lucide-react";

export default function LandingApp() {
  return (
    <div className="ls-root">
      <nav className="ls-nav">
        <span className="ls-logo">NFL Signal</span>
        <div className="ls-nav-links">
          <a href="matrix.html">Edge Board</a>
          <a href="matrix.html#pickem">Pick'em</a>
          <a href="matrix.html#survivor">Survivor</a>
          <a href="matrix.html" className="ls-nav-cta">Open the Board →</a>
        </div>
      </nav>

      <section className="ls-hero">
        <p className="ls-eyebrow">2026 NFL Season · Now Live</p>
        <h1 className="ls-headline">The edge your<br />picks are missing.</h1>
        <p className="ls-sub">
          Weekly spread, total, and moneyline analysis powered by 26 seasons of NFL data.
          Model-backed picks, fair value analysis, survivor tools — all in one board.
        </p>
        <div className="ls-hero-actions">
          <a href="matrix.html" className="ls-btn-primary">Open the Board</a>
          <a href="matrix.html#pickem" className="ls-btn-ghost">Pick'em →</a>
        </div>
      </section>

      <div className="ls-stats">
        <div className="ls-stat">
          <span className="ls-stat-num">26</span>
          <span className="ls-stat-label">seasons of data</span>
        </div>
        <div className="ls-stat">
          <span className="ls-stat-num">32</span>
          <span className="ls-stat-label">teams · 18 weeks</span>
        </div>
        <div className="ls-stat">
          <span className="ls-stat-num">25/26</span>
          <span className="ls-stat-label">beats Vegas baseline</span>
        </div>
      </div>

      <section className="ls-features">
        <div className="ls-feature-card">
          <div className="ls-feature-icon"><BarChart3 size={18} /></div>
          <h2 className="ls-feature-title">Weekly Edge Board</h2>
          <p className="ls-feature-desc">
            Every game rated across spread, total, and moneyline. Edge scores, referee lean,
            schedule context, and WARPS fair-value overlays — updated each week.
            Play / watch / pass with a reason why.
          </p>
          <a href="matrix.html" className="ls-feature-link">
            Open the Board <ExternalLink size={12} />
          </a>
        </div>

        <div className="ls-feature-card">
          <div className="ls-feature-icon"><Trophy size={18} /></div>
          <h2 className="ls-feature-title">Pick'em &amp; Survivor</h2>
          <p className="ls-feature-desc">
            Straight-up picks ranked by WARPS win probability and implied totals.
            Survivor manager tracks multiple pools, surfaces already-used teams,
            and maps optimal season paths.
          </p>
          <a href="matrix.html#pickem" className="ls-feature-link">
            Open Pick'em <ExternalLink size={12} />
          </a>
        </div>

        <div className="ls-feature-card">
          <div className="ls-feature-icon"><FlaskConical size={18} /></div>
          <h2 className="ls-feature-title">WARPS-NFL™</h2>
          <p className="ls-feature-desc">
            Preseason win-total model built on 26 seasons of NFL data. A 75%
            Pythagorean + 25% point differential blend beats the statistical
            baseline in 25 of 26 seasons (MAE 2.374, p &lt; 0.0001).
          </p>
          <a href="warps.html" className="ls-feature-link">
            Open WARPS <ExternalLink size={12} />
          </a>
        </div>
      </section>

      <footer className="ls-footer">
        © 2026 NFL Signal
      </footer>
    </div>
  );
}
