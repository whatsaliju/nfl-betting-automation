import { Activity, BarChart3, CalendarDays, ClipboardList, Crosshair, Flame, FlaskConical, Gauge, GitBranch, Grid3X3, Home, RotateCcw, ShieldCheck, Target, Trophy } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { BettingCardView } from "./components/BettingCardView";
import { buildScoutGames } from "./components/ScoutView";
import { CommandCenterView } from "./components/CommandCenterView";
import { CompareView } from "./components/CompareView";
import { EdgeBoardView } from "./components/EdgeBoardView";
import { ExpectationsView } from "./components/ExpectationsView";
import { LiveAuditView } from "./components/LiveAuditView";
import { MatrixTable } from "./components/MatrixTable";
import { PostseasonStrip } from "./components/PostseasonStrip";
import { ResearchView } from "./components/ResearchView";
import { ResultsView } from "./components/ResultsView";
import { ScoutView } from "./components/ScoutView";
import { SurvivorView } from "./components/SurvivorView";
import { TrackRecordView } from "./components/TrackRecordView";
import { WARPSView } from "./components/WARPSView";
import { TeamModal } from "./components/TeamModal";
import { WeekView } from "./components/WeekView";
import { availableSeasons, buildTeams, DEFAULT_SEASON, edgeBoardGames, getDisplayTeamStats, getSeasonResults, getSeasonSchedule, indexEdgeBoard, indexEngineCells, loadEngineFeed, postseasonCells } from "./lib/schedule";
import { historicalVegasLines } from "./data/nflData";
import warpsMarketOverlay2026 from "./data/warpsMarketOverlay2026.json";
import type { CurrentContext, EngineFeed, Filter, LineMoveAlert, TeamProfile, WarpsMarketOverlay, WeeklyBettingCard } from "./types";

type AppViewMode = "command" | "track" | "matrix" | "edges" | "card" | "survivor" | "expectations" | "research" | "week" | "compare" | "results" | "warps" | "audit" | "scout" | "projections";

function percent(value?: number) {
  return typeof value === "number" ? `${Math.round(value * 1000) / 10}%` : "n/a";
}

const VALID_VIEWS = new Set<AppViewMode>(["command", "track", "matrix", "edges", "card", "survivor", "expectations", "research", "week", "compare", "results", "warps", "audit", "scout", "projections"]);

function cardForContext(card?: WeeklyBettingCard, context?: CurrentContext): WeeklyBettingCard | undefined {
  if (!card || !context) return card;
  const cards = (card.cards || []).filter(
    (row) => row.season === context.season && row.season_type === context.season_type && row.week === context.week
  );
  return {
    ...card,
    card_count: cards.length,
    plays: cards.filter((row) => row.action === "play").length,
    watch: cards.filter((row) => row.action === "watch" || row.action === "lean").length,
    passes: cards.filter((row) => row.action === "pass").length,
    cards,
  };
}

function hashToView(): AppViewMode {
  const h = window.location.hash.replace("#", "") as AppViewMode;
  return VALID_VIEWS.has(h) ? h : "command";
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
  const [focusedEdgeGame, setFocusedEdgeGame] = useState<string | null>(null);
  const [focusedCard, setFocusedCard] = useState<string | null>(null);

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
  const warpsMarketIndex = useMemo(() => {
    const map = new Map<string, WarpsMarketOverlay>();
    if (selectedSeason !== 2026) return map;
    for (const row of warpsMarketOverlay2026 as WarpsMarketOverlay[]) {
      map.set(row.matchup_key, row);
    }
    return map;
  }, [selectedSeason]);
  const playoffCells = useMemo(() => postseasonCells(engineFeed, selectedSeason), [engineFeed, selectedSeason]);
const seasonResults = useMemo(() => getSeasonResults(seasonSchedule), [seasonSchedule]);
  const engineSeason = engineFeed?.games?.find((game) => game.season)?.season || DEFAULT_SEASON;
  // Don't use engine expectations for seasons that are already complete — those have stale
  // partial-season actual_wins from whenever the feed was last generated.  For finished
  // seasons we read actual wins straight from seasonSchedules.json (schedule.teamStats).
  const hasEngineForSeason = selectedSeason === engineSeason && !seasonSchedule.hasResults;
  const teamExpectations = hasEngineForSeason ? engineFeed?.team_expectations || {} : {};
  const hasEdges = edgeGames.length > 0;
  const hasProjections = Object.keys(teamExpectations).length > 0;
  const currentContext = engineFeed?.current_context;
  const lineMoveAlert: LineMoveAlert | null = engineFeed?.line_move_alert ?? null;
  const currentBettingCard = useMemo(
    () => cardForContext(engineFeed?.weekly_betting_card, currentContext),
    [engineFeed?.weekly_betting_card, currentContext]
  );
  const researchSummary = hasEngineForSeason ? engineFeed?.research_summary : undefined;
  const readiness = hasEngineForSeason ? engineFeed?.model_readiness : undefined;
  const modelStages = [
    {
      label: "This Week's Pick",
      value: currentBettingCard?.plays ? `${currentBettingCard.plays} live` : "None yet",
      detail: currentContext?.has_betting_card ? "Weekly betting card is live" : "Waiting for weekly data",
      status: currentBettingCard?.plays ? "ready" : "hold",
    },
    {
      label: "Watch List",
      value: currentBettingCard?.watch ? `${currentBettingCard.watch} games` : "Empty",
      detail: "Games to monitor — not quite a bet yet",
      status: currentBettingCard?.watch ? "watch" : "hold",
    },
    {
      label: "Win Prob Model",
      value: selectedSeason === 2026 ? "Active" : "Historical",
      detail: "Pre-game win probabilities for every matchup",
      status: "research",
    },
    {
      label: "Survivor Pool",
      value: "Planning",
      detail: "Starts Week 1 · regular season only",
      status: "research",
    },
  ];
  const metricMeta = {
    label: "Vegas O/U",
    title: "Preseason Vegas regular-season win total",
    legend: "Vegas O/U = preseason win total · ✓ over hit · ✗ under hit",
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

  const scoutAlerts = useMemo(() => {
    const games = buildScoutGames(allTeams, seasonVegasLines);
    const flagged = games.filter(g => g.category !== null);
    return {
      spots: flagged.filter(g => g.category === "spot").length,
      traps: flagged.filter(g => g.category === "trap").length,
      upsets: flagged.filter(g => g.category === "upset").length,
      total: flagged.length,
    };
  }, [allTeams, seasonVegasLines]);

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
        <div className="brand-block brand-home-btn" onClick={() => setViewMode("command")} title="Back to command center">
          <Grid3X3 size={26} />
          <div>
            <h1>NFL Edge Hub</h1>
            <p>NFL picks, win probabilities &amp; schedule analysis · 2015–2026</p>
          </div>
        </div>
        <div className="status-row">
          <a className="site-home-link" href="https://lijuvarughese.com/">
            <Home size={14} />
            Main Page
          </a>
          <span className={engineError ? "status-pill warning" : "status-pill ok"}>
            <ShieldCheck size={14} />
            {engineError ? "Feed offline" : `Live feed v${engineFeed?.feed_version || "…"}`}
          </span>
          {readiness?.available && (
            <span
              className={`status-pill ${readiness.status === "READY_FOR_MONITORING" ? "ok" : "warning"}`}
              title={readiness.reason || "Historical accuracy of the win-probability model"}
            >
              {readiness.status === "READY_FOR_MONITORING" ? "Model ready" : "Model warming up"}
              {readiness.active_walk_forward?.win_rate !== undefined && (
                <strong> · {percent(readiness.active_walk_forward.win_rate)} accuracy</strong>
              )}
            </span>
          )}
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
          <button className={viewMode === "command" ? "active" : ""} onClick={() => setViewMode("command")} data-tooltip="Weekly picks & decision hub"><Activity size={15} />Command</button>
          <button className={viewMode === "card" ? "active" : ""} onClick={() => setViewMode("card")} data-tooltip="This week's picks & confidence"><ClipboardList size={15} />Bet Card</button>
          <button className={viewMode === "edges" ? "active" : ""} onClick={() => setViewMode("edges")} data-tooltip="Games ranked by edge strength">{!hasEdges && <span className="tab-soon">Soon</span>}<Target size={15} />Edge Board</button>
          <button className={viewMode === "scout" ? "active" : ""} onClick={() => setViewMode("scout")} data-tooltip="Rest, travel & trap game alerts"><Crosshair size={15} />Scout</button>
          <button className={viewMode === "survivor" ? "active" : ""} onClick={() => setViewMode("survivor")} data-tooltip="Survivor pool picks by win prob"><ShieldCheck size={15} />Survivor</button>
          <button className={viewMode === "warps" ? "active" : ""} onClick={() => setViewMode("warps")} data-tooltip="Win probability rankings & model"><BarChart3 size={15} />WARPS</button>
          <span className="view-tab-sep" aria-hidden="true" />
          <button className={viewMode === "matrix" ? "active" : ""} onClick={() => setViewMode("matrix")} data-tooltip="Full season grid with engine ratings"><Grid3X3 size={15} />Matrix</button>
          <button className={viewMode === "week" ? "active" : ""} onClick={() => setViewMode("week")} data-tooltip="Weekly schedule & matchup view"><CalendarDays size={15} />Week</button>
          <button className={viewMode === "compare" ? "active" : ""} onClick={() => setViewMode("compare")} data-tooltip="Compare two teams head-to-head"><GitBranch size={15} />Compare</button>
          <button className={viewMode === "results" ? "active" : ""} onClick={() => setViewMode("results")} data-tooltip="Final scores & betting outcomes"><Trophy size={15} />Results</button>
          <button className={["projections", "audit", "expectations"].includes(viewMode) ? "active" : ""} onClick={() => setViewMode("projections")} data-tooltip="Win-total pace vs Vegas lines">{!hasProjections && <span className="tab-soon">Soon</span>}<Gauge size={15} />Projections</button>
          <span className="view-tab-sep" aria-hidden="true" />
          <button className={viewMode === "track" ? "active" : ""} onClick={() => setViewMode("track")} data-tooltip="Historical accuracy vs Vegas lines"><ClipboardList size={15} />Track Record</button>
          <button className={viewMode === "research" ? "active" : ""} onClick={() => setViewMode("research")} data-tooltip="Factor leaderboard & model research"><FlaskConical size={15} />Research</button>
        </div>
        <label className="toggle" data-tooltip="Color Matrix by edge score">
          <input type="checkbox" checked={showHeatmap} onChange={(event) => setShowHeatmap(event.target.checked)} />
          <Flame size={14} /> Heatmap
        </label>
        <label className="toggle" data-tooltip="Show W/L results on Matrix">
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

      <section className="model-status-strip" aria-label="Model status">
        {modelStages.map((stage) => (
          <button
            key={stage.label}
            className={`model-status-card ${stage.status}`}
            onClick={() => {
              if (stage.label === "This Week's Pick" || stage.label === "Watch List") setViewMode("card");
              else if (stage.label === "Win Prob Model") setViewMode("warps");
              else if (stage.label === "Survivor Pool") setViewMode("survivor");
              else setViewMode("research");
            }}
          >
            <span>{stage.label}</span>
            <strong>{stage.value}</strong>
            <small>{stage.detail}</small>
          </button>
        ))}
      </section>

      {viewMode === "command" && (
        <CommandCenterView
          engineFeed={engineFeed}
          bettingCard={currentBettingCard}
          edgeGames={edgeGames}
          warpsRows={warpsMarketOverlay2026 as WarpsMarketOverlay[]}
          onNavigate={setViewMode}
          scoutAlerts={scoutAlerts}
          onFocusCard={(key) => { setFocusedCard(key); setViewMode("card"); }}
        />
      )}

      {viewMode === "track" && <TrackRecordView />}

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
            warpsMarketIndex={warpsMarketIndex}
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

      {viewMode === "edges" && <EdgeBoardView games={edgeGames} focusGame={focusedEdgeGame} onFocusClear={() => setFocusedEdgeGame(null)} lineMoveAlert={lineMoveAlert} />}

      {viewMode === "card" && <BettingCardView card={currentBettingCard} context={currentContext} focusCard={focusedCard} onFocusClear={() => setFocusedCard(null)} onViewAnalysis={(key) => { setFocusedEdgeGame(key); setViewMode("edges"); }} lineMoveAlert={lineMoveAlert} />}

      {viewMode === "survivor" && <SurvivorView />}

      {viewMode === "research" && <ResearchView summary={researchSummary} />}

      {viewMode === "week" && (
        <WeekView
          teams={allTeams}
          weeks={seasonSchedule.weeks}
          week={selectedWeek}
          dayFilter={dayFilter}
          engineCells={engineCells}
          edgeIndex={edgeIndex}
          warpsMarketIndex={warpsMarketIndex}
          onWeekChange={setSelectedWeek}
          onDayChange={setDayFilter}
        />
      )}

      {viewMode === "compare" && (
        <CompareView teams={allTeams} expectations={teamExpectations} teamA={compareA} teamB={compareB} metricLabel={metricMeta.label} onTeamA={setCompareA} onTeamB={setCompareB} />
      )}

      {viewMode === "results" && <ResultsView results={seasonResults} loading={false} error={seasonSchedule.hasResults ? null : `${selectedSeason} results are not available yet.`} />}

      {viewMode === "warps" && <WARPSView />}

      {(viewMode === "projections" || viewMode === "audit" || viewMode === "expectations") && (
        <>
          {currentContext?.season_type === "PRE" && Object.keys(teamExpectations).length > 0 && (
            <div className="feed-warning">
              Preseason mode — projections below are based on early preseason data only and will stabilize once regular season games are played. Numbers will shift significantly after Week 1.
            </div>
          )}
          <LiveAuditView expectations={teamExpectations} vegasLines={seasonVegasLines} season={selectedSeason} />
          {Object.keys(teamExpectations).length > 0 && <ExpectationsView expectations={teamExpectations} />}
        </>
      )}

      {viewMode === "scout" && <ScoutView teams={allTeams} weeks={seasonSchedule.weeks} vegasLines={seasonVegasLines} />}

      <footer className="footer-note">
        <BarChart3 size={15} />
        NFL picks &amp; schedule analysis · data updates weekly during the season
        <span className="footer-links">
          <button className="footer-link-btn" onClick={() => setViewMode("warps")}>WARPS model</button>
          {researchSummary && <button className="footer-link-btn" onClick={() => setViewMode("research")}>Research notes</button>}
        </span>
      </footer>

      {modalTeam && <TeamModal team={modalTeam} engineCells={engineCells} expectation={teamExpectations[modalTeam.name]} metricLabel={metricMeta.label} onClose={() => setModalTeam(null)} />}
    </div>
  );
}

export default App;
