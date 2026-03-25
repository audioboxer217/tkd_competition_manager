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

    python scripts/match_analytics.py
"""

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


def main():
    with app.app_context():
        match_rows = _collect_match_durations()
        division_rows = _collect_division_durations()
        rows = match_rows + division_rows

        if not rows:
            print("No timed event data found (no records with both start_time and end_time).")
            return

        print(f"\nAnalysing {len(rows)} timed event(s)…")

        by_event = _stats_by_key(rows, "event_type")
        by_ring = _stats_by_key(rows, "ring_name")

        _print_table("Duration by Event Type", by_event)
        _print_table("Duration by Ring", by_ring)
        print()


if __name__ == "__main__":
    main()
