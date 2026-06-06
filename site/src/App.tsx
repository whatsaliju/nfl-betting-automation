import { BarChart3, Brain, CalendarDays, Gauge, GitBranch, Grid3X3, Home, RotateCcw, ShieldCheck, Target, Trophy } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { CompareView } from "./components/CompareView";
import { EdgeBoardView } from "./components/EdgeBoardView";
import { ExpectationsView } from "./components/ExpectationsView";
import { MatrixTable } from "./components/MatrixTable";
import { PostseasonStrip } from "./components/PostseasonStrip";
import { ResearchView } from "./components/ResearchView";
import { ResultsView } from "./components/ResultsView";
import { TeamModal } from "./components/TeamModal";
import { WeekView } from "./components/WeekView";
import { availableSeasons, buildTeams, DEFAULT_SEASON, edgeBoardGames, getDisplayTeamStats, getSeasonResults, getSeasonSchedule, indexEdgeBoard, indexEngineCells, loadEngineFeed, postseasonCells } from "./lib/schedule";
import type { EngineFeed, Filter, TeamProfile } from "./types";

type ViewMode = "matrix" | "edges" | "expectations" | "research" | "week" | "compare" | "results";
type AppViewMode = ViewMode | "home";

function percent(value?: number) {
  return typeof value === "number" ? `${Math.round(value * 1000) / 10}%` : "n/a";
}

const VALID_VIEWS = new Set<AppViewMode>(["home", "matrix", "edges", "expectations", "research", "week", "compare", "results"]);

function hashToView(): AppViewMode {
  const h = window.location.hash.replace("#", "") as AppViewMode;
  return VALID_VIEWS.has(h) ? h : "home";
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
    const hash = viewMode === "home" ? "" : `#${viewMode}`;
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
        legend: "Vegas O/U = preseason win total",
      }
    : seasonSchedule.hasResults
      ? {
          label: "Final W",
          title: "Completed regular-season wins",
          legend: "Final W = regular-season wins",
        }
      : {
          label: "Wins TBD",
          title: "Future season wins are not available yet",
          legend: "Wins TBD = future season",
        };

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
          <button className={viewMode === "home" ? "active" : ""} onClick={() => setViewMode("home")}><Home size={15} />Home</button>
          <button className={viewMode === "matrix" ? "active" : ""} onClick={() => setViewMode("matrix")}><Grid3X3 size={15} />Matrix</button>
          <button className={viewMode === "edges" ? "active" : ""} onClick={() => setViewMode("edges")}><Target size={15} />Edges</button>
          <button className={viewMode === "expectations" ? "active" : ""} onClick={() => setViewMode("expectations")}><Gauge size={15} />Expect</button>
          <button className={viewMode === "research" ? "active" : ""} onClick={() => setViewMode("research")}><Brain size={15} />Research</button>
          <button className={viewMode === "week" ? "active" : ""} onClick={() => setViewMode("week")}><CalendarDays size={15} />Week</button>
          <button className={viewMode === "compare" ? "active" : ""} onClick={() => setViewMode("compare")}><GitBranch size={15} />Compare</button>
          <button className={viewMode === "results" ? "active" : ""} onClick={() => setViewMode("results")}><Trophy size={15} />Results</button>
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

      {viewMode === "home" && (
        <section className="panel hub-home">
          <div className="panel-toolbar">
            <div>
              <h2>Labs Hub</h2>
              <p className="panel-subtitle">Experimental dashboards for football edges, model research, and investing screens</p>
            </div>
            <span className="status-pill warning">experimental</span>
          </div>
          <div className="season-jump-row">
            {availableSeasons.map((season) => (
              <button
                key={season}
                className={selectedSeason === season ? "active" : ""}
                onClick={() => {
                  setSelectedSeason(season);
                  setViewMode("matrix");
                }}
              >
                {season}
              </button>
            ))}
          </div>
          <div className="hub-grid">
            <article className="hub-card primary">
              <Grid3X3 size={20} />
              <h3>NFL Matrix</h3>
              <p>Schedule context, team filters, postseason support, matchup overlays, and expectation signals.</p>
              <button className="text-button" onClick={() => setViewMode("matrix")}>Open matrix</button>
            </article>
            <article className="hub-card">
              <Target size={20} />
              <h3>NFL Edge Board</h3>
              <p>Weekly play/watch/pass decisions with source gates, promoted factor matches, and concise pick explanations.</p>
              <button className="text-button" onClick={() => setViewMode("edges")}>Open edges</button>
            </article>
            <article className="hub-card">
              <Brain size={20} />
              <h3>Model Lab</h3>
              <p>Factor leaderboard, promotion rules, candidate overlays, and source reliability in one research surface.</p>
              <button className="text-button" onClick={() => setViewMode("research")}>Open research</button>
            </article>
          </div>
        </section>
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

      <footer className="footer-note">
        <BarChart3 size={15} />
        Public feed source: raw GitHub engine artifacts. The site remains static and embeddable.
      </footer>

      {modalTeam && <TeamModal team={modalTeam} engineCells={engineCells} expectation={teamExpectations[modalTeam.name]} metricLabel={metricMeta.label} onClose={() => setModalTeam(null)} />}
    </div>
  );
}

export default App;
