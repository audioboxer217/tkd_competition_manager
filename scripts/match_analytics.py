"""Match analytics: duration statistics by event type and ring.

Prints summary tables for:
- Average match duration by event type (kyorugi, poomsae)
- Average match duration by ring
- Longest match duration by event type (kyorugi, poomsae)
- Longest match duration by ring

Covers both bracket matches (kyorugi and poomsae bracket) tracked via the
Match model and group-based poomsae divisions tracked via the Division model.

Only records with both ``start_time`` and ``end_time`` are included.

Usage::

    python scripts/match_analytics.py                  # default: table
    python scripts/match_analytics.py --format csv     # CSV output
    python scripts/match_analytics.py --format json    # JSON output
"""

import argparse
import csv
import json
import sys
from datetime import timedelta

try:
    from scripts._bootstrap import add_repo_root_to_path
except ModuleNotFoundError:  # Allows `python scripts/match_analytics.py`
    from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

from sqlalchemy.orm import joinedload

from app import Division, Match, app


def _fmt_duration(td: timedelta) -> str:
    """Format a timedelta as M:SS."""
    total_seconds = int(td.total_seconds())
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"


def _collect_match_durations():
    """Return duration rows from bracket matches (Match model)."""
    matches = (
        Match.query.options(joinedload(Match.division), joinedload(Match.ring))
        .filter(
            Match.start_time.isnot(None),
            Match.end_time.isnot(None),
        )
        .all()
    )

    rows = []
    for match in matches:
        duration = match.end_time - match.start_time
        if duration.total_seconds() <= 0:
            continue
        event_type = match.division.event_type if match.division else "unknown"
        ring_name = match.ring.name if match.ring else "Unassigned"
        rows.append(
            {
                "event_type": event_type,
                "ring_name": ring_name,
                "duration": duration,
            }
        )
    return rows


def _collect_division_durations():
    """Return duration rows from group poomsae divisions (Division model)."""
    divisions = (
        Division.query.options(joinedload(Division.ring))
        .filter(
            Division.poomsae_style == "group",
            Division.start_time.isnot(None),
            Division.end_time.isnot(None),
        )
        .all()
    )

    rows = []
    for div in divisions:
        duration = div.end_time - div.start_time
        if duration.total_seconds() <= 0:
            continue
        ring_name = div.ring.name if div.ring else "Unassigned"
        rows.append(
            {
                "event_type": "poomsae (group)",
                "ring_name": ring_name,
                "duration": duration,
            }
        )
    return rows


def _stats_by_key(rows, key_field):
    """Return {key: {"avg": timedelta, "max": timedelta, "count": int}} grouped by key_field."""
    groups: dict[str, list[timedelta]] = {}
    for row in rows:
        k = row[key_field]
        groups.setdefault(k, []).append(row["duration"])

    result = {}
    for k, durations in sorted(groups.items()):
        total = sum((d.total_seconds() for d in durations), 0.0)
        avg = timedelta(seconds=total / len(durations))
        longest = max(durations)
        result[k] = {"avg": avg, "max": longest, "count": len(durations)}
    return result


def _build_output_rows(by_event: dict, by_ring: dict) -> list[dict]:
    """Return a flat list of dicts suitable for CSV/JSON serialisation.

    Each row contains:
      group        – "by_event_type" or "by_ring"
      category     – the group key (event type name or ring name)
      count        – number of timed events
      avg_seconds  – average duration in whole seconds
      avg_formatted – average duration formatted as M:SS
      longest_seconds  – longest duration in whole seconds
      longest_formatted – longest duration formatted as M:SS
    """
    output = []
    for group_label, stats in (("by_event_type", by_event), ("by_ring", by_ring)):
        for category, s in stats.items():
            output.append(
                {
                    "group": group_label,
                    "category": category,
                    "count": s["count"],
                    "avg_seconds": int(s["avg"].total_seconds()),
                    "avg_formatted": _fmt_duration(s["avg"]),
                    "longest_seconds": int(s["max"].total_seconds()),
                    "longest_formatted": _fmt_duration(s["max"]),
                }
            )
    return output


def _print_table(title: str, stats: dict) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")
    if not stats:
        print("  No data available.")
        return
    col_w = max(len(k) for k in stats) + 2
    print(f"  {'Category':<{col_w}}  {'Count':>6}  {'Average':>10}  {'Longest':>10}")
    print(f"  {'-'*col_w}  {'------':>6}  {'-------':>10}  {'-------':>10}")
    for name, s in stats.items():
        print(
            f"  {name:<{col_w}}  {s['count']:>6}  {_fmt_duration(s['avg']):>10}  {_fmt_duration(s['max']):>10}"
        )


def _output_table(by_event: dict, by_ring: dict, row_count: int) -> None:
    """Print the default human-readable table format."""
    print(f"\nAnalysing {row_count} timed event(s)…")
    _print_table("Duration by Event Type", by_event)
    _print_table("Duration by Ring", by_ring)
    print()


def _output_csv(by_event: dict, by_ring: dict) -> None:
    """Write CSV rows to stdout."""
    fieldnames = [
        "group",
        "category",
        "count",
        "avg_seconds",
        "avg_formatted",
        "longest_seconds",
        "longest_formatted",
    ]
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for row in _build_output_rows(by_event, by_ring):
        writer.writerow(row)


def _output_json(by_event: dict, by_ring: dict) -> None:
    """Write JSON to stdout."""
    def _section(stats: dict) -> list[dict]:
        return [
            {
                "category": category,
                "count": s["count"],
                "avg_seconds": int(s["avg"].total_seconds()),
                "avg_formatted": _fmt_duration(s["avg"]),
                "longest_seconds": int(s["max"].total_seconds()),
                "longest_formatted": _fmt_duration(s["max"]),
            }
            for category, s in stats.items()
        ]

    payload = {
        "by_event_type": _section(by_event),
        "by_ring": _section(by_ring),
    }
    print(json.dumps(payload, indent=2))


def main(fmt: str = "table") -> None:
    with app.app_context():
        match_rows = _collect_match_durations()
        division_rows = _collect_division_durations()
        rows = match_rows + division_rows

        if not rows:
            print("No timed event data found (no records with both start_time and end_time).")
            return

        by_event = _stats_by_key(rows, "event_type")
        by_ring = _stats_by_key(rows, "ring_name")

        if fmt == "csv":
            _output_csv(by_event, by_ring)
        elif fmt == "json":
            _output_json(by_event, by_ring)
        else:
            _output_table(by_event, by_ring, len(rows))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Match duration analytics.")
    parser.add_argument(
        "--format",
        dest="fmt",
        choices=["table", "csv", "json"],
        default="table",
        help="Output format (default: table)",
    )
    args = parser.parse_args()
    main(fmt=args.fmt)
