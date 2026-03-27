import logging
import math
import os
from collections import defaultdict
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, make_response, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from markupsafe import escape
from sqlalchemy import case
from sqlalchemy.orm import joinedload
from supabase import create_client
from supabase_auth.errors import AuthApiError

# Fetch variables
load_dotenv()
USER = os.getenv("user")
PASSWORD = os.getenv("password")
HOST = os.getenv("host")
PORT = os.getenv("port")
DBNAME = os.getenv("dbname")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable must be set.")
if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL environment variable must be set.")
if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_KEY environment variable must be set.")
app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL") or f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}?sslmode=require"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = SECRET_KEY
db = SQLAlchemy(app)
csrf = CSRFProtect(app)

supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("user"):
            if request.headers.get("HX-Request"):
                resp = Response("Unauthorized", status=401)
                resp.headers["HX-Redirect"] = url_for("login")
                return resp
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)

    return decorated_function


class Ring(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # e.g., 'Ring 1'
    matches = db.relationship("Match", backref="ring", lazy=True)
    divisions = db.relationship("Division", backref="ring", lazy=True)


VALID_EVENT_TYPES = {"poomsae", "kyorugi"}
COMPLETED_MATCH_STATUSES = {"Completed", "Completed (Bye)", "Disqualification"}


class Division(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # e.g., 'Male - Black Belt - Under 70kg'
    event_type = db.Column(db.String(20), nullable=False, default="kyorugi")  # 'poomsae' or 'kyorugi'
    poomsae_style = db.Column(db.String(10), nullable=True)  # For poomsae: 'bracket' or 'group'; None = not yet set
    ring_id = db.Column(db.Integer, db.ForeignKey("ring.id"), nullable=True)  # For poomsae: which ring is hosting this event
    ring_sequence = db.Column(db.Integer, nullable=True)  # For poomsae: display order within the ring (1, 2, 3, ...)
    event_status = db.Column(db.String(20), nullable=False, default="Pending")  # For poomsae: 'Pending', 'In Progress', 'Completed'

    # Timing for group poomsae events: set when the division is started/completed
    start_time = db.Column(db.DateTime(timezone=True), nullable=True)
    end_time = db.Column(db.DateTime(timezone=True), nullable=True)

    competitors = db.relationship("Competitor", backref="division", lazy=True)
    matches = db.relationship("Match", backref="division", lazy=True)

    __table_args__ = (db.Index("ix_division_ring_id", "ring_id"),)


class Competitor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    division_id = db.Column(db.Integer, db.ForeignKey("division.id"), nullable=False)
    position = db.Column(db.Integer, nullable=True, default=None)


class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    division_id = db.Column(db.Integer, db.ForeignKey("division.id"), nullable=False)
    ring_id = db.Column(db.Integer, db.ForeignKey("ring.id"), nullable=True)  # Nullable until scheduled

    competitor1_id = db.Column(db.Integer, db.ForeignKey("competitor.id"), nullable=True)
    competitor2_id = db.Column(db.Integer, db.ForeignKey("competitor.id"), nullable=True)
    winner_id = db.Column(db.Integer, db.ForeignKey("competitor.id"), nullable=True)

    # Tree structure for single-elimination
    next_match_id = db.Column(db.Integer, db.ForeignKey("match.id"), nullable=True)
    match_number = db.Column(db.Integer, nullable=True)  # E.g., 101, 525

    # Status: 'Pending', 'In Progress', 'Completed', 'Disqualification'
    status = db.Column(db.String(20), default="Pending")
    round_name = db.Column(db.String(50))  # e.g., 'Quarter-Final', 'Semi-Final'

    # Timing: set when match is started / completed
    start_time = db.Column(db.DateTime(timezone=True), nullable=True)
    end_time = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationships
    competitor1 = db.relationship("Competitor", foreign_keys=[competitor1_id])
    competitor2 = db.relationship("Competitor", foreign_keys=[competitor2_id])
    winner = db.relationship("Competitor", foreign_keys=[winner_id])

    __table_args__ = (
        db.Index("ix_match_division_id", "division_id"),
        db.Index("ix_match_status", "status"),
        db.Index("ix_match_division_status", "division_id", "status"),
    )


class Score(db.Model):
    """Poomsae score for an individual competitor in a division."""

    id = db.Column(db.Integer, primary_key=True)
    competitor_id = db.Column(db.Integer, db.ForeignKey("competitor.id"), nullable=False)
    division_id = db.Column(db.Integer, db.ForeignKey("division.id"), nullable=False)
    score_value = db.Column(db.Float, nullable=False)

    competitor = db.relationship("Competitor", foreign_keys=[competitor_id])

    __table_args__ = (db.UniqueConstraint("competitor_id", "division_id", name="uq_score_competitor_division"),)


# --- RING MANAGEMENT ---
@app.route("/rings", methods=["POST", "GET"])
@login_required
def manage_rings():
    if request.method == "POST":
        data = request.json
        new_ring = Ring(name=data["name"])
        db.session.add(new_ring)
        db.session.commit()
        return jsonify({"message": "Ring created", "id": new_ring.id}), 201

    rings = Ring.query.all()
    return jsonify([{"id": r.id, "name": r.name} for r in rings])


# --- DIVISION MANAGEMENT ---
@app.route("/divisions", methods=["POST", "GET"])
@login_required
def manage_divisions():
    if request.method == "POST":
        data = request.json
        event_type = data.get("event_type", "kyorugi")
        if event_type not in VALID_EVENT_TYPES:
            return jsonify({"error": "Invalid event type."}), 400
        new_division = Division(name=data["name"], event_type=event_type)
        db.session.add(new_division)
        db.session.commit()
        return jsonify({"message": "Division created", "id": new_division.id}), 201

    divisions = Division.query.all()
    return jsonify([{"id": d.id, "name": d.name, "event_type": d.event_type} for d in divisions])


@app.route("/divisions/<int:div_id>", methods=["DELETE", "PUT"])
@login_required
def edit_division(div_id):
    division = Division.query.get_or_404(div_id)
    if request.method == "DELETE":
        db.session.delete(division)
        db.session.commit()
        return jsonify({"message": "Division deleted"})
    if request.method == "PUT":
        data = request.json
        division.name = data.get("name", division.name)
        db.session.commit()
        return jsonify({"message": "Division updated"})


@app.route("/matches/<int:match_id>/result", methods=["POST"])
@login_required
def record_result(match_id):
    match = Match.query.get_or_404(match_id)
    data = request.json

    status = data.get("status")  # 'Completed' or 'Disqualification'
    winner_id = data.get("winner_id")

    match.status = status

    if status in ["Completed", "Disqualification"]:
        if not winner_id:
            return jsonify({"error": "Winner ID required for Completed/DQ matches"}), 400

        match.winner_id = winner_id

        # --- BRACKET ADVANCEMENT LOGIC ---
        if match.next_match_id:
            next_match = db.session.get(Match, match.next_match_id)
            # Assign the winner to the next match's open slot
            if not next_match.competitor1_id:
                next_match.competitor1_id = winner_id
            elif not next_match.competitor2_id:
                next_match.competitor2_id = winner_id

        db.session.commit()
        return jsonify({"message": "Result recorded and bracket updated."})


def _competitors_list_html(div_id):
    """Return HTML fragment for the competitor list with management controls."""
    competitors = Competitor.query.filter_by(division_id=div_id).order_by(Competitor.position).all()
    return render_template("_competitors_list.html", competitors=competitors, div_id=div_id)


def _division_name_display_html(division):
    """Return HTML fragment for the division name with inline rename controls."""
    return render_template("_division_name_display.html", division=division)


def _scorekeeper_match_card_html(match):
    """Return HTML fragment for a single scorekeeper match card."""
    return render_template("scorekeeper_match_card.html", match=match)


def _get_round_name(num_matches):
    """Return the standard tournament round name for a round with *num_matches* matches."""
    if num_matches == 1:
        return "Final"
    elif num_matches == 2:
        return "Semi-Final"
    elif num_matches == 4:
        return "Quarter-Final"
    else:
        return f"Round of {num_matches * 2}"


@app.route("/divisions/<int:div_id>/generate_bracket", methods=["POST"])
@login_required
def generate_bracket(div_id):
    Division.query.get_or_404(div_id)
    # Delete any existing matches before (re-)generating the bracket
    Match.query.filter_by(division_id=div_id).delete()
    db.session.flush()

    competitors = Competitor.query.filter_by(division_id=div_id).order_by(Competitor.position).all()

    num_comp = len(competitors)
    if num_comp < 2:
        db.session.rollback()
        return jsonify({"error": "Need at least 2 competitors to generate a bracket."}), 400

    # 1. Calculate bracket size (next power of 2) using log2
    # For N competitors, Next Power = 2^ceil(log2(N))
    next_power_of_2 = 2 ** math.ceil(math.log2(num_comp))
    num_first_round_matches = next_power_of_2 // 2

    # 2. Distribute competitors into bracket slots in roster order
    match_pairings = [[None, None] for _ in range(num_first_round_matches)]

    # Deal competitors into the pairings like a deck of cards
    for i, competitor in enumerate(competitors):
        slot = i // num_first_round_matches  # 0 for first pass, 1 for second pass
        match_index = i % num_first_round_matches
        match_pairings[match_index][slot] = competitor

    # 3. Create first-round matches, named by bracket size (e.g. "Quarter-Final", "Round of 16")
    first_round_name = _get_round_name(num_first_round_matches)
    current_round_matches = []
    for pair in match_pairings:
        comp1, comp2 = pair[0], pair[1]

        match = Match(
            division_id=div_id,
            competitor1_id=comp1.id if comp1 else None,
            competitor2_id=comp2.id if comp2 else None,
            round_name=first_round_name,
        )

        # Auto-advance if it's a bye
        if comp1 and not comp2:
            match.winner_id = comp1.id
            match.status = "Completed (Bye)"
        elif comp2 and not comp1:
            match.winner_id = comp2.id
            match.status = "Completed (Bye)"

        db.session.add(match)
        current_round_matches.append(match)

    # Flush to the database to generate the IDs for these new matches
    db.session.flush()

    # 4. Build Subsequent Rounds (Bottom-Up to the Final)
    while len(current_round_matches) > 1:
        next_round_matches = []

        # Group the previous round's matches in pairs
        for i in range(0, len(current_round_matches), 2):
            prev_match1 = current_round_matches[i]
            prev_match2 = current_round_matches[i + 1]

            # Determine round naming based on number of matches being created
            r_name = _get_round_name(len(current_round_matches) // 2)

            new_match = Match(division_id=div_id, round_name=r_name)
            db.session.add(new_match)
            db.session.flush()  # Get the ID for the new match

            # Link the previous matches to this new one
            prev_match1.next_match_id = new_match.id
            prev_match2.next_match_id = new_match.id

            # Push forward winners of byes immediately
            if prev_match1.winner_id:
                new_match.competitor1_id = prev_match1.winner_id
            if prev_match2.winner_id:
                new_match.competitor2_id = prev_match2.winner_id

            next_round_matches.append(new_match)

        current_round_matches = next_round_matches

    # Commit everything to the database
    db.session.commit()
    # Return a success message with links to manage or regenerate the bracket
    return render_template("_bracket_generate_success.html", div_id=div_id, num_comp=num_comp)


@app.route("/divisions/<int:div_id>/bracket", methods=["GET"])
def get_bracket(div_id):
    # Fetch all matches for the division
    matches = Match.query.filter_by(division_id=div_id).all()

    if not matches:
        return jsonify({"error": "No bracket found for this division."}), 404

    # Helper function to grab competitor names easily
    def get_comp_data(comp_id):
        if not comp_id:
            return None
        comp = db.session.get(Competitor, comp_id)
        return {"id": comp.id, "name": comp.name} if comp else None

    bracket_data = []
    for match in matches:
        bracket_data.append(
            {
                "match_id": match.id,
                "round_name": match.round_name,
                "status": match.status,
                "ring_id": match.ring_id,
                "next_match_id": match.next_match_id,
                "competitor1": get_comp_data(match.competitor1_id),
                "competitor2": get_comp_data(match.competitor2_id),
                "winner_id": match.winner_id,
            }
        )

    return jsonify(bracket_data), 200


# --- AUTH ROUTES ---
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        try:
            auth_response = supabase_client.auth.sign_in_with_password({"email": email, "password": password})
            session["user"] = {"email": auth_response.user.email, "id": str(auth_response.user.id)}
            next_url = request.form.get("next", "")
            parsed = urlparse(next_url)
            if parsed.scheme or parsed.netloc:
                next_url = url_for("admin_view")
            return redirect(next_url or url_for("admin_view"))
        except AuthApiError:
            error = "Invalid email or password."
        except Exception:
            logging.exception("Unexpected error during Supabase authentication")
            error = "Authentication is temporarily unavailable. Please try again later."
    return render_template("login.html", error=error)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))


# --- PAGE ROUTES ---
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/admin")
@login_required
def admin_view():
    return render_template("admin.html")


@app.route("/admin/schedule")
@login_required
def schedule_view():
    ring_filter = request.args.get("ring_id", "")
    event_type_filter = request.args.get("event_type", "")
    if event_type_filter not in ("", *VALID_EVENT_TYPES):
        event_type_filter = ""
    rings = Ring.query.order_by(Ring.name).all()

    # Fetch everything needed in one query to avoid per-division DB round trips.
    match_query = Match.query.options(
        joinedload(Match.division).joinedload(Division.ring),
        joinedload(Match.competitor1),
        joinedload(Match.competitor2),
    ).filter(Match.status != "Completed (Bye)")

    if event_type_filter:
        match_query = match_query.filter(Match.division.has(Division.event_type == event_type_filter))

    if ring_filter == "none":
        match_query = match_query.filter(Match.division.has(Division.ring_id.is_(None)))
    elif ring_filter:
        try:
            ring_id = int(ring_filter)
        except ValueError:
            ring_id = None
        if ring_id is not None:
            match_query = match_query.filter(Match.division.has(Division.ring_id == ring_id))

    matches = match_query.order_by(Match.division_id, Match.id).all()

    grouped_by_division = defaultdict(list)
    for match in matches:
        grouped_by_division[match.division].append(match)

    division_data = []
    for division in sorted(grouped_by_division.keys(), key=lambda d: d.name):
        grouped_rounds = defaultdict(list)
        for match in grouped_by_division[division]:
            grouped_rounds[match.round_name].append(match)

        sorted_rounds = dict(sorted(grouped_rounds.items(), key=lambda x: _round_sort_key(x[0]), reverse=True))
        division_data.append(
            {
                "division": division,
                "rounds": sorted_rounds,
                "ring": division.ring,
                "style": "bracket",
            }
        )

    # Fetch group-style poomsae divisions
    group_query = (
        Division.query.filter(Division.event_type == "poomsae", Division.poomsae_style == "group")
        .options(
            joinedload(Division.ring),
            joinedload(Division.competitors),
        )
        .order_by(Division.name)
    )

    if event_type_filter and event_type_filter != "poomsae":
        group_query = group_query.filter(False)  # Exclude group divisions if filtering for non-poomsae

    if ring_filter == "none":
        group_query = group_query.filter(Division.ring_id.is_(None))
    elif ring_filter:
        try:
            ring_id = int(ring_filter)
        except ValueError:
            ring_id = None
        if ring_id is not None:
            group_query = group_query.filter(Division.ring_id == ring_id)

    group_divisions = group_query.all()
    for division in group_divisions:
        # Get scores for this division
        scores_by_comp = {s.competitor_id: s for s in Score.query.filter_by(division_id=division.id).all()}

        # Sort: scored competitors first (highest score first), then unscored
        scored_competitors = sorted(
            [c for c in division.competitors if c.id in scores_by_comp],
            key=lambda c: scores_by_comp[c.id].score_value,
            reverse=True,
        )
        unscored_competitors = [c for c in division.competitors if c.id not in scores_by_comp]

        competitor_scores = [
            {"competitor": c, "score": scores_by_comp.get(c.id)} for c in scored_competitors + unscored_competitors
        ]

        division_data.append(
            {
                "division": division,
                "competitors": competitor_scores,
                "ring": division.ring,
                "style": "group",
            }
        )

    # Sort by ring first; within each ring, use sequence when present.
    def _schedule_sort_key(item):
        division = item["division"]
        ring_name = division.ring.name.lower() if division.ring else ""
        has_sequence = division.ring_sequence is not None
        sequence = division.ring_sequence if has_sequence else 0
        has_ring = division.ring is not None
        return (0 if has_ring else 1, ring_name, 0 if has_sequence else 1, sequence, division.name.lower())

    division_data.sort(key=_schedule_sort_key)

    return render_template(
        "admin_schedule.html",
        division_data=division_data,
        rings=rings,
        ring_filter=ring_filter,
        event_type_filter=event_type_filter,
    )


@app.route("/results")
def results_view():
    return render_template("results.html")


@app.route("/ui/divisions/<int:div_id>/bracket", methods=["GET"])
def brack(div_id):
    division = Division.query.get_or_404(div_id)
    return render_template("bracket_view.html", division=division)


def _extract_bracket_half(root_match, all_matches):
    """Extract match columns for one half of the bracket starting from *root_match*.

    Returns a list of lists ``[[root], [root's feeders], [their feeders], ...]``,
    i.e. innermost round first, outermost round last.
    """
    columns = [[root_match]]
    current_level = [root_match]
    while True:
        current_ids = {m.id for m in current_level}
        next_level = [m for m in all_matches if m.next_match_id in current_ids]
        if not next_level:
            break
        columns.append(next_level)
        current_level = next_level
    return columns


def _build_bracket_display(matches):
    """Build an ordered list of columns for a symmetric bracket display.

    The bracket is split into two halves that mirror each other around the Final:

        [left outermost] … [left innermost] [Final] [right innermost] … [right outermost]

    Each column is a ``dict`` with keys ``"title"`` (round name) and ``"matches"``
    (list of Match objects).  Returns the columns in left-to-right display order.
    """
    if not matches:
        return []

    # Championship match = the one with no next_match_id
    final = next((m for m in matches if m.next_match_id is None), None)
    if final is None:
        return []

    # Direct feeders into the Final
    feeders = sorted([m for m in matches if m.next_match_id == final.id], key=lambda m: m.id)

    columns = []

    if len(feeders) >= 2:
        left_root, right_root = feeders[0], feeders[1]

        # Left half: innermost→outermost; reverse so outermost is displayed first (leftmost)
        left_half = _extract_bracket_half(left_root, matches)
        left_half.reverse()
        for col_matches in left_half:
            columns.append({"title": col_matches[0].round_name, "matches": col_matches})

    # Center – the Final
    columns.append({"title": "Final", "matches": [final]})

    if len(feeders) >= 2:
        # Right half: innermost→outermost; display innermost first (closest to center)
        right_half = _extract_bracket_half(right_root, matches)
        for col_matches in right_half:
            columns.append({"title": col_matches[0].round_name, "matches": col_matches})

    return columns


@app.route("/divisions/<int:div_id>/bracket_ui", methods=["GET"])
def get_bracket_ui(div_id):
    matches = (
        Match.query.filter_by(division_id=div_id)
        .order_by(Match.id)
        .all()
    )

    if not matches:
        return render_template("_bracket_empty.html"), 404

    # Enrich matches with competitor names for template rendering
    for match in matches:
        match.competitor1_name = db.session.get(Competitor, match.competitor1_id).name if match.competitor1_id else "TBD"
        match.competitor2_name = db.session.get(Competitor, match.competitor2_id).name if match.competitor2_id else "TBD"

    # Build symmetric bracket columns
    columns = _build_bracket_display(matches)

    # Compute medal placements when the Final match is complete
    placements = _compute_placements(matches)

    return render_template("bracket_fragment.html", columns=columns, placements=placements)


def _round_sort_key(round_name):
    """Return a numeric sort key so rounds are ordered earliest-first.

    The key reflects the effective bracket size / competitor count for the round:
    'Final' -> 1, 'Semi-Final' -> 2, 'Quarter-Final' -> 4, and 'Round of N' -> N
    (e.g. 'Round of 16' -> 16).  Higher keys correspond to earlier rounds with
    more competitors; the exact numeric value is used only for ordering, and is
    not intended to equal the number of matches.
    """
    if round_name == "Final":
        return 1
    if round_name == "Semi-Final":
        return 2
    if round_name == "Quarter-Final":
        return 4
    if round_name and round_name.startswith("Round of "):
        try:
            return int(round_name[9:])
        except ValueError:
            pass
    return 0


def _abbrev_round(round_name):
    """Return a short display label for a round name.

    'Final' -> 'F', 'Semi-Final' -> 'SF', 'Quarter-Final' -> 'QF',
    'Round of N' -> 'R{N}'.  Any unrecognised value is returned unchanged.
    """
    if round_name == "Final":
        return "F"
    if round_name == "Semi-Final":
        return "SF"
    if round_name == "Quarter-Final":
        return "QF"
    if round_name and round_name.startswith("Round of"):
        return "R" + round_name[9:]
    return round_name


def _compute_placements(matches):
    """Return medal placements dict when the championship match is complete, else None.

    The championship match is identified as the one with no ``next_match_id``
    (the root of the bracket tree).  For all bracket sizes this is the match
    whose ``round_name`` is ``"Final"``.

    Returns a dict with keys:
        "first"  – winner of the championship match (Competitor name string)
        "second" – loser of the championship match
        "third"  – list of loser names from Semi-Final matches (0, 1, or 2 entries)
    """
    completed_statuses = COMPLETED_MATCH_STATUSES

    # The championship match is the one with no next_match_id.
    championship = next(
        (m for m in matches if m.next_match_id is None and m.status in completed_statuses),
        None,
    )
    if championship is None or not championship.winner_id:
        return None

    winner = db.session.get(Competitor, championship.winner_id)
    loser_id = (
        championship.competitor2_id
        if championship.winner_id == championship.competitor1_id
        else championship.competitor1_id
    )
    loser = db.session.get(Competitor, loser_id) if loser_id else None

    semi_losers = []
    # Semifinal matches are those that feed directly into the championship match.
    # Using the bracket structure (next_match_id) rather than round_name ensures
    # we correctly identify semifinals for all bracket sizes.
    for m in matches:
        if m.next_match_id == championship.id and m.status in completed_statuses and m.winner_id:
            sf_loser_id = (
                m.competitor2_id if m.winner_id == m.competitor1_id else m.competitor1_id
            )
            sf_loser = db.session.get(Competitor, sf_loser_id) if sf_loser_id else None
            if sf_loser:
                semi_losers.append(sf_loser.name)

    return {
        "first": winner.name if winner else None,
        "second": loser.name if loser else None,
        "third": semi_losers,
    }


# --- HTMX FRAGMENT ROUTES ---


# 1. Public Live Rings View
@app.route("/ui/public_rings")
def ui_public_rings():
    event_type = request.args.get("event_type", "kyorugi")
    if event_type not in VALID_EVENT_TYPES:
        return "Invalid event type.", 400

    rings = Ring.query.all()
    completed_statuses = ["Completed", "Completed (Bye)", "Disqualification"]
    # Find active/upcoming matches for each ring
    ring_data = []
    for ring in rings:
        # Fetch the most recently completed match (by match_number) for this ring
        last_completed = (
            Match.query.filter(
                Match.ring_id == ring.id,
                Match.division.has(event_type=event_type),
                Match.status.in_(completed_statuses),
                Match.match_number.isnot(None),
            )
            .order_by(Match.match_number.desc())
            .first()
        )
        if last_completed:
            last_completed.comp_1 = (
                f"{last_completed.competitor1.name.split()[0][0]}. {last_completed.competitor1.name.split()[-1]}"
                if last_completed.competitor1 else "TBD"
            )
            last_completed.comp_2 = (
                f"{last_completed.competitor2.name.split()[0][0]}. {last_completed.competitor2.name.split()[-1]}"
                if last_completed.competitor2 else "TBD"
            )
            last_completed.comp_1_result = (
                "W" if last_completed.winner_id == last_completed.competitor1_id
                else ("L" if last_completed.winner_id else "-")
            )
            last_completed.comp_2_result = (
                "W" if last_completed.winner_id == last_completed.competitor2_id
                else ("L" if last_completed.winner_id else "-")
            )
            last_completed.round_short = _abbrev_round(last_completed.round_name)

        matches = (
            Match.query.filter(
                Match.ring_id == ring.id,
                Match.division.has(event_type=event_type),
                Match.status.in_(["Pending", "In Progress"]),
                Match.match_number.isnot(None),
            )
            .order_by(case((Match.status == "In Progress", 0), else_=1), Match.match_number)
            .limit(4)
            .all()
        )
        for match in matches:
            match.comp_1 = (
                f"{match.competitor1.name.split()[0][0]}. {match.competitor1.name.split()[-1]}" if match.competitor1 else "TBD"
            )
            match.comp_2 = (
                f"{match.competitor2.name.split()[0][0]}. {match.competitor2.name.split()[-1]}" if match.competitor2 else "TBD"
            )
            match.round_short = _abbrev_round(match.round_name)

        ring_data.append({"name": ring.name, "last_completed": last_completed, "matches": matches})

        # For poomsae tab: merge bracket matches and group divisions into a single
        # interleaved list sorted by their common ring sequence number.
        if event_type == "poomsae":
            # Show group and un-configured poomsae divisions (exclude Completed); bracket ones appear via matches.
            group_divisions = Division.query.filter(
                Division.ring_id == ring.id,
                Division.event_type == "poomsae",
                db.or_(Division.poomsae_style != "bracket", Division.poomsae_style.is_(None)),
                Division.event_status != "Completed",
            ).all()
            # Build unified items: (sequence, type, object)
            poomsae_items = []
            for m in matches:
                seq = (m.match_number % 100) if m.match_number else None
                poomsae_items.append({"seq": seq, "kind": "match", "obj": m})
            for d in group_divisions:
                poomsae_items.append({"seq": d.ring_sequence, "kind": "division", "obj": d})
            poomsae_items.sort(key=lambda item: (item["seq"] is None, item["seq"] or 0))
            ring_data[-1]["poomsae_items"] = poomsae_items
            # Clear matches so the generic match loop in the template does not double-render them
            ring_data[-1]["matches"] = []
        else:
            ring_data[-1]["poomsae_items"] = []

    return render_template("_public_rings_fragment.html", rings=ring_data)


# 2. Results Divisions Fragment
@app.route("/ui/results_divisions")
def ui_results_divisions():
    event_type = request.args.get("event_type", "kyorugi")
    if event_type not in VALID_EVENT_TYPES:
        return "Invalid event type.", 400

    search = request.args.get("search", "").strip()

    divisions = Division.query.filter_by(event_type=event_type).order_by(Division.name).all()

    # Base query: all divisions for the given event type.
    division_query = Division.query.filter_by(event_type=event_type)

    # When a search term is provided, restrict to divisions that contain at least one
    # competitor whose name matches (case-insensitive substring match).
    if search:
        division_query = (
            division_query.join(Competitor, Division.id == Competitor.division_id)
            .filter(Competitor.name.ilike(f"%{search}%"))
            .distinct()
        )

    divisions = division_query.order_by(Division.name).all()
    # Single query for all match statuses — avoids N+1
    division_ids = [d.id for d in divisions]
    matches_by_division = defaultdict(list)
    if division_ids:
        for m in Match.query.filter(Match.division_id.in_(division_ids)).all():
            matches_by_division[m.division_id].append(m)

    division_data = []
    for division in divisions:
        matches = matches_by_division[division.id]
        if not matches:
            if division.event_type == "poomsae":
                status = division.event_status
            else:
                status = "No bracket"
        elif all(m.status in COMPLETED_MATCH_STATUSES for m in matches):
            status = "Completed"
        elif any(m.status in COMPLETED_MATCH_STATUSES or m.status == "In Progress" for m in matches):
            status = "In Progress"
        else:
            status = "Pending"
        division_data.append({"division": division, "status": status})

    return render_template("results_divisions_fragment.html", divisions=division_data)


# --- RING ROUTES ---


@app.route("/ui/rings", methods=["POST"])
@login_required
def ui_add_ring():
    name = request.form.get("name")
    new_ring = Ring(name=name)
    db.session.add(new_ring)
    db.session.commit()

    return render_template("_ring_list_item.html", ring=new_ring, include_scorekeeper=False)


@app.route("/ui/rings_list")
@login_required
def ui_rings_list():
    rings = Ring.query.all()
    return render_template("_rings_list.html", rings=rings, include_scorekeeper=True)


@app.route("/ui/rings/<int:ring_id>", methods=["DELETE"])
@login_required
def ui_delete_ring(ring_id):
    ring = Ring.query.get_or_404(ring_id)
    db.session.delete(ring)
    db.session.commit()
    # Return an empty string. HTMX will swap the <li> with this empty string, effectively removing it.
    return ""


# --- DIVISION ROUTES ---


@app.route("/ui/divisions", methods=["POST"])
@login_required
def ui_add_division():
    name = request.form.get("name")
    event_type = request.form.get("event_type", "kyorugi")
    if event_type not in VALID_EVENT_TYPES:
        return "Invalid event type.", 400
    new_div = Division(name=name, event_type=event_type)
    db.session.add(new_div)
    db.session.commit()

    return render_template("_division_list_item.html", division=new_div)


@app.route("/ui/divisions_list")
@login_required
def ui_divisions_list():
    event_type = request.args.get("event_type")
    if event_type and event_type not in VALID_EVENT_TYPES:
        return "Invalid event type.", 400
    query = Division.query
    if event_type:
        query = query.filter_by(event_type=event_type)
    divisions = query.all()
    return render_template("_divisions_list.html", divisions=divisions)


@app.route("/ui/divisions/<int:div_id>", methods=["DELETE"])
@login_required
def ui_delete_division(div_id):
    div = Division.query.get_or_404(div_id)

    # Delete all associated scores, matches and competitors first to maintain database integrity
    Score.query.filter_by(division_id=div_id).delete()
    Match.query.filter_by(division_id=div_id).delete()
    Competitor.query.filter_by(division_id=div_id).delete()

    db.session.delete(div)
    db.session.commit()
    return ""


@app.route("/admin/divisions/<int:div_id>/setup")
@login_required
def admin_division_setup(div_id):
    division = Division.query.get_or_404(div_id)
    return render_template("division_setup.html", division=division)


@app.route("/ui/divisions/<int:div_id>/competitors", methods=["POST"])
@login_required
def ui_add_competitors(div_id):
    names_text = request.form.get("names")

    if names_text:
        # Split the text area by newlines and remove empty lines
        name_list = [name.strip() for name in names_text.split("\n") if name.strip()]

        # Assign positions starting after the current maximum
        max_pos = db.session.query(db.func.max(Competitor.position)).filter_by(division_id=div_id).scalar() or 0
        for i, name in enumerate(name_list):
            comp = Competitor(name=name, division_id=div_id, position=max_pos + i + 1)
            db.session.add(comp)

        db.session.commit()

    return _competitors_list_html(div_id)


@app.route("/ui/divisions/<int:div_id>/competitors_list")
@login_required
def ui_competitors_list(div_id):
    return _competitors_list_html(div_id)


@app.route("/ui/divisions/<int:div_id>/bracket_controls")
@login_required
def ui_bracket_controls(div_id):
    division = Division.query.get_or_404(div_id)
    rings = Ring.query.all()
    return render_template("_bracket_controls.html", division=division, rings=rings)


@app.route("/ui/divisions/<int:div_id>/competitors/<int:comp_id>", methods=["DELETE"])
@login_required
def ui_delete_competitor(div_id, comp_id):
    comp = Competitor.query.get_or_404(comp_id)
    if comp.division_id != div_id:
        return "Not found", 404
    # Clear any existing bracket matches so FK constraints are not violated and
    # the user is required to regenerate the bracket after the roster change.
    Score.query.filter_by(competitor_id=comp_id).delete()
    Match.query.filter_by(division_id=div_id).delete()
    db.session.delete(comp)
    db.session.commit()
    return _competitors_list_html(div_id)


@app.route("/ui/divisions/<int:div_id>/competitors/<int:comp_id>/move", methods=["POST"])
@login_required
def ui_move_competitor(div_id, comp_id):
    direction = request.form.get("direction")
    competitors = Competitor.query.filter_by(division_id=div_id).order_by(Competitor.position).all()
    idx = next((i for i, c in enumerate(competitors) if c.id == comp_id), None)
    if idx is None:
        return "Competitor not found", 404
    if direction == "up" and idx > 0:
        competitors[idx].position, competitors[idx - 1].position = (
            competitors[idx - 1].position,
            competitors[idx].position,
        )
        db.session.commit()
    elif direction == "down" and idx < len(competitors) - 1:
        competitors[idx].position, competitors[idx + 1].position = (
            competitors[idx + 1].position,
            competitors[idx].position,
        )
        db.session.commit()
    return _competitors_list_html(div_id)


@app.route("/ui/divisions/<int:div_id>/name_form")
@login_required
def ui_division_name_form(div_id):
    division = Division.query.get_or_404(div_id)
    return render_template("_division_name_form.html", division=division)


@app.route("/ui/divisions/<int:div_id>/name_display")
@login_required
def ui_division_name_display(div_id):
    division = Division.query.get_or_404(div_id)
    return _division_name_display_html(division)


@app.route("/ui/divisions/<int:div_id>/name", methods=["PATCH"])
@login_required
def ui_rename_division(div_id):
    division = Division.query.get_or_404(div_id)
    new_name = request.form.get("name", "").strip()
    if new_name:
        division.name = new_name
        db.session.commit()
    return _division_name_display_html(division)


@app.route("/admin/divisions/<int:div_id>/bracket_manage")
@login_required
def manage_bracket_page(div_id):
    division = Division.query.get_or_404(div_id)
    matches = Match.query.filter_by(division_id=div_id).all()
    rings = Ring.query.all()

    # Group matches by round, then sort rounds earliest-first (most matches → fewest)
    grouped_matches = defaultdict(list)
    for match in matches:
        grouped_matches[match.round_name].append(match)

    sorted_rounds = dict(sorted(grouped_matches.items(), key=lambda x: _round_sort_key(x[0]), reverse=True))
    current_ring = Ring.query.get(division.ring_id) if division.ring_id else None

    return render_template("bracket_manage.html", division=division, rounds=sorted_rounds, rings=rings, current_ring=current_ring)

@app.route("/ui/divisions/<int:div_id>/bracket_ring", methods=["PATCH"])
@login_required
def ui_bracket_ring_assignment(div_id):
    division = Division.query.get_or_404(div_id)
    ring_id_raw = request.form.get("ring_id", "")
    if ring_id_raw == "":
        new_ring_id = None
    else:
        try:
            new_ring_id = int(ring_id_raw)
        except ValueError:
            return "Invalid ring_id value.", 400
        if Ring.query.get(new_ring_id) is None:
            return "Ring not found.", 404

    # When ring changes, clear scheduling for all matches in this division
    if new_ring_id != division.ring_id:
        for match in Match.query.filter_by(division_id=division.id).all():
            match.ring_id = None
            match.match_number = None

    division.ring_id = new_ring_id
    db.session.commit()
    rings = Ring.query.all()
    current_ring = Ring.query.get(division.ring_id) if division.ring_id else None
    return render_template(
        "_bracket_ring_assignment.html",
        division=division,
        rings=rings,
        current_ring=current_ring,
    )


@app.route("/matches/<int:match_id>/schedule", methods=["PUT"])
@login_required
def schedule_match_htmx(match_id):
    match = Match.query.get_or_404(match_id)

    ring_sequence = request.form.get("ring_sequence")  # e.g., the '25' in 525

    if ring_sequence:
        try:
            ring_sequence_int = int(ring_sequence)
        except ValueError:
            return "Invalid ring_sequence value.", 400
        if not (1 <= ring_sequence_int <= 99):
            return "ring_sequence must be between 1 and 99.", 400

        division_ring_id = match.division.ring_id
        if division_ring_id is None:
            return render_template(
                "_match_schedule_card.html",
                match=match,
                ring_sequence_value=ring_sequence_int,
                error_message="Error: No ring assigned to this bracket. Set the ring at the top of the page.",
            )

        proposed_match_number = (division_ring_id * 100) + ring_sequence_int
        event_type = match.division.event_type
        duplicate = (
            Match.query.join(Division)
            .filter(
                Division.event_type == event_type,
                Match.match_number == proposed_match_number,
                Match.id != match.id,
            )
            .first()
        )
        # Also check whether a poomsae division already occupies this ring+sequence
        # (poomsae divisions share the 1-99 sequence pool with bracket matches)
        conflicting_division = None
        if event_type == "poomsae":
            conflicting_division = (
                Division.query.filter(
                    Division.event_type == "poomsae",
                    Division.ring_id == division_ring_id,
                    Division.ring_sequence == ring_sequence_int,
                    Division.id != match.division_id,
                ).first()
            )
        if duplicate or conflicting_division:
            # Build a descriptive name for whatever is already using this slot
            if conflicting_division:
                conflict_name = conflicting_division.name
            else:
                # A bracket match from another division occupies this number
                conflict_name = duplicate.division.name
            return render_template(
                "_match_schedule_card.html",
                match=match,
                ring_sequence_value=ring_sequence_int,
                error_message=(f'Error: Sequence {ring_sequence_int} is already used by "{conflict_name}" in this ring.'),
            )
        match.ring_id = division_ring_id
        match.match_number = proposed_match_number
        db.session.commit()

    return render_template(
        "_match_schedule_card.html",
        match=match,
        ring_sequence_value=(match.match_number - match.ring_id * 100 if match.match_number and match.ring_id else ""),
        error_message=None,
    )


# --- SCOREKEEPER ROUTES ---
@app.route("/ring/<int:ring_id>/scorekeeper")
@login_required
def ring_scorekeeper(ring_id):
    ring = Ring.query.get_or_404(ring_id)
    event_type = request.args.get("event_type", "kyorugi")
    if event_type not in VALID_EVENT_TYPES:
        return "Invalid event type.", 400

    # Get all pending or in-progress matches for this ring, ordered by match number
    matches = (
        Match.query.filter(
            Match.ring_id == ring.id,
            Match.division.has(event_type=event_type),
            Match.status.in_(["Pending", "In Progress"]),
        )
        .order_by(Match.match_number)
        .all()
    )

    return render_template("scorekeeper.html", ring=ring, matches=matches, event_type=event_type)


@app.route("/ui/rings/<int:ring_id>/scorekeeper_matches")
@login_required
def ui_scorekeeper_matches(ring_id):
    """HTMX fragment: pending/in-progress kyorugi matches for a ring, ordered by match number."""
    Ring.query.get_or_404(ring_id)
    matches = (
        Match.query.filter(
            Match.ring_id == ring_id,
            Match.division.has(event_type="kyorugi"),
            Match.status.in_(["Pending", "In Progress"]),
        )
        .order_by(Match.match_number)
        .all()
    )
    return render_template("scorekeeper_matches_fragment.html", matches=matches)


@app.route("/ui/matches/<int:match_id>/result", methods=["POST"])
@login_required
def ui_record_result(match_id):
    match = Match.query.get_or_404(match_id)

    if not match.competitor1_id or not match.competitor2_id:
        return render_template(
            "_inline_error.html",
            message="Error: Cannot submit result for a match with TBD competitors.",
        ), 400

    status = request.form.get("status")
    winner_id = request.form.get("winner_id")

    if status == "In Progress":
        if match.ring_id is not None:
            existing_in_progress = Match.query.filter(
                Match.ring_id == match.ring_id,
                Match.status == "In Progress",
                Match.id != match.id,
            ).first()
            if existing_in_progress:
                resp = make_response(_scorekeeper_match_card_html(match))
                resp.headers["HX-Trigger"] = "showInProgressError"
                return resp

        match.status = status
        if match.start_time is None:
            match.start_time = datetime.now(timezone.utc)
        db.session.commit()
        db.session.refresh(match)
        return _scorekeeper_match_card_html(match)

    if status in ["Completed", "Disqualification"]:
        if not winner_id:
            return render_template("_inline_error.html", message="Error: Winner must be selected."), 400

        match.status = status
        match.winner_id = int(winner_id)

        # Record end_time only if the match was actually started and end_time is not already set
        if match.start_time is not None and match.end_time is None:
            match.end_time = datetime.now(timezone.utc)

        # --- BRACKET ADVANCEMENT LOGIC ---
        if match.next_match_id:
            next_match = db.session.get(Match, match.next_match_id)
            # Push the winner into the next match's open slot
            if not next_match.competitor1_id:
                next_match.competitor1_id = match.winner_id
            elif not next_match.competitor2_id:
                next_match.competitor2_id = match.winner_id

        db.session.commit()

        winner = db.session.get(Competitor, match.winner_id)

        winner_name = winner.name
        match_number = match.match_number

        if match.round_name == "Final":
            result_message = "wins gold!"
        else:
            result_message = "advances to the next round!"

        # Return OOB swaps: result notification + refreshed match/division container.
        # Each OOB element uses hx-trigger="load" to trigger a fresh HTMX fetch so that
        # newly rendered buttons are fully processed by HTMX (same pattern for both
        # kyorugi and poomsae).
        return render_template(
            "_scorekeeper_result_oob.html",
            match=match,
            match_number=match_number,
            winner_name=winner_name,
            result_message=result_message,
            is_poomsae=(match.division.event_type == "poomsae"),
        )


# --- POOMSAE ROUTES ---

def _build_poomsae_ranked(div_id):
    """Return a list of (Competitor, Score|None) tuples for a division, ranked by score.

    Scored competitors appear first (highest score first); unscored competitors
    follow in their roster order.
    """
    competitors = Competitor.query.filter_by(division_id=div_id).order_by(Competitor.position).all()
    scores_by_comp = {
        s.competitor_id: s
        for s in Score.query.filter_by(division_id=div_id).all()
    }
    scored = sorted(
        [c for c in competitors if c.id in scores_by_comp],
        key=lambda c: scores_by_comp[c.id].score_value,
        reverse=True,
    )
    unscored = [c for c in competitors if c.id not in scores_by_comp]
    return [(c, scores_by_comp.get(c.id)) for c in scored + unscored]


def _group_results_fragment_html(div_id, scorekeeper_mode=False):
    """Return the ranked scores table with score-entry forms for a poomsae/breaking division."""
    division = Division.query.get_or_404(div_id)
    ranked = _build_poomsae_ranked(div_id)
    return render_template(
        "group_results_fragment.html",
        division=division,
        ranked=ranked,
        scorekeeper_mode=scorekeeper_mode,
    )


@app.route("/ui/divisions/<int:div_id>/poomsae_style", methods=["POST"])
@login_required
def ui_set_poomsae_style(div_id):
    """Set the poomsae division style ('bracket' or 'group'). Locked once set."""
    division = Division.query.get_or_404(div_id)
    if division.event_type != "poomsae":
        return "Not a poomsae division.", 400
    if division.poomsae_style is not None:
        return "Style already set.", 400
    style = request.form.get("poomsae_style")
    if style not in ("bracket", "group"):
        return "Invalid style.", 400
    division.poomsae_style = style
    db.session.commit()
    rings = Ring.query.all()
    return render_template("_bracket_controls.html", division=division, rings=rings)


@app.route("/ui/divisions/<int:div_id>/ring_assignment", methods=["PATCH"])
@login_required
def ui_poomsae_ring_assignment(div_id):
    """Assign a poomsae division to a ring and update its event status and ring sequence."""
    division = Division.query.get_or_404(div_id)
    if division.event_type != "poomsae":
        return "Not a poomsae division.", 400

    ring_id = request.form.get("ring_id")
    event_status = request.form.get("event_status", "Pending")
    ring_sequence_raw = request.form.get("ring_sequence", "")

    if ring_id:
        ring = Ring.query.get_or_404(int(ring_id))
        division.ring_id = ring.id
    else:
        division.ring_id = None
    division.event_status = event_status

    if ring_sequence_raw.strip():
        try:
            ring_sequence_int = int(ring_sequence_raw)
        except ValueError:
            return "Invalid ring_sequence value.", 400
        if not (1 <= ring_sequence_int <= 99):
            return "ring_sequence must be between 1 and 99.", 400
        # Check that no bracket match already occupies this ring+sequence slot.
        # Bracket match_number encodes (ring_id * 100) + ring_sequence.
        target_ring_id = division.ring_id  # already updated above
        if target_ring_id is not None:
            proposed_match_number = (target_ring_id * 100) + ring_sequence_int
            conflicting_match = (
                Match.query.join(Division)
                .filter(
                    Division.event_type == "poomsae",
                    Match.ring_id == target_ring_id,
                    Match.match_number == proposed_match_number,
                )
                .first()
            )
            # Also check another group division in the same ring (excluding this one)
            conflicting_div = Division.query.filter(
                Division.id != div_id,
                Division.ring_id == target_ring_id,
                Division.ring_sequence == ring_sequence_int,
                Division.poomsae_style == "group",
            ).first()
            if conflicting_match or conflicting_div:
                conflict_name = (
                    escape(conflicting_match.division.name)
                    if conflicting_match
                    else escape(conflicting_div.name)
                )
                db.session.rollback()
                return f"Sequence {ring_sequence_int} is already used by \"{conflict_name}\" in this ring.", 400
        division.ring_sequence = ring_sequence_int
    else:
        division.ring_sequence = None
    db.session.commit()

    rings = Ring.query.all()
    return render_template("_bracket_controls.html", division=division, rings=rings)


@app.route("/ui/divisions/<int:div_id>/event_status", methods=["PATCH"])
@login_required
def ui_update_event_status(div_id):
    """Update the event status of a poomsae division (used from the Scorekeeper page)."""
    division = Division.query.get_or_404(div_id)
    event_status = request.form.get("event_status", "Pending")
    if event_status not in ("Pending", "In Progress", "Completed"):
        return "Invalid status.", 400
    division.event_status = event_status
    if event_status == "In Progress":
        if division.start_time is None:
            division.start_time = datetime.now(timezone.utc)
    elif event_status == "Completed":
        if division.start_time is not None and division.end_time is None:
            division.end_time = datetime.now(timezone.utc)
    elif event_status == "Pending":
        division.start_time = None
        division.end_time = None
    db.session.commit()
    ranked = _build_poomsae_ranked(div_id)
    return render_template(
        "group_results_fragment.html",
        division=division,
        ranked=ranked,
        scorekeeper_mode=True,
    )


@app.route("/ui/divisions/<int:div_id>/competitors/<int:comp_id>/score", methods=["POST"])
@login_required
def ui_record_poomsae_score(div_id, comp_id):
    """Record or update a poomsae score for a single competitor."""
    division = Division.query.get_or_404(div_id)
    # Ensure this route is only used for poomsae divisions.
    if division.event_type != "poomsae":
        return "Division is not a poomsae division.", 400

    competitor = Competitor.query.get_or_404(comp_id)
    if competitor.division_id != div_id:
        return "Not found", 404

    try:
        score_value = float(request.form.get("score_value", ""))
    except (ValueError, TypeError):
        return "Invalid score value.", 400

    # Reject NaN, Infinity, negative scores, and scores above the maximum of 10.000.
    if not math.isfinite(score_value) or score_value < 0 or score_value > 10.0:
        return "Invalid score value.", 400

    score = Score.query.filter_by(competitor_id=comp_id, division_id=div_id).first()
    if score:
        score.score_value = score_value
    else:
        score = Score(competitor_id=comp_id, division_id=div_id, score_value=score_value)
        db.session.add(score)
    db.session.commit()

    scorekeeper_mode = request.form.get("scorekeeper_mode") == "1"
    return _group_results_fragment_html(div_id, scorekeeper_mode=scorekeeper_mode)


@app.route("/ui/divisions/<int:div_id>/group_results_fragment")
@login_required
def ui_group_results_fragment(div_id):
    """HTMX fragment: ranked group results with score-entry forms (for score_manage and scorekeeper)."""
    scorekeeper_mode = request.args.get("scorekeeper_mode") == "1"
    return _group_results_fragment_html(div_id, scorekeeper_mode=scorekeeper_mode)


@app.route("/ui/divisions/<int:div_id>/poomsae_placements_fragment")
def ui_poomsae_placements_fragment(div_id):
    """HTMX fragment: read-only poomsae placements with medal rankings (1 gold, 1 silver, 2 bronze)."""
    division = Division.query.get_or_404(div_id)
    ranked = _build_poomsae_ranked(div_id)
    return render_template("poomsae_placements_fragment.html", division=division, ranked=ranked)


@app.route("/admin/divisions/<int:div_id>/group_results")
def group_results_page(div_id):
    """Read-only group results page showing medal placements (public/display view)."""
    division = Division.query.get_or_404(div_id)
    return render_template("group_results.html", division=division)


@app.route("/admin/divisions/<int:div_id>/score_manage")
@login_required
def poomsae_score_manage_page(div_id):
    """Admin poomsae score management page for entering and updating competitor scores."""
    division = Division.query.get_or_404(div_id)
    return render_template("score_manage.html", division=division)


@app.route("/ui/rings/<int:ring_id>/poomsae_divisions")
@login_required
def ui_ring_poomsae_divisions(ring_id):
    """HTMX fragment: all poomsae items for a ring (bracket matches + group divisions), sorted
    by their common ring sequence number so both types appear in the correct order together."""
    Ring.query.get_or_404(ring_id)

    # --- Bracket poomsae matches assigned to this ring (Pending or In Progress) ---
    bracket_matches = (
        Match.query.filter(
            Match.ring_id == ring_id,
            Match.division.has(event_type="poomsae"),
            Match.status.in_(["Pending", "In Progress"]),
        )
        .order_by(Match.match_number)
        .all()
    )

    # --- Group poomsae divisions assigned to this ring (exclude Completed) ---
    group_divisions = Division.query.filter(
        Division.ring_id == ring_id,
        Division.event_type == "poomsae",
        Division.poomsae_style == "group",
        Division.event_status != "Completed",
    ).all()

    if not bracket_matches and not group_divisions:
        return render_template("_empty_state.html", message="No poomsae divisions assigned to this ring.")

    # Build a unified list of (sequence, html) items so both types interleave correctly.
    # Bracket match sequence = match_number % 100 (the sequence portion of ring_id*100 + seq).
    # Group division sequence = division.ring_sequence (1-99, same pool). Nulls sort last.
    items = []

    for match in bracket_matches:
        seq = (match.match_number % 100) if match.match_number else None
        html = render_template("scorekeeper_match_card.html", match=match)
        items.append((seq, html))

    for division in group_divisions:
        seq = division.ring_sequence  # 1-99 or None
        ranked = _build_poomsae_ranked(division.id)
        html = render_template(
            "group_results_fragment.html",
            division=division,
            ranked=ranked,
            scorekeeper_mode=True,
        )
        items.append((seq, html))

    # Sort: sequenced items first (ascending), unsequenced last
    items.sort(key=lambda item: (item[0] is None, item[0] or 0))

    return "\n".join(html for _, html in items)


# Initialize DB for testing
if __name__ == "__main__":
    app.run(host="0.0.0.0")
