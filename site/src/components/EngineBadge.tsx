import { Activity, CheckCircle2, ShieldAlert } from "lucide-react";
import type { EngineTeamCell } from "../types";


export function EngineBadge({ cell }: { cell?: EngineTeamCell }) {
  if (!cell?.analysis_available) return null;

  const sourceRisk = !!(cell.source_health_status && cell.source_health_status !== "OK");
  const pickText = cell.pick_market && cell.pick_market !== "none"
    ? `${cell.pick_market}${cell.pick_side ? ` ${cell.pick_side}` : ""}`
    : null;

  const tooltip = [
    cell.classification,
    cell.source_health_status && cell.source_health_status !== "OK" ? `⚠ ${cell.source_health_status}` : null,
  ].filter(Boolean).join(" · ") || "Engine analysis available";

  return (
    <div className="engine-badge" title={tooltip}>
      <span className={`engine-stage${sourceRisk ? " engine-stage-risk" : ""}`}>
        {sourceRisk ? <ShieldAlert size={11} /> : <CheckCircle2 size={11} />}
        {cell.latest_stage || "run"}
      </span>
      {pickText && (
        <span className={cell.pick_on_team ? "pick-on-team" : "pick-other-team"}>
          <Activity size={11} />
          {pickText}
        </span>
      )}
    </div>
  );
}
