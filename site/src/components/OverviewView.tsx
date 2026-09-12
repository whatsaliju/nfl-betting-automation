import { Activity, BarChart3, Crosshair, Grid3X3, ShieldCheck, Target, Trophy } from "lucide-react";

interface Props {
  onNavigate: (view: string) => void;
}

const TOOLS = [
  {
    icon: <Grid3X3 size={20} />,
    goal: "See the full 2026 season at a glance",
    name: "Season Matrix",
    desc: "Every team, every week — engine ratings, win probabilities, and heatmap coloring across all 18 weeks in one grid.",
    view: "matrix",
    accent: "navy",
    cta: "Open the Matrix",
  },
  {
    icon: <Activity size={20} />,
    goal: "What should I bet this week?",
    name: "Weekly Picks",
    desc: "Model-backed grades for every game — spread, total, and moneyline. See where the value is before Sunday.",
    view: "command",
    accent: "navy",
    cta: "See this week's picks",
  },
  {
    icon: <Target size={20} />,
    goal: "Which games have real market value?",
    name: "Edge Board",
    desc: "Games where the model disagrees with the market. Ranked A–F by edge strength and confidence.",
    view: "edges",
    accent: "red",
    cta: "See the Edge Board",
  },
  {
    icon: <Trophy size={20} />,
    goal: "Who wins straight-up this week?",
    name: "Pick'em",
    desc: "Straight-up winner picks with confidence tiers. Completed games show final scores automatically.",
    view: "pickem",
    accent: "gold",
    cta: "Go to Pick'em",
  },
  {
    icon: <ShieldCheck size={20} />,
    goal: "Which team for Survivor this week?",
    name: "Survivor Pool",
    desc: "Weekly survivor picks ranked by win probability and remaining schedule value.",
    view: "survivor",
    accent: "green",
    cta: "Open Survivor",
  },
  {
    icon: <Crosshair size={20} />,
    goal: "What does my team's schedule look like?",
    name: "Schedule & Scout",
    desc: "Team-by-team schedule with rest, travel, and trap-game alerts rated across all 18 weeks.",
    view: "scout",
    accent: "slate",
    cta: "View Schedule",
  },
  {
    icon: <BarChart3 size={20} />,
    goal: "Can I trust this model?",
    name: "Track Record",
    desc: "Historical accuracy vs. Vegas lines from 2000–2025. Season-by-season MAE, win rates, and methodology.",
    view: "track",
    accent: "slate",
    cta: "See the data",
  },
];

export function OverviewView({ onNavigate }: Props) {
  return (
    <div className="ov-root">
      {/* Hero */}
      <div className="ov-hero">
        <div className="ov-hero-inner">
          <div className="ov-eyebrow">NFL Signal · 2026 Season</div>
          <h2 className="ov-title">Stop guessing.<br />Start picking.</h2>
          <p className="ov-sub">
            Seven tools backed by 26 seasons of data — spread picks, survivor,
            Pick'em, edge board, and more.
          </p>
          <div className="ov-hero-actions">
            <button className="ov-cta-primary" onClick={() => onNavigate("command")}>
              Weekly Picks
            </button>
            <button className="ov-cta-ghost" onClick={() => onNavigate("pickem")}>
              Pick'em →
            </button>
          </div>
        </div>
      </div>

      {/* Stats strip */}
      <div className="ov-stats">
        <div className="ov-stat">
          <span className="ov-stat-num">26</span>
          <span className="ov-stat-label">seasons of data</span>
        </div>
        <div className="ov-stat">
          <span className="ov-stat-num">32</span>
          <span className="ov-stat-label">teams · 18 weeks</span>
        </div>
        <div className="ov-stat">
          <span className="ov-stat-num">25/26</span>
          <span className="ov-stat-label">beats Vegas baseline</span>
        </div>
      </div>

      {/* Tools grid */}
      <div className="ov-tools-section">
        <div className="ov-tools-header">
          <h3 className="ov-tools-title">Seven tools. One question each.</h3>
          <p className="ov-tools-sub">Pick where to start — or bookmark the tool you use every week.</p>
        </div>
        <div className="ov-grid">
          {TOOLS.map((tool) => (
            <div
              key={tool.view}
              className={`ov-card ov-${tool.accent}`}
              onClick={() => onNavigate(tool.view)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && onNavigate(tool.view)}
            >
              <div className="ov-card-top">
                <div className="ov-icon">{tool.icon}</div>
                <div className="ov-goal">{tool.goal}</div>
              </div>
              <div className="ov-name">{tool.name}</div>
              <div className="ov-desc">{tool.desc}</div>
              <span className="ov-btn">{tool.cta} →</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
