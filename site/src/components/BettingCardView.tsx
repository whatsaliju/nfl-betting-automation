import { AlertTriangle, BadgeCheck, CircleSlash, Clock, ShieldAlert, Target } from "lucide-react";
import { useEffect } from "react";
import { teamLogos } from "../data/nflData";
import type { CurrentContext, WeeklyBettingCard, WeeklyBettingCardRow } from "../types";

function formatScore(value?: number | null) {
  return typeof value === "number" ? value.toFixed(1) : "n/a";
}

function titleCase(value?: string | null) {
  if (!value) return "n/a";
  return value.replace(/_/g, " ");
}

function snapshotLabel(cards: WeeklyBettingCardRow[]) {
  if (!cards.length) return "No games loaded";
  const seasons = Array.from(new Set(cards.map((card) => card.season))).sort();
  const seasonText = seasons.length === 1 ? String(seasons[0]) : `${seasons[0]}-${seasons[seasons.length - 1]}`;
  const numWeeks = cards.map((card) => card.week).filter((w) => typeof w === "number") as number[];
  if (!numWeeks.length) {
    const strWeeks = Array.from(new Set(cards.map((card) => String(card.week ?? "")))).filter(Boolean);
    return strWeeks.length === 1 ? `${seasonText} ${strWeeks[0]}` : `${seasonText}`;
  }
  const minWeek = Math.min(...numWeeks);
  const maxWeek = Math.max(...numWeeks);
  const weekText = minWeek === maxWeek ? `W${minWeek}` : `W${minWeek}-W${maxWeek}`;
  return `${seasonText} ${weekText}`;
}

function contextLabel(context?: CurrentContext) {
  if (!context) return null;
  const stage = context.stage ? ` · ${titleCase(context.stage)}` : "";
  return `${context.season} ${context.week_label}${stage}`;
}

function actionIcon(action: string) {
  if (action === "play") return <BadgeCheck size={16} />;
  if (action === "pass") return <CircleSlash size={16} />;
  return <Clock size={16} />;
}

function actionGroups(cards: WeeklyBettingCardRow[]) {
  return {
    plays: cards.filter((card) => card.action === "play"),
    watch: cards.filter((card) => card.action === "watch" || card.action === "lean"),
    passes: cards.filter((card) => card.action === "pass"),
  };
}

function weekDisplay(week: string | number | undefined | null) {
  const wk = String(week ?? "");
  return /^\d+$/.test(wk) ? `W${wk}` : wk;
}

function decisionTitle(card: WeeklyBettingCardRow) {
  if (card.action === "pass") return "PASS";
  const label = card.pick_label;
  if (card.action === "watch" || card.action === "lean") {
    return label ? `WATCH · ${label}` : card.market ? `WATCH ${card.market.toUpperCase()} ${card.side || ""}` : "WATCH";
  }
  return label || (card.market ? `${card.market.toUpperCase()} ${card.side || ""}` : "PLAY");
}

function stripLeadingEmoji(text: string) {
  return text.replace(/^[\u{1F300}-\u{1FFFF}\u{2600}-\u{27FF}\u{2300}-\u{23FF}\u{1F000}-\u{1FFFF}]+\s*/gu, "");
}

function decisionSubtitle(card: WeeklyBettingCardRow) {
  if (card.action === "pass") return "No bet from the selector";
  return card.classification ? stripLeadingEmoji(titleCase(card.classification)) : "Engine recommendation";
}

function CardItem({ card, isFocused, onViewAnalysis }: { card: WeeklyBettingCardRow; isFocused?: boolean; onViewAnalysis?: (matchupKey: string) => void }) {
  return (
    <article
      className={`betting-card-item ${card.action}${isFocused ? " focused" : ""}`}
      data-matchup={card.matchup_key}
    >
      <div className="betting-card-top">
        <span>{weekDisplay(card.week)}</span>
        <span>{titleCase(card.confidence)}</span>
      </div>
      <div className="edge-matchup">
        <img src={teamLogos[card.away_tla]} alt="" />
        <strong>{card.away_tla}</strong>
        <span>@</span>
        <img src={teamLogos[card.home_tla]} alt="" />
        <strong>{card.home_tla}</strong>
      </div>
      <div className="betting-card-decision">
        {actionIcon(card.action)}
        <div>
          <strong>{decisionTitle(card)}</strong>
          <span>{decisionSubtitle(card)}</span>
        </div>
        <b>{formatScore(card.selector_score)}</b>
      </div>

      <div className="betting-card-linebox">
        <div>
          <span>Need</span>
          <strong>{card.required_line || "n/a"}</strong>
        </div>
        <div>
          <span>Current</span>
          <strong>{card.current_line || "n/a"}</strong>
        </div>
      </div>

      <div className="betting-card-reasons">
        {card.route_reason && <p>{card.route_reason}</p>}
        {(card.main_reasons || []).slice(0, 3).map((reason) => (
          <p key={reason}>{reason}</p>
        ))}
      </div>

      <div className="context-tags">
        {card.warps_alignment && <span>WARPS {titleCase(card.warps_alignment)}</span>}
        {card.quality_gate && <span>Gate {titleCase(card.quality_gate)}</span>}
        {card.source_health && card.source_health !== "OK" && <span>Source {card.source_health}</span>}
        {card.data_quality && card.data_quality !== "OK" && <span>Data {card.data_quality}</span>}
        {card.referee && <span className="referee-tag">🦓 {card.referee}</span>}
        {card.referee_stats && (
          <span className={`referee-stat-tag ${(card.referee_stats.ou_pct ?? 50) >= 55 ? "ou-over" : (card.referee_stats.ou_pct ?? 50) <= 45 ? "ou-under" : ""}`}>
            OU {card.referee_stats.ou_pct?.toFixed(0)}% · ATS {card.referee_stats.ats_pct?.toFixed(0)}% {card.referee_stats.favorite} · n={card.referee_stats.sample_size}
          </span>
        )}
      </div>

      {(card.risk_flags || []).length > 0 && (
        <div className="risk-list">
          {(card.risk_flags || []).map((flag) => (
            <span key={flag}><ShieldAlert size={12} />{flag}</span>
          ))}
        </div>
      )}
      {onViewAnalysis && (
        <button className="text-button card-analysis-link" onClick={() => onViewAnalysis(card.matchup_key)}>
          Edge analysis →
        </button>
      )}
    </article>
  );
}

function EmptyBucket({ label }: { label: string }) {
  return (
    <div className="coming-soon-empty compact-empty">
      <AlertTriangle size={18} />
      <p>No {label.toLowerCase()} in the current card.</p>
    </div>
  );
}

export function BettingCardView({ card, context, focusCard, onFocusClear, onViewAnalysis }: { card?: WeeklyBettingCard; context?: CurrentContext; focusCard?: string | null; onFocusClear?: () => void; onViewAnalysis?: (matchupKey: string) => void }) {
  const cards = card?.cards || [];
  const grouped = actionGroups(cards);

  useEffect(() => {
    if (!focusCard) return;
    const el = document.querySelector(`[data-matchup="${focusCard}"]`) as HTMLElement | null;
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    const t = setTimeout(() => onFocusClear?.(), 2000);
    return () => clearTimeout(t);
  }, [focusCard, onFocusClear]);
  const hasActionable = grouped.plays.length > 0 || grouped.watch.length > 0;
  const activeLabel = contextLabel(context) || snapshotLabel(cards);
  const isLiveCard = Boolean(context?.has_betting_card);

  return (
    <section className="panel betting-card-panel">
      <div className="panel-toolbar">
        <div>
          <h2>Weekly Betting Card</h2>
          <p className="panel-subtitle">This week's picks · {activeLabel}</p>
        </div>
        <div className="edge-board-stats">
          <span><BadgeCheck size={14} />{card?.plays ?? 0} plays</span>
          <span><Clock size={14} />{card?.watch ?? 0} watch</span>
          <span><CircleSlash size={14} />{card?.passes ?? 0} passes</span>
        </div>
      </div>

      {!card?.available && (
        <div className="feed-warning">Picks aren't published yet for this week — check back soon.</div>
      )}

      {card?.available && context && !isLiveCard && (
        <div className="feed-warning">
          {context.message || "No picks published for this week yet. They'll appear once the weekly engine runs."}
        </div>
      )}

      {card?.available && isLiveCard && !hasActionable && (
        <div className="feed-warning">
          No bets or watchlist spots this week. Passes (games we're skipping) are shown below for reference.
        </div>
      )}

      <div className="betting-card-active-columns">
        <div className="betting-card-column play">
          <h3><Target size={15} /> Plays</h3>
          {grouped.plays.length ? grouped.plays.map((row) => <CardItem card={row} key={row.key} isFocused={focusCard === row.matchup_key} onViewAnalysis={onViewAnalysis} />) : <EmptyBucket label="Plays" />}
        </div>
        <div className="betting-card-column watch">
          <h3><Clock size={15} /> Watchlist</h3>
          {grouped.watch.length ? grouped.watch.map((row) => <CardItem card={row} key={row.key} isFocused={focusCard === row.matchup_key} onViewAnalysis={onViewAnalysis} />) : <EmptyBucket label="Watchlist" />}
        </div>
      </div>

      <details className="pass-drawer">
        <summary><CircleSlash size={15} /> Review {grouped.passes.length} passes</summary>
        <div className="betting-card-columns pass-grid">
          {grouped.passes.length ? grouped.passes.map((row) => <CardItem card={row} key={row.key} />) : <EmptyBucket label="Passes" />}
        </div>
      </details>
    </section>
  );
}
