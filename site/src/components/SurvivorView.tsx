import { BadgeCheck, CalendarDays, CircleSlash, Route, ShieldAlert, SlidersHorizontal, Star, Trophy } from "lucide-react";
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
  pool_cards?: SurvivorPoolCard[];
  candidates: SurvivorCandidate[];
};

type SurvivorPoolPick = {
  strategy: "safe" | "balanced" | "leverage" | string;
  pool_size: number;
  payout_style: PayoutStyle;
  team: string;
  opponent: string;
  week: number;
  matchup_key: string;
  home_away: "home" | "away";
  win_probability: number;
  survivor_score: number;
  future_value_cost: number;
  volatility_penalty: number;
  risk_band: string;
  tier: SurvivorTier;
  division_game: boolean;
  public_pick_pct: number;
  expected_entries_eliminated: number;
  safe_score: number;
  balanced_score: number;
  leverage_score: number;
  reasons: string[];
};

type SurvivorPoolCard = {
  week: number;
  pool_size: number;
  payout_style: PayoutStyle;
  safe: SurvivorPoolPick | null;
  balanced: SurvivorPoolPick | null;
  leverage: SurvivorPoolPick | null;
};

type StrategyMode = "survive" | "balanced" | "leverage";
type PayoutStyle = "winner_take_all" | "top_heavy" | "flat";
type ScoredCandidate = SurvivorCandidate & {
  public_pick_pct: number;
  pool_ev_score: number;
  leverage_score: number;
  strategy_score: number;
};

const survivor = survivorPayload as SurvivorPayload;
const teams = Array.from(new Set(survivor.candidates.map((row) => row.team))).sort();
const weeks = Array.from(new Set(survivor.candidates.map((row) => row.week))).sort((a, b) => a - b);
const BRAND_CHALK: Record<string, number> = {
  BUF: 4.5, KC: 5.5, PHI: 5, DAL: 3.5, SF: 4.5, BAL: 4, DET: 3.5, GB: 3,
  LAR: 2.5, PIT: 2.5, CIN: 2.5, CHI: 2, NE: 2, DEN: 1.5,
};

function pct(value?: number | null) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "n/a";
}

function tierLabel(value?: string) {
  return (value || "n/a").replace(/_/g, " ");
}

function clamp(value: number, low: number, high: number) {
  return Math.max(low, Math.min(high, value));
}

function publicPickEstimate(candidate: SurvivorCandidate, poolSize: number) {
  const favoriteComponent = Math.max(0, candidate.win_probability - 0.55) * 62;
  const brandComponent = BRAND_CHALK[candidate.team] || 0;
  const homeComponent = candidate.home_away === "home" ? 1.2 : -0.6;
  const poolComponent = poolSize >= 100 ? 1.5 : poolSize <= 15 ? -1.2 : 0;
  const divisionDiscount = candidate.division_game ? -1.4 : 0;
  return clamp(favoriteComponent + brandComponent + homeComponent + poolComponent + divisionDiscount, 1, 38);
}

function payoutMultiplier(style: PayoutStyle) {
  if (style === "winner_take_all") return 1.25;
  if (style === "top_heavy") return 1.0;
  return 0.65;
}

function scoreCandidate(
  candidate: SurvivorCandidate,
  settings: { poolSize: number; strategy: StrategyMode; payoutStyle: PayoutStyle; chalkPenalty: number }
): ScoredCandidate {
  const publicPick = publicPickEstimate(candidate, settings.poolSize);
  const leverage = (candidate.win_probability * 100) - publicPick * settings.chalkPenalty * payoutMultiplier(settings.payoutStyle);
  const poolEv = candidate.survivor_score + leverage * 0.18 - candidate.future_value_cost * 0.25;
  const strategyScore =
    settings.strategy === "survive"
      ? candidate.win_probability * 100 - candidate.volatility_penalty * 0.8
      : settings.strategy === "leverage"
        ? poolEv + (candidate.win_probability * 100 - publicPick) * 0.32
        : candidate.survivor_score * 0.65 + poolEv * 0.35;
  return {
    ...candidate,
    public_pick_pct: publicPick,
    leverage_score: leverage,
    pool_ev_score: poolEv,
    strategy_score: strategyScore,
  };
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

function PoolPickCell({ pick }: { pick: SurvivorPoolPick | null }) {
  if (!pick) return <td>n/a</td>;
  return (
    <td>
      <span className="table-team">
        <img src={teamLogos[pick.team]} alt="" />
        {pick.team}
      </span>
      <small>{pct(pick.win_probability)} · {pick.public_pick_pct.toFixed(1)}% public</small>
    </td>
  );
}

export function SurvivorView() {
  const [week, setWeek] = useState(1);
  const [usedTeams, setUsedTeams] = useState<Set<string>>(new Set());
  const [poolSize, setPoolSize] = useState(25);
  const [strategy, setStrategy] = useState<StrategyMode>("balanced");
  const [payoutStyle, setPayoutStyle] = useState<PayoutStyle>("top_heavy");
  const [chalkPenalty, setChalkPenalty] = useState(0.7);
  const weekRows = useMemo(
    () => survivor.candidates
      .filter((row) => row.week === week)
      .map((row) => scoreCandidate(row, { poolSize, strategy, payoutStyle, chalkPenalty }))
      .sort((a, b) => b.strategy_score - a.strategy_score || b.win_probability - a.win_probability),
    [week, poolSize, strategy, payoutStyle, chalkPenalty]
  );
  const safestPick = useMemo(
    () => [...weekRows].sort((a, b) => b.win_probability - a.win_probability || a.future_value_cost - b.future_value_cost)[0] || null,
    [weekRows]
  );
  const availablePick = weekRows.find((row) => !usedTeams.has(row.team) && row.tier !== "avoid") || null;
  const pathPick = survivor.optimal_path.picks.find((row) => row.week === week) || null;
  const poolCards = useMemo(
    () => (survivor.pool_cards || [])
      .filter((row) => row.week === week && row.payout_style === payoutStyle)
      .sort((a, b) => a.pool_size - b.pool_size),
    [week, payoutStyle]
  );

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
        <div className="survivor-settings-grid">
          <label>
            <CalendarDays size={14} />
            Week
            <select value={week} onChange={(event) => setWeek(Number(event.target.value))}>
              {weeks.map((item) => (
                <option value={item} key={item}>Week {item}</option>
              ))}
            </select>
          </label>
          <label>
            <SlidersHorizontal size={14} />
            Strategy
            <select value={strategy} onChange={(event) => setStrategy(event.target.value as StrategyMode)}>
              <option value="balanced">Balanced</option>
              <option value="survive">Must survive</option>
              <option value="leverage">Max EV / leverage</option>
            </select>
          </label>
          <label>
            Pool size
            <input
              type="number"
              min={2}
              max={10000}
              value={poolSize}
              onChange={(event) => setPoolSize(Number(event.target.value) || 2)}
            />
          </label>
          <label>
            Payout
            <select value={payoutStyle} onChange={(event) => setPayoutStyle(event.target.value as PayoutStyle)}>
              <option value="top_heavy">Top heavy</option>
              <option value="winner_take_all">Winner take all</option>
              <option value="flat">Flat/split friendly</option>
            </select>
          </label>
          <label>
            Chalk penalty
            <input
              type="range"
              min={0}
              max={1.5}
              step={0.1}
              value={chalkPenalty}
              onChange={(event) => setChalkPenalty(Number(event.target.value))}
            />
            <b>{chalkPenalty.toFixed(1)}</b>
          </label>
        </div>
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
        <div className="survivor-section-head">
          <h3><SlidersHorizontal size={15} /> Pool Structure Card</h3>
          <span>{tierLabel(payoutStyle)} · safe vs balanced vs leverage</span>
        </div>
        <table className="data-table survivor-table survivor-pool-table">
          <thead>
            <tr>
              <th>Pool</th>
              <th>Safe</th>
              <th>Balanced</th>
              <th>Leverage</th>
              <th>Signal</th>
            </tr>
          </thead>
          <tbody>
            {poolCards.map((card) => {
              const changed = card.safe?.team !== card.leverage?.team || card.safe?.team !== card.balanced?.team;
              return (
                <tr key={`${card.week}-${card.pool_size}-${card.payout_style}`}>
                  <td>{card.pool_size}</td>
                  <PoolPickCell pick={card.safe} />
                  <PoolPickCell pick={card.balanced} />
                  <PoolPickCell pick={card.leverage} />
                  <td>{changed ? "pool edge differs" : "same pick"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
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
              <th>Public</th>
              <th>Pool EV</th>
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
                <td>{row.strategy_score.toFixed(1)}</td>
                <td>{row.public_pick_pct.toFixed(1)}%</td>
                <td>{row.pool_ev_score.toFixed(1)}</td>
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
