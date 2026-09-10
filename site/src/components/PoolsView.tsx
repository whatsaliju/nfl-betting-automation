import { useEffect, useRef, useState } from "react";
import { Star, X, LogOut } from "lucide-react";
import type { User } from "@supabase/supabase-js";
import { supabase } from "../lib/supabase";
import { teamLogos } from "../data/nflData";
import { AuthGate } from "./AuthGate";

const ALL_TEAMS = Object.keys(teamLogos).sort();
const WEEKS = Array.from({ length: 18 }, (_, i) => i + 1);
const CURRENT_WEEK = 1;

interface Pool {
  id: string;
  name: string;
  picks: Record<number, string>;
}

const DEFAULT_POOL_NAMES = ["Pool 1", "Pool 2", "Pool 3", "Pool 4", "Pool 5"];

async function loadUserPools(userId: string): Promise<Pool[]> {
  const { data, error } = await supabase
    .from("pools")
    .select("id, name, picks")
    .eq("user_id", userId)
    .order("created_at");
  if (error || !data) return [];
  return data.map((row) => ({ id: row.id, name: row.name, picks: row.picks ?? {} }));
}

async function ensureDefaultPools(userId: string): Promise<Pool[]> {
  const inserts = DEFAULT_POOL_NAMES.map((name) => ({
    user_id: userId,
    name,
    picks: {},
  }));
  const { data, error } = await supabase
    .from("pools")
    .insert(inserts)
    .select("id, name, picks");
  if (error || !data) return [];
  return data.map((row) => ({ id: row.id, name: row.name, picks: row.picks ?? {} }));
}

async function savePool(pool: Pool) {
  await supabase
    .from("pools")
    .update({ name: pool.name, picks: pool.picks })
    .eq("id", pool.id);
}

interface EditCell {
  poolId: string;
  week: number;
}

export function PoolsView({ onOpenSurvivor }: { onOpenSurvivor?: () => void }) {
  const [user, setUser] = useState<User | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [pools, setPools] = useState<Pool[]>([]);
  const [loadingPools, setLoadingPools] = useState(false);
  const [editCell, setEditCell] = useState<EditCell | null>(null);
  const [editName, setEditName] = useState<string | null>(null);

  // Track which pool ids have pending saves
  const saveTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      setUser(data.user ?? null);
      setAuthReady(true);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!user) {
      setPools([]);
      return;
    }
    setLoadingPools(true);
    loadUserPools(user.id).then(async (loaded) => {
      if (loaded.length === 0) {
        const created = await ensureDefaultPools(user.id);
        setPools(created);
      } else {
        // Ensure exactly 5 pools, backfill if needed
        if (loaded.length < 5) {
          const missing = DEFAULT_POOL_NAMES.slice(loaded.length).map((name) => ({
            user_id: user.id,
            name,
            picks: {},
          }));
          const { data } = await supabase
            .from("pools")
            .insert(missing)
            .select("id, name, picks");
          const extra = (data ?? []).map((r) => ({ id: r.id, name: r.name, picks: r.picks ?? {} }));
          setPools([...loaded, ...extra]);
        } else {
          setPools(loaded);
        }
      }
      setLoadingPools(false);
    });
  }, [user]);

  function updatePool(updated: Pool) {
    setPools((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    // Debounce DB write 800ms
    clearTimeout(saveTimers.current[updated.id]);
    saveTimers.current[updated.id] = setTimeout(() => savePool(updated), 800);
  }

  function setPick(poolId: string, week: number, team: string | null) {
    const pool = pools.find((p) => p.id === poolId);
    if (!pool) return;
    const picks = { ...pool.picks };
    if (team) picks[week] = team;
    else delete picks[week];
    updatePool({ ...pool, picks });
    setEditCell(null);
  }

  function renamePool(poolId: string, name: string) {
    const pool = pools.find((p) => p.id === poolId);
    if (!pool) return;
    updatePool({ ...pool, name });
    setEditName(null);
  }

  async function signOut() {
    await supabase.auth.signOut();
    setPools([]);
  }

  if (!authReady) return null;
  if (!user) return <AuthGate />;

  const editPool = editCell ? pools.find((p) => p.id === editCell.poolId) ?? null : null;
  const editUsed = editPool ? new Set(Object.values(editPool.picks)) : new Set<string>();

  return (
    <section className="panel pools-view">
      <div className="panel-toolbar">
        <div>
          <h2>Survivor Pools · 2026</h2>
          <p className="panel-subtitle">Click a week cell to set your pick · Used teams flagged per pool · Click pool name to rename</p>
        </div>
        <div className="pools-toolbar-actions">
          <button className="pools-link-btn" onClick={onOpenSurvivor}>
            <Star size={13} /> Model picks
          </button>
          <button className="pools-signout-btn" onClick={signOut} title="Sign out">
            <LogOut size={13} />
          </button>
        </div>
      </div>

      {loadingPools ? (
        <div className="pools-loading">Loading your pools…</div>
      ) : (
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
      )}

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
