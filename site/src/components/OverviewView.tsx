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
  },
  {
    icon: <Activity size={20} />,
    goal: "What should I bet this week?",
    name: "Weekly Picks",
    desc: "Model-backed grades for every game — spread, total, and moneyline. See where the value is before Sunday.",
    view: "command",
    accent: "navy",
  },
  {
    icon: <Target size={20} />,
    goal: "Which games have real market value?",
    name: "Edge Board",
    desc: "Games where the model disagrees with the market. Ranked A–F by edge strength and confidence.",
    view: "edges",
    accent: "red",
  },
  {
    icon: <Trophy size={20} />,
    goal: "Who wins straight-up this week?",
    name: "Pick'em",
    desc: "Straight-up winner picks with confidence tiers. Completed games show final scores automatically.",
    view: "pickem",
    accent: "gold",
  },
  {
    icon: <ShieldCheck size={20} />,
    goal: "Which team for Survivor this week?",
    name: "Survivor Pool",
    desc: "Weekly survivor picks ranked by win probability and remaining schedule value.",
    view: "survivor",
    accent: "green",
  },
  {
    icon: <Crosshair size={20} />,
    goal: "What does my team's schedule look like?",
    name: "Schedule & Scout",
    desc: "Team-by-team schedule with rest, travel, and trap-game alerts rated across all 18 weeks.",
    view: "scout",
    accent: "slate",
  },
  {
    icon: <BarChart3 size={20} />,
    goal: "Can I trust this model?",
    name: "Track Record",
    desc: "Historical accuracy vs. Vegas lines from 2000–2025. Season-by-season MAE, win rates, and methodology.",
    view: "track",
    accent: "slate",
  },
];

export function OverviewView({ onNavigate }: Props) {
  return (
    <div className="ov-root">
      <div className="ov-header">
        <div className="ov-eyebrow">NFL Signal · 2026 Season</div>
        <h2 className="ov-title">Where do you want to start?</h2>
        <p className="ov-sub">Seven tools — pick your question and go straight there.</p>
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
            <span className="ov-btn">Open {tool.name} →</span>
          </div>
        ))}
      </div>
    </div>
  );
}
