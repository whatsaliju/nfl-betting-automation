import { BarChart3, Brain, CalendarDays, FlaskConical, Gauge, GitBranch, Grid3X3, RotateCcw, ShieldCheck, Target, Trophy } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { CompareView } from "./components/CompareView";
import { EdgeBoardView } from "./components/EdgeBoardView";
import { ExpectationsView } from "./components/ExpectationsView";
import { MatrixTable } from "./components/MatrixTable";
import { PostseasonStrip } from "./components/PostseasonStrip";
import { ResearchView } from "./components/ResearchView";
import { ResultsView } from "./components/ResultsView";
import { WARPSView } from "./components/WARPSView";
import { TeamModal } from "./components/TeamModal";
import { WeekView } from "./components/WeekView";
import { availableSeasons, buildTeams, DEFAULT_SEASON, edgeBoardGames, getDisplayTeamStats, getSeasonResults, getSeasonSchedule, indexEdgeBoard, indexEngineCells, loadEngineFeed, postseasonCells } from "./lib/schedule";
import { historicalVegasLines } from "./data/nflData";
import type { EngineFeed, Filter, TeamProfile } from "./types";

type AppViewMode = "matrix" | "edges" | "expectations" | "research" | "week" | "compare" | "results" | "warps";

function percent(value?: number) {
  return typeof value === "number" ? `${Math.round(value * 1000) / 10}%` : "n/a";
}

const VALID_VIEWS = new Set<AppViewMode>(["matrix", "edges", "expectations", "research", "week", "compare", "results", "warps"]);

function hashToView(): AppViewMode {
  const h = window.location.hash.replace("#", "") as AppViewMode;
  return VALID_VIEWS.has(h) ? h : "matrix";
}

function urlToSeason() {
  const parsed = Number(new URLSearchParams(window.location.search).get("season"));
  return availableSeasons.includes(parsed) ? parsed : DEFAULT_SEASON;
}

function App() {
  const [filter, setFilter] = useState<Filter>("All");
  const [viewMode, setViewMode] = useState<AppViewMode>(hashToView);
  const [selectedSeason, setSelectedSeason] = useState(urlToSeason);
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const [modalTeam, setModalTeam] = useState<TeamProfile | null>(null);
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [selectedWeek, setSelectedWeek] = useState(1);
  const [dayFilter, setDayFilter] = useState("all");
  const [compareA, setCompareA] = useState("ARI");
  const [compareB, setCompareB] = useState("ATL");
  const [engineFeed, setEngineFeed] = useState<EngineFeed | null>(null);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [showResults, setShowResults] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (selectedSeason === DEFAULT_SEASON) {
      params.delete("season");
    } else {
      params.set("season", String(selectedSeason));
    }
    const query = params.toString();
    const hash = `#${viewMode}`;
    window.history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}${hash}`);
  }, [selectedSeason, viewMode]);

  useEffect(() => {
    const onHashChange = () => {
      setViewMode(hashToView());
      setSelectedSeason(urlToSeason());
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const seasonSchedule = useMemo(() => getSeasonSchedule(selectedSeason), [selectedSeason]);
  const displayTeamStats = useMemo(() => getDisplayTeamStats(seasonSchedule), [seasonSchedule]);
  const allTeams = useMemo(() => buildTeams(seasonSchedule), [seasonSchedule]);
  const teams = useMemo(
    () => allTeams.filter((team) => filter === "All" || team.conference === filter),
    [allTeams, filter]
  );
  const engineCells = useMemo(() => indexEngineCells(engineFeed, selectedSeason), [engineFeed, selectedSeason]);
  const edgeGames = useMemo(() => edgeBoardGames(engineFeed, selectedSeason), [engineFeed, selectedSeason]);
  const edgeIndex = useMemo(() => indexEdgeBoard(engineFeed, selectedSeason), [engineFeed, selectedSeason]);
  const playoffCells = useMemo(() => postseasonCells(engineFeed, selectedSeason), [engineFeed, selectedSeason]);
  const overlayCount = engineCells.size + playoffCells.length;
  const seasonResults = useMemo(() => getSeasonResults(seasonSchedule), [seasonSchedule]);
  const engineSeason = engineFeed?.games?.find((game) => game.season)?.season || DEFAULT_SEASON;
  const hasEngineForSeason = selectedSeason === engineSeason;
  const teamExpectations = hasEngineForSeason ? engineFeed?.team_expectations || {} : {};
  const researchSummary = hasEngineForSeason ? engineFeed?.research_summary : undefined;
  const readiness = hasEngineForSeason ? engineFeed?.model_readiness : undefined;
  const metricMeta = hasEngineForSeason
    ? {
        label: "Vegas O/U",
        title: "Preseason Vegas regular-season win total",
        legend: "Vegas O/U = preseason win total · ✓ over hit · ✗ under hit",
      }
    : seasonSchedule.hasResults
      ? {
          label: "O/U Result",
          title: "Did the team beat their Vegas preseason win total?",
          legend: "O/U = Vegas preseason line · ✓ over hit · ✗ under hit",
        }
      : {
          label: "Wins TBD",
          title: "Future season wins are not available yet",
          legend: "Wins TBD = future season",
        };

  // Resolve Vegas lines for the selected season (historical lookup or engine feed)
  const seasonVegasLines = useMemo((): Record<string, number | null> => {
    const hist = historicalVegasLines[String(selectedSeason)];
    if (hist) return hist;
    if (hasEngineForSeason) {
      const out: Record<string, number | null> = {};
      for (const [team, exp] of Object.entries(teamExpectations)) {
        out[team] = exp.vegas_win_total ?? null;
      }
      return out;
    }
    return {};
  }, [selectedSeason, hasEngineForSeason, teamExpectations]);

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
    if (!seasonSchedule.weeks.includes(selectedWeek)) {
      setSelectedWeek(seasonSchedule.weeks[0] || 1);
    }
  }, [seasonSchedule, selectedWeek]);

  useEffect(() => {
    setSelectedTeam(null);
    setModalTeam(null);
  }, [selectedSeason]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-block">
            <Grid3X3 size={26} />
          <div>
            <h1>NFL Edge Hub</h1>
            <p>{selectedSeason} Season · Matrix, betting edges, source health, and model research</p>
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
          {engineFeed && <span className="status-pill">{overlayCount} overlays</span>}
          {!hasEngineForSeason && <span className="status-pill">matrix only</span>}
        </div>
      </header>

      <section className="controls">
        <select className="season-select" value={selectedSeason} onChange={(event) => setSelectedSeason(Number(event.target.value))}>
          {availableSeasons.map((season) => (
            <option key={season} value={season}>{season}</option>
          ))}
        </select>
        <div className="segmented">
          {(["All", "AFC", "NFC"] as Filter[]).map((item) => (
            <button key={item} className={filter === item ? "active" : ""} onClick={() => setFilter(item)}>
              {item}
            </button>
          ))}
        </div>
        <div className="segmented view-tabs">
          <button className={viewMode === "matrix" ? "active" : ""} onClick={() => setViewMode("matrix")}><Grid3X3 size={15} />Matrix</button>
          <button className={viewMode === "edges" ? "active" : ""} onClick={() => setViewMode("edges")}><Target size={15} />Edges</button>
          <button className={viewMode === "expectations" ? "active" : ""} onClick={() => setViewMode("expectations")}><Gauge size={15} />Expect</button>
          <button className={viewMode === "research" ? "active" : ""} onClick={() => setViewMode("research")}><Brain size={15} />Research</button>
          <button className={viewMode === "week" ? "active" : ""} onClick={() => setViewMode("week")}><CalendarDays size={15} />Week</button>
          <button className={viewMode === "compare" ? "active" : ""} onClick={() => setViewMode("compare")}><GitBranch size={15} />Compare</button>
          <button className={viewMode === "results" ? "active" : ""} onClick={() => setViewMode("results")}><Trophy size={15} />Results</button>
          <button className={viewMode === "warps" ? "active" : ""} onClick={() => setViewMode("warps")}><FlaskConical size={15} />WARPS</button>
        </div>
        <label className="toggle">
          <input type="checkbox" checked={showHeatmap} onChange={(event) => setShowHeatmap(event.target.checked)} />
          🔥 Heatmap
        </label>
        <label className="toggle">
          <input type="checkbox" checked={showResults} onChange={(event) => setShowResults(event.target.checked)} />
          W/L results
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
            weeks={seasonSchedule.weeks}
            teamStats={displayTeamStats}
            metricLabel={metricMeta.label}
            metricTitle={metricMeta.title}
            metricLegend={metricMeta.legend}
            engineCells={engineCells}
            selectedTeam={selectedTeam}
            showHeatmap={showHeatmap}
            expectations={teamExpectations}
            results={seasonResults}
            showCellResults={showResults}
            vegasLines={seasonVegasLines}
            onSelectTeam={setSelectedTeam}
            onOpenTeam={setModalTeam}
          />
          <PostseasonStrip cells={playoffCells} />
        </>
      )}

      {viewMode === "edges" && <EdgeBoardView games={edgeGames} />}

      {viewMode === "expectations" && <ExpectationsView expectations={teamExpectations} />}

      {viewMode === "research" && <ResearchView summary={researchSummary} />}

      {viewMode === "week" && (
        <WeekView
          teams={allTeams}
          weeks={seasonSchedule.weeks}
          week={selectedWeek}
          dayFilter={dayFilter}
          engineCells={engineCells}
          edgeIndex={edgeIndex}
          onWeekChange={setSelectedWeek}
          onDayChange={setDayFilter}
        />
      )}

      {viewMode === "compare" && (
        <CompareView teams={allTeams} expectations={teamExpectations} teamA={compareA} teamB={compareB} metricLabel={metricMeta.label} onTeamA={setCompareA} onTeamB={setCompareB} />
      )}

      {viewMode === "results" && <ResultsView results={seasonResults} loading={false} error={seasonSchedule.hasResults ? null : `${selectedSeason} results are not available yet.`} />}

      {viewMode === "warps" && <WARPSView />}

      <footer className="footer-note">
        <BarChart3 size={15} />
        Public feed source: raw GitHub engine artifacts. The site remains static and embeddable.
      </footer>

      {modalTeam && <TeamModal team={modalTeam} engineCells={engineCells} expectation={teamExpectations[modalTeam.name]} metricLabel={metricMeta.label} onClose={() => setModalTeam(null)} />}
    </div>
  );
}

export default App;
