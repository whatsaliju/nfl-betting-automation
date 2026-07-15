import { AlertTriangle, BadgeCheck, Brain, ClipboardList, FlaskConical, Gauge, Route, ShieldCheck, Target } from "lucide-react";
import { teamLogos } from "../data/nflData";
import survivorPayload from "../data/survivorRecommendations2026.json";
import type { EdgeBoardGame, EngineFeed, WarpsMarketOverlay, WeeklyBettingCard, WeeklyBettingCardRow } from "../types";

type SurvivorCandidate = {
  week: number;
  team: string;
  opponent: string;
  matchup_key: string;
  home_away: "home" | "away";
  day: string;
  win_probability: number;
  survivor_score: number;
  tier: string;
};

type SurvivorPayload = {
  metadata: { model: string; candidate_count: number };
  optimal_path: {
    average_pick_probability: number | null;
    picks: SurvivorCandidate[];
  };
  candidates: SurvivorCandidate[];
};

const survivor = survivorPayload as SurvivorPayload;

function pct(value?: number | null) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "n/a";
}

function score(value?: number | null) {
  return typeof value === "number" ? value.toFixed(1) : "n/a";
}

function titleCase(value?: string | null) {
  if (!value) return "n/a";
  return value.replace(/_/g, " ");
}

function currentCardRows(feed?: EngineFeed | null) {
  return feed?.weekly_betting_card?.cards || [];
}

function cardSnapshot(cards: WeeklyBettingCardRow[]) {
  if (!cards.length) return "No card loaded";
  const seasons = Array.from(new Set(cards.map((card) => card.season))).sort();
  const weeks = cards.map((card) => card.week);
  const minWeek = Math.min(...weeks);
  const maxWeek = Math.max(...weeks);
  return `${seasons.join("-")} W${minWeek === maxWeek ? minWeek : `${minWeek}-${maxWeek}`}`;
}

function nextSurvivorWeek(cards: WeeklyBettingCardRow[]) {
  const regularWeeks = cards.filter((card) => card.season === 2026 && card.season_type === "REG").map((card) => card.week);
  if (regularWeeks.length) return Math.min(...regularWeeks);
  return 1;
}

function strongestWarps(week: number, rows: WarpsMarketOverlay[]) {
  return rows
    .filter((row) => row.week === week)
    .flatMap((row) => [
      {
        team: row.home_tla,
        opponent: row.away_tla,
        matchup: row.matchup_key,
        homeAway: "home",
        winProb: row.home_win_prob,
        fairSpread: row.fair_home_spread,
        fairMl: row.home_fair_moneyline,
      },
      {
        team: row.away_tla,
        opponent: row.home_tla,
        matchup: row.matchup_key,
        homeAway: "away",
        winProb: row.away_win_prob,
        fairSpread: row.fair_away_spread,
        fairMl: row.away_fair_moneyline,
      },
    ])
    .sort((a, b) => b.winProb - a.winProb)
    .slice(0, 5);
}

function survivorForWeek(week: number) {
  const rows = survivor.candidates
    .filter((row) => row.week === week)
    .sort((a, b) => b.survivor_score - a.survivor_score || b.win_probability - a.win_probability);
  const path = survivor.optimal_path.picks.find((row) => row.week === week);
  return { primary: rows[0], alternatives: rows.slice(1, 4), path };
}

function bettingGroups(cards: WeeklyBettingCardRow[]) {
  return {
    plays: cards.filter((card) => card.action === "play"),
    watch: cards.filter((card) => card.action === "watch" || card.action === "lean"),
    passes: cards.filter((card) => card.action === "pass"),
  };
}

function playableEdges(games: EdgeBoardGame[]) {
  return games
    .filter((game) => game.season_type === "REG" && game.best_edge.status === "play")
    .sort((a, b) => (b.best_edge.score || 0) - (a.best_edge.score || 0))
    .slice(0, 4);
}

function TeamLogo({ team }: { team: string }) {
  return <img src={teamLogos[team]} alt="" />;
}

export function CommandCenterView({
  engineFeed,
  bettingCard,
  edgeGames,
  warpsRows,
  onNavigate,
}: {
  engineFeed: EngineFeed | null;
  bettingCard?: WeeklyBettingCard;
  edgeGames: EdgeBoardGame[];
  warpsRows: WarpsMarketOverlay[];
  onNavigate: (view: "card" | "edges" | "survivor" | "warps" | "scout") => void;
}) {
  const command = engineFeed?.weekly_command_center;
  const context = command?.current_context || engineFeed?.current_context;
  const cards = bettingCard?.cards || currentCardRows(engineFeed).filter(
    (card) => context && card.season === context.season && card.season_type === context.season_type && card.week === context.week
  );
  const groups = bettingGroups(cards);
  const commandWeek = context?.week || nextSurvivorWeek(cards);
  const commandWeekLabel = context?.week_label || `W${commandWeek}`;
  const survivorWeek = survivorForWeek(commandWeek);
  const warpsTop = strongestWarps(commandWeek, warpsRows);
  const edges = playableEdges(edgeGames);
  const cardAvailable = Boolean(context?.has_betting_card && bettingCard?.available);
  const preseason = engineFeed?.preseason_dry_run;
  const preseasonOk = preseason?.available && preseason.status === "PASS";
  const survivorBacktest = engineFeed?.survivor_backtest;
  const survivorBacktestBest = survivorBacktest?.best_strategy;
  const survivorPoolEv = engineFeed?.survivor_pool_ev;
  const survivorPoolBest = survivorPoolEv?.best_strategy;
  const commandCard = command?.betting_card;
  const hasAction = command ? !command.do_nothing_warning : groups.plays.length + groups.watch.length + edges.length > 0;
  const laneCards = [
    {
      icon: <Target size={15} />,
      label: "Live Betting",
      value: command?.recommended_action || "Pending",
      detail: cardAvailable ? "Selector card is available for the current context." : "No current betting card is published yet.",
      state: command?.recommended_action?.startsWith("NO BET") || !cardAvailable ? "hold" : "ready",
    },
    {
      icon: <Brain size={15} />,
      label: "WARPS",
      value: "Forecast prior",
      detail: "Useful for fair spread, fair ML, and season-strength context.",
      state: "research",
    },
    {
      icon: <ShieldCheck size={15} />,
      label: "Survivor",
      value: survivorWeek.primary?.team || "n/a",
      detail: "Offseason board uses WARPS priors, future value, and estimated public pick data.",
      state: "watch",
    },
    {
      icon: <FlaskConical size={15} />,
      label: "Research",
      value: "Monitor",
      detail: "ML, market router, and factor promotion remain gated by historical validation.",
      state: "research",
    },
  ];

  return (
    <section className="command-center">
      <div className="command-hero panel">
        <div>
          <span className="command-eyebrow">Weekly Command Center</span>
          <h2>{commandWeekLabel} Decision Board</h2>
          <p>
            Betting card, survivor, WARPS priors, and engine health in one place. {command?.action_reason || command?.warnings?.[0] || context?.message || "Detailed tabs stay available when you want to drill in."}
          </p>
        </div>
        <div className="command-status-stack">
          <span className={command?.recommended_action?.startsWith("NO BET") ? "status-pill warning" : "status-pill ok"}>
            <Gauge size={14} />
            {command?.recommended_action || "Action pending"}
            {command?.confidence_tier && <strong> · {command.confidence_tier}</strong>}
          </span>
          <span className={cardAvailable ? "status-pill ok" : "status-pill warning"}>
            <ShieldCheck size={14} />
            {cardAvailable ? "Current card live" : "Current card pending"}
          </span>
          <span className="status-pill">
            <ClipboardList size={14} />
            {context ? `${context.season} ${context.week_label} · ${titleCase(context.mode)}` : cardSnapshot(cards)}
          </span>
          <span className={hasAction ? "status-pill ok" : "status-pill warning"}>
            <Gauge size={14} />
            {hasAction ? "Action exists" : "No current betting action"}
          </span>
          <span className={preseasonOk ? "status-pill ok" : "status-pill warning"}>
            <ShieldCheck size={14} />
            PRE dry-run {preseason?.status || "missing"}
          </span>
        </div>
      </div>

      <div className="command-lane-grid">
        {laneCards.map((lane) => (
          <article className={`command-lane ${lane.state}`} key={lane.label}>
            <div>
              {lane.icon}
              <span>{lane.label}</span>
            </div>
            <strong>{lane.value}</strong>
            <p>{lane.detail}</p>
          </article>
        ))}
      </div>

      <div className="command-kpi-grid">
        <button className="command-kpi" onClick={() => onNavigate("card")}>
          <span>Betting Plays</span>
          <strong>{commandCard?.plays ?? groups.plays.length}</strong>
          <small>{commandCard?.watch ?? groups.watch.length} watch · {commandCard?.passes ?? groups.passes.length} pass</small>
        </button>
        <button className="command-kpi" onClick={() => onNavigate("survivor")}>
          <span>Survivor Pick</span>
          <strong>{survivorWeek.primary?.team || "n/a"}</strong>
          <small>{pct(survivorWeek.primary?.win_probability)} vs {survivorWeek.primary?.opponent || "n/a"}</small>
        </button>
        <button className="command-kpi" onClick={() => onNavigate("warps")}>
          <span>Top WARPS ML</span>
          <strong>{warpsTop[0]?.team || "n/a"}</strong>
          <small>{pct(warpsTop[0]?.winProb)} · {warpsTop[0]?.fairMl || "n/a"}</small>
        </button>
        <button className="command-kpi" onClick={() => onNavigate("edges")}>
          <span>Engine Edges</span>
          <strong>{edges.length}</strong>
          <small>{edgeGames.length || 0} games in board</small>
        </button>
      </div>

      {command?.do_nothing_warning ? (
        <div className="feed-warning command-warning">
          <AlertTriangle size={16} />
          {command.warnings.join(" ")}
        </div>
      ) : !hasAction && (
        <div className="feed-warning command-warning">
          <AlertTriangle size={16} />
          The current context has no actionable plays. That is expected while live 2026 weekly inputs are not flowing yet; use Survivor and WARPS as planning layers.
        </div>
      )}

      <div className="command-grid">
        <article className="panel command-panel">
          <div className="command-panel-head">
            <div>
              <h3><Route size={15} /> Survivor</h3>
              <p>Best pool pick after future-value and volatility penalties.</p>
            </div>
            <button className="text-button" onClick={() => onNavigate("survivor")}>Open</button>
          </div>
          {survivorWeek.primary ? (
            <div className="command-feature-pick">
              <TeamLogo team={survivorWeek.primary.team} />
              <div>
                <strong>{survivorWeek.primary.team}</strong>
                <span>
                  {survivorWeek.primary.home_away === "home" ? "vs" : "@"} {survivorWeek.primary.opponent} · {pct(survivorWeek.primary.win_probability)}
                </span>
              </div>
              <b>{score(survivorWeek.primary.survivor_score)}</b>
            </div>
          ) : (
            <div className="compact-empty">No survivor candidate loaded.</div>
          )}
          <div className="command-mini-list">
            {survivorWeek.alternatives.map((row) => (
              <span key={`${row.week}-${row.team}`}>{row.team} {pct(row.win_probability)}</span>
            ))}
          </div>
          {survivorWeek.path && (
            <div className="command-note">Season path wants {survivorWeek.path.team} in Week {commandWeek}.</div>
          )}
        </article>

        <article className="panel command-panel">
          <div className="command-panel-head">
            <div>
              <h3><Target size={15} /> Betting Card</h3>
              <p>Selector plays and watchlist spots from the weekly engine.</p>
            </div>
            <button className="text-button" onClick={() => onNavigate("card")}>Open</button>
          </div>
          {[...groups.plays, ...groups.watch].slice(0, 4).map((card) => (
            <div className={`command-bet-row ${card.action}`} key={card.key}>
              <span>W{card.week}</span>
              <strong>{card.away_tla}@{card.home_tla}</strong>
              <b>{card.market ? `${card.market} ${card.side || ""}` : titleCase(card.action)}</b>
            </div>
          ))}
          {!groups.plays.length && !groups.watch.length && (
            <div className="compact-empty">No plays or watchlist spots in the current card.</div>
          )}
        </article>

        <article className="panel command-panel">
          <div className="command-panel-head">
            <div>
              <h3><BadgeCheck size={15} /> WARPS Prior Watch</h3>
              <p>Highest {commandWeekLabel} win probabilities from preseason WARPS priors.</p>
            </div>
            <button className="text-button" onClick={() => onNavigate("warps")}>Open</button>
          </div>
          {warpsTop.map((row) => (
            <div className="command-warps-row" key={`${row.matchup}-${row.team}`}>
              <TeamLogo team={row.team} />
              <strong>{row.team}</strong>
              <span>{row.homeAway === "home" ? "vs" : "@"} {row.opponent}</span>
              <b>{pct(row.winProb)}</b>
            </div>
          ))}
        </article>

        <article className="panel command-panel">
          <div className="command-panel-head">
            <div>
              <h3><ShieldCheck size={15} /> Readiness</h3>
              <p>Whether this week is ready for betting decisions.</p>
            </div>
            <button className="text-button" onClick={() => onNavigate("scout")}>Scout</button>
          </div>
          <div className="command-readiness-list">
            <span className={cardAvailable ? "ok" : "warn"}>Current betting card {cardAvailable ? "available" : "pending"}</span>
            <span className={engineFeed?.model_readiness?.available ? "ok" : "warn"}>
              Model readiness {engineFeed?.model_readiness?.status ? titleCase(engineFeed.model_readiness.status) : "unavailable"}
            </span>
            <span className={engineFeed?.research_summary?.source_reliability ? "ok" : "warn"}>
              Source reliability {engineFeed?.research_summary?.source_reliability?.overall_status || "not loaded"}
            </span>
            <span className={preseasonOk ? "ok" : "warn"}>
              Preseason dry run {preseason?.status || "unavailable"}
              {preseason?.checks_total ? ` · ${preseason.checks_passed}/${preseason.checks_total} checks` : ""}
            </span>
            <span className={survivorBacktest?.available ? "ok" : "warn"}>
              Survivor backtest {survivorBacktestBest ? `${titleCase(survivorBacktestBest.strategy)} · ${survivorBacktestBest.avg_survived_weeks} avg weeks` : "unavailable"}
            </span>
            <span className={survivorPoolEv?.available ? "ok" : "warn"}>
              Pool EV {survivorPoolBest ? `${titleCase(survivorPoolBest.strategy)} · ${survivorPoolBest.pool_size}-entry · ${survivorPoolBest.avg_roi_units.toFixed(2)} ROI` : "unavailable"}
            </span>
            <span className={context?.mode === "live" ? "ok" : "warn"}>
              Current context {context ? `${context.week_label} · ${titleCase(context.status)}` : "not published"}
            </span>
            {command?.source_gates && Object.entries(command.source_gates).map(([gate, status]) => (
              <span className={status === "PASS" ? "ok" : "warn"} key={gate}>
                {titleCase(gate)} {status}
              </span>
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}
