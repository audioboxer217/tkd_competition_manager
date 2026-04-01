import hashlib
import logging
import math
import secrets
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, jsonify, request

from models import VALID_EVENT_TYPES, ApiToken, Competitor, Division, Match, Ring, db

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")


# --- Response helpers ---


def success_response(data, status_code=200):
    """Return a consistent success JSON envelope: {"data": ..., "error": null}."""
    return jsonify({"data": data, "error": None}), status_code


def error_response(code, message, details=None, status_code=400):
    """Return a consistent error JSON envelope.

    {"data": null, "error": {"code": "...", "message": "...", "details": {...}}}
    """
    return jsonify({"data": None, "error": {"code": code, "message": message, "details": details or {}}}), status_code


# --- Token helpers ---


def _generate_raw_token() -> str:
    """Generate a cryptographically secure, URL-safe token string (32 bytes → 43 chars)."""
    return secrets.token_urlsafe(32)


def _hash_token(raw_token: str) -> str:
    """Return the hex SHA-256 digest of *raw_token*."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


# --- API-specific auth decorator (Bearer token, returns JSON 401, never redirects) ---


def api_login_required(f):
    """Require a valid API bearer token stored in the ApiToken table.

    Extracts the token from ``Authorization: Bearer <token>``, hashes it, and
    looks it up in the database.  Returns a JSON 401 envelope on failure —
    never redirects.  Updates ``last_used_at`` on every successful request.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return error_response(
                "UNAUTHORIZED",
                "Authorization header with Bearer token is required.",
                status_code=401,
            )
        raw_token = auth_header[len("Bearer ") :]
        token_hash = _hash_token(raw_token)
        api_token = ApiToken.query.filter_by(token_hash=token_hash, is_active=True).first()
        if api_token is None:
            return error_response("UNAUTHORIZED", "Invalid or revoked token.", status_code=401)
        api_token.last_used_at = datetime.now(timezone.utc)
        db.session.commit()
        return f(*args, **kwargs)

    return decorated_function


# --- Enforce JSON Content-Type on mutating requests ---


@api_v1.before_request
def enforce_json_content_type():
    """Reject POST/PUT/PATCH requests that include a body without application/json Content-Type.

    Body-less requests are allowed without a Content-Type header so that action
    endpoints such as ``generate_bracket`` can be called without an explicit
    request body.  Body presence is detected by reading the raw data (which
    also handles chunked transfer encoding where Content-Length is absent).
    """
    if request.method in ("POST", "PUT", "PATCH"):
        if request.get_data(cache=True) and not request.is_json:
            return error_response(
                "UNSUPPORTED_MEDIA_TYPE",
                "Content-Type must be application/json.",
                status_code=415,
            )


# --- Blueprint-level error handlers ---


@api_v1.errorhandler(400)
def api_bad_request(e):
    return error_response("BAD_REQUEST", str(e), status_code=400)


@api_v1.errorhandler(401)
def api_unauthorized(e):
    return error_response("UNAUTHORIZED", str(e), status_code=401)


@api_v1.errorhandler(404)
def api_not_found(e):
    return error_response("NOT_FOUND", str(e), status_code=404)


@api_v1.errorhandler(409)
def api_conflict(e):
    return error_response("CONFLICT", str(e), status_code=409)


@api_v1.errorhandler(422)
def api_unprocessable(e):
    return error_response("UNPROCESSABLE_ENTITY", str(e), status_code=422)


@api_v1.errorhandler(500)
def api_internal_error(e):
    logging.exception("Unhandled exception in /api/v1", exc_info=(type(e), e, e.__traceback__))
    return error_response("INTERNAL_SERVER_ERROR", "An internal server error occurred.", status_code=500)


# --- /api/v1/rings ---


@api_v1.route("/rings", methods=["GET"])
@api_login_required
def api_list_rings():
    rings = Ring.query.all()
    return success_response([{"id": r.id, "name": r.name} for r in rings])


@api_v1.route("/rings", methods=["POST"])
@api_login_required
def api_create_ring():
    data = request.get_json()
    if not isinstance(data, dict):
        return error_response("BAD_REQUEST", "Request JSON body must be an object.", status_code=400)
    name = (data.get("name") or "").strip()
    if not name:
        return error_response("BAD_REQUEST", "Ring name is required.", details={"field": "name"}, status_code=400)
    new_ring = Ring(name=name)
    db.session.add(new_ring)
    db.session.commit()
    return success_response({"id": new_ring.id, "name": new_ring.name}, status_code=201)


@api_v1.route("/rings/<int:ring_id>", methods=["GET"])
@api_login_required
def api_get_ring(ring_id):
    ring = db.session.get(Ring, ring_id)
    if not ring:
        return error_response("NOT_FOUND", f"Ring {ring_id} not found.", status_code=404)
    return success_response({"id": ring.id, "name": ring.name})


@api_v1.route("/rings/<int:ring_id>", methods=["PATCH"])
@api_login_required
def api_update_ring(ring_id):
    ring = db.session.get(Ring, ring_id)
    if not ring:
        return error_response("NOT_FOUND", f"Ring {ring_id} not found.", status_code=404)
    data = request.get_json()
    if not isinstance(data, dict):
        return error_response("BAD_REQUEST", "Request JSON body must be an object.", status_code=400)
    if "name" in data:
        new_name = (data.get("name") or "").strip()
        if not new_name:
            return error_response("BAD_REQUEST", "Ring name is required.", details={"field": "name"}, status_code=400)
        ring.name = new_name
    db.session.commit()
    return success_response({"id": ring.id, "name": ring.name})


@api_v1.route("/rings/<int:ring_id>", methods=["DELETE"])
@api_login_required
def api_delete_ring(ring_id):
    ring = db.session.get(Ring, ring_id)
    if not ring:
        return error_response("NOT_FOUND", f"Ring {ring_id} not found.", status_code=404)
    db.session.delete(ring)
    db.session.commit()
    return success_response({"id": ring_id, "deleted": True})


# --- /api/v1/divisions ---


@api_v1.route("/divisions", methods=["GET"])
@api_login_required
def api_list_divisions():
    divisions = Division.query.all()
    return success_response([{"id": d.id, "name": d.name, "event_type": d.event_type} for d in divisions])


@api_v1.route("/divisions", methods=["POST"])
@api_login_required
def api_create_division():
    data = request.get_json()
    if not isinstance(data, dict):
        return error_response("BAD_REQUEST", "Request JSON body must be an object.", status_code=400)
    name = (data.get("name") or "").strip()
    if not name:
        return error_response("BAD_REQUEST", "Division name is required.", details={"field": "name"}, status_code=400)
    event_type = data.get("event_type", "kyorugi")
    if event_type not in VALID_EVENT_TYPES:
        return error_response(
            "BAD_REQUEST",
            "Invalid event type.",
            details={"field": "event_type", "valid_values": sorted(VALID_EVENT_TYPES)},
            status_code=400,
        )
    new_division = Division(name=name, event_type=event_type)
    db.session.add(new_division)
    db.session.commit()
    return success_response(
        {"id": new_division.id, "name": new_division.name, "event_type": new_division.event_type},
        status_code=201,
    )


@api_v1.route("/divisions/<int:div_id>", methods=["GET"])
@api_login_required
def api_get_division(div_id):
    division = db.session.get(Division, div_id)
    if not division:
        return error_response("NOT_FOUND", f"Division {div_id} not found.", status_code=404)
    return success_response({"id": division.id, "name": division.name, "event_type": division.event_type})


@api_v1.route("/divisions/<int:div_id>", methods=["PUT", "PATCH"])
@api_login_required
def api_update_division(div_id):
    division = db.session.get(Division, div_id)
    if not division:
        return error_response("NOT_FOUND", f"Division {div_id} not found.", status_code=404)
    data = request.get_json()
    if not isinstance(data, dict):
        return error_response("BAD_REQUEST", "Request JSON body must be an object.", status_code=400)
    new_name = (data.get("name") or "").strip()
    if not new_name:
        return error_response("BAD_REQUEST", "Division name is required.", details={"field": "name"}, status_code=400)
    division.name = new_name
    db.session.commit()
    return success_response({"id": division.id, "name": division.name, "event_type": division.event_type})


@api_v1.route("/divisions/<int:div_id>", methods=["DELETE"])
@api_login_required
def api_delete_division(div_id):
    division = db.session.get(Division, div_id)
    if not division:
        return error_response("NOT_FOUND", f"Division {div_id} not found.", status_code=404)
    db.session.delete(division)
    db.session.commit()
    return success_response({"id": div_id, "deleted": True})


# --- /api/v1/divisions/<id>/bracket ---


@api_v1.route("/divisions/<int:div_id>/bracket", methods=["GET"])
@api_login_required
def api_get_bracket(div_id):
    division = db.session.get(Division, div_id)
    if not division:
        return error_response("NOT_FOUND", f"Division {div_id} not found.", status_code=404)
    matches = Match.query.filter_by(division_id=div_id).all()
    if not matches:
        return error_response("NOT_FOUND", "No bracket found for this division.", status_code=404)

    # Bulk-load all competitors referenced in this division's matches to avoid N+1 queries.
    competitor_ids = {comp_id for m in matches for comp_id in (m.competitor1_id, m.competitor2_id) if comp_id is not None}
    comp_map = {}
    if competitor_ids:
        comps = Competitor.query.filter(Competitor.id.in_(competitor_ids)).all()
        comp_map = {c.id: {"id": c.id, "name": c.name} for c in comps}

    def _comp_data(comp_id):
        if not comp_id:
            return None
        return comp_map.get(comp_id)

    bracket_data = [
        {
            "match_id": m.id,
            "round_name": m.round_name,
            "status": m.status,
            "ring_id": m.ring_id,
            "next_match_id": m.next_match_id,
            "competitor1": _comp_data(m.competitor1_id),
            "competitor2": _comp_data(m.competitor2_id),
            "winner_id": m.winner_id,
        }
        for m in matches
    ]
    return success_response(bracket_data)


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


@api_v1.route("/divisions/<int:div_id>/generate_bracket", methods=["POST"])
@api_login_required
def api_generate_bracket(div_id):
    """Generate (or regenerate) a single-elimination bracket for the given division.

    Clears any existing matches and creates a new bracket from the division's
    competitors (ordered by their ``position`` field).  At least 2 competitors
    are required.  Bye slots are auto-completed immediately.

    The request body is optional; no configuration options are needed because
    all inputs are derived from the division's competitors.  Clients may omit
    the body entirely or send ``{}``.
    """
    division = db.session.get(Division, div_id)
    if not division:
        return error_response("NOT_FOUND", f"Division {div_id} not found.", status_code=404)

    # Delete any existing matches before (re-)generating the bracket
    Match.query.filter_by(division_id=div_id).delete()
    db.session.flush()

    competitors = Competitor.query.filter_by(division_id=div_id).order_by(Competitor.position).all()
    num_comp = len(competitors)
    if num_comp < 2:
        db.session.rollback()
        return error_response(
            "BAD_REQUEST",
            "At least 2 competitors are required to generate a bracket.",
            status_code=400,
        )

    # Calculate bracket size (next power of 2)
    next_power_of_2 = 2 ** math.ceil(math.log2(num_comp))
    num_first_round_matches = next_power_of_2 // 2

    # Distribute competitors into bracket slots in roster order
    match_pairings = [[None, None] for _ in range(num_first_round_matches)]
    for i, competitor in enumerate(competitors):
        slot = i // num_first_round_matches
        match_index = i % num_first_round_matches
        match_pairings[match_index][slot] = competitor

    # Create first-round matches
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
        if comp1 and not comp2:
            match.winner_id = comp1.id
            match.status = "Completed (Bye)"
        elif comp2 and not comp1:
            match.winner_id = comp2.id
            match.status = "Completed (Bye)"
        db.session.add(match)
        current_round_matches.append(match)

    db.session.flush()

    # Build subsequent rounds bottom-up to the Final
    matches_created = len(current_round_matches)
    while len(current_round_matches) > 1:
        next_round_matches = []
        for i in range(0, len(current_round_matches), 2):
            prev_match1 = current_round_matches[i]
            prev_match2 = current_round_matches[i + 1]
            r_name = _get_round_name(len(current_round_matches) // 2)
            new_match = Match(division_id=div_id, round_name=r_name)
            db.session.add(new_match)
            db.session.flush()
            prev_match1.next_match_id = new_match.id
            prev_match2.next_match_id = new_match.id
            if prev_match1.winner_id:
                new_match.competitor1_id = prev_match1.winner_id
            if prev_match2.winner_id:
                new_match.competitor2_id = prev_match2.winner_id
            next_round_matches.append(new_match)
            matches_created += 1
        current_round_matches = next_round_matches

    db.session.commit()
    return success_response(
        {
            "division_id": div_id,
            "competitors": num_comp,
            "matches_created": matches_created,
        },
        status_code=201,
    )


# --- /api/v1/competitors ---


@api_v1.route("/competitors", methods=["GET"])
@api_login_required
def api_list_competitors():
    division_id = request.args.get("division_id", type=int)
    query = Competitor.query
    if division_id is not None:
        query = query.filter_by(division_id=division_id)
    competitors = query.all()
    return success_response(
        [{"id": c.id, "name": c.name, "division_id": c.division_id, "position": c.position} for c in competitors]
    )


@api_v1.route("/competitors", methods=["POST"])
@api_login_required
def api_create_competitor():
    data = request.get_json()
    if not isinstance(data, dict):
        return error_response("BAD_REQUEST", "Request JSON body must be an object.", status_code=400)
    name = (data.get("name") or "").strip()
    if not name:
        return error_response("BAD_REQUEST", "Competitor name is required.", details={"field": "name"}, status_code=400)
    raw_division_id = data.get("division_id")
    if raw_division_id is None:
        return error_response("BAD_REQUEST", "division_id is required.", details={"field": "division_id"}, status_code=400)
    try:
        division_id = int(raw_division_id)
    except (TypeError, ValueError):
        return error_response("BAD_REQUEST", "division_id must be an integer.", details={"field": "division_id"}, status_code=400)
    division = db.session.get(Division, division_id)
    if not division:
        return error_response("NOT_FOUND", f"Division {division_id} not found.", status_code=404)
    raw_position = data.get("position")
    position = None
    if raw_position is not None:
        try:
            position = int(raw_position)
        except (TypeError, ValueError):
            return error_response("BAD_REQUEST", "position must be an integer.", details={"field": "position"}, status_code=400)
    new_competitor = Competitor(name=name, division_id=division_id, position=position)
    db.session.add(new_competitor)
    db.session.commit()
    return success_response(
        {
            "id": new_competitor.id,
            "name": new_competitor.name,
            "division_id": new_competitor.division_id,
            "position": new_competitor.position,
        },
        status_code=201,
    )


@api_v1.route("/competitors/<int:competitor_id>", methods=["GET"])
@api_login_required
def api_get_competitor(competitor_id):
    competitor = db.session.get(Competitor, competitor_id)
    if not competitor:
        return error_response("NOT_FOUND", f"Competitor {competitor_id} not found.", status_code=404)
    return success_response(
        {"id": competitor.id, "name": competitor.name, "division_id": competitor.division_id, "position": competitor.position}
    )


@api_v1.route("/competitors/<int:competitor_id>", methods=["PATCH"])
@api_login_required
def api_update_competitor(competitor_id):
    competitor = db.session.get(Competitor, competitor_id)
    if not competitor:
        return error_response("NOT_FOUND", f"Competitor {competitor_id} not found.", status_code=404)
    data = request.get_json()
    if not isinstance(data, dict):
        return error_response("BAD_REQUEST", "Request JSON body must be an object.", status_code=400)
    if "name" in data:
        new_name = (data.get("name") or "").strip()
        if not new_name:
            return error_response("BAD_REQUEST", "Competitor name is required.", details={"field": "name"}, status_code=400)
        competitor.name = new_name
    if "division_id" in data:
        new_division_id = data.get("division_id")
        if new_division_id is None:
            return error_response("BAD_REQUEST", "division_id must be a valid integer.", details={"field": "division_id"}, status_code=400)
        try:
            new_division_id = int(new_division_id)
        except (TypeError, ValueError):
            return error_response("BAD_REQUEST", "division_id must be an integer.", details={"field": "division_id"}, status_code=400)
        division = db.session.get(Division, new_division_id)
        if not division:
            return error_response("NOT_FOUND", f"Division {new_division_id} not found.", status_code=404)
        competitor.division_id = new_division_id
    if "position" in data:
        raw_position = data.get("position")
        if raw_position is not None:
            try:
                raw_position = int(raw_position)
            except (TypeError, ValueError):
                return error_response("BAD_REQUEST", "position must be an integer.", details={"field": "position"}, status_code=400)
        competitor.position = raw_position
    db.session.commit()
    return success_response(
        {"id": competitor.id, "name": competitor.name, "division_id": competitor.division_id, "position": competitor.position}
    )


@api_v1.route("/competitors/<int:competitor_id>", methods=["DELETE"])
@api_login_required
def api_delete_competitor(competitor_id):
    competitor = db.session.get(Competitor, competitor_id)
    if not competitor:
        return error_response("NOT_FOUND", f"Competitor {competitor_id} not found.", status_code=404)
    db.session.delete(competitor)
    db.session.commit()
    return success_response({"id": competitor_id, "deleted": True})


# --- /api/v1/matches ---


def _match_to_dict(m):
    """Serialize a Match instance to a dictionary."""
    return {
        "id": m.id,
        "division_id": m.division_id,
        "ring_id": m.ring_id,
        "competitor1_id": m.competitor1_id,
        "competitor2_id": m.competitor2_id,
        "winner_id": m.winner_id,
        "next_match_id": m.next_match_id,
        "match_number": m.match_number,
        "status": m.status,
        "round_name": m.round_name,
        "start_time": m.start_time.isoformat() if m.start_time else None,
        "end_time": m.end_time.isoformat() if m.end_time else None,
    }


@api_v1.route("/matches", methods=["GET"])
@api_login_required
def api_list_matches():
    division_id = request.args.get("division_id", type=int)
    query = Match.query
    if division_id is not None:
        query = query.filter_by(division_id=division_id)
    matches = query.all()
    return success_response([_match_to_dict(m) for m in matches])


@api_v1.route("/matches", methods=["POST"])
@api_login_required
def api_create_match():
    data = request.get_json()
    if not isinstance(data, dict):
        return error_response("BAD_REQUEST", "Request JSON body must be an object.", status_code=400)
    division_id = data.get("division_id")
    if division_id is None:
        return error_response("BAD_REQUEST", "division_id is required.", details={"field": "division_id"}, status_code=400)
    try:
        division_id = int(division_id)
    except (TypeError, ValueError):
        return error_response("BAD_REQUEST", "division_id must be an integer.", details={"field": "division_id"}, status_code=400)
    division = db.session.get(Division, division_id)
    if not division:
        return error_response("NOT_FOUND", f"Division {division_id} not found.", status_code=404)
    ring_id = data.get("ring_id")
    if ring_id is not None and not db.session.get(Ring, ring_id):
        return error_response("NOT_FOUND", f"Ring {ring_id} not found.", status_code=404)
    competitor1_id = data.get("competitor1_id")
    competitor1 = None
    if competitor1_id is not None:
        competitor1 = db.session.get(Competitor, competitor1_id)
        if not competitor1:
            return error_response("NOT_FOUND", f"Competitor {competitor1_id} not found.", status_code=404)
        if competitor1.division_id != division_id:
            return error_response(
                "BAD_REQUEST",
                f"Competitor {competitor1_id} does not belong to division {division_id}.",
                details={"field": "competitor1_id"},
                status_code=400,
            )
    competitor2_id = data.get("competitor2_id")
    competitor2 = None
    if competitor2_id is not None:
        competitor2 = db.session.get(Competitor, competitor2_id)
        if not competitor2:
            return error_response("NOT_FOUND", f"Competitor {competitor2_id} not found.", status_code=404)
        if competitor2.division_id != division_id:
            return error_response(
                "BAD_REQUEST",
                f"Competitor {competitor2_id} does not belong to division {division_id}.",
                details={"field": "competitor2_id"},
                status_code=400,
            )
    if competitor1_id is not None and competitor2_id is not None and competitor1_id == competitor2_id:
        return error_response(
            "BAD_REQUEST",
            "competitor1_id and competitor2_id must refer to different competitors.",
            details={"field": "competitor1_id"},
            status_code=400,
        )
    next_match_id = data.get("next_match_id")
    if next_match_id is not None and not db.session.get(Match, next_match_id):
        return error_response("NOT_FOUND", f"Match {next_match_id} not found.", status_code=404)
    round_name = (data.get("round_name") or "").strip() or None
    raw_match_number = data.get("match_number")
    match_number = None
    if raw_match_number is not None:
        try:
            match_number = int(raw_match_number)
        except (TypeError, ValueError):
            return error_response("BAD_REQUEST", "match_number must be an integer.", details={"field": "match_number"}, status_code=400)
    new_match = Match(
        division_id=division_id,
        ring_id=ring_id,
        competitor1_id=competitor1_id,
        competitor2_id=competitor2_id,
        next_match_id=next_match_id,
        round_name=round_name,
        match_number=match_number,
    )
    db.session.add(new_match)
    db.session.commit()
    return success_response(_match_to_dict(new_match), status_code=201)


@api_v1.route("/matches/<int:match_id>", methods=["GET"])
@api_login_required
def api_get_match(match_id):
    match = db.session.get(Match, match_id)
    if not match:
        return error_response("NOT_FOUND", f"Match {match_id} not found.", status_code=404)
    return success_response(_match_to_dict(match))


@api_v1.route("/matches/<int:match_id>", methods=["PATCH"])
@api_login_required
def api_update_match(match_id):
    match = db.session.get(Match, match_id)
    if not match:
        return error_response("NOT_FOUND", f"Match {match_id} not found.", status_code=404)
    data = request.get_json()
    if not isinstance(data, dict):
        return error_response("BAD_REQUEST", "Request JSON body must be an object.", status_code=400)
    if "ring_id" in data:
        ring_id = data.get("ring_id")
        if ring_id is not None and not db.session.get(Ring, ring_id):
            return error_response("NOT_FOUND", f"Ring {ring_id} not found.", status_code=404)
        match.ring_id = ring_id
    if "status" in data:
        new_status = data.get("status")
        valid_statuses = {"Pending", "In Progress", "Completed", "Disqualification", "Completed (Bye)"}
        if new_status not in valid_statuses:
            return error_response(
                "BAD_REQUEST",
                "Invalid status.",
                details={"field": "status", "valid_values": sorted(valid_statuses)},
                status_code=400,
            )
        terminal_statuses = {"Completed", "Disqualification", "Completed (Bye)"}
        if new_status in terminal_statuses:
            return error_response(
                "BAD_REQUEST",
                "Cannot set a terminal status via PATCH. Use the /matches/<id>/result endpoint to complete a match.",
                details={"field": "status", "allowed_statuses": sorted(valid_statuses - terminal_statuses)},
                status_code=400,
            )
        match.status = new_status
    if "round_name" in data:
        match.round_name = (data.get("round_name") or "").strip() or None
    if "match_number" in data:
        raw_match_number = data.get("match_number")
        if raw_match_number is not None:
            try:
                raw_match_number = int(raw_match_number)
            except (TypeError, ValueError):
                return error_response("BAD_REQUEST", "match_number must be an integer.", details={"field": "match_number"}, status_code=400)
        match.match_number = raw_match_number
    # Prepare new competitor IDs so we can validate before assigning
    new_competitor1_id = match.competitor1_id
    new_competitor2_id = match.competitor2_id
    if "competitor1_id" in data:
        competitor1_id = data.get("competitor1_id")
        if competitor1_id is not None:
            competitor1 = db.session.get(Competitor, competitor1_id)
            if not competitor1:
                return error_response("NOT_FOUND", f"Competitor {competitor1_id} not found.", status_code=404)
            if competitor1.division_id != match.division_id:
                return error_response(
                    "BAD_REQUEST",
                    f"Competitor {competitor1_id} does not belong to this match's division.",
                    details={"field": "competitor1_id"},
                    status_code=400,
                )
        new_competitor1_id = competitor1_id
    if "competitor2_id" in data:
        competitor2_id = data.get("competitor2_id")
        if competitor2_id is not None:
            competitor2 = db.session.get(Competitor, competitor2_id)
            if not competitor2:
                return error_response("NOT_FOUND", f"Competitor {competitor2_id} not found.", status_code=404)
            if competitor2.division_id != match.division_id:
                return error_response(
                    "BAD_REQUEST",
                    f"Competitor {competitor2_id} does not belong to this match's division.",
                    details={"field": "competitor2_id"},
                    status_code=400,
                )
        new_competitor2_id = competitor2_id
    # Ensure the two competitors are not the same when both are set
    if new_competitor1_id is not None and new_competitor2_id is not None:
        if new_competitor1_id == new_competitor2_id:
            return error_response(
                "BAD_REQUEST",
                "competitor1_id and competitor2_id must refer to different competitors.",
                details={"field": "competitor1_id"},
                status_code=400,
            )
    match.competitor1_id = new_competitor1_id
    match.competitor2_id = new_competitor2_id
    db.session.commit()
    return success_response(_match_to_dict(match))


@api_v1.route("/matches/<int:match_id>/result", methods=["POST"])
@api_login_required
def api_record_result(match_id):
    match = db.session.get(Match, match_id)
    if not match:
        return error_response("NOT_FOUND", f"Match {match_id} not found.", status_code=404)

    data = request.get_json()
    if not isinstance(data, dict):
        return error_response("BAD_REQUEST", "Request JSON body must be an object.", status_code=400)
    status = data.get("status")
    winner_id = data.get("winner_id")

    valid_statuses = {"Completed", "Disqualification"}
    if status not in valid_statuses:
        return error_response(
            "BAD_REQUEST",
            "Invalid status.",
            details={"field": "status", "valid_values": sorted(valid_statuses)},
            status_code=400,
        )
    if not winner_id:
        return error_response("BAD_REQUEST", "winner_id is required.", details={"field": "winner_id"}, status_code=400)

    valid_competitors = {match.competitor1_id, match.competitor2_id} - {None}
    if winner_id not in valid_competitors:
        return error_response(
            "BAD_REQUEST",
            "winner_id must be a participant in this match.",
            details={"field": "winner_id", "valid_winner_ids": sorted(valid_competitors)},
            status_code=400,
        )

    match.status = status
    match.winner_id = winner_id

    if match.next_match_id:
        next_match = db.session.get(Match, match.next_match_id)
        if not next_match.competitor1_id:
            next_match.competitor1_id = winner_id
        elif not next_match.competitor2_id:
            next_match.competitor2_id = winner_id

    db.session.commit()
    return success_response({"match_id": match_id, "status": match.status, "winner_id": match.winner_id})
