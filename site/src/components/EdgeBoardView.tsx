import { Activity, AlertTriangle, BadgeCheck, CircleSlash, Gauge, Info, TrendingUp } from "lucide-react";
import { teamLogos } from "../data/nflData";
import type { EdgeBoardGame, EdgeMarket } from "../types";

function formatScore(value: number | null) {
  return typeof value === "number" ? value.toFixed(1) : "n/a";
}

function edgeTitle(edge: EdgeBoardGame) {
  const best = edge.best_edge;
  if (best.status === "play" && best.market) {
    return `${best.market.toUpperCase()} ${best.side || ""}`;
  }
  return "PASS";
}

function marketLabel(market: EdgeMarket) {
  if (market.status === "not_priced") return "not priced";
  if (market.status === "playable") return "playable";
  if (market.status === "lean") return "lean";
  if (market.status === "blocked") return "blocked";
  return "unavailable";
}

function MarketMini({ market }: { market: EdgeMarket }) {
  return (
    <div className={`market-mini ${market.status}`}>
      <div>
        <strong>{market.market}</strong>
        <span>{market.side || marketLabel(market)}</span>
      </div>
      <b>{formatScore(market.score)}</b>
    </div>
  );
}

function signed(value?: number | null) {
  if (typeof value !== "number") return "n/a";
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}

function percent(value?: number | null) {
  if (typeof value !== "number") return "n/a";
  return `${(value * 100).toFixed(1)}%`;
}

function actionLabel(action?: string) {
  if (!action) return "pass";
  return action.replace(/_/g, " ");
}

function alignmentLabel(value?: string | null) {
  if (!value) return "unavailable";
  return value.replace(/_/g, " ");
}

export function EdgeBoardView({ games }: { games: EdgeBoardGame[] }) {
  const regularGames = games.filter((game) => game.season_type === "REG");
  const playable = regularGames.filter((game) => game.best_edge.status === "play");
  const passes = regularGames.length - playable.length;

  return (
    <section className="panel edge-board-panel">
      <div className="panel-toolbar">
        <div>
          <h2>Weekly Edge Board</h2>
          <p className="panel-subtitle">Spread, total, and moneyline readiness by matchup</p>
        </div>
        <div className="edge-board-stats">
          <span><BadgeCheck size={14} />{playable.length} playable</span>
          <span><CircleSlash size={14} />{passes} passes</span>
          <span><Info size={14} />ML not priced yet</span>
        </div>
      </div>

      {!regularGames.length && (
        <div className="coming-soon-empty">
          <div className="coming-soon-icon">📡</div>
          <h3>Edge board goes live with the season</h3>
          <p>Once Week 1 kicks off (September 2026), this view will show spread, total, and moneyline recommendations for every game — updated weekly as the engine runs.</p>
        </div>
      )}

      <div className="edge-board-grid">
        {regularGames.map((game) => {
          const best = game.best_edge;
          const factors = game.factor_summary.slice(0, 4);
          return (
            <article className={`edge-card ${best.status}`} key={`${game.week}-${game.matchup_key}`}>
              <div className="edge-card-top">
                <span>W{game.week}</span>
                <span>{game.stage || "no run"}</span>
              </div>
              <div className="edge-matchup">
                <img src={teamLogos[game.away_tla]} alt="" />
                <strong>{game.away_tla}</strong>
                <span>@</span>
                <img src={teamLogos[game.home_tla]} alt="" />
                <strong>{game.home_tla}</strong>
              </div>
              <div className="edge-decision">
                {best.status === "play" ? <TrendingUp size={18} /> : <AlertTriangle size={18} />}
                <div>
                  <strong>{edgeTitle(game)}</strong>
                  <span>{best.label || "No isolated edge"}</span>
                </div>
                <b>{formatScore(best.score)}</b>
              </div>

              {game.explanation && (
                <div className={`why-box ${game.explanation.quality_action}`}>
                  <div className="why-box-top">
                    <span className={`action-pill ${game.explanation.quality_action}`}>
                      {actionLabel(game.explanation.quality_action)}
                    </span>
                    <span>{game.explanation.confidence}</span>
                    <span>{game.explanation.quality_gate}</span>
                  </div>
                  <ul>
                    {(game.explanation.reasons || []).slice(0, 3).map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                  {game.explanation.promoted_matches?.length ? (
                    <div className="why-tags">
                      {game.explanation.promoted_matches.slice(0, 3).map((match) => (
                        <span key={match.factor}>{match.factor.replace(/_/g, " ")}</span>
                      ))}
                    </div>
                  ) : null}
                </div>
              )}

              <div className="market-row">
                <MarketMini market={game.markets.spread} />
                <MarketMini market={game.markets.total} />
                <MarketMini market={game.markets.moneyline} />
              </div>

              <div className="context-tags">
                {game.schedule_context.division_game && <span>Division</span>}
                {game.schedule_context.conference_game && !game.schedule_context.division_game && <span>Conference</span>}
                {game.expectation_context?.sample_warning && <span>Thin expectation sample</span>}
                {game.source_health_status && game.source_health_status !== "OK" && <span>Source risk</span>}
                {game.data_quality_status && game.data_quality_status !== "OK" && <span>Data quality</span>}
              </div>

              {game.expectation_context && (
                <div className="expectation-mini">
                  <span>Py {game.expectation_context.pythagorean_side || "n/a"} {signed(game.expectation_context.pythagorean_wins_delta)}</span>
                  <span>Value {game.expectation_context.value_gap_side || "n/a"} {signed(game.expectation_context.pythagorean_vs_vegas_delta)}</span>
                  <span>Act-Py {game.expectation_context.overperformance_side || "n/a"} {signed(game.expectation_context.actual_vs_pythagorean_delta)}</span>
                </div>
              )}

              {game.warps_market_overlay?.available && (
                <div className={`warps-edge-strip ${game.warps_market_overlay.spread_pick_alignment || "context"}`}>
                  <div>
                    <strong>WARPS</strong>
                    <span>{alignmentLabel(game.warps_market_overlay.spread_pick_alignment)}</span>
                  </div>
                  <div>
                    <span>Fair spread</span>
                    <b>
                      {game.home_tla} {signed(game.warps_market_overlay.fair_home_spread)}
                    </b>
                  </div>
                  <div>
                    <span>Win prob</span>
                    <b>
                      {game.home_tla} {percent(game.warps_market_overlay.home_win_prob)}
                    </b>
                  </div>
                </div>
              )}

              {factors.length > 0 ? (
                <div className="factor-list">
                  {factors.map((factor, index) => (
                    <span key={`${factor.market}-${factor.source}-${index}`}>
                      <Activity size={12} />
                      {factor.market} {factor.source} {factor.side || ""}
                    </span>
                  ))}
                </div>
              ) : (
                <div className="factor-list muted">
                  <span><Gauge size={12} />No selector factors captured for this run</span>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
