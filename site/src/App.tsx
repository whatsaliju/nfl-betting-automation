import { BarChart3, CalendarDays, GitBranch, Grid3X3, RotateCcw, ShieldCheck, Trophy } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { CompareView } from "./components/CompareView";
import { MatrixTable } from "./components/MatrixTable";
import { PostseasonStrip } from "./components/PostseasonStrip";
import { ResultsView } from "./components/ResultsView";
import { TeamModal } from "./components/TeamModal";
import { WeekView } from "./components/WeekView";
import { buildTeams, indexEngineCells, loadEngineFeed, loadEspnResults, postseasonCells } from "./lib/schedule";
import type { EngineFeed, Filter, GameResult, TeamProfile } from "./types";

type ViewMode = "matrix" | "week" | "compare" | "results";

function percent(value?: number) {
  return typeof value === "number" ? `${Math.round(value * 1000) / 10}%` : "n/a";
}

function App() {
  const [filter, setFilter] = useState<Filter>("All");
  const [viewMode, setViewMode] = useState<ViewMode>("matrix");
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const [modalTeam, setModalTeam] = useState<TeamProfile | null>(null);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [selectedWeek, setSelectedWeek] = useState(1);
  const [dayFilter, setDayFilter] = useState("all");
  const [compareA, setCompareA] = useState("ARI");
  const [compareB, setCompareB] = useState("ATL");
  const [engineFeed, setEngineFeed] = useState<EngineFeed | null>(null);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [results, setResults] = useState<GameResult[]>([]);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [resultsError, setResultsError] = useState<string | null>(null);

  const allTeams = useMemo(() => buildTeams(), []);
  const teams = useMemo(
    () => allTeams.filter((team) => filter === "All" || team.conference === filter),
    [allTeams, filter]
  );
  const engineCells = useMemo(() => indexEngineCells(engineFeed), [engineFeed]);
  const playoffCells = useMemo(() => postseasonCells(engineFeed), [engineFeed]);
  const readiness = engineFeed?.model_readiness;

  useEffect(() => {
    loadEngineFeed()
      .then((feed) => {
        setEngineFeed(feed);
        setEngineError(null);
      })
      .catch((error: Error) => {
        setEngineError(error.message);
      });
  }, []);

  useEffect(() => {
    if (viewMode !== "results" || results.length || resultsLoading) return;
    setResultsLoading(true);
    loadEspnResults()
      .then((loaded) => {
        setResults(loaded);
        setResultsError(null);
      })
      .catch((error: Error) => {
        setResultsError(error.message || "ESPN scores unavailable");
      })
      .finally(() => setResultsLoading(false));
  }, [results.length, resultsLoading, viewMode]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
          <Grid3X3 size={26} />
          <div>
            <h1>NFL 2025 Matrix</h1>
            <p>Schedule analytics with betting engine overlays</p>
          </div>
        </div>
        <div className="status-row">
          <span className={engineError ? "status-pill warning" : "status-pill ok"}>
            <ShieldCheck size={14} />
            {engineError ? "Engine feed unavailable" : `Engine feed ${engineFeed?.feed_version || "loading"}`}
          </span>
          {readiness?.available && (
            <span
              className={`status-pill readiness ${
                readiness.status === "READY_FOR_MONITORING" ? "ok" : "warning"
              }`}
              title={readiness.reason}
            >
              {readiness.status.replace(/_/g, " ")}
              {readiness.active_walk_forward?.win_rate !== undefined && (
                <strong>{percent(readiness.active_walk_forward.win_rate)} WF</strong>
              )}
            </span>
          )}
          {engineFeed && <span className="status-pill">{engineFeed.team_cell_count} overlays</span>}
        </div>
      </header>

      <section className="controls">
        <div className="segmented">
          {(["All", "AFC", "NFC"] as Filter[]).map((item) => (
            <button key={item} className={filter === item ? "active" : ""} onClick={() => setFilter(item)}>
              {item}
            </button>
          ))}
        </div>
        <div className="segmented view-tabs">
          <button className={viewMode === "matrix" ? "active" : ""} onClick={() => setViewMode("matrix")}><Grid3X3 size={15} />Matrix</button>
          <button className={viewMode === "week" ? "active" : ""} onClick={() => setViewMode("week")}><CalendarDays size={15} />Week</button>
          <button className={viewMode === "compare" ? "active" : ""} onClick={() => setViewMode("compare")}><GitBranch size={15} />Compare</button>
          <button className={viewMode === "results" ? "active" : ""} onClick={() => setViewMode("results")}><Trophy size={15} />Results</button>
        </div>
        <label className="toggle">
          <input type="checkbox" checked={showHeatmap} onChange={(event) => setShowHeatmap(event.target.checked)} />
          Opponent heatmap
        </label>
        {selectedTeam && (
          <button className="text-button" onClick={() => setSelectedTeam(null)}>
            <RotateCcw size={15} /> Clear {selectedTeam}
          </button>
        )}
      </section>

      {engineError && (
        <div className="feed-warning">
          Engine overlay feed could not be loaded. The schedule, filters, modals, and ESPN result views still work.
        </div>
      )}

      {viewMode === "matrix" && (
        <>
          <MatrixTable
            teams={teams}
            engineCells={engineCells}
            selectedTeam={selectedTeam}
            showHeatmap={showHeatmap}
            onSelectTeam={setSelectedTeam}
            onOpenTeam={setModalTeam}
          />
          <PostseasonStrip cells={playoffCells} />
        </>
      )}

      {viewMode === "week" && (
        <WeekView
          teams={allTeams}
          week={selectedWeek}
          dayFilter={dayFilter}
          engineCells={engineCells}
          onWeekChange={setSelectedWeek}
          onDayChange={setDayFilter}
        />
      )}

      {viewMode === "compare" && (
        <CompareView teams={allTeams} teamA={compareA} teamB={compareB} onTeamA={setCompareA} onTeamB={setCompareB} />
      )}

      {viewMode === "results" && <ResultsView results={results} loading={resultsLoading} error={resultsError} />}

      <footer className="footer-note">
        <BarChart3 size={15} />
        Public feed source: raw GitHub engine artifacts. The site remains static and embeddable.
      </footer>

      {modalTeam && <TeamModal team={modalTeam} engineCells={engineCells} onClose={() => setModalTeam(null)} />}
    </div>
  );
}

export default App;
