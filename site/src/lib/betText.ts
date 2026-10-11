import type { EdgeBoardGame } from "../types";

// Feed lines are "away | home" for spread/moneyline and "o44.5 (+106) | u44.5 (-106)" for totals.
// The two halves are scraped separately and can disagree (e.g. "-7.5 | +6.5"), so only show the picked half.
export function lineForSide(line: string | null | undefined, side: string | null | undefined): string | null {
  if (!line) return null;
  const parts = line.split("|").map((p) => p.trim());
  const s = (side || "").toUpperCase();
  const idx = s === "HOME" || s === "UNDER" ? 1 : 0;
  return parts[idx] || null;
}

function sideTeam(side: string | null | undefined, awayTla: string, homeTla: string): string | null {
  const s = (side || "").toUpperCase();
  if (s === "AWAY") return awayTla;
  if (s === "HOME") return homeTla;
  return null;
}

export function betText(
  market: string | null | undefined,
  side: string | null | undefined,
  line: string | null | undefined,
  awayTla: string,
  homeTla: string,
): string | null {
  if (!market || !side) return null;
  const s = side.toUpperCase();
  const half = lineForSide(line, side);
  if (market === "total") {
    const word = s === "UNDER" ? "Under" : "Over";
    const num = half?.replace(/^[ou]/i, "");
    return num ? `${word} ${num}` : word;
  }
  const team = sideTeam(side, awayTla, homeTla) ?? side;
  return half ? `${team} ${half}` : team;
}

export function teamify(text: string, awayTla: string, homeTla: string): string {
  return text.replace(/\bAWAY\b/g, awayTla).replace(/\bHOME\b/g, homeTla);
}

// Spread from the favorite's view, e.g. fairHome=+1.9 → "CIN -1.9".
export function favoriteLine(homeSpread: number | null | undefined, awayTla: string, homeTla: string): string | null {
  if (typeof homeSpread !== "number") return null;
  if (homeSpread === 0) return "Pick'em";
  const v = Math.abs(homeSpread).toFixed(1);
  return homeSpread < 0 ? `${homeTla} -${v}` : `${awayTla} -${v}`;
}

export type Verdict = "bet" | "watch" | "pass";

export const VERDICT_TEXT: Record<Verdict, string> = {
  bet: "Bet",
  watch: "Watch — not a bet yet",
  pass: "No bet",
};

// best_edge can say "play" while the quality gate downgrades it to watch; the gate is the final word.
export function verdictOf(game: EdgeBoardGame): Verdict {
  if (game.best_edge.status !== "play") return "pass";
  const q = game.explanation?.quality_action;
  if (q === "watch" || q === "lean") return "watch";
  if (q === "pass") return "pass";
  return "bet";
}

export function edgeBetText(game: EdgeBoardGame): string | null {
  const best = game.best_edge;
  if (best.status !== "play" || !best.market) return null;
  return betText(best.market, best.side, game.markets[best.market]?.line, game.away_tla, game.home_tla);
}
