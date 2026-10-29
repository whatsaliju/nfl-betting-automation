import modelViewData from "../data/modelView.json";

// Weekly-prize strategy for a ~56-player straight-up pool (simulated Oct 2026):
// all favorites wins the week ~0.2% of the time, 5-6 upsets in the closest games ~4.5%
// (an even share is 1.8%). Upsets only where the favorite is 3.5 points or less.
const POOL_SIZE = 56;
const MAX_SPREAD = 3.5;
const MAX_UPSETS = 6;

interface UpsetGame {
  awayTla: string;
  homeTla: string;
  matchupKey: string;
  gameTime: string;
  isCompleted: boolean;
  favTla: string | null;
  dogTla: string | null;
  spreadVal: number | null;
  ou: number | null;
}

const mv = modelViewData as { week: number | null; games: { away: string; home: string; side_pick: string; side_conf: number }[] };

function modelNote(g: UpsetGame, week: number) {
  if (mv.week !== week) return null;
  const m = mv.games.find((x) => x.away === g.awayTla && x.home === g.homeTla);
  if (!m) return null;
  const pct = Math.round(m.side_conf * 100);
  if (m.side_conf < 0.52) return { agree: false, text: `Model: coin flip (${pct}%)` };
  return m.side_pick.startsWith(g.dogTla ?? "~")
    ? { agree: true, text: `Model leans ${g.dogTla} (${pct}%)` }
    : { agree: false, text: `Model leans ${g.favTla} (${pct}%)` };
}

export function UpsetPicksPanel({ games, week }: { games: UpsetGame[]; week: number }) {
  const now = Date.now();
  const open = games.filter((g) => !g.isCompleted && (!g.gameTime || new Date(g.gameTime).getTime() > now));
  const picks = open
    .filter((g) => g.favTla && g.dogTla && g.spreadVal !== null && g.spreadVal > 0 && g.spreadVal <= MAX_SPREAD)
    .map((g) => ({ g, note: modelNote(g, week) }))
    .sort((a, b) => (a.g.spreadVal! - b.g.spreadVal!) || Number(b.note?.agree ?? false) - Number(a.note?.agree ?? false))
    .slice(0, MAX_UPSETS);
  const lastGame = [...open].filter((g) => g.gameTime).sort((a, b) => (a.gameTime < b.gameTime ? 1 : -1))[0];

  if (!picks.length) return null;
  return (
    <section className="tp upset-panel">
      <div className="tp-head">
        <h3>Upset picks · Week {week}</h3>
        <span>
          For the weekly prize in a ~{POOL_SIZE}-player pool, take {Math.min(5, picks.length)}–{picks.length} of these underdogs
          and the favorite everywhere else.
        </span>
      </div>
      <ol className="tp-list">
        {picks.map(({ g, note }) => (
          <li key={g.matchupKey} className="tp-row tp-take">
            <div className="tp-main">
              <strong>{g.dogTla} +{g.spreadVal}</strong>
              <span className="tp-matchup">{g.awayTla}@{g.homeTla} · {g.favTla} favored by {g.spreadVal}</span>
              {note && <span className="tp-signal">{note.text}</span>}
            </div>
            <div className="tp-conf">
              <span className={`tp-tag${note?.agree ? " on" : ""}`}>{note?.agree ? "Model agrees" : "Coin flip"}</span>
            </div>
          </li>
        ))}
      </ol>
      {lastGame && lastGame.ou !== null && (
        <p className="tp-note">
          Tiebreaker: {lastGame.awayTla}@{lastGame.homeTla} total {lastGame.ou}. Enter a number near it but not the obvious one
          (e.g. {Math.floor(lastGame.ou) - 1} or {Math.ceil(lastGame.ou) + 1}) so you don't tie the crowd.
        </p>
      )}
      <p className="tp-note">
        Why: in a pool this size someone always beats the favorites, so all-favorites almost never wins a week (about 0.2%).
        Five or six upsets in the closest games win the week about 4.5% of the time, 2.5× an even share. It costs about one
        expected win a week in the season standings. Never take an underdog of 6 or more just to fill the count.
      </p>
    </section>
  );
}
