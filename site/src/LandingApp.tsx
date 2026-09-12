import { Activity, CalendarDays, Crosshair, FlaskConical, Grid3X3, ShieldCheck, Trophy } from "lucide-react";

const TOOLS = [
  {
    icon: <Grid3X3 size={20} />,
    goal: "See the full 2026 season at a glance",
    title: "Season Matrix",
    desc: "Every team, every week — engine ratings, win probabilities, and heatmap coloring across all 18 weeks in one grid.",
    link: "matrix.html#matrix",
    cta: "Open the Matrix",
    accent: "navy",
  },
  {
    icon: <Activity size={20} />,
    goal: "What should I bet this week?",
    title: "Weekly Picks",
    desc: "Every Tuesday the model grades all 16 games. You get a ranked shortlist — bet, lean, or skip — with plain-English reasons and a confidence rating.",
    link: "matrix.html#command",
    cta: "See this week's picks",
    accent: "blue",
  },
  {
    icon: <Trophy size={20} />,
    goal: "Who wins straight-up for my pool?",
    title: "Pick'em",
    desc: "Games sorted by win probability for the week. Tiebreaker guidance, time-slot grouping, and logos so you can scan and submit in under a minute.",
    link: "matrix.html#pickem",
    cta: "Go to Pick'em",
    accent: "gold",
  },
  {
    icon: <ShieldCheck size={20} />,
    goal: "Which team do I pick for Survivor?",
    title: "Survivor Pool",
    desc: "The model recommends a pick each week and flags teams you've already used. See the safest path through the full season before you commit.",
    link: "matrix.html#survivor",
    cta: "Open Survivor",
    accent: "green",
  },
  {
    icon: <Crosshair size={20} />,
    goal: "Which games have real value on the spread?",
    title: "Edge Board",
    desc: "All matchups ranked by edge strength across spread, total, and moneyline. Filter to plays only or browse the full slate with WARPS fair-value overlays.",
    link: "matrix.html#edges",
    cta: "See the Edge Board",
    accent: "red",
  },
  {
    icon: <CalendarDays size={20} />,
    goal: "What does my team's schedule look like?",
    title: "Schedule & Scout",
    desc: "The full 18-week grid with rest advantages, back-to-back flags, trap game alerts, and travel context — the schedule angles Vegas already prices in.",
    link: "matrix.html#scout",
    cta: "View Schedule",
    accent: "navy",
  },
  {
    icon: <FlaskConical size={20} />,
    goal: "Can I trust this model?",
    title: "Track Record & Model",
    desc: "26 seasons of NFL data. Win-probability model built on Pythagorean expectation (beats statistical baseline in 25 of 26 seasons). Season-by-season performance vs. Vegas.",
    link: "warps.html",
    cta: "See the data",
    accent: "slate",
  },
];

export default function LandingApp() {
  return (
    <div className="ls-root">
      <nav className="ls-nav">
        <span className="ls-logo">NFL Signal</span>
        <div className="ls-nav-links">
          <a href="matrix.html#command">Weekly Picks</a>
          <a href="matrix.html#pickem">Pick'em</a>
          <a href="matrix.html#survivor">Survivor</a>
          <a href="matrix.html" className="ls-nav-cta">Open the Board →</a>
        </div>
      </nav>

      <section className="ls-hero">
        <p className="ls-eyebrow">2026 NFL Season · Week 1 Live</p>
        <h1 className="ls-headline">Stop guessing.<br />Start picking.</h1>
        <p className="ls-sub">
          Seven tools that answer the seven questions every NFL fan asks each week —
          backed by 26 seasons of data and a model that beats Vegas year over year.
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

      <section className="ls-tools-section">
        <div className="ls-tools-header">
          <h2 className="ls-tools-title">Seven tools. One question each.</h2>
          <p className="ls-tools-sub">Everything lives in one board — no tabs to hunt through.</p>
        </div>
        <div className="ls-tools-grid">
          {TOOLS.map((tool) => (
            <a key={tool.title} href={tool.link} className={`ls-tool-card ls-tool-${tool.accent}`}>
              <div className="ls-tool-top">
                <div className="ls-tool-icon">{tool.icon}</div>
                <span className="ls-tool-goal">{tool.goal}</span>
              </div>
              <h3 className="ls-tool-title">{tool.title}</h3>
              <p className="ls-tool-desc">{tool.desc}</p>
              <span className="ls-tool-cta">{tool.cta} →</span>
            </a>
          ))}
        </div>
      </section>

      <footer className="ls-footer">
        <div>© 2026 NFL Signal Research</div>
        <div className="ls-disclaimer">
          For entertainment purposes only. Not financial advice. Sports betting involves financial risk — only bet what you can afford to lose. Must be 21+ and in a jurisdiction where sports betting is legal.
        </div>
      </footer>
    </div>
  );
}
