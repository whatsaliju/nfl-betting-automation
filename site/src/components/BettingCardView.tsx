import { AlertTriangle, BadgeCheck, CircleSlash, Clock, ShieldAlert, Target } from "lucide-react";
import { teamLogos } from "../data/nflData";
import type { WeeklyBettingCard, WeeklyBettingCardRow } from "../types";

function formatScore(value?: number | null) {
  return typeof value === "number" ? value.toFixed(1) : "n/a";
}

function titleCase(value?: string | null) {
  if (!value) return "n/a";
  return value.replace(/_/g, " ");
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

function CardItem({ card }: { card: WeeklyBettingCardRow }) {
  return (
    <article className={`betting-card-item ${card.action}`}>
      <div className="betting-card-top">
        <span>W{card.week}</span>
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
          <strong>{card.market ? `${card.market.toUpperCase()} ${card.side || ""}` : "PASS"}</strong>
          <span>{card.classification || "No isolated selector edge"}</span>
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
        {(card.main_reasons || []).slice(0, 3).map((reason) => (
          <p key={reason}>{reason}</p>
        ))}
      </div>

      <div className="context-tags">
        {card.warps_alignment && <span>WARPS {titleCase(card.warps_alignment)}</span>}
        {card.quality_gate && <span>Gate {titleCase(card.quality_gate)}</span>}
        {card.source_health && card.source_health !== "OK" && <span>Source {card.source_health}</span>}
        {card.data_quality && card.data_quality !== "OK" && <span>Data {card.data_quality}</span>}
      </div>

      {(card.risk_flags || []).length > 0 && (
        <div className="risk-list">
          {(card.risk_flags || []).map((flag) => (
            <span key={flag}><ShieldAlert size={12} />{flag}</span>
          ))}
        </div>
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

export function BettingCardView({ card }: { card?: WeeklyBettingCard }) {
  const cards = card?.cards || [];
  const grouped = actionGroups(cards);

  return (
    <section className="panel betting-card-panel">
      <div className="panel-toolbar">
        <div>
          <h2>Weekly Betting Card</h2>
          <p className="panel-subtitle">Actionable plays, watchlist spots, and passes from the selector workflow</p>
        </div>
        <div className="edge-board-stats">
          <span><BadgeCheck size={14} />{card?.plays ?? 0} plays</span>
          <span><Clock size={14} />{card?.watch ?? 0} watch</span>
          <span><CircleSlash size={14} />{card?.passes ?? 0} passes</span>
        </div>
      </div>

      {!card?.available && (
        <div className="feed-warning">Weekly betting card is not available in the current engine feed.</div>
      )}

      <div className="betting-card-columns">
        <div className="betting-card-column play">
          <h3><Target size={15} /> Plays</h3>
          {grouped.plays.length ? grouped.plays.map((row) => <CardItem card={row} key={row.key} />) : <EmptyBucket label="Plays" />}
        </div>
        <div className="betting-card-column watch">
          <h3><Clock size={15} /> Watchlist</h3>
          {grouped.watch.length ? grouped.watch.map((row) => <CardItem card={row} key={row.key} />) : <EmptyBucket label="Watchlist" />}
        </div>
        <div className="betting-card-column pass">
          <h3><CircleSlash size={15} /> Passes</h3>
          {grouped.passes.length ? grouped.passes.map((row) => <CardItem card={row} key={row.key} />) : <EmptyBucket label="Passes" />}
        </div>
      </div>
    </section>
  );
}
