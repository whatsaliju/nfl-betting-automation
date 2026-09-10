import { useEffect, useRef, useState } from "react";
import { Star, X, LogOut, Plus, Trash2, ChevronDown, ChevronUp } from "lucide-react";
import type { User } from "@supabase/supabase-js";
import { supabase } from "../lib/supabase";
import { teamLogos } from "../data/nflData";
import { AuthGate } from "./AuthGate";
import consensusRaw from "../data/survivorConsensus2026.json";

const ALL_TEAMS = Object.keys(teamLogos).sort();
const WEEKS = Array.from({ length: 18 }, (_, i) => i + 1);
const CURRENT_WEEK = 1;

interface ConsensusWeek {
  [team: string]: { w: number | null; p: number | null; ev: number | null };
}
interface ConsensusData {
  updated: string | null;
  source: string;
  weeks: Record<string, ConsensusWeek>;
}
const consensus = consensusRaw as ConsensusData;

interface Pool {
  id: string;
  name: string;
  picks: Record<number, string>;
}

async function loadUserPools(userId: string): Promise<Pool[]> {
  const { data } = await supabase
    .from("pools")
    .select("id, name, picks")
    .eq("user_id", userId)
    .order("created_at");
  return (data ?? []).map((r) => ({ id: r.id, name: r.name, picks: r.picks ?? {} }));
}

async function createPool(userId: string, name: string): Promise<Pool | null> {
  const { data } = await supabase
    .from("pools")
    .insert({ user_id: userId, name, picks: {} })
    .select("id, name, picks")
    .single();
  return data ? { id: data.id, name: data.name, picks: data.picks ?? {} } : null;
}

async function deletePool(id: string): Promise<void> {
  await supabase.from("pools").delete().eq("id", id);
}

async function savePool(pool: Pool): Promise<void> {
  await supabase.from("pools").update({ name: pool.name, picks: pool.picks }).eq("id", pool.id);
}

interface EditCell { poolId: string; week: number; }

export function PoolsView({ onOpenSurvivor }: { onOpenSurvivor?: () => void }) {
  const [user, setUser] = useState<User | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [pools, setPools] = useState<Pool[]>([]);
  const [loadingPools, setLoadingPools] = useState(false);
  const [editCell, setEditCell] = useState<EditCell | null>(null);
  const [editName, setEditName] = useState<string | null>(null);
  const [expandedPool, setExpandedPool] = useState<string | null>(null);
  const saveTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      setUser(data.user ?? null);
      setAuthReady(true);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_e, session) => {
      setUser(session?.user ?? null);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (!user) { setPools([]); return; }
    setLoadingPools(true);
    loadUserPools(user.id).then(async (loaded) => {
      if (loaded.length === 0) {
        // Bootstrap 5 default pools for new user
        const created = await Promise.all(
          ["Pool 1", "Pool 2", "Pool 3", "Pool 4", "Pool 5"].map((n) => createPool(user.id, n))
        );
        setPools(created.filter(Boolean) as Pool[]);
      } else {
        setPools(loaded);
      }
      setLoadingPools(false);
    });
  }, [user]);

  function schedulePoolSave(pool: Pool) {
    clearTimeout(saveTimers.current[pool.id]);
    saveTimers.current[pool.id] = setTimeout(() => savePool(pool), 800);
  }

  function updatePool(updated: Pool) {
    setPools((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));
    schedulePoolSave(updated);
  }

  function setPick(poolId: string, week: number, team: string | null) {
    const pool = pools.find((p) => p.id === poolId);
    if (!pool) return;
    const picks = { ...pool.picks };
    if (team) picks[week] = team; else delete picks[week];
    updatePool({ ...pool, picks });
    setEditCell(null);
  }

  function renamePool(poolId: string, name: string) {
    const pool = pools.find((p) => p.id === poolId);
    if (!pool) return;
    updatePool({ ...pool, name });
    setEditName(null);
  }

  async function addPool() {
    if (!user) return;
    const name = `Pool ${pools.length + 1}`;
    const created = await createPool(user.id, name);
    if (created) setPools((prev) => [...prev, created]);
  }

  async function removePool(poolId: string) {
    setPools((prev) => prev.filter((p) => p.id !== poolId));
    await deletePool(poolId);
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
          <p className="panel-subtitle">
            Click a week cell to set your pick · Used teams flagged per pool · Click pool name to rename
            {consensus.updated && (
              <span className="pools-consensus-updated"> · Consensus: {consensus.updated.slice(0, 10)}</span>
            )}
          </p>
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
        <>
          <div className="pools-grid-wrap">
            <table className="pools-table">
              <thead>
                <tr>
                  <th className="pools-th-name">Pool</th>
                  {WEEKS.map((w) => {
                    const cw = consensus.weeks[String(w)];
                    const topPick = cw
                      ? Object.entries(cw).sort((a, b) => (b[1].p ?? 0) - (a[1].p ?? 0))[0]
                      : null;
                    return (
                      <th
                        key={w}
                        className={`pools-th-week${w === CURRENT_WEEK ? " pools-current-week" : ""}`}
                        title={topPick ? `Top pick: ${topPick[0]} (${Math.round((topPick[1].p ?? 0) * 100)}% P%)` : undefined}
                      >
                        W{w}
                        {topPick && (
                          <span className="pools-week-top-pick">{topPick[0]}</span>
                        )}
                      </th>
                    );
                  })}
                  <th className="pools-th-remaining">Remaining</th>
                  <th className="pools-th-actions"></th>
                </tr>
              </thead>
              <tbody>
                {pools.map((pool) => {
                  const usedTeams = new Set(Object.values(pool.picks));
                  const remaining = ALL_TEAMS.filter((t) => !usedTeams.has(t));
                  const isExpanded = expandedPool === pool.id;
                  return (
                    <>
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
                            {remaining.slice(0, 3).join(" · ")}
                            {remaining.length > 3 ? ` +${remaining.length - 3}` : ""}
                          </span>
                        </td>
                        <td className="pools-td-row-actions">
                          <button
                            className="pools-row-action-btn"
                            onClick={() => setExpandedPool(isExpanded ? null : pool.id)}
                            title={isExpanded ? "Collapse path" : "View path & suggestions"}
                          >
                            {isExpanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                          </button>
                          <button
                            className="pools-row-action-btn pools-delete-btn"
                            onClick={() => removePool(pool.id)}
                            title="Remove pool"
                          >
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr key={`${pool.id}-path`} className="pools-path-row">
                          <td colSpan={WEEKS.length + 3}>
                            <PoolPathView pool={pool} usedTeams={usedTeams} />
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>

          <button className="pools-add-btn" onClick={addPool}>
            <Plus size={14} /> Add pool
          </button>
        </>
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

function PoolPathView({ pool, usedTeams }: { pool: Pool; usedTeams: Set<string> }) {
  const remainingTeams = ALL_TEAMS.filter((t) => !usedTeams.has(t));

  return (
    <div className="pools-path-view">
      <div className="pools-path-weeks">
        {WEEKS.map((w) => {
          const pick = pool.picks[w];
          const isPast = w < CURRENT_WEEK;
          const isCurrent = w === CURRENT_WEEK;
          const isFuture = w > CURRENT_WEEK;
          const cw = consensus.weeks[String(w)];

          // Top model suggestion for this week (excluding already-used teams)
          const suggestion = cw
            ? Object.entries(cw)
                .filter(([team]) => !usedTeams.has(team) || team === pick)
                .sort((a, b) => (b[1].ev ?? 0) - (a[1].ev ?? 0))[0]
            : null;

          return (
            <div
              key={w}
              className={`pools-path-week${isCurrent ? " current" : ""}${isPast ? " past" : ""}${isFuture && !pick ? " future-empty" : ""}`}
            >
              <div className="pools-path-week-label">W{w}</div>
              {pick ? (
                <div className="pools-path-pick">
                  <img src={teamLogos[pick]} alt={pick} className="pools-path-logo" />
                  <span>{pick}</span>
                </div>
              ) : (
                <div className="pools-path-empty">—</div>
              )}
              {isFuture && suggestion && !pick && (
                <div className="pools-path-suggestion" title={`EV: ${suggestion[1].ev != null ? (suggestion[1].ev * 100).toFixed(0) : "?"}%`}>
                  <span className="pools-path-sug-label">suggest</span>
                  <img src={teamLogos[suggestion[0]]} alt={suggestion[0]} className="pools-path-sug-logo" />
                  <span className="pools-path-sug-team">{suggestion[0]}</span>
                  {suggestion[1].p != null && (
                    <span className="pools-path-sug-pct">{Math.round(suggestion[1].p * 100)}%P</span>
                  )}
                </div>
              )}
              {isFuture && !cw && !pick && (
                <div className="pools-path-no-data">no data yet</div>
              )}
            </div>
          );
        })}
      </div>
      {remainingTeams.length > 0 && (
        <div className="pools-path-remaining">
          <span className="pools-path-remaining-label">Remaining teams ({remainingTeams.length})</span>
          <div className="pools-path-remaining-teams">
            {remainingTeams.map((t) => (
              <span key={t} className="pools-path-team-chip">
                <img src={teamLogos[t]} alt={t} />
                {t}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function TeamPickerModal({
  pool, week, usedTeams, currentPick, onPick, onClear, onClose,
}: {
  pool: Pool; week: number; usedTeams: Set<string>; currentPick: string | null;
  onPick: (team: string) => void; onClear: () => void; onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const cw = consensus.weeks[String(week)];

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [onClose]);

  useEffect(() => {
    function handler(e: KeyboardEvent) { if (e.key === "Escape") onClose(); }
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  // Sort teams: available first (by EV desc), then used
  const sortedTeams = [...ALL_TEAMS].sort((a, b) => {
    const aUsed = usedTeams.has(a) && a !== currentPick;
    const bUsed = usedTeams.has(b) && b !== currentPick;
    if (aUsed !== bUsed) return aUsed ? 1 : -1;
    const aEv = cw?.[a]?.ev ?? -1;
    const bEv = cw?.[b]?.ev ?? -1;
    return bEv - aEv;
  });

  return (
    <div className="pools-picker-overlay">
      <div className="pools-picker-modal" ref={ref}>
        <div className="pools-picker-header">
          <span><strong>{pool.name}</strong> · Week {week}</span>
          <div className="pools-picker-header-actions">
            {currentPick && <button className="pools-picker-clear" onClick={onClear}>Clear pick</button>}
            <button className="pools-picker-close" onClick={onClose} aria-label="Close"><X size={15} /></button>
          </div>
        </div>
        {cw && (
          <div className="pools-picker-consensus-header">
            <span>Sorted by EV · Consensus from survivorgrid.com</span>
          </div>
        )}
        <div className="pools-picker-grid">
          {sortedTeams.map((team) => {
            const isUsed = usedTeams.has(team) && team !== currentPick;
            const isCurrent = team === currentPick;
            const td = cw?.[team];
            return (
              <button
                key={team}
                className={`pools-picker-team${isUsed ? " used" : ""}${isCurrent ? " current" : ""}`}
                onClick={() => { if (!isUsed) onPick(team); }}
                title={isUsed ? `${team} already used` : undefined}
              >
                <img src={teamLogos[team]} alt={team} />
                <span>{team}</span>
                {td && !isUsed && (
                  <span className="pools-picker-ev">
                    {td.p != null ? `${Math.round(td.p * 100)}%P` : ""}
                    {td.w != null ? ` ${Math.round(td.w * 100)}%W` : ""}
                  </span>
                )}
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
