import type { EngineFeed } from "../types";

interface PickemGame {
  awayTla: string;
  homeTla: string;
  matchupKey: string;
  awaySpread: number | null;
  homeSpread: number | null;
  spreadVal: number | null;   // absolute value of spread
  favTla: string | null;      // Vegas SU favorite
  dogTla: string | null;
  ou: number | null;
  favImplied: number | null;
  dogImplied: number | null;
  awayImplied: number | null;
  homeImplied: number | null;
  modelPickSide: string | null;  // "HOME" | "AWAY" | null
  modelPickMarket: string | null;
  classification: string | null;
}

function parseSpreadVal(raw: string): number | null {
  const m = raw.match(/([+-]?\d+(?:\.\d+)?)/);
  return m ? parseFloat(m[1]) : null;
}

function parseGame(game: {
  away_tla: string;
  home_tla: string;
  matchup_key: string;
  latest: Record<string, unknown>;
}): PickemGame {
  const lat = game.latest as Record<string, string | null>;
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
      favTla = game.away_tla;
      dogTla = game.home_tla;
      spreadVal = Math.abs(awaySpread);
    } else if (homeSpread < 0) {
      favTla = game.home_tla;
      dogTla = game.away_tla;
      spreadVal = Math.abs(homeSpread);
    } else {
      spreadVal = 0;
    }
  }

  const favImplied = ou !== null && spreadVal !== null ? (ou + spreadVal) / 2 : null;
  const dogImplied = ou !== null && spreadVal !== null ? (ou - spreadVal) / 2 : null;

  const awayImplied = favTla === game.away_tla ? favImplied : dogImplied;
  const homeImplied = favTla === game.home_tla ? favImplied : dogImplied;

  const modelPickSide = (lat.pick_side as string) || null;
  const modelPickMarket = (lat.pick_market as string) || null;
  const classification = (lat.classification as string) || null;

  return {
    awayTla: game.away_tla,
    homeTla: game.home_tla,
    matchupKey: game.matchup_key,
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
    modelPickSide,
    modelPickMarket,
    classification,
  };
}

function classTag(cls: string | null): string {
  if (!cls) return "pass";
  if (cls.includes("BLUE") || cls.includes("TARGETED")) return "hot";
  if (cls.includes("LEAN")) return "lean";
  if (cls.includes("FADE") || cls.includes("LANDMINE")) return "fade";
  return "pass";
}

function signed(n: number): string {
  return n >= 0 ? `+${n}` : `${n}`;
}

export function PickemView({ feed }: { feed: EngineFeed | null }) {
  if (!feed) {
    return <div className="pickem-empty">Loading engine feed…</div>;
  }

  const ctx = feed.current_context;
  if (!ctx) {
    return <div className="pickem-empty">No active week context.</div>;
  }

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

  const games: PickemGame[] = weekGames.map((g) =>
    parseGame({
      away_tla: g.away_tla,
      home_tla: g.home_tla,
      matchup_key: g.matchup_key,
      latest: g.latest as Record<string, unknown>,
    })
  );

  // Build team implied totals for tiebreakers
  const teamImplied: { tla: string; implied: number; gameKey: string; role: "fav" | "dog" | "pk" }[] = [];
  for (const g of games) {
    if (g.awayImplied !== null) {
      teamImplied.push({
        tla: g.awayTla,
        implied: g.awayImplied,
        gameKey: `${g.awayTla}@${g.homeTla}`,
        role: g.favTla === g.awayTla ? "fav" : "dog",
      });
    }
    if (g.homeImplied !== null) {
      teamImplied.push({
        tla: g.homeTla,
        implied: g.homeImplied,
        gameKey: `${g.awayTla}@${g.homeTla}`,
        role: g.favTla === g.homeTla ? "fav" : "dog",
      });
    }
  }
  const sorted = [...teamImplied].sort((a, b) => b.implied - a.implied);
  const mostPoints = sorted[0] ?? null;
  const fewestPoints = sorted[sorted.length - 1] ?? null;

  return (
    <section className="pickem-view">
      <div className="pickem-header">
        <h2>Pick'em — {ctx.season_type} Week {ctx.week}</h2>
        <p>Straight-up picks derived from Vegas spreads · implied totals from O/U + spread</p>
      </div>

      {/* Tiebreaker callout */}
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

      {/* Game cards */}
      <div className="pickem-grid">
        {games.map((g) => {
          const myPick = g.modelPickSide === "HOME" ? g.homeTla : g.modelPickSide === "AWAY" ? g.awayTla : null;
          const modelAgreesWithVegas = myPick && myPick === g.favTla;
          const modelFadesVegas = myPick && myPick !== g.favTla;
          const tag = classTag(g.classification);

          return (
            <div key={g.matchupKey} className={`pickem-card pickem-${tag}`}>
              <div className="pickem-matchup">
                <span className={g.favTla === g.awayTla ? "pk-team fav" : "pk-team"}>{g.awayTla}</span>
                <span className="pk-at">@</span>
                <span className={g.favTla === g.homeTla ? "pk-team fav" : "pk-team"}>{g.homeTla}</span>
              </div>

              <div className="pickem-lines">
                {g.awaySpread !== null && (
                  <span className="pk-line">
                    {g.awayTla} {signed(g.awaySpread)} · O/U {g.ou?.toFixed(1) ?? "—"}
                  </span>
                )}
              </div>

              <div className="pickem-su">
                <span className="pk-su-label">SU pick</span>
                <strong className="pk-su-team">{g.favTla ?? "Pick'em"}</strong>
              </div>

              {myPick && (
                <div className={`pickem-model ${modelFadesVegas ? "model-fade" : "model-agree"}`}>
                  {modelFadesVegas
                    ? `Model fades → ${myPick}`
                    : `Model: ${myPick} ✓`}
                  {g.modelPickMarket && g.modelPickMarket !== "none" && (
                    <span className="pk-market"> ({g.modelPickMarket})</span>
                  )}
                </div>
              )}

              <div className="pickem-implied">
                {g.awayImplied !== null && (
                  <span>{g.awayTla}: {g.awayImplied.toFixed(1)}</span>
                )}
                {g.homeImplied !== null && (
                  <span>{g.homeTla}: {g.homeImplied.toFixed(1)}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Full implied totals table for tiebreaker reference */}
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
