import { useEffect, useRef, useState } from "react";
import { Star, X } from "lucide-react";
import { teamLogos } from "../data/nflData";

const STORAGE_KEY = "nfl_survivor_pools_2026";
const ALL_TEAMS = Object.keys(teamLogos).sort();
const WEEKS = Array.from({ length: 18 }, (_, i) => i + 1);
const CURRENT_WEEK = 1;

interface Pool {
  id: string;
  name: string;
  picks: Record<number, string>;
}

const DEFAULT_POOLS: Pool[] = [1, 2, 3, 4, 5].map((i) => ({
  id: `pool${i}`,
  name: `Pool ${i}`,
  picks: {},
}));

function loadPools(): Pool[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_POOLS;
    const parsed = JSON.parse(raw) as Pool[];
    // Ensure exactly 5 pools — backfill if saved data has fewer
    while (parsed.length < 5) {
      const i = parsed.length + 1;
      parsed.push({ id: `pool${i}`, name: `Pool ${i}`, picks: {} });
    }
    return parsed;
  } catch {
    return DEFAULT_POOLS;
  }
}

interface EditCell {
  poolId: string;
  week: number;
}

export function PoolsView({ onOpenSurvivor }: { onOpenSurvivor?: () => void }) {
  const [pools, setPools] = useState<Pool[]>(loadPools);
  const [editCell, setEditCell] = useState<EditCell | null>(null);
  const [editName, setEditName] = useState<string | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(pools));
    } catch {}
  }, [pools]);

  function setPick(poolId: string, week: number, team: string | null) {
    setPools((prev) =>
      prev.map((p) => {
        if (p.id !== poolId) return p;
        const picks = { ...p.picks };
        if (team) picks[week] = team;
        else delete picks[week];
        return { ...p, picks };
      })
    );
    setEditCell(null);
  }

  function renamePool(poolId: string, name: string) {
    setPools((prev) => prev.map((p) => (p.id === poolId ? { ...p, name } : p)));
    setEditName(null);
  }

  const editPool = editCell ? pools.find((p) => p.id === editCell.poolId) ?? null : null;
  const editUsed = editPool ? new Set(Object.values(editPool.picks)) : new Set<string>();

  return (
    <section className="panel pools-view">
      <div className="panel-toolbar">
        <div>
          <h2>Survivor Pools · 2026</h2>
          <p className="panel-subtitle">Click a week cell to set your pick · Used teams flagged per pool · Click pool name to rename</p>
        </div>
        <button className="pools-link-btn" onClick={onOpenSurvivor}>
          <Star size={13} /> Model picks
        </button>
      </div>

      <div className="pools-grid-wrap">
        <table className="pools-table">
          <thead>
            <tr>
              <th className="pools-th-name">Pool</th>
              {WEEKS.map((w) => (
                <th key={w} className={`pools-th-week${w === CURRENT_WEEK ? " pools-current-week" : ""}`}>
                  W{w}
                </th>
              ))}
              <th className="pools-th-remaining">Remaining</th>
            </tr>
          </thead>
          <tbody>
            {pools.map((pool) => {
              const usedTeams = new Set(Object.values(pool.picks));
              const remaining = ALL_TEAMS.filter((t) => !usedTeams.has(t));
              return (
                <tr key={pool.id}>
                  <td className="pools-td-name">
                    {editName === pool.id ? (
                      <input
                        className="pools-name-input"
                        defaultValue={pool.name}
                        autoFocus
                        onBlur={(e) => renamePool(pool.id, e.target.value.trim() || pool.name)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                          if (e.key === "Escape") setEditName(null);
                        }}
                      />
                    ) : (
                      <span className="pools-name-label" onClick={() => setEditName(pool.id)} title="Click to rename">
                        {pool.name}
                      </span>
                    )}
                  </td>
                  {WEEKS.map((w) => {
                    const pick = pool.picks[w];
                    const isActive = editCell?.poolId === pool.id && editCell?.week === w;
                    return (
                      <td key={w} className="pools-td-cell">
                        <button
                          className={`pools-cell${pick ? " has-pick" : ""}${isActive ? " active" : ""}`}
                          onClick={() => setEditCell(isActive ? null : { poolId: pool.id, week: w })}
                        >
                          {pick ? (
                            <>
                              <img src={teamLogos[pick]} alt={pick} className="pools-pick-logo" />
                              <span>{pick}</span>
                            </>
                          ) : (
                            <span className="pools-cell-empty">—</span>
                          )}
                        </button>
                      </td>
                    );
                  })}
                  <td className="pools-td-remaining">
                    <b>{remaining.length}</b>
                    <span>
                      {remaining.slice(0, 5).join(" · ")}
                      {remaining.length > 5 ? ` +${remaining.length - 5}` : ""}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {editCell && editPool && (
        <TeamPickerModal
          pool={editPool}
          week={editCell.week}
          usedTeams={editUsed}
          currentPick={editPool.picks[editCell.week] ?? null}
          onPick={(team) => setPick(editCell.poolId, editCell.week, team)}
          onClear={() => setPick(editCell.poolId, editCell.week, null)}
          onClose={() => setEditCell(null)}
        />
      )}
    </section>
  );
}

function TeamPickerModal({
  pool,
  week,
  usedTeams,
  currentPick,
  onPick,
  onClear,
  onClose,
}: {
  pool: Pool;
  week: number;
  usedTeams: Set<string>;
  currentPick: string | null;
  onPick: (team: string) => void;
  onClear: () => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div className="pools-picker-overlay">
      <div className="pools-picker-modal" ref={ref}>
        <div className="pools-picker-header">
          <span>
            <strong>{pool.name}</strong> · Week {week}
          </span>
          <div className="pools-picker-header-actions">
            {currentPick && (
              <button className="pools-picker-clear" onClick={onClear}>
                Clear pick
              </button>
            )}
            <button className="pools-picker-close" onClick={onClose} aria-label="Close">
              <X size={15} />
            </button>
          </div>
        </div>
        <div className="pools-picker-grid">
          {ALL_TEAMS.map((team) => {
            const isUsed = usedTeams.has(team) && team !== currentPick;
            const isCurrent = team === currentPick;
            return (
              <button
                key={team}
                className={`pools-picker-team${isUsed ? " used" : ""}${isCurrent ? " current" : ""}`}
                onClick={() => { if (!isUsed) onPick(team); }}
                title={isUsed ? `${team} already used` : undefined}
              >
                <img src={teamLogos[team]} alt={team} />
                <span>{team}</span>
                {isCurrent && <span className="pools-picker-badge current-badge">✓</span>}
                {isUsed && <span className="pools-picker-badge used-badge">used</span>}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
