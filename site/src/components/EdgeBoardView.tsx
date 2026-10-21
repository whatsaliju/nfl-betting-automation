import { Activity, AlertTriangle, BadgeCheck, CircleSlash, Gauge, Info, TrendingDown, TrendingUp } from "lucide-react";
import { useEffect } from "react";
import { teamLogos } from "../data/nflData";
import type { EdgeBoardGame, EdgeMarket, LineMoveAlert, LiveTrackRecord, TrackRecordBlock, WarpsMarketOverlay } from "../types";
import { betText, edgeBetText, favoriteLine, teamify, verdictOf, VERDICT_TEXT } from "../lib/betText";

const DAY_ORDER: Record<string, number> = { Thu: 0, Fri: 1, Sat: 2, Sun: 3, Mon: 4, Tue: 5, Wed: 6 };

function stripEmoji(text: string) {
  return text.replace(/[\u{1F000}-\u{1FFFF}\u{2600}-\u{27FF}\u{FE0F}]/gu, "").trim();
}

function tierText(label: string | null) {
  if (!label) return "No isolated edge";
  const t = stripEmoji(label).toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

const MARKET_STATUS_TEXT: Record<string, string> = {
  playable: "Strong signal",
  lean: "Weak signal",
  blocked: "Blocked",
  research_only: "Research only",
  not_priced: "Not priced",
  unavailable: "No data",
};

// "blocked" covers several different reasons; say which one.
function marketStatus(market: EdgeMarket): { text: string; reason: string | null } {
  const blocker = market.blockers?.[0] ?? null;
  if (market.status === "blocked") {
    if (blocker?.startsWith("underdog ML")) return { text: "Not bet", reason: "Underdog moneylines aren't bet (32% historical win rate)" };
    if (blocker?.includes("candidate unavailable")) return { text: "No data", reason: null };
    if (blocker?.includes("conflict")) return { text: "Signals conflict", reason: (market.score ?? 0) === 0 ? null : blocker };
    if ((market.score ?? 0) === 0 || blocker?.includes("required") || blocker?.startsWith("no sharp")) return { text: "No signal", reason: null };
    return { text: "Ruled out", reason: blocker };
  }
  if (market.status === "lean" && (market.score ?? 0) === 0) return { text: "No signal", reason: null };
  return { text: MARKET_STATUS_TEXT[market.status] ?? market.status.replace(/_/g, " "), reason: blocker };
}

function MarketMini({ market, awayTla, homeTla }: { market: EdgeMarket; awayTla: string; homeTla: string }) {
  const pct = market.score != null && market.threshold != null
    ? Math.min(100, Math.max(0, (market.score / market.threshold) * 100))
    : null;
  const pick = betText(market.market, market.side, market.line, awayTla, homeTla);
  const { text, reason } = marketStatus(market);
  const live = market.status === "playable" || (market.status === "lean" && (market.score ?? 0) > 0);
  return (
    <div className={`market-mini ${market.status}`}>
      <div>
        <strong>{market.market}</strong>
        <span className={`market-line${live ? "" : " market-line-muted"}`}>{pick ?? "No side"}</span>
        {reason && <span className="market-blocker">{teamify(reason, awayTla, homeTla)}</span>}
      </div>
      <div className="market-mini-right">
        <b>{text}</b>
        {market.score != null && market.threshold != null && (
          <span className="market-score">score {market.score.toFixed(1)} · needs {market.threshold.toFixed(1)}</span>
        )}
        {pct !== null && (
          <div className="score-meter">
            <div className="score-meter-fill" style={{ width: `${pct}%` }} />
          </div>
        )}
      </div>
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

function TrackStat({ label, block }: { label: string; block: TrackRecordBlock }) {
  return (
    <div className="track-stat">
      <span>{label}</span>
      <b>{block.wins}–{block.losses}{block.pushes ? `–${block.pushes}` : ""}</b>
      <span>
        {block.avg_clv !== null ? `CLV ${block.avg_clv > 0 ? "+" : ""}${block.avg_clv.toFixed(2)}` : "CLV n/a"}
        {block.beat_close_rate !== null ? ` · beat close ${Math.round(block.beat_close_rate * 100)}%` : ""}
        {block.pending ? ` · ${block.pending} pending` : ""}
      </span>
    </div>
  );
}

function expectationLine(
  label: string,
  side: string | null | undefined,
  delta: number | null | undefined,
  joiner: string,
  away: string,
  home: string,
) {
  if (side == null) return null;
  if (side === "NEUTRAL" || typeof delta !== "number") return <span>{label}: even</span>;
  const team = side === "AWAY" ? away : home;
  return <span>{label}: {team} {joiner} {Math.abs(delta).toFixed(1)} wins</span>;
}

// After Week 5, WARPS spread edges went 48.8% against the closing line (2015-2025,
// in-season blend included): the market has caught up, so show them as context only.
const WARPS_SPREAD_WEEKS = 5;

const WARPS_ALIGNMENT_TEXT: Record<string, string> = {
  conflict: "Disagrees",
  aligned: "Agrees",
  neutral: "Neutral",
  no_spread_pick: "No engine pick",
};

function winProbText(awayProb: number | null | undefined, homeProb: number | null | undefined, away: string, home: string) {
  if (typeof awayProb !== "number" || typeof homeProb !== "number") return "n/a";
  return awayProb >= homeProb ? `${away} ${percent(awayProb)}` : `${home} ${percent(homeProb)}`;
}

export function EdgeBoardView({ games, focusGame, onFocusClear, lineMoveAlert, warpsRows, trackRecord }: { games: EdgeBoardGame[]; focusGame?: string | null; onFocusClear?: () => void; lineMoveAlert?: LineMoveAlert | null; warpsRows?: WarpsMarketOverlay[]; trackRecord?: LiveTrackRecord | null }) {
  useEffect(() => {
    if (!focusGame) return;
    const el = document.getElementById(`edge-${focusGame}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    const t = setTimeout(() => onFocusClear?.(), 2000);
    return () => clearTimeout(t);
  }, [focusGame, onFocusClear]);

  const warpsDateIndex = new Map((warpsRows ?? []).map((r) => [r.matchup_key, r]));

  const regularGames = games
    .sort((a, b) => {
      const wa = warpsDateIndex.get(a.matchup_key);
      const wb = warpsDateIndex.get(b.matchup_key);
      if (wa?.game_date && wb?.game_date && wa.game_date !== wb.game_date) {
        return wa.game_date < wb.game_date ? -1 : 1;
      }
      const dayA = DAY_ORDER[wa?.game_day ?? ""] ?? 9;
      const dayB = DAY_ORDER[wb?.game_day ?? ""] ?? 9;
      if (dayA !== dayB) return dayA - dayB;
      if (a.week !== b.week) return String(a.week).localeCompare(String(b.week));
      return (b.best_edge.score ?? 0) - (a.best_edge.score ?? 0);
    });
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

      {trackRecord && trackRecord.overall.plays > 0 && (
        <div className="track-record-strip">
          <div className="track-record-head">
            <strong>Engine track record · {trackRecord.season}</strong>
            <span>Pregame picks only, graded at the line taken</span>
          </div>
          <div className="track-record-stats">
            <TrackStat label="All plays" block={trackRecord.overall} />
            {Object.entries(trackRecord.by_market).map(([market, block]) => (
              <TrackStat key={market} label={market === "total" ? "Totals" : market === "spread" ? "Spreads" : market} block={block} />
            ))}
          </div>
          <p className="track-record-note">
            CLV is points gained against the closing line. Consistently positive CLV is the earliest sign of a real edge.
            {trackRecord.overall.wins + trackRecord.overall.losses < 50 ? " The sample is still small." : ""}
          </p>
        </div>
      )}

      {lineMoveAlert && lineMoveAlert.total_moves > 0 && (
        <div className="line-move-alert">
          <TrendingDown size={16} />
          <div>
            <strong>Line Alert: {lineMoveAlert.total_moves} significant move{lineMoveAlert.total_moves !== 1 ? "s" : ""} since last analysis</strong>
            {lineMoveAlert.pick_affected > 0 && <span> &mdash; {lineMoveAlert.pick_affected} affect model pick{lineMoveAlert.pick_affected !== 1 ? "s" : ""}</span>}
            {lineMoveAlert.summary && <p className="line-move-detail">{lineMoveAlert.summary}</p>}
            <p className="line-move-note">Re-analysis ran automatically with updated lines.</p>
          </div>
        </div>
      )}

      {!regularGames.length && (
        <div className="coming-soon-empty">
          <div className="coming-soon-icon">📡</div>
          <h3>No edge board data loaded</h3>
          <p>Spread, total, and moneyline recommendations populate here each week as the engine runs. Check back after the next weekly run.</p>
        </div>
      )}

      <div className="edge-board-grid">
        {regularGames.map((game) => {
          const best = game.best_edge;
          const factors = game.factor_summary.slice(0, 4);
          const away = game.away_tla;
          const home = game.home_tla;
          const verdict = verdictOf(game);
          const bet = edgeBetText(game);
          const wo = game.warps_market_overlay;
          const exp = game.expectation_context;
          return (
            <article className={`edge-card ${best.status}${focusGame === game.matchup_key ? " focused" : ""}`} key={`${game.week}-${game.matchup_key}`} id={`edge-${game.matchup_key}`}>
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
                {verdict === "bet" ? <TrendingUp size={18} /> : <AlertTriangle size={18} />}
                <div>
                  <strong>{bet ?? "No bet"}</strong>
                  <span>{best.market ? `${best.market} · ` : ""}{tierText(best.label)}</span>
                </div>
                <span className={`verdict-pill ${verdict}`}>{VERDICT_TEXT[verdict]}</span>
              </div>

              {game.explanation && (
                <div className={`why-box ${game.explanation.quality_action}`}>
                  {game.explanation.quality_gate === "warn" && (
                    <div className="why-box-top">
                      <span className="action-pill watch">Quality check flagged</span>
                    </div>
                  )}
                  <ul>
                    {(game.explanation.reasons || []).slice(0, 3).map((reason) => (
                      <li key={reason}>{teamify(reason, away, home)}</li>
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
                <MarketMini market={game.markets.spread} awayTla={away} homeTla={home} />
                <MarketMini market={game.markets.total} awayTla={away} homeTla={home} />
                <MarketMini market={game.markets.moneyline} awayTla={away} homeTla={home} />
              </div>

              <div className="context-tags">
                {game.schedule_context.division_game && <span>Division</span>}
                {game.schedule_context.conference_game && !game.schedule_context.division_game && <span>Conference</span>}
                {game.expectation_context?.sample_warning && <span>Thin expectation sample</span>}
                {game.source_health_status && game.source_health_status !== "OK" && <span>Source risk</span>}
                {game.data_quality_status && game.data_quality_status !== "OK" && <span>Data quality</span>}
              </div>

              {game.referee && (
                <div className={`referee-strip${
                  game.referee_stats
                    ? (game.referee_stats.ou_pct ?? 50) >= 55
                      ? " over-lean"
                      : (game.referee_stats.ou_pct ?? 50) <= 45
                      ? " under-lean"
                      : ""
                    : ""
                }`}>
                  <div className="ref-name-col">
                    <strong>🦓 {game.referee}</strong>
                    {game.referee_stats && <span>{game.referee_stats.sample_size} games · {game.referee_stats.game_type}</span>}
                  </div>
                  {game.referee_stats ? (
                    <>
                      <div className={`ref-stat-col${
                        (game.referee_stats.ats_pct ?? 50) >= 55 ? " ats-high"
                          : (game.referee_stats.ats_pct ?? 50) <= 45 ? " ats-low" : ""
                      }`}>
                        <span>ATS (fav)</span>
                        <b>{game.referee_stats.ats_record} · {(game.referee_stats.ats_pct ?? 0).toFixed(0)}%</b>
                      </div>
                      <div className={`ref-stat-col${
                        (game.referee_stats.ou_pct ?? 50) >= 55 ? " ou-high"
                          : (game.referee_stats.ou_pct ?? 50) <= 45 ? " ou-low" : ""
                      }`}>
                        <span>Over rate</span>
                        <b>{game.referee_stats.ou_record} · {(game.referee_stats.ou_pct ?? 0).toFixed(0)}%</b>
                      </div>
                    </>
                  ) : (
                    <div className="ref-stat-col"><span>No history</span></div>
                  )}
                </div>
              )}

              {exp && (exp.pythagorean_side || exp.value_gap_side || exp.overperformance_side) && (
                <div className="expectation-mini">
                  {expectationLine("Points-based strength", exp.pythagorean_side, exp.pythagorean_wins_delta, "better by", away, home)}
                  {expectationLine("Underrated vs Vegas", exp.value_gap_side, exp.pythagorean_vs_vegas_delta, "by", away, home)}
                  {expectationLine("Luckier record", exp.overperformance_side, exp.actual_vs_pythagorean_delta, "by", away, home)}
                </div>
              )}

              {wo?.available && (
                <div className={`warps-edge-strip ${game.week > WARPS_SPREAD_WEEKS ? "neutral" : wo.spread_pick_alignment || "context"}`}>
                  <div>
                    <strong>WARPS</strong>
                    <span>{game.week > WARPS_SPREAD_WEEKS ? "Info only" : WARPS_ALIGNMENT_TEXT[wo.spread_pick_alignment ?? ""] ?? "Context"}</span>
                  </div>
                  <div>
                    <span>Fair line</span>
                    <b>{favoriteLine(wo.fair_home_spread, away, home) ?? "n/a"}</b>
                  </div>
                  <div>
                    <span>Win prob</span>
                    <b>{winProbText(wo.away_win_prob, wo.home_win_prob, away, home)}</b>
                  </div>
                  {game.week > WARPS_SPREAD_WEEKS ? (
                    <p className="warps-note info">
                      After Week {WARPS_SPREAD_WEEKS}, WARPS spread edges have gone 49% against the closing line
                      (2015–2025). Use its win probability for pick'em and survivor, not for spreads.
                    </p>
                  ) : wo.spread_pick_alignment === "conflict" && wo.spread_team && (
                    <p className="warps-note">
                      WARPS disagrees with the pick and sees value on {wo.spread_team}
                      {wo.spread_side === "HOME" && typeof wo.market_home_spread === "number" ? ` ${signed(wo.market_home_spread)}` : ""}
                      {wo.spread_side === "AWAY" && typeof wo.market_away_spread === "number" ? ` ${signed(wo.market_away_spread)}` : ""}.
                    </p>
                  )}
                </div>
              )}

              {factors.length > 0 ? (
                <div className="factor-list">
                  {factors.map((factor, index) => (
                    <span key={`${factor.market}-${factor.source}-${index}`}>
                      <Activity size={12} />
                      {factor.market} {factor.source} {factor.side ? teamify(factor.side, away, home) : ""}
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
