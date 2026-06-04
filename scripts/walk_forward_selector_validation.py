#!/usr/bin/env python3
"""Walk-forward validation for selector calibration policies.

Each fold chooses the best selector policy on earlier replay weeks, then grades
that policy on held-out future weeks. This helps catch threshold changes that
only look good because they were tuned on the exact same games.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.calibrate_selector_thresholds import (
    DEFAULT_REPLAY_ROOT,
    iter_games,
    parse_ints,
    run_policy,
    summarize,
)
from scripts.compare_replay_to_results import load_results


def parse_weeks(value):
    weeks = []
    for part in str(value).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            weeks.extend(range(int(start), int(end) + 1))
        else:
            weeks.append(int(part))
    return sorted(set(weeks))


def policy_grid(args):
    for spread_threshold in parse_ints(args.spread_thresholds):
        for total_threshold in parse_ints(args.total_thresholds):
            for injury_policy in [part.strip() for part in args.injury_policies.split(",") if part.strip()]:
                for total_policy in [part.strip() for part in args.total_policies.split(",") if part.strip()]:
                    yield {
                        "spread_threshold": spread_threshold,
                        "total_threshold": total_threshold,
                        "injury_policy": injury_policy,
                        "total_policy": total_policy,
                    }


def filter_games(games, weeks):
    wanted = set(weeks)
    return [(week, game) for week, game in games if week in wanted]


def policy_key(summary, min_plays):
    if summary["plays"] < min_plays:
        return (-1, summary["plays"], summary.get("avg_margin_to_line") or -999)
    return (
        summary.get("win_rate") or 0,
        summary["plays"],
        summary.get("avg_margin_to_line") or 0,
    )


def flatten_summary(prefix, summary):
    row = {
        f"{prefix}_plays": summary["plays"],
        f"{prefix}_graded": summary["graded"],
        f"{prefix}_wins": summary["wins"],
        f"{prefix}_losses": summary["losses"],
        f"{prefix}_pushes": summary["pushes"],
        f"{prefix}_win_rate": summary["win_rate"],
        f"{prefix}_avg_margin_to_line": summary["avg_margin_to_line"],
    }
    for market, market_summary in summary["by_market"].items():
        row[f"{prefix}_{market}_plays"] = market_summary["plays"]
        row[f"{prefix}_{market}_wins"] = market_summary["wins"]
        row[f"{prefix}_{market}_losses"] = market_summary["losses"]
        row[f"{prefix}_{market}_win_rate"] = market_summary["win_rate"]
    return row


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def expanding_folds(weeks, min_train_weeks):
    for index in range(min_train_weeks, len(weeks)):
        yield weeks[:index], [weeks[index]]


def choose_best_policy(train_games, results, policies, min_train_plays):
    best_policy = None
    best_rows = []
    best_summary = None
    best_key = None
    for policy in policies:
        rows = run_policy(train_games, results, **policy)
        summary = summarize(rows)
        key = policy_key(summary, min_train_plays)
        if best_key is None or key > best_key:
            best_key = key
            best_policy = policy
            best_rows = rows
            best_summary = summary
    return best_policy, best_summary, best_rows


def aggregate(rows):
    return summarize(rows)


def main():
    parser = argparse.ArgumentParser(description="Walk-forward validate selector policies")
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--season-type", default="REG")
    parser.add_argument("--stage", default="final")
    parser.add_argument("--replay-root", default=str(DEFAULT_REPLAY_ROOT))
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--weeks", default="11-18")
    parser.add_argument("--min-train-weeks", type=int, default=3)
    parser.add_argument("--min-train-plays", type=int, default=4)
    parser.add_argument("--spread-thresholds", default="3,4,5")
    parser.add_argument("--total-thresholds", default="3,4,5,6")
    parser.add_argument(
        "--injury-policies",
        default="allow,raise_spread_threshold,block_spread_if_injury_context,block_spread_if_injury_conflict",
    )
    parser.add_argument("--total-policies", default="allow,require_ref_weather,require_sharp_and_ref_weather")
    args = parser.parse_args()

    replay_root = Path(args.replay_root)
    output_dir = Path(args.output_dir) if args.output_dir else replay_root
    output_dir.mkdir(parents=True, exist_ok=True)

    weeks = parse_weeks(args.weeks)
    games = filter_games(list(iter_games(replay_root, args.stage)), weeks)
    results = load_results(args.season, args.season_type)
    policies = list(policy_grid(args))
    active_policy = {
        "spread_threshold": 3,
        "total_threshold": 4,
        "injury_policy": "raise_spread_threshold",
        "total_policy": "allow",
    }

    fold_rows = []
    heldout_pick_rows = []
    active_pick_rows = []

    for fold_number, (train_weeks, test_weeks) in enumerate(expanding_folds(weeks, args.min_train_weeks), start=1):
        train_games = filter_games(games, train_weeks)
        test_games = filter_games(games, test_weeks)
        best_policy, train_summary, _ = choose_best_policy(train_games, results, policies, args.min_train_plays)

        test_rows = run_policy(test_games, results, **best_policy)
        test_summary = summarize(test_rows)
        active_rows = run_policy(test_games, results, **active_policy)
        active_summary = summarize(active_rows)

        fold = {
            "fold": fold_number,
            "train_weeks": ",".join(str(week) for week in train_weeks),
            "test_weeks": ",".join(str(week) for week in test_weeks),
            **best_policy,
            **flatten_summary("train", train_summary),
            **flatten_summary("test", test_summary),
            **flatten_summary("active_test", active_summary),
        }
        fold_rows.append(fold)

        for row in test_rows:
            heldout_pick_rows.append({"fold": fold_number, **best_policy, **row})
        for row in active_rows:
            active_pick_rows.append({"fold": fold_number, **active_policy, **row})

    heldout_summary = aggregate(heldout_pick_rows)
    active_summary = aggregate(active_pick_rows)
    summary = {
        "replay_root": str(replay_root),
        "stage": args.stage,
        "weeks": weeks,
        "folds": len(fold_rows),
        "min_train_weeks": args.min_train_weeks,
        "min_train_plays": args.min_train_plays,
        "walk_forward": heldout_summary,
        "active_policy": active_policy,
        "active_policy_walk_forward": active_summary,
        "folds_detail": fold_rows,
    }

    write_csv(output_dir / "selector_walk_forward_folds.csv", fold_rows)
    write_csv(output_dir / "selector_walk_forward_picks.csv", heldout_pick_rows)
    write_csv(output_dir / "selector_walk_forward_active_picks.csv", active_pick_rows)
    (output_dir / "selector_walk_forward_summary.json").write_text(json.dumps(summary, indent=2))

    print(json.dumps({
        "folds": summary["folds"],
        "walk_forward": heldout_summary,
        "active_policy_walk_forward": active_summary,
    }, indent=2))
    print(f"Wrote {output_dir / 'selector_walk_forward_folds.csv'}")
    print(f"Wrote {output_dir / 'selector_walk_forward_picks.csv'}")
    print(f"Wrote {output_dir / 'selector_walk_forward_active_picks.csv'}")
    print(f"Wrote {output_dir / 'selector_walk_forward_summary.json'}")


if __name__ == "__main__":
    main()
