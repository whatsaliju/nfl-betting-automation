import { useMemo, useState } from "react";
import { teamLogos } from "../data/nflData";
import { cleanOpponent, isDivisionGame, isSignificantTravel } from "../lib/schedule";
import type { TeamProfile } from "../types";

interface Props {
  teams: TeamProfile[];
  weeks: number[];
  vegasLines: Record<string, number | null>;
}

type Category = "spot" | "trap" | "upset";

interface SpotGame {
  week: number;
  homeTeam: string;
  awayTeam: string;
  dayOfWeek: string;
  homeDaysRest: number | null;
  awayDaysRest: number | null;
  awayHasTravel: boolean;
  awayIsB2B: boolean;
  homeIsPostBye: boolean;
  homeIsShortRest: boolean;
  awayIsShortRest: boolean;
  awayIsPostBye: boolean;
  isDivision: boolean;
  homeVegas: number | null;
  awayVegas: number | null;
  warpsDelta: number | null;
  score: number;
  scheduleScore: number;
  tags: string[];
  narrative: string;
  category: Category | null;
}

function buildGames(teams: TeamProfile[], vegasLines: Record<string, number | null>): SpotGame[] {
  const seen = new Set<string>();
  const games: SpotGame[] = [];

  for (const team of teams) {
    for (const gameWeek of team.weeks) {
      if (!gameWeek.opponent || gameWeek.opponent === "BYE" || gameWeek.opponent.startsWith("@")) continue;
      const homeTeam = team.name;
      const awayTeam = cleanOpponent(gameWeek.opponent);
      const key = `${awayTeam}@${homeTeam}:${gameWeek.week}`;
      if (seen.has(key)) continue;
      seen.add(key);

      const awayProfile = teams.find(t => t.name === awayTeam);
      if (!awayProfile) continue;
      const awayGW = awayProfile.weeks.find(w => w.week === gameWeek.week);
      if (!awayGW) continue;

      const homeDaysRest = gameWeek.daysRest;
      const awayDaysRest = awayGW.daysRest;
      const homeVegas = vegasLines[homeTeam] ?? null;
      const awayVegas = vegasLines[awayTeam] ?? null;
      const warpsDelta = homeVegas !== null && awayVegas !== null ? homeVegas - awayVegas : null;

      const awayHasTravel = isSignificantTravel(awayTeam, homeTeam, gameWeek.week);
      const awayIsB2B = awayProfile.backToBackInfo.some(b => b.week === gameWeek.week);
      const homeIsPostBye = homeDaysRest !== null && homeDaysRest >= 14;
      const homeIsShortRest = homeDaysRest !== null && homeDaysRest < 6;
      const awayIsShortRest = awayDaysRest !== null && awayDaysRest < 6;
      const awayIsPostBye = awayDaysRest !== null && awayDaysRest >= 14;
      const isDivision = isDivisionGame(homeTeam, `@${awayTeam}`);

      // Schedule-only score (excludes WARPS delta)
      let scheduleScore = 1.0; // home field baseline
      if (homeIsPostBye) scheduleScore += 2.0;
      if (homeIsShortRest) scheduleScore -= 2.0;
      if (awayIsShortRest) scheduleScore += 2.0;
      if (awayIsPostBye) scheduleScore -= 1.0;
      if (awayHasTravel) scheduleScore += 1.5;
      if (awayIsB2B) scheduleScore += 1.0;

      const warpsBump = warpsDelta !== null ? warpsDelta * 0.2 : 0;
      const score = scheduleScore + warpsBump;

      const tags: string[] = [];
      if (homeIsPostBye) tags.push("Home Post-Bye");
      if (homeIsShortRest) tags.push("Home Short Rest");
      if (awayIsShortRest) tags.push("Away Short Rest");
      if (awayIsPostBye) tags.push("Away Post-Bye");
      if (awayHasTravel) tags.push("Cross-Country");
      if (awayIsB2B) tags.push("B2B Road");
      if (isDivision) tags.push("Division");

      const parts: string[] = [];
      if (homeIsPostBye) parts.push(`${homeTeam} off bye`);
      if (homeIsShortRest) parts.push(`${homeTeam} on short rest`);
      if (awayIsShortRest) parts.push(`${awayTeam} on short rest`);
      if (awayIsB2B) parts.push(`${awayTeam} on 2nd straight road trip`);
      if (awayHasTravel) parts.push(`coast-to-coast travel for ${awayTeam}`);
      if (awayIsPostBye) parts.push(`${awayTeam} coming off bye`);
      if (warpsDelta !== null && warpsDelta > 2) parts.push(`WARPS favors ${homeTeam} by ${warpsDelta.toFixed(1)}w`);
      if (warpsDelta !== null && warpsDelta < -2) parts.push(`WARPS favors ${awayTeam} by ${Math.abs(warpsDelta).toFixed(1)}w`);
      const narrative = parts.join(" · ") || "Neutral matchup";

      // Classify
      let category: Category | null = null;
      if (scheduleScore >= 2.5 && (warpsDelta === null || warpsDelta >= -1)) {
        category = "spot"; // home team clear situational edge
      } else if (scheduleScore <= 0.5 && warpsDelta !== null && warpsDelta > 1.5) {
        category = "trap"; // strong home favorite but in a bad spot
      } else if (scheduleScore >= 2.0 && warpsDelta !== null && warpsDelta < -1.5) {
        category = "upset"; // WARPS underdog at home with big situational edge
      }

      games.push({
        week: gameWeek.week, homeTeam, awayTeam, dayOfWeek: gameWeek.dayOfWeek,
        homeDaysRest, awayDaysRest, awayHasTravel, awayIsB2B,
        homeIsPostBye, homeIsShortRest, awayIsShortRest, awayIsPostBye,
        isDivision, homeVegas, awayVegas, warpsDelta,
        score, scheduleScore, tags, narrative, category,
      });
    }
  }

  return games.sort((a, b) => Math.abs(b.score) - Math.abs(a.score));
}

function CategoryPill({ cat }: { cat: Category }) {
  const map: Record<Category, { label: string; cls: string }> = {
    spot: { label: "Spot Play", cls: "cat-spot" },
    trap: { label: "Trap Alert", cls: "cat-trap" },
    upset: { label: "Upset Watch", cls: "cat-upset" },
  };
  return <span className={`cat-pill ${map[cat].cls}`}>{map[cat].label}</span>;
}

function GameCard({ game }: { game: SpotGame }) {
  return (
    <article className={`scout-card scout-card-${game.category}`}>
      <div className="scout-card-top">
        <div className="scout-card-meta">
          <span className="scout-week-tag">Wk {game.week}</span>
          <span className="scout-day-tag">{game.dayOfWeek}</span>
          {game.category && <CategoryPill cat={game.category} />}
        </div>
        {game.warpsDelta !== null && (
          <span className={`scout-delta ${game.warpsDelta >= 0 ? "scout-delta-pos" : "scout-delta-neg"}`}>
            Δ{game.warpsDelta > 0 ? "+" : ""}{game.warpsDelta.toFixed(1)}w
          </span>
        )}
      </div>

      <div className="scout-matchup">
        <div className="scout-team">
          <img src={teamLogos[game.awayTeam]} alt="" className="scout-logo" />
          <span>{game.awayTeam}</span>
        </div>
        <span className="scout-at">@</span>
        <div className="scout-team scout-home">
          <img src={teamLogos[game.homeTeam]} alt="" className="scout-logo" />
          <span>{game.homeTeam}</span>
        </div>
      </div>

      <div className="scout-tags">
        {game.tags.map(t => <span key={t} className="scout-tag">{t}</span>)}
      </div>

      <p className="scout-narrative">{game.narrative}</p>

      <div className="scout-rest-row">
        {game.homeDaysRest !== null && (
          <span className={game.homeIsPostBye ? "rest-good" : game.homeIsShortRest ? "rest-bad" : "rest-neutral"}>
            {game.homeTeam} {game.homeDaysRest}d rest
          </span>
        )}
        {game.awayDaysRest !== null && (
          <span className={game.awayIsPostBye ? "rest-good" : game.awayIsShortRest ? "rest-bad" : "rest-neutral"}>
            {game.awayTeam} {game.awayDaysRest}d rest
          </span>
        )}
      </div>
    </article>
  );
}

export function ScoutView({ teams, weeks, vegasLines }: Props) {
  const [filter, setFilter] = useState<"all" | Category>("all");
  const [weekFilter, setWeekFilter] = useState<number | "all">("all");

  const allGames = useMemo(() => buildGames(teams, vegasLines), [teams, vegasLines]);
  const flagged = useMemo(() => allGames.filter(g => g.category !== null), [allGames]);

  const spots  = useMemo(() => flagged.filter(g => g.category === "spot").length, [flagged]);
  const traps  = useMemo(() => flagged.filter(g => g.category === "trap").length, [flagged]);
  const upsets = useMemo(() => flagged.filter(g => g.category === "upset").length, [flagged]);

  const visible = useMemo(() => {
    return flagged.filter(g => {
      if (weekFilter !== "all" && g.week !== weekFilter) return false;
      if (filter !== "all" && g.category !== filter) return false;
      return true;
    });
  }, [flagged, filter, weekFilter]);

  return (
    <div className="scout-wrapper">
      <div className="scout-header">
        <div>
          <h2 className="scout-title">Schedule Scout</h2>
          <p className="scout-subtitle">
            Spot plays, trap games, and upset watch — schedule intelligence beyond win-total projections.
            Factors: rest, travel, B2B road trips, divisional context, WARPS quality gap.
          </p>
        </div>
      </div>

      <div className="scout-kpis">
        <div className="scout-kpi scout-kpi-spot">
          <strong>{spots}</strong><span>Spot Plays</span>
        </div>
        <div className="scout-kpi scout-kpi-trap">
          <strong>{traps}</strong><span>Trap Alerts</span>
        </div>
        <div className="scout-kpi scout-kpi-upset">
          <strong>{upsets}</strong><span>Upset Watch</span>
        </div>
        <div className="scout-kpi">
          <strong>{allGames.length}</strong><span>Total games</span>
        </div>
      </div>

      <div className="scout-controls">
        <div className="segmented">
          {(
            [
              ["all", `All (${spots + traps + upsets})`],
              ["spot", `Spot Plays (${spots})`],
              ["trap", `Trap Alerts (${traps})`],
              ["upset", `Upset Watch (${upsets})`],
            ] as [string, string][]
          ).map(([val, label]) => (
            <button
              key={val}
              className={filter === val ? "active" : ""}
              onClick={() => setFilter(val as typeof filter)}
            >
              {label}
            </button>
          ))}
        </div>
        <select
          value={weekFilter}
          onChange={e => setWeekFilter(e.target.value === "all" ? "all" : Number(e.target.value))}
        >
          <option value="all">All weeks</option>
          {weeks.map(w => <option key={w} value={w}>Week {w}</option>)}
        </select>
      </div>

      {visible.length === 0 ? (
        <div className="scout-empty">No flagged games match the current filter.</div>
      ) : (
        <div className="scout-grid">
          {visible.map(g => (
            <GameCard key={`${g.awayTeam}@${g.homeTeam}:${g.week}`} game={g} />
          ))}
        </div>
      )}
    </div>
  );
}
