import { Activity, CalendarDays, Crosshair, FlaskConical, Grid3X3, ShieldCheck, Trophy } from "lucide-react";

// Ordered col-first so same-color cards share a column: navy | red | gold (left→right)
// Row 1: Season Matrix | Weekly Picks | Pick'em
// Row 2: Schedule & Scout | Edge Board | Survivor Pool
// Full: Track Record (teal, featured)
const TOOLS = [
  {
    icon: <Grid3X3 size={28} />,
    goal: "See the full 2026 season at a glance",
    title: "Season Matrix",
    desc: "Every team, every week — engine ratings, win probabilities, and heatmap coloring across all 18 weeks in one grid.",
    link: "matrix.html#matrix",
    cta: "Open the Matrix",
    accent: "navy",
  },
  {
    icon: <Activity size={28} />,
    goal: "What should I bet this week?",
    title: "Weekly Picks",
    desc: "Every Tuesday the model grades all 16 games. You get a ranked shortlist — bet, lean, or skip — with plain-English reasons and a confidence rating.",
    link: "matrix.html#command",
    cta: "See this week's picks",
    accent: "red",
  },
  {
    icon: <Trophy size={28} />,
    goal: "Who wins straight-up for my pool?",
    title: "Pick'em",
    desc: "Games sorted by win probability for the week. Tiebreaker guidance, time-slot grouping, and logos so you can scan and submit in under a minute.",
    link: "matrix.html#pickem",
    cta: "Go to Pick'em",
    accent: "gold",
  },
  {
    icon: <CalendarDays size={28} />,
    goal: "What does my team's schedule look like?",
    title: "Schedule & Scout",
    desc: "The full 18-week grid with rest advantages, back-to-back flags, trap game alerts, and travel context — the schedule angles Vegas already prices in.",
    link: "matrix.html#scout",
    cta: "View Schedule",
    accent: "navy",
  },
  {
    icon: <Crosshair size={28} />,
    goal: "Which games have real value on the spread?",
    title: "Edge Board",
    desc: "All matchups ranked by edge strength across spread, total, and moneyline. Filter to plays only or browse the full slate with WARPS fair-value overlays.",
    link: "matrix.html#edges",
    cta: "See the Edge Board",
    accent: "red",
  },
  {
    icon: <ShieldCheck size={28} />,
    goal: "Which team do I pick for Survivor?",
    title: "Survivor Pool",
    desc: "The model recommends a pick each week and flags teams you've already used. See the safest path through the full season before you commit.",
    link: "matrix.html#survivor",
    cta: "Open Survivor",
    accent: "gold",
  },
  {
    icon: <FlaskConical size={28} />,
    goal: "Can I trust this model?",
    title: "Track Record & Model",
    desc: "26 seasons of NFL data. Win-probability model built on Pythagorean expectation (beats statistical baseline in 25 of 26 seasons). Season-by-season performance vs. Vegas.",
    link: "warps.html",
    cta: "See the data",
    accent: "teal",
  },
];

// Decorative mini-heatmap that evokes the Season Matrix without any real data
const GRID_VALS = [
  .12,.72,.28,.55,.18,.85,.38,.65,.22,.48,.78,.08,.58,
  .65,.18,.48,.12,.75,.28,.58,.38,.88,.18,.52,.72,.32,
  .38,.58,.82,.22,.48,.68,.12,.78,.28,.42,.62,.85,.18,
  .52,.72,.35,.62,.48,.30,.65,.20,.75,.45,.15,.55,.82,
];

function HeroGrid() {
  const cols = 13, rows = 4, cell = 20, gap = 3;
  const W = cols * (cell + gap) - gap;
  const H = rows * (cell + gap) - gap;
  return (
    <svg className="ls-hero-grid" viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
      {GRID_VALS.slice(0, cols * rows).map((v, i) => {
        const col = i % cols;
        const row = Math.floor(i / cols);
        const isRed = v > 0.7 && col % 4 === row % 3;
        return (
          <rect
            key={i}
            x={col * (cell + gap)}
            y={row * (cell + gap)}
            width={cell}
            height={cell}
            rx={3}
            fill={isRed ? "#D50A0A" : "#013369"}
            opacity={v}
          />
        );
      })}
    </svg>
  );
}

export default function LandingApp() {
  return (
    <div className="ls-root">
      <nav className="ls-nav">
        <span className="ls-logo">NFL Signal</span>
        <a href="warps.html" className="ls-nav-model">About the model →</a>
      </nav>

      <section className="ls-hero">
        <div className="ls-hero-content">
          <p className="ls-eyebrow">2026 NFL Season · Live</p>
          <h1 className="ls-headline">NFL analysis.<br />26 seasons deep.</h1>
          <p className="ls-sub">
            Seven tools. Seven questions every NFL fan asks each week.
            Pick the one you need.
          </p>
        </div>
        <HeroGrid />
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
        <div className="ls-stat ls-stat-record">
          <span className="ls-stat-num">25<span className="ls-stat-denom">/26</span></span>
          <div className="ls-stat-bar-track" aria-label="25 of 26 seasons beat Vegas baseline">
            <div className="ls-stat-bar-fill" style={{ width: `${(25/26)*100}%` }} />
          </div>
          <span className="ls-stat-label">beats Vegas baseline</span>
        </div>
      </div>

      <section className="ls-tools-section">
        <div className="ls-tools-header">
          <h2 className="ls-tools-title">Seven tools. One question each.</h2>
          <p className="ls-tools-sub">Everything lives in one board — no tabs to hunt through.</p>
        </div>
        <div className="ls-group-labels">
          <span className="ls-group-label ls-group-navy">Season Overview</span>
          <span className="ls-group-label ls-group-red">Betting Value</span>
          <span className="ls-group-label ls-group-gold">Pool Games</span>
        </div>
        <div className="ls-tools-grid">
          {TOOLS.map((tool, i) => (
            <a
              key={tool.title}
              href={tool.link}
              className={`ls-tool-card ls-tool-${tool.accent}${i === TOOLS.length - 1 ? " ls-tool-featured" : ""}`}
            >
              <div className="ls-card-header">
                <div className="ls-tool-icon">{tool.icon}</div>
              </div>
              <div className="ls-card-body">
                <span className="ls-tool-goal">{tool.goal}</span>
                <h3 className="ls-tool-title">{tool.title}</h3>
                <p className="ls-tool-desc">{tool.desc}</p>
                <span className="ls-tool-cta">{tool.cta} →</span>
              </div>
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
