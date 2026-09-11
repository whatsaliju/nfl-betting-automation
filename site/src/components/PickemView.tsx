import { teamLogos } from "../data/nflData";
import type { EngineFeed, WarpsMarketOverlay } from "../types";

interface PickemGame {
  awayTla: string;
  homeTla: string;
  matchupKey: string;
  gameDate: string;     // ISO date from WARPS overlay e.g. "2026-09-13"
  gameDay: string;      // "Thu" | "Sat" | "Sun" | "Mon"
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

function classTag(cls: string | null): string {
  if (!cls) return "pass";
  if (cls.includes("BLUE") || cls.includes("TARGETED")) return "hot";
  if (cls.includes("LEAN")) return "lean";
  if (cls.includes("FADE") || cls.includes("LANDMINE")) return "fade";
  return "pass";
}

function parseGame(
  g: { away_tla: string; home_tla: string; matchup_key: string; latest: Record<string, unknown> },
  warps: WarpsMarketOverlay | undefined
): PickemGame {
  const lat = g.latest as Record<string, string | null>;
  const spreadLine = lat.sharp_spread_line ?? "";
  const totalLine = lat.sharp_total_line ?? "";

  const spreadParts = spreadLine.split("|");
  const awaySpread = parseSpreadVal(spreadParts[0] ?? "");
  const homeSpread = parseSpreadVal(spreadParts[1] ?? "");

  const totalParts = totalLine.split("|");
  const overMatch = (totalParts[0] ?? "").match(/[ou](\d+(?:\.\d+)?)/i);
  const underMatch = (totalParts[1] ?? "").match(/[ou](\d+(?:\.\d+)?)/i);
  const over = overMatch ? parseFloat(overMatch[1]) : null;
  const under = underMatch ? parseFloat(underMatch[1]) : null;
  const ou = over !== null && under !== null ? (over + under) / 2 : (over ?? under);

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

  return {
    awayTla: g.away_tla,
    homeTla: g.home_tla,
    matchupKey: g.matchup_key,
    gameDate: warps?.game_date ?? "",
    gameDay: warps?.game_day ?? "",
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
    warpsAwayWinProb: warps?.away_win_prob ?? null,
    warpsFairHomeSpread: warps?.fair_home_spread ?? null,
    warpsOverlaySide: warps?.spread_overlay_side ?? null,
    warpsOverlayTeam: warps?.spread_overlay_team ?? null,
    warpsOverlayEdge: typeof warps?.spread_overlay_edge_points === "number" ? warps.spread_overlay_edge_points : null,
  };
}

export function PickemView({
  feed,
  warpsRows,
}: {
  feed: EngineFeed | null;
  warpsRows: WarpsMarketOverlay[];
}) {
  if (!feed) return <div className="pickem-empty">Loading engine feed…</div>;

  const ctx = feed.current_context;
  if (!ctx) return <div className="pickem-empty">No active week context.</div>;

  const warpsIndex = new Map(warpsRows.map((r) => [r.matchup_key, r]));

  const weekGames = (feed.games ?? []).filter(
    (g) =>
      g.season === ctx.season &&
      g.season_type === ctx.season_type &&
      String(g.week) === String(ctx.week) &&
      g.latest?.available
  );

  if (weekGames.length === 0) {
    return <div className="pickem-empty">No games found for {ctx.season_type} Week {ctx.week}.</div>;
  }

  const games: PickemGame[] = weekGames
    .map((g) =>
      parseGame(
        { away_tla: g.away_tla, home_tla: g.home_tla, matchup_key: g.matchup_key, latest: g.latest as Record<string, unknown> },
        warpsIndex.get(g.matchup_key)
      )
    )
    .sort((a, b) => {
      // Sort by date first, then by day-of-week order within same date
      if (a.gameDate !== b.gameDate) return a.gameDate < b.gameDate ? -1 : 1;
      return (DAY_ORDER[a.gameDay] ?? 9) - (DAY_ORDER[b.gameDay] ?? 9);
    });

  // Tiebreakers
  const teamImplied: { tla: string; implied: number; gameKey: string; role: "fav" | "dog" }[] = [];
  for (const g of games) {
    if (g.awayImplied !== null)
      teamImplied.push({ tla: g.awayTla, implied: g.awayImplied, gameKey: g.matchupKey, role: g.favTla === g.awayTla ? "fav" : "dog" });
    if (g.homeImplied !== null)
      teamImplied.push({ tla: g.homeTla, implied: g.homeImplied, gameKey: g.matchupKey, role: g.favTla === g.homeTla ? "fav" : "dog" });
  }
  const sorted = [...teamImplied].sort((a, b) => b.implied - a.implied);
  const mostPoints = sorted[0] ?? null;
  const fewestPoints = sorted[sorted.length - 1] ?? null;

  // Group by date for day headers
  const byDate: { date: string; day: string; games: PickemGame[] }[] = [];
  for (const g of games) {
    const last = byDate[byDate.length - 1];
    if (last && last.date === g.gameDate) {
      last.games.push(g);
    } else {
      byDate.push({ date: g.gameDate, day: g.gameDay || g.gameDate, games: [g] });
    }
  }

  return (
    <section className="pickem-view">
      <div className="pickem-header">
        <h2>Pick'em — {ctx.season_type} Week {ctx.week}</h2>
        <p>SU picks from Vegas spreads · WARPS fair value · implied totals from O/U + spread</p>
      </div>

      <div className="pickem-tiebreakers">
        <div className="pickem-tb most">
          <span className="tb-label">Most Points</span>
          <strong className="tb-team">{mostPoints?.tla ?? "—"}</strong>
          <span className="tb-implied">{mostPoints ? `${mostPoints.implied.toFixed(1)} pts implied` : ""}</span>
          <span className="tb-matchup">{mostPoints?.gameKey ?? ""}</span>
        </div>
        <div className="pickem-tb fewest">
          <span className="tb-label">Fewest Points</span>
          <strong className="tb-team">{fewestPoints?.tla ?? "—"}</strong>
          <span className="tb-implied">{fewestPoints ? `${fewestPoints.implied.toFixed(1)} pts implied` : ""}</span>
          <span className="tb-matchup">{fewestPoints?.gameKey ?? ""}</span>
        </div>
      </div>

      {byDate.map(({ date, day, games: dayGames }) => (
        <div key={date} className="pickem-day-group">
          <div className="pickem-day-label">{day} · {date}</div>
          <div className="pickem-grid">
            {dayGames.map((g) => {
              const myPick = g.modelPickSide === "HOME" ? g.homeTla : g.modelPickSide === "AWAY" ? g.awayTla : null;
              const modelFadesVegas = myPick && myPick !== g.favTla;
              const tag = classTag(g.classification);

              // WARPS: does WARPS agree with Vegas fav or back the dog?
              const warpsAgreesWithFav = g.warpsOverlayTeam && g.warpsOverlayTeam === g.favTla;
              const warpsBetsAwayWinPct = g.warpsAwayWinProb !== null ? Math.round(g.warpsAwayWinProb * 100) : null;
              const warpsHomeWinPct = warpsBetsAwayWinPct !== null ? 100 - warpsBetsAwayWinPct : null;
              const warpsFavWinPct = g.favTla === g.awayTla ? warpsBetsAwayWinPct : warpsHomeWinPct;

              return (
                <div key={g.matchupKey} className={`pickem-card pickem-${tag}`}>
                  <div className="pickem-matchup">
                    <div className={g.favTla === g.awayTla ? "pk-team fav" : "pk-team"}>
                      <img src={teamLogos[g.awayTla]} alt={g.awayTla} className="pk-logo" />
                      <span>{g.awayTla}</span>
                    </div>
                    <span className="pk-at">@</span>
                    <div className={g.favTla === g.homeTla ? "pk-team fav" : "pk-team"}>
                      <img src={teamLogos[g.homeTla]} alt={g.homeTla} className="pk-logo" />
                      <span>{g.homeTla}</span>
                    </div>
                  </div>

                  <div className="pickem-lines">
                    {g.awaySpread !== null && (
                      <span className="pk-line">{g.awayTla} {signed(g.awaySpread)} · O/U {g.ou?.toFixed(1) ?? "—"}</span>
                    )}
                  </div>

                  <div className="pickem-su">
                    <span className="pk-su-label">SU pick</span>
                    <strong className="pk-su-team">{g.favTla ?? "Pick'em"}</strong>
                    {warpsFavWinPct !== null && (
                      <span className="pk-win-prob">{warpsFavWinPct}%</span>
                    )}
                  </div>

                  {g.warpsFairHomeSpread !== null && (
                    <div className={`pickem-warps ${warpsAgreesWithFav ? "warps-agree" : "warps-fade"}`}>
                      <span className="warps-label">WARPS</span>
                      <span className="warps-fair">fair {g.favTla === g.homeTla ? signed(-g.warpsFairHomeSpread) : signed(g.warpsFairHomeSpread)} {g.favTla}</span>
                      {g.warpsOverlayEdge !== null && (
                        <span className="warps-edge">{warpsAgreesWithFav ? "▲" : "▼"} {g.warpsOverlayEdge.toFixed(1)}pt edge</span>
                      )}
                    </div>
                  )}

                  {myPick && (
                    <div className={`pickem-model ${modelFadesVegas ? "model-fade" : "model-agree"}`}>
                      {modelFadesVegas ? `Model fades → ${myPick}` : `Model: ${myPick} ✓`}
                      {g.modelPickMarket && g.modelPickMarket !== "none" && (
                        <span className="pk-market"> ({g.modelPickMarket})</span>
                      )}
                    </div>
                  )}

                  <div className="pickem-implied">
                    {g.awayImplied !== null && <span>{g.awayTla}: {g.awayImplied.toFixed(1)}</span>}
                    {g.homeImplied !== null && <span>{g.homeTla}: {g.homeImplied.toFixed(1)}</span>}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ))}

      <div className="pickem-totals-section">
        <h3>All Implied Totals (tiebreaker reference)</h3>
        <div className="pickem-totals-table">
          {sorted.map((row, i) => (
            <div key={row.tla} className={`pt-row ${i === 0 ? "pt-most" : i === sorted.length - 1 ? "pt-fewest" : ""}`}>
              <span className="pt-rank">{i + 1}</span>
              <span className="pt-tla">{row.tla}</span>
              <span className="pt-implied">{row.implied.toFixed(1)}</span>
              <span className="pt-matchup">{row.gameKey}</span>
              <span className="pt-role">{row.role === "fav" ? "fav" : "dog"}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
