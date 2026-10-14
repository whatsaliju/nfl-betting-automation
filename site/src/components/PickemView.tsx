import { useState } from "react";
import { teamLogos } from "../data/nflData";
import gameTimesData from "../data/gameTimes.json";
import trendsData from "../data/teamTrends.json";
import { TopPicksPanel } from "./TopPicksPanel";
import type { EngineFeed, WarpsMarketOverlay } from "../types";
import { betText, favoriteLine } from "../lib/betText";

const gameTimes = (gameTimesData as { weeks: Record<string, Record<string, string>> }).weeks;

function normalizeTla(tla: string): string {
  const aliases: Record<string, string> = { WSH: "WAS" };
  return aliases[tla] ?? tla;
}

function normalizeKey(key: string): string {
  const parts = key.split("@");
  return parts.length === 2 ? `${normalizeTla(parts[0])}@${normalizeTla(parts[1])}` : key;
}

// Convert UTC ISO time to Eastern Time (EDT = UTC-4 for early NFL season)
function utcToEt(iso: string): { date: string; day: string; timeLabel: string } {
  if (!iso) return { date: "", day: "", timeLabel: "" };
  const d = new Date(iso);
  const etMs = d.getTime() - 4 * 60 * 60 * 1000;
  const et = new Date(etMs);
  const etHour = et.getUTCHours();
  const etMin = et.getUTCMinutes();
  const period = etHour >= 12 ? "PM" : "AM";
  const h12 = etHour % 12 || 12;
  const timeLabel = `${h12}:${String(etMin).padStart(2, "0")} ${period}`;
  return {
    date: et.toISOString().slice(0, 10),
    day: ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"][et.getUTCDay()],
    timeLabel,
  };
}

interface PickemGame {
  awayTla: string;
  homeTla: string;
  matchupKey: string;
  gameDate: string;     // ISO date from WARPS overlay e.g. "2026-09-13"
  gameDay: string;      // "Thu" | "Sat" | "Sun" | "Mon"
  gameTime: string;     // ISO kickoff time from gameTimes e.g. "2026-09-13T17:00:00Z"
  isCompleted: boolean;
  awayScore: number | null;
  homeScore: number | null;
  awaySpread: number | null;
  homeSpread: number | null;
  spreadVal: number | null;
  favTla: string | null;
  dogTla: string | null;
  ou: number | null;
  favImplied: number | null;
  dogImplied: number | null;
  awayImplied: number | null;
  homeImplied: number | null;
  modelPickSide: string | null;
  modelPickMarket: string | null;
  classification: string | null;
  // WARPS
  warpsAwayWinProb: number | null;
  marketAwayWinProb: number | null;
  warpsFairHomeSpread: number | null;
  warpsOverlaySide: string | null;   // "AWAY" | "HOME"
  warpsOverlayTeam: string | null;
  warpsOverlayEdge: number | null;
}

const DAY_ORDER: Record<string, number> = { Thu: 0, Fri: 1, Sat: 2, Sun: 3, Mon: 4, Tue: 5, Wed: 6 };

function parseSpreadVal(raw: string): number | null {
  const m = raw.match(/([+-]?\d+(?:\.\d+)?)/);
  return m ? parseFloat(m[1]) : null;
}

function signed(n: number): string {
  return n >= 0 ? `+${n}` : `${n}`;
}

type ConfidenceTier = "lean" | "moderate" | "high" | "strong";

function suConfidence(pct: number | null): ConfidenceTier | null {
  if (pct === null) return null;
  if (pct >= 70) return "strong";
  if (pct >= 62) return "high";
  if (pct >= 55) return "moderate";
  return "lean";
}

function spreadConfidence(edge: number | null): ConfidenceTier | null {
  if (edge === null) return null;
  const e = Math.abs(edge);
  if (e >= 5)   return "strong";
  if (e >= 3)   return "high";
  if (e >= 1.5) return "moderate";
  return "lean";
}

function classTag(cls: string | null): string {
  if (!cls) return "pass";
  if (cls.includes("BLUE") || cls.includes("TARGETED")) return "hot";
  if (cls.includes("LEAN")) return "lean";
  if (cls.includes("FADE") || cls.includes("LANDMINE")) return "fade";
  return "pass";
}

// Parse a spread/total that may be a number or a numeric string from the overlay JSON
function toNum(v: number | string | "" | null | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : parseFloat(String(v));
  return isNaN(n) ? null : n;
}

function parseGame(
  g: { away_tla: string; home_tla: string; matchup_key: string; latest: Record<string, unknown>; away_score?: number | null; home_score?: number | null },
  warps: WarpsMarketOverlay | undefined,
  kickoffTime: string | undefined
): PickemGame {
  const hasScores = g.away_score != null && g.home_score != null;
  const kickoffMs = kickoffTime ? new Date(kickoffTime).getTime() : 0;
  // Treat as completed only if scores are real (non-zero) or kickoff was 4+ hours ago
  const isCompleted = hasScores && (
    (g.away_score ?? 0) > 0 ||
    (g.home_score ?? 0) > 0 ||
    (kickoffMs > 0 && Date.now() > kickoffMs + 4 * 3600 * 1000)
  );
  const lat = g.latest as Record<string, string | null>;
  const spreadLine = lat.sharp_spread_line ?? "";
  const totalLine = lat.sharp_total_line ?? "";

  const spreadParts = spreadLine.split("|");
  let awaySpread = parseSpreadVal(spreadParts[0] ?? "");
  let homeSpread = parseSpreadVal(spreadParts[1] ?? "");
  // When engine stage data isn't available yet, fall back to WARPS overlay market spreads.
  // Overlay values may be numeric strings ("4.5") rather than numbers, so use toNum().
  if (awaySpread === null && homeSpread === null && warps) {
    awaySpread = toNum(warps.market_away_spread);
    homeSpread = toNum(warps.market_home_spread);
  }

  const totalParts = totalLine.split("|");
  const overMatch = (totalParts[0] ?? "").match(/[ou](\d+(?:\.\d+)?)/i);
  const underMatch = (totalParts[1] ?? "").match(/[ou](\d+(?:\.\d+)?)/i);
  const over = overMatch ? parseFloat(overMatch[1]) : null;
  const under = underMatch ? parseFloat(underMatch[1]) : null;
  let ou = over !== null && under !== null ? (over + under) / 2 : (over ?? under);
  // Fall back to overlay market total when engine stage data has no O/U yet
  if (ou === null && warps) {
    ou = toNum(warps.market_total);
  }

  let favTla: string | null = null;
  let dogTla: string | null = null;
  let spreadVal: number | null = null;

  if (awaySpread !== null && homeSpread !== null) {
    if (awaySpread < 0) {
      favTla = g.away_tla; dogTla = g.home_tla; spreadVal = Math.abs(awaySpread);
    } else if (homeSpread < 0) {
      favTla = g.home_tla; dogTla = g.away_tla; spreadVal = Math.abs(homeSpread);
    } else {
      spreadVal = 0;
    }
  }

  const favImplied = ou !== null && spreadVal !== null ? (ou + spreadVal) / 2 : null;
  const dogImplied = ou !== null && spreadVal !== null ? (ou - spreadVal) / 2 : null;
  const awayImplied = favTla === g.away_tla ? favImplied : dogImplied;
  const homeImplied = favTla === g.home_tla ? favImplied : dogImplied;

  const isoTime = kickoffTime ?? "";
  const etFallback = utcToEt(isoTime);
  const fallbackDate = etFallback.date;
  const parsedDay = etFallback.day;

  return {
    awayTla: normalizeTla(g.away_tla),
    homeTla: normalizeTla(g.home_tla),
    matchupKey: normalizeKey(g.matchup_key),
    gameDate: warps?.game_date ?? fallbackDate,
    gameDay: warps?.game_day ?? parsedDay,
    gameTime: isoTime,
    isCompleted,
    awayScore: g.away_score ?? null,
    homeScore: g.home_score ?? null,
    awaySpread,
    homeSpread,
    spreadVal,
    favTla,
    dogTla,
    ou,
    favImplied,
    dogImplied,
    awayImplied,
    homeImplied,
    modelPickSide: (lat.pick_side as string) || null,
    modelPickMarket: (lat.pick_market as string) || null,
    classification: (lat.classification as string) || null,
    warpsAwayWinProb: toNum(warps?.away_win_prob),
    marketAwayWinProb: toNum(warps?.away_ml_no_vig_prob),
    warpsFairHomeSpread: toNum(warps?.fair_home_spread),
    warpsOverlaySide: warps?.spread_overlay_side ?? null,
    warpsOverlayTeam: warps?.spread_overlay_team ?? null,
    warpsOverlayEdge: toNum(warps?.spread_overlay_edge_points),
  };
}

type PickemTab = "games" | "contest";

function initialTab(): PickemTab {
  try {
    if (window.location.hash === "#contest") return "contest";
    return localStorage.getItem("pickem-tab") === "contest" ? "contest" : "games";
  } catch {
    return "games";
  }
}

export function PickemView({
  feed,
  warpsRows,
}: {
  feed: EngineFeed | null;
  warpsRows: WarpsMarketOverlay[];
}) {
  const [tab, setTabState] = useState<PickemTab>(initialTab);
  const setTab = (t: PickemTab) => {
    setTabState(t);
    try { localStorage.setItem("pickem-tab", t); } catch { /* per-visit only */ }
  };
  if (!feed) return <div className="pickem-empty">Loading engine feed…</div>;

  const ctx = feed.current_context;
  if (!ctx) return <div className="pickem-empty">No active week context.</div>;

  const warpsIndex = new Map(warpsRows.map((r) => [normalizeKey(r.matchup_key), r]));
  const weekTimes: Record<string, string> = gameTimes[String(ctx.week)] ?? {};
  const edgeIndex = new Map(
    (feed.edge_board ?? [])
      .filter((e) => e.season === ctx.season && String(e.week) === String(ctx.week))
      .map((e) => [normalizeKey(e.matchup_key), e])
  );

  const weekGames = (feed.games ?? []).filter(
    (g) =>
      g.season === ctx.season &&
      g.season_type === ctx.season_type &&
      String(g.week) === String(ctx.week)
  );

  if (weekGames.length === 0) {
    return <div className="pickem-empty">No games found for {ctx.season_type} Week {ctx.week}.</div>;
  }

  const games: PickemGame[] = weekGames
    .map((g) => {
      const normKey = normalizeKey(g.matchup_key);
      return parseGame(
        { away_tla: g.away_tla, home_tla: g.home_tla, matchup_key: g.matchup_key, latest: g.latest as Record<string, unknown>, away_score: g.away_score, home_score: g.home_score },
        warpsIndex.get(normKey),
        weekTimes[normKey]
      );
    })
    .sort((a, b) => {
      // Sort by kickoff time first (ISO string sort), then date, then day-of-week
      if (a.gameTime && b.gameTime) return a.gameTime < b.gameTime ? -1 : a.gameTime > b.gameTime ? 1 : 0;
      if (a.gameDate !== b.gameDate) return a.gameDate < b.gameDate ? -1 : 1;
      return (DAY_ORDER[a.gameDay] ?? 9) - (DAY_ORDER[b.gameDay] ?? 9);
    });

  // Tiebreakers — actual scores for completed games, implied totals for upcoming
  const teamImplied: { tla: string; implied: number; gameKey: string; role: "fav" | "dog"; isActual: boolean }[] = [];
  for (const g of games) {
    if (g.isCompleted) {
      if (g.awayScore !== null)
        teamImplied.push({ tla: g.awayTla, implied: g.awayScore, gameKey: g.matchupKey, role: g.favTla === g.awayTla ? "fav" : "dog", isActual: true });
      if (g.homeScore !== null)
        teamImplied.push({ tla: g.homeTla, implied: g.homeScore, gameKey: g.matchupKey, role: g.favTla === g.homeTla ? "fav" : "dog", isActual: true });
    } else {
      if (g.awayImplied !== null)
        teamImplied.push({ tla: g.awayTla, implied: g.awayImplied, gameKey: g.matchupKey, role: g.favTla === g.awayTla ? "fav" : "dog", isActual: false });
      if (g.homeImplied !== null)
        teamImplied.push({ tla: g.homeTla, implied: g.homeImplied, gameKey: g.matchupKey, role: g.favTla === g.homeTla ? "fav" : "dog", isActual: false });
    }
  }
  const sorted = [...teamImplied].sort((a, b) => b.implied - a.implied);
  const mostPoints = sorted[0] ?? null;
  const fewestPoints = sorted[sorted.length - 1] ?? null;

  // Group by ET date, then by kickoff time slot within each day
  type TimeSlot = { timeLabel: string; games: PickemGame[] };
  type DateGroup = { date: string; day: string; slots: TimeSlot[] };
  const byDate: DateGroup[] = [];

  for (const g of games) {
    const et = g.gameTime ? utcToEt(g.gameTime) : { date: g.gameDate, day: g.gameDay, timeLabel: "" };
    const groupDate = et.date || g.gameDate;
    const dayLabel = g.gameDay || et.day || groupDate;

    let dateGroup = byDate.find((d) => d.date === groupDate);
    if (!dateGroup) {
      dateGroup = { date: groupDate, day: dayLabel, slots: [] };
      byDate.push(dateGroup);
    }

    const slotLabel = et.timeLabel;
    let slot = dateGroup.slots.find((s) => s.timeLabel === slotLabel);
    if (!slot) {
      slot = { timeLabel: slotLabel, games: [] };
      dateGroup.slots.push(slot);
    }
    slot.games.push(g);
  }

  const favRecord = (trendsData as { season: number; league: { fav_su?: { w: number; l: number } } });
  const recWins = favRecord.league.fav_su?.w ?? 0;
  const recLosses = favRecord.league.fav_su?.l ?? 0;
  const recTotal = recWins + recLosses;
  const recPct = recTotal > 0 ? Math.round((recWins / recTotal) * 100) : 0;
  // WARPS spread leans only beat the closing line in Weeks 1-5 (55% vs 49.8% after, 2015-2025).
  const warpsSpreadLive = Number(ctx.week) <= 5;

  return (
    <section className="pickem-view">
      <div className="pickem-header">
        <div className="pk-header-top">
          <h2>Pick'em — {ctx.season_type} Week {ctx.week}</h2>
          {recTotal > 0 && (
            <div className="pk-season-record">
              <span className="pk-record-label">Favorites {favRecord.season}</span>
              <span className="pk-record-wl">{recWins}–{recLosses}</span>
              <span className="pk-record-pct">{recPct}%</span>
            </div>
          )}
        </div>
        <p>Winner = Vegas favorite (66% historically, better than WARPS's 63%) · WARPS shown when it disagrees · implied totals from O/U + spread</p>
      </div>

      <div className="pk-tabs" role="tablist">
        <button role="tab" aria-selected={tab === "games"} className={tab === "games" ? "pk-tab active" : "pk-tab"} onClick={() => setTab("games")}>Games</button>
        <button role="tab" aria-selected={tab === "contest"} className={tab === "contest" ? "pk-tab active" : "pk-tab"} onClick={() => setTab("contest")}>Contest</button>
      </div>

      {tab === "contest" ? (
        <TopPicksPanel week={Number(ctx.week)} />
      ) : (
      <>
      <div className="pickem-tiebreakers">
        <div className="pickem-tb most">
          <span className="tb-label">Most Points</span>
          {mostPoints ? (
            <>
              <div className="tb-pick">
                {mostPoints.tla && <img src={teamLogos[mostPoints.tla]} alt={mostPoints.tla} className="tb-logo" />}
                <strong className="tb-team">{mostPoints.tla}</strong>
              </div>
              <span className="tb-implied">{mostPoints.isActual ? Math.round(mostPoints.implied) : mostPoints.implied.toFixed(1)} pts {mostPoints.isActual ? "scored" : "implied"}</span>
              <span className="tb-matchup">{mostPoints.gameKey}</span>
            </>
          ) : (
            <span className="tb-unavailable">Totals pending</span>
          )}
        </div>
        <div className="pickem-tb fewest">
          <span className="tb-label">Fewest Points</span>
          {fewestPoints ? (
            <>
              <div className="tb-pick">
                {fewestPoints.tla && <img src={teamLogos[fewestPoints.tla]} alt={fewestPoints.tla} className="tb-logo" />}
                <strong className="tb-team">{fewestPoints.tla}</strong>
              </div>
              <span className="tb-implied">{fewestPoints.isActual ? Math.round(fewestPoints.implied) : fewestPoints.implied.toFixed(1)} pts {fewestPoints.isActual ? "scored" : "implied"}</span>
              <span className="tb-matchup">{fewestPoints.gameKey}</span>
            </>
          ) : (
            <span className="tb-unavailable">Totals pending</span>
          )}
        </div>
      </div>

      {byDate.map(({ date, day, slots }) => (
        <div key={date} className="pickem-day-group">
          <div className="pickem-day-label">{day} · {date}</div>
          {slots.map(({ timeLabel, games: slotGames }) => (
            <div key={timeLabel || "slot"} className="pickem-time-slot">
              {slots.length > 1 && timeLabel && (
                <div className="pickem-time-label">{timeLabel} ET</div>
              )}
              <div className="pickem-grid">
              {slotGames.map((g) => {
              const myPick = g.modelPickSide === "HOME" ? g.homeTla : g.modelPickSide === "AWAY" ? g.awayTla : null;
              const tag = classTag(g.classification);

              const awayPct = g.warpsAwayWinProb !== null ? Math.round(g.warpsAwayWinProb * 100) : null;
              const warpsSuTla = awayPct !== null ? (awayPct >= 50 ? g.awayTla : g.homeTla) : null;
              const warpsSuPct = warpsSuTla ? (warpsSuTla === g.awayTla ? awayPct : 100 - (awayPct as number)) : null;
              // Winner pick = Vegas favorite (market beats WARPS straight up, 66% vs 63% 2015-2025);
              // WARPS only when there is no line yet.
              const suPickTla = g.favTla ?? warpsSuTla;
              const suFromMarket = !!g.favTla;
              const marketAwayPct = g.marketAwayWinProb !== null ? Math.round(g.marketAwayWinProb * 100) : null;
              const suPickPct = suFromMarket
                ? (marketAwayPct !== null ? (suPickTla === g.awayTla ? marketAwayPct : 100 - marketAwayPct) : null)
                : warpsSuPct;
              const suTier = suConfidence(suPickPct);
              const warpsDissent = suFromMarket && warpsSuTla && warpsSuTla !== suPickTla ? `${warpsSuTla} ${warpsSuPct}%` : null;

              const spreadPickTla = g.warpsOverlayTeam;
              const spreadPickSide = g.warpsOverlaySide;
              const spreadMktLine = spreadPickSide === "AWAY" ? g.awaySpread
                : spreadPickSide === "HOME" ? g.homeSpread : null;
              const spreadTier = spreadConfidence(g.warpsOverlayEdge);
              const warpsLine = favoriteLine(g.warpsFairHomeSpread, g.awayTla, g.homeTla);
              const vegasLine = favoriteLine(g.homeSpread ?? (g.awaySpread !== null ? -g.awaySpread : null), g.awayTla, g.homeTla);
              // Under a point of edge, WARPS's "side" is noise; don't present it as a pick.
              const spreadTossUp = !warpsSpreadLive || (g.warpsOverlayEdge !== null && Math.abs(g.warpsOverlayEdge) < 1);
              const splitPick = !!spreadPickTla && !!suPickTla && spreadPickTla !== suPickTla && spreadMktLine !== null && !spreadTossUp;

              const engineBet = g.modelPickMarket === "spread" && myPick
                ? `${myPick}${(g.modelPickSide === "AWAY" ? g.awaySpread : g.homeSpread) !== null ? ` ${signed((g.modelPickSide === "AWAY" ? g.awaySpread : g.homeSpread) as number)}` : ""}`
                : g.modelPickMarket === "total" && g.modelPickSide
                  ? `${g.modelPickSide === "UNDER" ? "Under" : "Over"}${g.ou !== null ? ` ${g.ou.toFixed(1)}` : ""}`
                  : g.modelPickMarket === "moneyline" && myPick ? `${myPick} moneyline` : null;

              const awayWon = g.isCompleted && g.awayScore !== null && g.homeScore !== null && g.awayScore > g.homeScore;
              const homeWon = g.isCompleted && g.awayScore !== null && g.homeScore !== null && g.homeScore > g.awayScore;
              const suResult = g.isCompleted && suPickTla
                ? ((awayWon && suPickTla === g.awayTla) || (homeWon && suPickTla === g.homeTla) ? "win" : "loss")
                : null;

              const enginePickTla = g.modelPickMarket === "spread" ? myPick : null;
              const modelsDisagree = !!enginePickTla && !!spreadPickTla && !spreadTossUp && enginePickTla !== spreadPickTla;

              let atsResult: "win" | "loss" | "push" | null = null;
              if (g.isCompleted && spreadPickTla && !spreadTossUp && g.awayScore !== null && g.homeScore !== null) {
                if (spreadPickSide === "AWAY" && g.awaySpread !== null) {
                  const margin = g.awayScore + g.awaySpread - g.homeScore;
                  atsResult = margin > 0 ? "win" : margin < 0 ? "loss" : "push";
                } else if (spreadPickSide === "HOME" && g.homeSpread !== null) {
                  const margin = g.homeScore + g.homeSpread - g.awayScore;
                  atsResult = margin > 0 ? "win" : margin < 0 ? "loss" : "push";
                }
              }

              // Engine total lean (WARPS has no totals signal). Unproven, so shown as a lean without a confidence tier.
              const totalMkt = edgeIndex.get(g.matchupKey)?.markets.total;
              const totalLeanSide = totalMkt && totalMkt.side && (totalMkt.score ?? 0) > 0
                && !["not_priced", "unavailable", "blocked"].includes(totalMkt.status)
                ? (totalMkt.side.toUpperCase() === "UNDER" ? "UNDER" : "OVER") : null;
              const totalLean = totalLeanSide
                ? (betText("total", totalLeanSide, totalMkt?.line, g.awayTla, g.homeTla) ?? "").replace(/\s*\(.*\)$/, "")
                : null;
              const totalLeanStrength = totalMkt && totalMkt.score != null && totalMkt.threshold != null && totalMkt.score >= totalMkt.threshold
                ? "strong signal" : "weak signal";

              const actualTotal = g.isCompleted && g.awayScore !== null && g.homeScore !== null ? g.awayScore + g.homeScore : null;
              const ouResult = actualTotal !== null && g.ou !== null
                ? (actualTotal > g.ou ? "over" : actualTotal < g.ou ? "under" : "push")
                : null;

              return (
                <div key={g.matchupKey} className={`pickem-card ${g.isCompleted ? "pickem-final" : `pickem-${tag}`}`}>
                  {g.isCompleted && (
                    <div className="pk-final-row">
                      <div className="pk-final-badge">Final</div>
                      <div className="pk-result-chips">
                        {suResult && (
                          <div className={`pk-su-result pk-su-${suResult}`}>
                            {suResult === "win" ? "✓" : "✗"} {suPickTla} win
                          </div>
                        )}
                        {atsResult && (
                          <div className={`pk-su-result pk-ats-${atsResult}`}>
                            {atsResult === "win" ? "✓" : atsResult === "push" ? "=" : "✗"} {spreadPickTla} spread
                          </div>
                        )}
                        {ouResult && (
                          <div className={`pk-su-result ${totalLeanSide && ouResult !== "push" ? (ouResult === totalLeanSide.toLowerCase() ? "pk-ats-win" : "pk-ats-loss") : "pk-ou-chip"}`}>
                            {totalLeanSide && ouResult !== "push" ? (ouResult === totalLeanSide.toLowerCase() ? "✓ " : "✗ ") : ""}
                            {ouResult === "over" ? "Over" : ouResult === "under" ? "Under" : "Push"} · {actualTotal}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  <div className="pickem-matchup">
                    <div className={`pk-team ${g.isCompleted ? (awayWon ? "pk-winner" : "pk-loser") : g.favTla === g.awayTla ? "fav" : ""}`}>
                      <img src={teamLogos[g.awayTla]} alt={g.awayTla} className="pk-logo" />
                      <span>{g.awayTla}</span>
                      {g.isCompleted && <span className="pk-score">{g.awayScore}</span>}
                    </div>
                    <span className="pk-at">{g.isCompleted ? "vs" : "@"}</span>
                    <div className={`pk-team ${g.isCompleted ? (homeWon ? "pk-winner" : "pk-loser") : g.favTla === g.homeTla ? "fav" : ""}`}>
                      <img src={teamLogos[g.homeTla]} alt={g.homeTla} className="pk-logo" />
                      <span>{g.homeTla}</span>
                      {g.isCompleted && <span className="pk-score">{g.homeScore}</span>}
                    </div>
                  </div>

                  {/* Pre-game picks stay visible (dimmed) after the final so model vs result can be compared */}
                  <div className={g.isCompleted ? "pk-pregame-frozen" : undefined}>
                    {vegasLine && (
                      <div className="pk-gameline">Vegas: {vegasLine}{g.ou !== null ? ` · O/U ${g.ou.toFixed(1)}` : ""}</div>
                    )}

                    <div className="pk-rows">
                      <div className="pk-row">
                        <span className="pk-row-label">Winner</span>
                        <div className="pk-row-main">
                          <div className="pk-row-pick">
                            {suPickTla && <img src={teamLogos[suPickTla]} alt="" className="pk-row-logo" />}
                            <strong>{suPickTla ?? "—"}</strong>
                          </div>
                          <span className="pk-row-detail">
                            {suFromMarket ? `Vegas favorite${suPickPct !== null ? ` · ${suPickPct}% to win` : ""}` : `WARPS · ${suPickPct}% to win (no line yet)`}
                          </span>
                          {warpsDissent && <span className="pk-row-detail pk-dissent">WARPS dissent: {warpsDissent}</span>}
                        </div>
                        {suTier && <span className={`pk-confidence pk-conf-${suTier}`}>{suTier}</span>}
                      </div>

                      <div className="pk-row">
                        <span className="pk-row-label">Spread</span>
                        <div className="pk-row-main">
                          {spreadPickTla && spreadTossUp ? (
                            <>
                              <div className="pk-row-pick"><strong>{warpsSpreadLive ? "Toss-up" : "No model lean"}</strong></div>
                              <span className="pk-row-detail">
                                {warpsLine ? `WARPS line ${warpsLine}` : "WARPS"}{vegasLine ? ` vs Vegas ${vegasLine}` : ""}
                                {warpsSpreadLive ? " · no real edge" : " · WARPS spread leans only hold up in Weeks\u00a01\u20115"}
                              </span>
                            </>
                          ) : spreadPickTla ? (
                            <>
                              <div className="pk-row-pick">
                                <img src={teamLogos[spreadPickTla]} alt="" className="pk-row-logo" />
                                <strong>{spreadPickTla}{spreadMktLine !== null ? ` ${signed(spreadMktLine)}` : ""}</strong>
                              </div>
                              <span className="pk-row-detail">
                                {warpsLine ? `WARPS line ${warpsLine}` : "WARPS"}
                                {g.warpsOverlayEdge !== null ? ` · ${g.warpsOverlayEdge.toFixed(1)} pts of value` : ""}
                              </span>
                            </>
                          ) : (
                            <span className="pk-row-detail">No line yet</span>
                          )}
                        </div>
                        {spreadPickTla && !spreadTossUp && spreadTier && <span className={`pk-confidence pk-conf-${spreadTier}`}>{spreadTier}</span>}
                      </div>

                      <div className="pk-row">
                        <span className="pk-row-label">Total</span>
                        <div className="pk-row-main">
                          {g.ou !== null ? (
                            <>
                              <div className="pk-row-pick"><strong>{totalLean || `O/U ${g.ou.toFixed(1)}`}</strong></div>
                              <span className="pk-row-detail">
                                {totalLean ? `Engine lean, ${totalLeanStrength} · unproven` : "No model pick"}
                              </span>
                              {g.awayImplied !== null && g.homeImplied !== null && (
                                <span className="pk-row-detail">
                                  Vegas implies {g.awayTla} {g.awayImplied.toFixed(1)}, {g.homeTla} {g.homeImplied.toFixed(1)}
                                </span>
                              )}
                            </>
                          ) : (
                            <span className="pk-row-detail">No total yet</span>
                          )}
                        </div>
                      </div>
                    </div>

                    {splitPick && !g.isCompleted && spreadTier !== "lean" && (
                      <p className="pk-summary">WARPS has {suPickTla} winning, but by less than the spread, so {spreadPickTla} {signed(spreadMktLine as number)} covers.</p>
                    )}
                    {modelsDisagree && !g.isCompleted && (
                      <p className="pk-summary">
                        Models disagree: WARPS takes {spreadPickTla} {spreadMktLine !== null ? signed(spreadMktLine) : ""}, the betting engine takes {engineBet}. Neither has a proven record yet.
                      </p>
                    )}
                    {engineBet && (
                      <div className="pk-engine">Betting engine: <strong>{engineBet}</strong>{spreadTossUp && enginePickTla && warpsSpreadLive ? " · WARPS sees no edge here" : ""}</div>
                    )}
                  </div>
                </div>
              );
            })}
              </div>
            </div>
          ))}
        </div>
      ))}

      <div className="pickem-totals-section">
        <h3>All Team Totals (tiebreaker reference)</h3>
        <div className="pickem-totals-table">
          {sorted.map((row, i) => (
            <div key={row.tla} className={`pt-row ${i === 0 ? "pt-most" : i === sorted.length - 1 ? "pt-fewest" : ""}`}>
              <span className="pt-rank">{i + 1}</span>
              <span className="pt-tla">{row.tla}</span>
              <span className="pt-implied">{row.isActual ? Math.round(row.implied) : row.implied.toFixed(1)}</span>
              <span className="pt-matchup">{row.gameKey}</span>
              <span className="pt-role">{row.isActual ? "final" : row.role === "fav" ? "fav" : "dog"}</span>
            </div>
          ))}
        </div>
      </div>
      </>
      )}
    </section>
  );
}
