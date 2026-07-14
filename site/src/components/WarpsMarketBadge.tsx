import type { WarpsMarketOverlay } from "../types";

interface Props {
  overlay?: WarpsMarketOverlay;
  team?: string;
  compact?: boolean;
}

function signed(value: number, digits = 1) {
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}`;
}

function fairSpreadForTeam(overlay: WarpsMarketOverlay, team?: string) {
  if (team && team === overlay.away_tla) return overlay.fair_away_spread;
  return overlay.fair_home_spread;
}

function fairMlForTeam(overlay: WarpsMarketOverlay, team?: string) {
  if (team && team === overlay.away_tla) return overlay.away_fair_moneyline;
  return overlay.home_fair_moneyline;
}

function winProbForTeam(overlay: WarpsMarketOverlay, team?: string) {
  if (team && team === overlay.away_tla) return overlay.away_win_prob;
  return overlay.home_win_prob;
}

export function WarpsMarketBadge({ overlay, team, compact = false }: Props) {
  if (!overlay) return null;

  const fairSpread = fairSpreadForTeam(overlay, team);
  const fairMl = fairMlForTeam(overlay, team);
  const winProb = winProbForTeam(overlay, team);
  const lineText = `${team || overlay.home_tla} ${signed(fairSpread)} · ML ${fairMl}`;
  const tooltip = [
    "WARPS fair-line prior",
    `${overlay.away_tla}@${overlay.home_tla}`,
    lineText,
    `Win probability ${(winProb * 100).toFixed(1)}%`,
    overlay.status === "priced" ? "Book price joined" : "No current book price joined",
    "Overlay only until weekly engine confirmation",
  ].join(" · ");

  if (compact) {
    return (
      <div className="warps-market-badge compact" title={tooltip}>
        <span>W</span>
        <strong>{signed(fairSpread)}</strong>
      </div>
    );
  }

  return (
    <div className="warps-market-badge" title={tooltip}>
      <div className="warps-market-head">
        <span>WARPS fair line</span>
        <strong>{overlay.status === "priced" ? "priced" : "prior"}</strong>
      </div>
      <div className="warps-market-lines">
        <span>{team || overlay.home_tla} {signed(fairSpread)}</span>
        <span>ML {fairMl}</span>
        <span>{(winProb * 100).toFixed(0)}%</span>
      </div>
      {overlay.status === "priced" && overlay.spread_overlay_team && (
        <div className="warps-market-edge">
          Spread edge {overlay.spread_overlay_team} {signed(Number(overlay.spread_overlay_edge_points))}
        </div>
      )}
    </div>
  );
}
