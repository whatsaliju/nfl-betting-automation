import { BadgeCheck, CalendarDays, CircleSlash, Route, ShieldAlert, Star, Trophy } from "lucide-react";
import { useMemo, useState } from "react";
import { teamLogos } from "../data/nflData";
import survivorPayload from "../data/survivorRecommendations2026.json";

type SurvivorTier = "primary" | "secondary" | "deep_pool" | "avoid" | string;

type SurvivorCandidate = {
  season: number;
  week: number;
  team: string;
  opponent: string;
  matchup_key: string;
  home_away: "home" | "away";
  day: string;
  win_probability: number;
  fair_moneyline: string;
  warps_wins: number;
  opponent_warps_wins: number;
  division_game: boolean;
  future_safe_spots: number;
  future_elite_spots: number;
  best_future_win_probability: number | null;
  future_value_cost: number;
  volatility_penalty: number;
  safety_score: number;
  survivor_score: number;
  risk_band: string;
  tier: SurvivorTier;
  reasons: string[];
};

type SurvivorWeek = {
  week: number;
  primary: SurvivorCandidate | null;
  safest: SurvivorCandidate | null;
  alternatives: SurvivorCandidate[];
  avoid: SurvivorCandidate[];
};

type SurvivorPayload = {
  metadata: {
    model: string;
    policy: string;
    candidate_count: number;
  };
  weekly?: SurvivorWeek[];
  optimal_path: {
    available: boolean;
    survival_probability: number | null;
    average_pick_probability: number | null;
    picks: SurvivorCandidate[];
  };
  candidates: SurvivorCandidate[];
};

const survivor = survivorPayload as SurvivorPayload;
const teams = Array.from(new Set(survivor.candidates.map((row) => row.team))).sort();
const weeks = Array.from(new Set(survivor.candidates.map((row) => row.week))).sort((a, b) => a - b);

function pct(value?: number | null) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "n/a";
}

function tierLabel(value?: string) {
  return (value || "n/a").replace(/_/g, " ");
}

function CandidateCard({
  candidate,
  label,
  used,
  onToggle,
}: {
  candidate: SurvivorCandidate | null;
  label: string;
  used: boolean;
  onToggle: (team: string) => void;
}) {
  if (!candidate) {
    return (
      <article className="survivor-card empty">
        <strong>{label}</strong>
        <p>No candidate available.</p>
      </article>
    );
  }

  return (
    <article className={`survivor-card ${candidate.tier} ${used ? "used" : ""}`}>
      <div className="survivor-card-top">
        <span>{label}</span>
        <span>{tierLabel(candidate.tier)}</span>
      </div>
      <div className="survivor-pick-team">
        <img src={teamLogos[candidate.team]} alt="" />
        <div>
          <strong>{candidate.team}</strong>
          <span>
            {candidate.home_away === "home" ? "vs" : "@"} {candidate.opponent} · {candidate.day}
          </span>
        </div>
        <b>{pct(candidate.win_probability)}</b>
      </div>
      <div className="survivor-score-grid">
        <div>
          <span>Survivor</span>
          <strong>{candidate.survivor_score.toFixed(1)}</strong>
        </div>
        <div>
          <span>Safety</span>
          <strong>{candidate.safety_score.toFixed(1)}</strong>
        </div>
        <div>
          <span>Future cost</span>
          <strong>{candidate.future_value_cost.toFixed(1)}</strong>
        </div>
      </div>
      <div className="context-tags">
        <span>{candidate.home_away}</span>
        <span>{candidate.risk_band}</span>
        {candidate.division_game && <span>Division risk</span>}
        {candidate.future_elite_spots > 0 && <span>{candidate.future_elite_spots} elite future</span>}
      </div>
      <ul className="survivor-reasons">
        {candidate.reasons.slice(0, 4).map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
      <button className="text-button survivor-used-btn" onClick={() => onToggle(candidate.team)}>
        {used ? <BadgeCheck size={14} /> : <CircleSlash size={14} />}
        {used ? "Marked used" : "Mark used"}
      </button>
    </article>
  );
}

export function SurvivorView() {
  const [week, setWeek] = useState(1);
  const [usedTeams, setUsedTeams] = useState<Set<string>>(new Set());
  const weekRows = useMemo(
    () => survivor.candidates
      .filter((row) => row.week === week)
      .sort((a, b) => b.survivor_score - a.survivor_score || b.win_probability - a.win_probability),
    [week]
  );
  const safestPick = useMemo(
    () => [...weekRows].sort((a, b) => b.win_probability - a.win_probability || a.future_value_cost - b.future_value_cost)[0] || null,
    [weekRows]
  );
  const availablePick = weekRows.find((row) => !usedTeams.has(row.team) && row.tier !== "avoid") || null;
  const pathPick = survivor.optimal_path.picks.find((row) => row.week === week) || null;

  function toggleTeam(team: string) {
    setUsedTeams((current) => {
      const next = new Set(current);
      if (next.has(team)) next.delete(team);
      else next.add(team);
      return next;
    });
  }

  return (
    <section className="panel survivor-panel">
      <div className="panel-toolbar">
        <div>
          <h2>Survivor Intelligence</h2>
          <p className="panel-subtitle">{survivor.metadata.model} · {survivor.metadata.policy}</p>
        </div>
        <div className="edge-board-stats">
          <span><Trophy size={14} />{survivor.metadata.candidate_count} picks scored</span>
          <span><Route size={14} />Path avg {pct(survivor.optimal_path.average_pick_probability)}</span>
          <span><ShieldAlert size={14} />Use as planning, not a lock</span>
        </div>
      </div>

      <div className="survivor-controls">
        <label>
          <CalendarDays size={14} />
          Week
          <select value={week} onChange={(event) => setWeek(Number(event.target.value))}>
            {weeks.map((item) => (
              <option value={item} key={item}>Week {item}</option>
            ))}
          </select>
        </label>
        <div className="used-team-strip">
          {teams.map((team) => (
            <button
              key={team}
              className={usedTeams.has(team) ? "used" : ""}
              onClick={() => toggleTeam(team)}
              title={usedTeams.has(team) ? `${team} already used` : `Mark ${team} used`}
            >
              {team}
            </button>
          ))}
        </div>
      </div>

      <div className="survivor-hero-grid">
        <CandidateCard candidate={availablePick} label="Available Pick" used={availablePick ? usedTeams.has(availablePick.team) : false} onToggle={toggleTeam} />
        <CandidateCard candidate={safestPick} label="Safest Pure Pick" used={safestPick ? usedTeams.has(safestPick.team) : false} onToggle={toggleTeam} />
        <CandidateCard candidate={pathPick} label="Season Path Pick" used={pathPick ? usedTeams.has(pathPick.team) : false} onToggle={toggleTeam} />
      </div>

      <div className="survivor-table-wrap">
        <table className="data-table survivor-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Team</th>
              <th>Game</th>
              <th>Win Prob</th>
              <th>Score</th>
              <th>Future</th>
              <th>Risk</th>
              <th>Tier</th>
            </tr>
          </thead>
          <tbody>
            {weekRows.slice(0, 12).map((row, index) => (
              <tr key={`${row.week}-${row.team}`} className={usedTeams.has(row.team) ? "row-used" : ""}>
                <td>{index + 1}</td>
                <td>
                  <span className="table-team">
                    <img src={teamLogos[row.team]} alt="" />
                    {row.team}
                  </span>
                </td>
                <td>{row.home_away === "home" ? "vs" : "@"} {row.opponent}</td>
                <td>{pct(row.win_probability)}</td>
                <td>{row.survivor_score.toFixed(1)}</td>
                <td>{row.future_safe_spots} safe · {row.future_elite_spots} elite</td>
                <td>{row.division_game ? "division" : row.home_away}</td>
                <td>{tierLabel(row.tier)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="survivor-path">
        <h3><Star size={15} /> Suggested Season Path</h3>
        <div className="survivor-path-grid">
          {survivor.optimal_path.picks.map((pick) => (
            <button key={`${pick.week}-${pick.team}`} className={week === pick.week ? "active" : ""} onClick={() => setWeek(pick.week)}>
              <span>W{pick.week}</span>
              <strong>{pick.team}</strong>
              <b>{pct(pick.win_probability)}</b>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
