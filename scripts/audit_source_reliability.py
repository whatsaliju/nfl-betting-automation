#!/usr/bin/env python3
"""Audit source reliability and its impact on graded picks."""

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEATURES = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "game_features.csv"
DEFAULT_REPLAY_ROOT = ROOT / "data" / "backtests" / "engine_2026_1_configured"
DEFAULT_JSON = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "source_reliability_report.json"
DEFAULT_CSV = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "source_reliability_by_source.csv"
DEFAULT_MD = ROOT / "data" / "backtests" / "engine_2026_1_configured" / "source_reliability_report.md"


def load_features(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f))


def pct(wins, losses):
    return round(wins / (wins + losses), 4) if wins + losses else None


def int_week(path):
    match = re.search(r"week(\d+)", str(path))
    return int(match.group(1)) if match else 0


def summarize_pick_rows(rows, label):
    graded = [
        row for row in rows
        if row.get("best_edge_market") and row.get("bet_result") in {"win", "loss", "push"}
    ]
    wins = sum(1 for row in graded if row.get("bet_result") == "win")
    losses = sum(1 for row in graded if row.get("bet_result") == "loss")
    pushes = sum(1 for row in graded if row.get("bet_result") == "push")
    return {
        "bucket": label,
        "games": len(rows),
        "graded_picks": len(graded),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "win_rate": pct(wins, losses),
    }


def feature_status_buckets(rows):
    output = []
    for field in ("source_health_status", "data_quality_status"):
        values = sorted({row.get(field) or "NONE" for row in rows})
        for value in values:
            summary = summarize_pick_rows(
                [row for row in rows if (row.get(field) or "NONE") == value],
                value,
            )
            summary["dimension"] = field
            output.append(summary)
    return output


def source_health_paths(replay_root):
    return sorted(Path(replay_root).glob("week*/final/week*_source_health.json"), key=int_week)


def source_score(source):
    if not source.get("exists"):
        return 0
    status = source.get("status") or "UNKNOWN"
    if status == "UNSAFE":
        return 0
    if status == "DEGRADED":
        return 60
    warnings = len(source.get("warnings") or [])
    critical = len(source.get("critical_warnings") or [])
    age_days = source.get("age_days")
    score = 100
    score -= min(warnings * 8, 24)
    score -= min(critical * 35, 70)
    if isinstance(age_days, (int, float)) and age_days > 3:
        score -= min((age_days - 3) * 5, 25)
    return max(0, round(score, 1))


def week_source_rows(replay_root):
    rows = []
    weeks = []
    for path in source_health_paths(replay_root):
        payload = json.loads(path.read_text())
        week = payload.get("week") or int_week(path)
        source_rows = payload.get("sources") or []
        scores = [source_score(source) for source in source_rows]
        week_score = round(sum(scores) / len(scores), 1) if scores else 0
        weeks.append({
            "week": week,
            "status": payload.get("status") or "UNKNOWN",
            "source_count": len(source_rows),
            "score": week_score,
            "unsafe_sources": payload.get("unsafe_sources") or [],
            "degraded_sources": payload.get("degraded_sources") or [],
            "warnings": payload.get("warnings") or [],
            "critical_warnings": payload.get("critical_warnings") or [],
        })
        for source in source_rows:
            rows.append({
                "week": week,
                "source": source.get("name") or "unknown",
                "status": source.get("status") or "UNKNOWN",
                "exists": bool(source.get("exists")),
                "rows": source.get("rows") or 0,
                "age_days": source.get("age_days"),
                "warnings": len(source.get("warnings") or []),
                "critical_warnings": len(source.get("critical_warnings") or []),
                "score": source_score(source),
            })
    return weeks, rows


def source_summary(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["source"]].append(row)
    output = []
    for source, source_rows in sorted(grouped.items()):
        scores = [row["score"] for row in source_rows]
        statuses = defaultdict(int)
        for row in source_rows:
            statuses[row["status"]] += 1
        output.append({
            "source": source,
            "weeks": len(source_rows),
            "avg_score": round(sum(scores) / len(scores), 1) if scores else 0,
            "min_score": min(scores) if scores else 0,
            "ok_weeks": statuses.get("OK", 0),
            "degraded_weeks": statuses.get("DEGRADED", 0),
            "unsafe_weeks": statuses.get("UNSAFE", 0),
            "missing_weeks": sum(1 for row in source_rows if not row["exists"]),
            "total_warnings": sum(row["warnings"] for row in source_rows),
            "total_critical_warnings": sum(row["critical_warnings"] for row in source_rows),
        })
    return sorted(output, key=lambda row: (row["avg_score"], row["source"]))


def report(features, replay_root):
    weeks, source_rows = week_source_rows(replay_root)
    by_source = source_summary(source_rows)
    degraded_weeks = [row for row in weeks if row["status"] != "OK"]
    status_buckets = feature_status_buckets(features)
    scores = [row["score"] for row in weeks]
    overall_score = round(sum(scores) / len(scores), 1) if scores else 0
    return {
        "overall_status": "OK" if not degraded_weeks else "DEGRADED",
        "overall_score": overall_score,
        "weeks": weeks,
        "by_source": by_source,
        "feature_status_buckets": status_buckets,
        "recommendations": recommendations(by_source, status_buckets),
    }


def recommendations(by_source, status_buckets):
    recs = []
    weak_sources = [row for row in by_source if row["avg_score"] < 90]
    if weak_sources:
        names = ", ".join(row["source"] for row in weak_sources[:4])
        recs.append(f"Monitor lower-scoring source groups: {names}.")
    degraded_bucket = [
        row for row in status_buckets
        if row["bucket"] == "DEGRADED" and row["graded_picks"]
    ]
    if degraded_bucket:
        recs.append("Keep degraded source status visible; current sample is too small for a hard veto.")
    recs.append("Do not promote factor overlays to production when critical sources are unsafe or missing.")
    recs.append("For live 2026 runs, require action markets, queries, and referee trends before final recommendations.")
    return recs


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "source",
        "weeks",
        "avg_score",
        "min_score",
        "ok_weeks",
        "degraded_weeks",
        "unsafe_weeks",
        "missing_weeks",
        "total_warnings",
        "total_critical_warnings",
    ]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path, payload):
    lines = [
        "# Source Reliability Report",
        "",
        f"- Overall status: {payload['overall_status']}",
        f"- Overall score: {payload['overall_score']}",
        f"- Weeks audited: {len(payload['weeks'])}",
        "",
        "## Recommendations",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["recommendations"])
    lines.extend([
        "",
        "## Source Scores",
        "",
        "| Source | Weeks | Avg | Min | OK | Degraded | Unsafe | Missing |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in payload["by_source"]:
        lines.append(
            f"| {row['source']} | {row['weeks']} | {row['avg_score']} | {row['min_score']} | "
            f"{row['ok_weeks']} | {row['degraded_weeks']} | {row['unsafe_weeks']} | {row['missing_weeks']} |"
        )
    lines.extend([
        "",
        "## Performance By Quality Status",
        "",
        "| Dimension | Status | Games | Picks | W-L | Win Rate |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for row in payload["feature_status_buckets"]:
        lines.append(
            f"| {row['dimension']} | {row['bucket']} | {row['games']} | {row['graded_picks']} | "
            f"{row['wins']}-{row['losses']} | {row['win_rate']} |"
        )
    path.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--replay-root", type=Path, default=DEFAULT_REPLAY_ROOT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    args = parser.parse_args()

    payload = report(load_features(args.features), args.replay_root)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, indent=2))
    write_csv(args.csv_output, payload["by_source"])
    write_markdown(args.md_output, payload)
    print(json.dumps({
        "overall_status": payload["overall_status"],
        "overall_score": payload["overall_score"],
        "sources": len(payload["by_source"]),
        "weeks": len(payload["weeks"]),
    }, indent=2))


if __name__ == "__main__":
    main()
