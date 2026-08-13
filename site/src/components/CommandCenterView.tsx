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
  const numWeeks = cards.map((card) => card.week).filter((w) => typeof w === "number") as number[];
  if (!numWeeks.length) {
    const strWeeks = Array.from(new Set(cards.map((card) => String(card.week ?? "")))).filter(Boolean);
    return strWeeks.length === 1 ? `${seasons.join("-")} ${strWeeks[0]}` : `${seasons.join("-")}`;
  }
  const minWeek = Math.min(...numWeeks);
  const maxWeek = Math.max(...numWeeks);
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
  const isPreseason = context?.season_type === "PRE";
  // WARPS priors and survivor use regular-season week numbers; during preseason
  // point them at the first upcoming regular season week.
  const planningWeek = isPreseason ? nextSurvivorWeek(cards) : (typeof commandWeek === "number" ? commandWeek : parseInt(String(commandWeek), 10) || 1);
  const planningWeekLabel = isPreseason ? `Reg W${planningWeek}` : commandWeekLabel;
  const survivorWeek = survivorForWeek(planningWeek);
  const warpsTop = strongestWarps(planningWeek, warpsRows);
  const edges = playableEdges(edgeGames);
  const cardAvailable = Boolean(context?.has_betting_card && bettingCard?.available);
  const commandCard = command?.betting_card;
  const hasAction = command ? !command.do_nothing_warning : groups.plays.length + groups.watch.length + edges.length > 0;
  const playCount = commandCard?.plays ?? groups.plays.length;
  const watchCount = commandCard?.watch ?? groups.watch.length;
  const laneCards = [
    {
      icon: <Target size={15} />,
      label: "Live Betting",
      value: !cardAvailable ? "No card" : playCount ? `${playCount} play${playCount !== 1 ? "s" : ""} · ${watchCount} watch` : watchCount ? `${watchCount} watch` : "No plays",
      detail: cardAvailable ? "Selector card is available for the current context." : "No current betting card is published yet.",
      state: command?.recommended_action?.startsWith("NO BET") || !cardAvailable ? "hold" : "ready",
    },
    {
      icon: <Brain size={15} />,
      label: "Win Prob Model",
      value: warpsTop[0] ? pct(warpsTop[0].winProb) : "n/a",
      detail: "Pre-game win probabilities for every matchup — good for spreads and moneylines.",
      state: "research",
    },
    {
      icon: <ShieldCheck size={15} />,
      label: "Survivor",
      value: survivorWeek.primary ? pct(survivorWeek.primary.win_probability) : "n/a",
      detail: "Offseason board uses WARPS priors, future value, and estimated public pick data.",
      state: "watch",
    },
    {
      icon: <FlaskConical size={15} />,
      label: "Research",
      value: "In progress",
      detail: "Advanced model layers under testing — not yet used for live picks.",
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
            Your weekly picks, survivor pool recommendation, and win probabilities — all in one place. {command?.action_reason || command?.warnings?.[0] || context?.message || "Use the tabs above to dig into any area."}
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
            {cardAvailable ? "Card live" : "Card pending"}
          </span>
          <span className="status-pill">
            <ClipboardList size={14} />
            {context ? `${context.season} ${context.week_label} · ${titleCase(context.mode)}` : cardSnapshot(cards)}
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

      {isPreseason && (
        <div className="command-preseason-banner">
          <strong>Preseason mode:</strong> The 2026 regular season hasn't started yet. Survivor and WARPS data is showing Reg W{planningWeek} projections so you can start planning. Betting card data will populate once weekly feeds begin.
        </div>
      )}

      <div className="command-kpi-grid">
        <button className="command-kpi" onClick={() => onNavigate("card")}>
          <span>Betting Plays</span>
          <strong>{playCount}</strong>
          <small>{watchCount} watch · {commandCard?.passes ?? groups.passes.length} pass</small>
        </button>
        <button className="command-kpi" onClick={() => onNavigate("survivor")}>
          <span>Survivor Score{isPreseason ? ` (${planningWeekLabel})` : ""}</span>
          <strong>{score(survivorWeek.primary?.survivor_score)}</strong>
          <small>{survivorWeek.primary?.team || "n/a"} · {pct(survivorWeek.primary?.win_probability)} win prob</small>
        </button>
        <button className="command-kpi" onClick={() => onNavigate("warps")}>
          <span>WARPS · Top Win Prob{isPreseason ? ` (${planningWeekLabel})` : ""}</span>
          <strong>{pct(warpsTop[0]?.winProb)}</strong>
          <small>{warpsTop[0]?.team || "n/a"} · {warpsTop[0]?.fairMl || "n/a"} fair line</small>
        </button>
        <button className="command-kpi" onClick={() => onNavigate("edges")}>
          <span>Edge Plays</span>
          <strong>{edges.length}</strong>
          <small>{edgeGames.length || 0} games analyzed</small>
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
          {isPreseason
            ? "No bets recommended yet — it's preseason. Your survivor pick is ready below. Betting picks will appear once regular season weekly data starts flowing."
            : "No bets to recommend this week. Check back as new data comes in."}
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
          {[...groups.plays, ...groups.watch].slice(0, 4).map((card) => {
            const wk = String(card.week ?? "");
            const weekDisplay = /^\d+$/.test(wk) ? `W${wk}` : wk;
            const betDisplay = card.pick_label || (card.market ? `${card.market} ${card.side || ""}` : titleCase(card.action));
            return (
              <div className={`command-bet-row ${card.action}`} key={card.key}>
                <span>{weekDisplay}</span>
                <strong>{card.away_tla}@{card.home_tla}</strong>
                <b>{betDisplay}</b>
              </div>
            );
          })}
          {!groups.plays.length && !groups.watch.length && (
            <div className="compact-empty">No plays or watchlist spots in the current card.</div>
          )}
        </article>

        <article className="panel command-panel">
          <div className="command-panel-head">
            <div>
              <h3><BadgeCheck size={15} /> Win Probability Watch</h3>
              <p>Teams with the highest modeled win probability for {planningWeekLabel}.{isPreseason ? " Planning ahead for regular season." : ""}</p>
            </div>
            <button className="text-button" onClick={() => onNavigate("warps")}>Open</button>
          </div>
          {warpsTop.length ? warpsTop.map((row) => (
            <div className="command-warps-row" key={`${row.matchup}-${row.team}`}>
              <TeamLogo team={row.team} />
              <strong>{row.team}</strong>
              <span>{row.homeAway === "home" ? "vs" : "@"} {row.opponent}</span>
              <b>{pct(row.winProb)}</b>
            </div>
          )) : (
            <div className="compact-empty">No win probability data loaded for {planningWeekLabel}.</div>
          )}
        </article>

        <article className="panel command-panel">
          <div className="command-panel-head">
            <div>
              <h3><Target size={15} /> Edge Board</h3>
              <p>Top-rated plays from the weekly engine, ranked by edge score.</p>
            </div>
            <button className="text-button" onClick={() => onNavigate("edges")}>Open</button>
          </div>
          {edges.length ? edges.map((game) => {
            const betDisplay = game.best_edge.label || game.best_edge.recommendation || `${game.best_edge.market || ""} ${game.best_edge.side || ""}`.trim() || "pick";
            return (
              <div className="command-bet-row play" key={game.matchup_key}>
                <span>W{game.week}</span>
                <strong>{game.away_tla}@{game.home_tla}</strong>
                <b>{betDisplay}</b>
              </div>
            );
          }) : (
            <div className="compact-empty">
              {isPreseason
                ? "No active edge picks yet · Plays populate once regular season games begin."
                : "No playable edge games this week."}
            </div>
          )}
        </article>
      </div>
    </section>
  );
}
