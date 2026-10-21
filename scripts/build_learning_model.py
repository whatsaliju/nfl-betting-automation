#!/usr/bin/env python3
"""2026 learning layer on top of the history model, plus the site's Model view.

The history layer (scripts/build_history_model.py, lean models) gives every game a
side and total probability from inputs that exist back to 2015. This layer adds
signals we only have for the current season and lets each one earn weight from
graded 2026 games:

  sharp_home    Action Network money% minus bets% on the home spread (last pregame read)
  sharp_over    the same for the over
  move_home     home spread now minus the opening line we first saw (points; negative =
                the market moved toward the home team)
  move_total    total now minus opening total

Each market is a logistic model whose offset is the history-layer logit, so with no
evidence it returns the history probability exactly. New weights start at zero and are
pulled back hard (L2 = PRIOR_GAMES on standardised inputs), so a handful of weeks can
only nudge them. Week-by-week walk-forward inside 2026: week W is scored by a layer
fitted on weeks before W.

Writes data/backtests/history_model/learning_2026.json and site/src/data/modelView.json.
"""

import csv
import glob
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "analyzers"))
import build_history_model as hm  # noqa: E402
from nfl_common import canonical_team  # noqa: E402

SEASON = hm.LIVE_SEASON
PRIOR_GAMES = 150.0
MIN_WEEKS = 2
LEAN = 0.53
SNAPSHOTS = ROOT / "data" / "historical" / f"engine_line_snapshots_{SEASON}.csv"
OUT_JSON = ROOT / "data" / "backtests" / "history_model" / f"learning_{SEASON}.json"
SITE_JSON = ROOT / "site" / "src" / "data" / "modelView.json"

LAYERS = {
    "sides": {"base": "sides_lean", "target": "home_cover", "features": ["sharp_home", "move_home"]},
    "totals": {"base": "totals_lean", "target": "over", "features": ["sharp_over", "move_total"]},
}


def pct_pair(text):
    nums = re.findall(r"(\d+)%", text or "")
    return (float(nums[0]), float(nums[1])) if len(nums) == 2 else None


def first_number(text):
    m = re.search(r"([+-]?\d+(?:\.\d+)?)", (text or "").replace("PK", "0"))
    return float(m.group(1)) if m else None


def is_pregame(game_time):
    """Action Network shows a kickoff time (AM/PM) before the game, a clock or Final after."""
    return bool(re.search(r"\b(AM|PM)\b", game_time or ""))


def load_splits():
    """Latest pregame money%-bets% per (away, home), keyed with the fetch time."""
    out = {}
    for path in sorted(glob.glob(str(ROOT / "data" / f"action_all_markets_{SEASON}-*.csv"))):
        try:
            rows = list(csv.DictReader(open(path)))
        except OSError:
            continue
        for r in rows:
            if not is_pregame(r.get("Game Time")) or "@" not in r.get("Matchup", ""):
                continue
            away, home = (canonical_team(t.strip()) for t in r["Matchup"].split("@"))
            bets, money = pct_pair(r.get("Bets %")), pct_pair(r.get("Money %"))
            if not bets or not money:
                continue
            fetched = r.get("Fetched", "")
            key = (away, home)
            entry = out.setdefault(key, [])
            # Bets/money pairs are away|home for spreads, over|under for totals.
            if r["Market"] == "Spread":
                entry.append((fetched, "sharp_home", (money[1] - bets[1]) / 100))
            elif r["Market"] == "Total":
                entry.append((fetched, "sharp_over", (money[0] - bets[0]) / 100))
    return out


def load_openers():
    """First spread and total we captured for each game (engine snapshots)."""
    openers = {}
    if not SNAPSHOTS.exists():
        return openers
    for r in sorted(csv.DictReader(open(SNAPSHOTS)), key=lambda r: r["captured_at"]):
        key = (int(float(r["week"])), r["matchup_key"].replace("WSH", "WAS"))
        if key in openers:
            continue
        parts = (r.get("spread_line") or "").split("|")
        home = first_number(parts[1]) if len(parts) > 1 else None
        total = first_number((r.get("total_line") or "").split("|")[0].lstrip("ou"))
        if home is not None and total is not None:
            openers[key] = (home, total)
    return openers


def attach_live_features(rows, splits, openers, kickoffs):
    for r in rows:
        kick = kickoffs.get(r["game_id"], "9999")
        for f in ("sharp_home", "sharp_over"):
            vals = [v for fetched, name, v in splits.get((r["away"], r["home"]), [])
                    if name == f and fetched[:10] <= kick[:10]]
            r[f] = vals[-1] if vals else 0.0
        op = openers.get((r["week"], r["matchup"]))
        r["move_home"] = (r["home_spread_line"] - op[0]) if op else 0.0
        r["move_total"] = (r["total_line_raw"] - op[1]) if op else 0.0
        r["has_live"] = bool(op) or any(splits.get((r["away"], r["home"]), []))


def fit_layer(X, y, offset):
    """Logistic regression with a fixed offset and a strong pull of new weights to zero."""
    mu, sd = X.mean(0), X.std(0)
    sd[sd == 0] = 1
    Z = (X - mu) / sd
    w = np.zeros(Z.shape[1])
    for _ in range(50):
        p = 1 / (1 + np.exp(-(offset + Z @ w)))
        grad = Z.T @ (p - y) + PRIOR_GAMES * w
        H = (Z * (p * (1 - p))[:, None]).T @ Z + PRIOR_GAMES * np.eye(len(w))
        step = np.linalg.solve(H, grad)
        w -= step
        if np.abs(step).max() < 1e-9:
            break
    return mu, sd, w


def apply_layer(model, X, offset):
    if model is None:
        return 1 / (1 + np.exp(-offset))
    mu, sd, w = model
    return 1 / (1 + np.exp(-(offset + ((X - mu) / sd) @ w)))


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def record(probs, ys):
    w = l = 0
    for p, y in zip(probs, ys):
        if p >= LEAN:
            w += y == 1; l += y == 0
        elif p <= 1 - LEAN:
            w += y == 0; l += y == 1
    return {"w": int(w), "l": int(l), "pct": round(w / (w + l), 4) if w + l else None}


def main():
    games_path = sys.argv[1] if len(sys.argv) > 1 else None
    schedule = hm.load_schedule(games_path)
    kickoffs = {g["game_id"]: f"{g['gameday']}T{g.get('gametime') or '13:00'}" for g in schedule}
    rows = hm.build_rows(schedule, hm.load_warps())

    # History layer: the 2015-2025 lean models.
    models = {}
    for key, _, feats, target, l2 in hm.MODELS:
        train = [r for r in rows if hm.TRAIN_START <= r["season"] < SEASON and r[target] is not None
                 and (target != "home_cover" or r["has_warps"])]
        models[key] = hm.Logistic(l2).fit(hm.matrix(train, feats), np.array([r[target] for r in train]))

    live = [r for r in rows if r["season"] == SEASON]
    attach_live_features(live, load_splits(), load_openers(), kickoffs)
    for key, _, feats, _, _ in hm.MODELS:
        probs = models[key].predict(hm.matrix(live, feats))
        for r, p in zip(live, probs):
            r[f"{key}_prob"] = float(p)

    graded_weeks = sorted({r["week"] for r in live if r["played"]})
    summary = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "season": SEASON, "prior_games": PRIOR_GAMES, "markets": {}}
    final_layers = {}
    for market, cfg in LAYERS.items():
        target, feats, base = cfg["target"], cfg["features"], f"{cfg['base']}_prob"
        graded = [r for r in live if r["played"] and r[target] is not None and r["has_live"]]
        wf_p, wf_y, wf_base = [], [], []
        for wk in graded_weeks:
            prior = [r for r in graded if r["week"] < wk]
            test = [r for r in graded if r["week"] == wk]
            if not test:
                continue
            layer = None
            if len({r["week"] for r in prior}) >= MIN_WEEKS:
                layer = fit_layer(hm.matrix(prior, feats), np.array([r[target] for r in prior]),
                                  logit(np.array([r[base] for r in prior])))
            off = logit(np.array([r[base] for r in test]))
            wf_p += list(apply_layer(layer, hm.matrix(test, feats), off))
            wf_base += [r[base] for r in test]
            wf_y += [int(r[target]) for r in test]
        layer = None
        if len({r["week"] for r in graded}) >= MIN_WEEKS:
            layer = fit_layer(hm.matrix(graded, feats), np.array([r[target] for r in graded]),
                              logit(np.array([r[base] for r in graded])))
        final_layers[market] = layer
        summary["markets"][market] = {
            "graded_games": len(graded),
            "history_only_walk_forward": record(wf_base, wf_y),
            "with_2026_layer_walk_forward": record(wf_p, wf_y),
            "weights_per_sd": ({f: round(float(c), 4) for f, c in zip(feats, layer[2])} if layer else {}),
        }

    upcoming_week = min((r["week"] for r in live if not r["played"]), default=None)
    view = []
    for r in live:
        if r["week"] != upcoming_week:
            continue
        item = {"matchup": r["matchup"], "away": r["away"], "home": r["home"],
                "home_spread": r["home_spread_line"], "total": r["total_line_raw"]}
        for market, cfg in LAYERS.items():
            base_p = r[f"{cfg['base']}_prob"]
            p = float(apply_layer(final_layers[market], hm.matrix([r], cfg["features"]),
                                  logit(np.array([base_p])))[0])
            item[market] = {"history": round(base_p, 4), "prob": round(p, 4)}
        hs, total = r["home_spread_line"], r["total_line_raw"]
        sp, tp = item["sides"]["prob"], item["totals"]["prob"]
        side_pick = (f"{r['home']} {hs:+g}" if sp >= 0.5 else f"{r['away']} {-hs:+g}")
        total_pick = f"{'Over' if tp >= 0.5 else 'Under'} {total:g}"
        item["side_pick"], item["side_conf"] = side_pick, round(max(sp, 1 - sp), 4)
        item["total_pick"], item["total_conf"] = total_pick, round(max(tp, 1 - tp), 4)
        view.append(item)
    view.sort(key=lambda g: -max(g["side_conf"], g["total_conf"]))

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(summary, indent=2) + "\n")
    hist = json.loads((ROOT / "data" / "backtests" / "history_model" / "summary.json").read_text()) \
        if (ROOT / "data" / "backtests" / "history_model" / "summary.json").exists() else {}
    SITE_JSON.write_text(json.dumps({
        "generated_at": summary["generated_at"],
        "season": SEASON,
        "week": upcoming_week,
        "lean_threshold": LEAN,
        "history": {k: hist.get(k, {}).get("walk_forward", {}).get("pooled", {}).get("picks", {}).get(str(LEAN))
                    for k in ("sides_lean", "totals_lean")},
        "live": summary["markets"],
        "games": view,
    }, indent=2) + "\n")
    for market, m in summary["markets"].items():
        print(market, m["graded_games"], "history", m["history_only_walk_forward"],
              "with layer", m["with_2026_layer_walk_forward"], m["weights_per_sd"])
    print(f"Model view: week {upcoming_week}, {len(view)} games")


if __name__ == "__main__":
    main()
