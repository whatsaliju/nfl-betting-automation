import { BarChart3, FlaskConical } from "lucide-react";
import { WARPSView } from "./components/WARPSView";
import { bootstrapStats } from "./data/warpsData";

export default function WARPSApp() {
  return (
    <div className="warps-standalone-shell">
      <header className="warps-standalone-header">
        <div className="warps-brand">
          <FlaskConical size={28} className="warps-brand-icon" />
          <div>
            <h1>WARPS-NFL™</h1>
            <p>Win Average Regression Predictive Score · v1.8 · 2026 season</p>
          </div>
        </div>
        <div className="warps-header-kpis">
          <div className="warps-header-kpi">
            <strong>{bootstrapStats.warpsMaeFull.toFixed(3)}</strong>
            <span>MAE wins (26 seasons)</span>
          </div>
          <div className="warps-header-kpi">
            <strong>{bootstrapStats.seasonsBeatingPyth}/{bootstrapStats.totalSeasons}</strong>
            <span>seasons beat Pythagorean</span>
          </div>
          <div className="warps-header-kpi">
            <strong>p&lt;0.0001</strong>
            <span>DM vs Pythagorean</span>
          </div>
          <div className="warps-header-kpi highlight">
            <strong>2026</strong>
            <span>consensus slate live</span>
          </div>
        </div>
      </header>

      <main className="warps-standalone-main">
        <WARPSView hashNav />
      </main>

      <footer className="warps-standalone-footer">
        <BarChart3 size={14} />
        <span>
          WARPS-NFL™ is an experimental model. Not financial advice. Data: nflverse, Pro Football Reference, public Vegas lines.
        </span>
        <span className="warps-footer-copy">© 2026 · All rights reserved</span>
      </footer>
    </div>
  );
}
