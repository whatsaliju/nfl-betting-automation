import { AlertTriangle, BadgeCheck, Brain, ClipboardList, Crosshair, Gauge, Route, ShieldCheck, Target } from "lucide-react";
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
    .filter((game) => game.best_edge.status === "play")
    .sort((a, b) => (b.best_edge.score || 0) - (a.best_edge.score || 0))
    .slice(0, 4);
}

function TeamLogo({ team }: { team: string }) {
  return <img src={teamLogos[team]} alt="" />;
}

function weekDisplay(week: string | number | undefined | null) {
  const wk = String(week ?? "");
  return /^\d+$/.test(wk) ? `W${wk}` : wk;
}

export function CommandCenterView({
  engineFeed,
  bettingCard,
  edgeGames,
  warpsRows,
  scoutAlerts,
  onNavigate,
  onFocusCard,
}: {
  engineFeed: EngineFeed | null;
  bettingCard?: WeeklyBettingCard;
  edgeGames: EdgeBoardGame[];
  warpsRows: WarpsMarketOverlay[];
  scoutAlerts?: { spots: number; traps: number; upsets: number; total: number };
  onNavigate: (view: "card" | "edges" | "survivor" | "warps" | "scout") => void;
  onFocusCard?: (matchupKey: string) => void;
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
  const regularEdgeCount = edgeGames.length;

  const kpiCards = [
    {
      icon: <Target size={14} />,
      label: "Live Betting",
      value: !cardAvailable ? "—" : String(playCount || 0),
      detail: !cardAvailable
        ? "Picks pending for this week"
        : playCount
        ? `${playCount} play${playCount !== 1 ? "s" : ""} · ${watchCount} watch`
        : watchCount
        ? `${watchCount} on watch · no plays`
        : "No plays this week",
      state: command?.recommended_action?.startsWith("NO BET") || !cardAvailable ? "hold" : playCount ? "ready" : "watch",
      onClick: () => onNavigate("card"),
    },
    {
      icon: <Crosshair size={14} />,
      label: "Scout",
      value: scoutAlerts ? String(scoutAlerts.total) : "—",
      detail: scoutAlerts?.total
        ? `${scoutAlerts.spots} spot · ${scoutAlerts.traps} trap · ${scoutAlerts.upsets} upset`
        : "Rest, travel & trap game alerts",
      state: (scoutAlerts?.traps ?? 0) > 0 ? "watch" : "research",
      onClick: () => onNavigate("scout"),
    },
    {
      icon: <Brain size={14} />,
      label: isPreseason ? `WARPS (${planningWeekLabel})` : "WARPS · Win Prob",
      value: warpsTop[0] ? pct(warpsTop[0].winProb) : "n/a",
      detail: warpsTop[0]
        ? `${warpsTop[0].team} · ${warpsTop[0].fairMl || "n/a"} fair line`
        : "No model data loaded",
      state: "research",
      onClick: () => onNavigate("warps"),
    },
    {
      icon: <Gauge size={14} />,
      label: "Edge Board",
      value: String(edges.length),
      detail: edges.length
        ? `of ${regularEdgeCount} game${regularEdgeCount !== 1 ? "s" : ""} analyzed`
        : isPreseason
        ? "Populates once regular season begins"
        : "No edge plays this week",
      state: edges.length > 0 ? "ready" : "hold",
      onClick: () => onNavigate("edges"),
    },
  ];

  return (
    <section className="command-center">
      <div className="command-hero panel">
        <div>
          <span className="command-eyebrow">Weekly Command Center</span>
          <h2>{commandWeekLabel} Decision Board</h2>
          <p>
            {command?.action_reason || command?.warnings?.[0] || context?.message || "Your weekly picks, survivor pool recommendation, and win probabilities — all in one place."}
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

      {isPreseason && (
        <div className="command-preseason-banner">
          <strong>Preseason mode:</strong> The 2026 regular season hasn't started yet. Survivor and WARPS data shows Reg W{planningWeek} projections for early planning. Betting picks populate once weekly feeds begin.
        </div>
      )}

      <div className="command-kpi-grid">
        {kpiCards.map((kpi) => (
          <button key={kpi.label} className={`command-kpi ${kpi.state}`} onClick={kpi.onClick}>
            <div className="command-kpi-head">
              {kpi.icon}
              <span>{kpi.label}</span>
            </div>
            <strong>{kpi.value}</strong>
            <small>{kpi.detail}</small>
          </button>
        ))}
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
            <button className="text-button" onClick={() => onNavigate("survivor")}>Open →</button>
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
              <p>Plays and watchlist from the weekly engine — click any row to open.</p>
            </div>
            <button className="text-button" onClick={() => onNavigate("card")}>Open →</button>
          </div>
          {[...groups.plays, ...groups.watch].slice(0, 4).map((card) => {
            const betDisplay = card.pick_label || (card.market ? `${card.market} ${card.side || ""}` : titleCase(card.action));
            return (
              <div
                className={`command-bet-row ${card.action}`}
                key={card.key}
                onClick={() => { onNavigate("card"); onFocusCard?.(card.matchup_key); }}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === "Enter") { onNavigate("card"); onFocusCard?.(card.matchup_key); } }}
              >
                <span>{weekDisplay(card.week)}</span>
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
              <p>Highest modeled win prob for {planningWeekLabel} — click any row to open.</p>
            </div>
            <button className="text-button" onClick={() => onNavigate("warps")}>Open →</button>
          </div>
          {warpsTop.length ? warpsTop.map((row) => (
            <div
              className="command-warps-row"
              key={`${row.matchup}-${row.team}`}
              onClick={() => onNavigate("warps")}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && onNavigate("warps")}
            >
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
              <p>Top-rated plays ranked by edge score — click any row to open.</p>
            </div>
            <button className="text-button" onClick={() => onNavigate("edges")}>Open →</button>
          </div>
          {edges.length ? edges.map((game) => {
            const betDisplay = game.best_edge.label || game.best_edge.recommendation || `${game.best_edge.market || ""} ${game.best_edge.side || ""}`.trim() || "pick";
            return (
              <div
                className="command-bet-row play"
                key={game.matchup_key}
                onClick={() => onNavigate("edges")}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && onNavigate("edges")}
              >
                <span>W{game.week}</span>
                <strong>{game.away_tla}@{game.home_tla}</strong>
                <b>{betDisplay}</b>
              </div>
            );
          }) : (
            <div className="compact-empty">
              {isPreseason
                ? "No edge picks yet · Plays populate once regular season begins."
                : "No playable edge games this week."}
            </div>
          )}
        </article>
      </div>
    </section>
  );
}
