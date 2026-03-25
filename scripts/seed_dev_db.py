"""Seed the database with sample data for development and testing.

Creates:
  - 6 rings
  - 6 kyorugi divisions (1 per ring, 4 competitors each, bracket generated)
  - 2 poomsae bracket divisions (4 competitors each, bracket generated)
  - 2 breaking group divisions (4 competitors each)
  - 2 poomsae group divisions (4 competitors each)

Ring assignment ensures each ring has content for both the "Kyorugi"
and "Poomsae/Breaking" scorekeeper tabs.
"""

try:
    from scripts._bootstrap import add_repo_root_to_path
except ModuleNotFoundError:  # Allows `python scripts/seed_dev_db.py`
    from _bootstrap import add_repo_root_to_path

add_repo_root_to_path()

import math
import os
import sys

from app import Competitor, Division, Match, Ring, app, db

# ---------------------------------------------------------------------------
# Seed data definitions
# ---------------------------------------------------------------------------

RING_NAMES = [
    "Ring 1",
    "Ring 2",
    "Ring 3",
    "Ring 4",
    "Ring 5",
    "Ring 6",
]

# (division name, gender prefix for competitors)
KYORUGI_DIVISIONS = [
    ("Male - Senior - Under 58kg", "M"),
    ("Male - Senior - Under 63kg", "M"),
    ("Male - Senior - Under 68kg", "M"),
    ("Female - Senior - Under 53kg", "F"),
    ("Female - Senior - Under 57kg", "F"),
    ("Female - Senior - Under 62kg", "F"),
]

POOMSAE_BRACKET_DIVISIONS = [
    ("Male - Senior - Individual Poomsae", "M"),
    ("Female - Senior - Individual Poomsae", "F"),
]

BREAKING_GROUP_DIVISIONS = [
    ("Male - Senior - Power Breaking", "M"),
    ("Female - Senior - Power Breaking", "F"),
]

POOMSAE_GROUP_DIVISIONS = [
    ("Male - Senior - Team Poomsae", "M"),
    ("Female - Senior - Team Poomsae", "F"),
]

COMPETITOR_SUFFIXES = ["Athlete A", "Athlete B", "Athlete C", "Athlete D"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_round_name(num_matches: int) -> str:
    if num_matches == 1:
        return "Final"
    elif num_matches == 2:
        return "Semi-Final"
    elif num_matches == 4:
        return "Quarter-Final"
    return f"Round of {num_matches * 2}"


def _add_competitors(division: Division, gender_prefix: str) -> list[Competitor]:
    competitors = []
    for pos, suffix in enumerate(COMPETITOR_SUFFIXES, start=1):
        name = f"{gender_prefix} - {suffix}"
        comp = Competitor(name=name, division_id=division.id, position=pos)
        db.session.add(comp)
        competitors.append(comp)
    db.session.flush()
    return competitors


def _generate_bracket(division: Division, competitors: list[Competitor], ring: Ring, start_seq: int) -> int:
    """Build a single-elimination bracket for *division*, assigning all matches
    to *ring*.  Match numbers are encoded as ring.id * 100 + sequence.

    Returns the next available sequence number within the ring.
    """
    num_comp = len(competitors)
    next_power = 2 ** math.ceil(math.log2(num_comp))
    num_first_round = next_power // 2

    # Distribute competitors into pairings (deal like a deck of cards)
    pairings = [[None, None] for _ in range(num_first_round)]
    for i, comp in enumerate(competitors):
        slot = i // num_first_round
        idx = i % num_first_round
        pairings[idx][slot] = comp

    first_round_name = _get_round_name(num_first_round)
    seq = start_seq
    current_round: list[Match] = []

    for comp1, comp2 in pairings:
        match = Match(
            division_id=division.id,
            ring_id=ring.id,
            match_number=ring.id * 100 + seq,
            competitor1_id=comp1.id if comp1 else None,
            competitor2_id=comp2.id if comp2 else None,
            round_name=first_round_name,
        )
        if comp1 and not comp2:
            match.winner_id = comp1.id
            match.status = "Completed (Bye)"
        elif comp2 and not comp1:
            match.winner_id = comp2.id
            match.status = "Completed (Bye)"
        db.session.add(match)
        current_round.append(match)
        seq += 1

    db.session.flush()

    # Build subsequent rounds (bottom-up to the Final)
    while len(current_round) > 1:
        next_round: list[Match] = []
        for i in range(0, len(current_round), 2):
            prev1 = current_round[i]
            prev2 = current_round[i + 1]
            r_name = _get_round_name(len(current_round) // 2)

            new_match = Match(
                division_id=division.id,
                ring_id=ring.id,
                match_number=ring.id * 100 + seq,
                round_name=r_name,
            )
            # Push bye winners forward immediately
            if prev1.winner_id:
                new_match.competitor1_id = prev1.winner_id
            if prev2.winner_id:
                new_match.competitor2_id = prev2.winner_id

            db.session.add(new_match)
            db.session.flush()

            prev1.next_match_id = new_match.id
            prev2.next_match_id = new_match.id
            next_round.append(new_match)
            seq += 1

        current_round = next_round

    return seq


# ---------------------------------------------------------------------------
# Main seed routine
# ---------------------------------------------------------------------------


def seed():
    app_env = (os.environ.get("APP_ENV") or os.environ.get("app_env") or "").lower()
    if app_env != "dev":
        print("ERROR: Refusing to seed database because APP_ENV/app_env is not explicitly set to 'dev'.")

    with app.app_context():
        db.create_all()

        # ------------------------------------------------------------------
        # Safety check: abort if the database already has data
        # ------------------------------------------------------------------
        if Ring.query.count() or Division.query.count() or Competitor.query.count() or Match.query.count():
            print("ERROR: Database is not empty. Run `scripts/reset_db.py` before seeding.")
            sys.exit(1)

        # ------------------------------------------------------------------
        # 1. Rings
        # ------------------------------------------------------------------
        print("Creating rings...")
        rings: list[Ring] = []
        for name in RING_NAMES:
            ring = Ring(name=name)
            db.session.add(ring)
            rings.append(ring)
        db.session.flush()

        # ------------------------------------------------------------------
        # 2. Kyorugi divisions – one per ring, bracket generated
        #    Match numbers for kyorugi start at sequence 1 within each ring.
        # ------------------------------------------------------------------
        print("Creating kyorugi divisions...")
        for (div_name, gender), ring in zip(KYORUGI_DIVISIONS, rings):
            division = Division(name=div_name, event_type="kyorugi")
            db.session.add(division)
            db.session.flush()

            competitors = _add_competitors(division, gender)
            next_seq = _generate_bracket(division, competitors, ring, start_seq=1)
            print(f"  {div_name} → {ring.name} (sequences 1–{next_seq - 1})")

        # ------------------------------------------------------------------
        # 3. Poomsae bracket divisions – rings 1 & 2, bracket generated
        #    Match numbers start at sequence 4 to avoid collisions with kyorugi.
        # ------------------------------------------------------------------
        print("Creating poomsae bracket divisions...")
        poomsae_bracket_rings = rings[:2]  # Ring 1, Ring 2
        for (div_name, gender), ring in zip(POOMSAE_BRACKET_DIVISIONS, poomsae_bracket_rings):
            division = Division(name=div_name, event_type="poomsae", poomsae_style="bracket", ring_id=ring.id, ring_sequence=1)
            db.session.add(division)
            db.session.flush()

            competitors = _add_competitors(division, gender)
            next_seq = _generate_bracket(division, competitors, ring, start_seq=4)
            print(f"  {div_name} → {ring.name} (sequences 4–{next_seq - 1})")

        # ------------------------------------------------------------------
        # 4. Breaking group divisions – rings 3 & 4
        # ------------------------------------------------------------------
        print("Creating breaking group divisions...")
        breaking_rings = rings[2:4]  # Ring 3, Ring 4
        for (div_name, gender), ring in zip(BREAKING_GROUP_DIVISIONS, breaking_rings):
            division = Division(
                name=div_name,
                event_type="poomsae",
                poomsae_style="group",
                ring_id=ring.id,
                ring_sequence=1,
            )
            db.session.add(division)
            db.session.flush()

            _add_competitors(division, gender)
            print(f"  {div_name} → {ring.name}")

        # ------------------------------------------------------------------
        # 5. Poomsae group divisions – rings 5 & 6
        # ------------------------------------------------------------------
        print("Creating poomsae group divisions...")
        poomsae_group_rings = rings[4:6]  # Ring 5, Ring 6
        for (div_name, gender), ring in zip(POOMSAE_GROUP_DIVISIONS, poomsae_group_rings):
            division = Division(
                name=div_name,
                event_type="poomsae",
                poomsae_style="group",
                ring_id=ring.id,
                ring_sequence=1,
            )
            db.session.add(division)
            db.session.flush()

            _add_competitors(division, gender)
            print(f"  {div_name} → {ring.name}")

        # ------------------------------------------------------------------
        # Commit all changes
        # ------------------------------------------------------------------
        db.session.commit()
        print("\nSeed complete.")
        print(f"  {len(rings)} rings")
        print(f"  {len(KYORUGI_DIVISIONS)} kyorugi divisions (brackets generated)")
        print(f"  {len(POOMSAE_BRACKET_DIVISIONS)} poomsae bracket divisions (brackets generated)")
        print(f"  {len(BREAKING_GROUP_DIVISIONS)} breaking group divisions")
        print(f"  {len(POOMSAE_GROUP_DIVISIONS)} poomsae group divisions")
        print("\nRing assignment summary:")
        print("  Ring 1: Kyorugi (Male U58kg) + Poomsae Bracket (Male Individual)")
        print("  Ring 2: Kyorugi (Male U63kg) + Poomsae Bracket (Female Individual)")
        print("  Ring 3: Kyorugi (Male U68kg) + Breaking Group (Male Power Breaking)")
        print("  Ring 4: Kyorugi (Female U53kg) + Breaking Group (Female Power Breaking)")
        print("  Ring 5: Kyorugi (Female U57kg) + Poomsae Group (Male Team Poomsae)")
        print("  Ring 6: Kyorugi (Female U62kg) + Poomsae Group (Female Team Poomsae)")


if __name__ == "__main__":
    seed()
