import math
import random
from collections import defaultdict

from flask import Flask, jsonify, render_template, render_template_string, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tournament.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class Ring(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # e.g., 'Ring 1'
    matches = db.relationship("Match", backref="ring", lazy=True)


class Division(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # e.g., 'Male - Black Belt - Under 70kg'
    competitors = db.relationship("Competitor", backref="division", lazy=True)
    matches = db.relationship("Match", backref="division", lazy=True)


class Competitor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    division_id = db.Column(db.Integer, db.ForeignKey("division.id"), nullable=False)


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

    # Relationships
    competitor1 = db.relationship("Competitor", foreign_keys=[competitor1_id])
    competitor2 = db.relationship("Competitor", foreign_keys=[competitor2_id])
    winner = db.relationship("Competitor", foreign_keys=[winner_id])


# --- RING MANAGEMENT ---
@app.route("/rings", methods=["POST", "GET"])
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
def manage_divisions():
    if request.method == "POST":
        data = request.json
        new_division = Division(name=data["name"])
        db.session.add(new_division)
        db.session.commit()
        return jsonify({"message": "Division created", "id": new_division.id}), 201

    divisions = Division.query.all()
    return jsonify([{"id": d.id, "name": d.name} for d in divisions])


@app.route("/divisions/<int:div_id>", methods=["DELETE", "PUT"])
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
            next_match = Match.query.get(match.next_match_id)
            # Assign the winner to the next match's open slot
            if not next_match.competitor1_id:
                next_match.competitor1_id = winner_id
            elif not next_match.competitor2_id:
                next_match.competitor2_id = winner_id

        db.session.commit()
        return jsonify({"message": "Result recorded and bracket updated."})


@app.route("/divisions/<int:div_id>/generate_bracket", methods=["POST"])
def generate_bracket(div_id):
    # division = Division.query.get_or_404(div_id)
    competitors = Competitor.query.filter_by(division_id=div_id).all()

    num_comp = len(competitors)
    if num_comp < 2:
        return jsonify({"error": "Need at least 2 competitors to generate a bracket."}), 400

    # 1. Calculate bracket size (next power of 2) using log2
    # For N competitors, Next Power = 2^ceil(log2(N))
    next_power_of_2 = 2 ** math.ceil(math.log2(num_comp))
    num_first_round_matches = next_power_of_2 // 2

    # 2. Distribute competitors to avoid empty branches
    random.shuffle(competitors)
    match_pairings = [[None, None] for _ in range(num_first_round_matches)]

    # Deal competitors into the pairings like a deck of cards
    for i, competitor in enumerate(competitors):
        slot = i // num_first_round_matches  # 0 for first pass, 1 for second pass
        match_index = i % num_first_round_matches
        match_pairings[match_index][slot] = competitor

    # 3. Create Round 1 Matches
    current_round_matches = []
    for pair in match_pairings:
        comp1, comp2 = pair[0], pair[1]

        match = Match(
            division_id=div_id,
            competitor1_id=comp1.id if comp1 else None,
            competitor2_id=comp2.id if comp2 else None,
            round_name="Round 1",
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
    round_num = 2
    while len(current_round_matches) > 1:
        next_round_matches = []

        # Group the previous round's matches in pairs
        for i in range(0, len(current_round_matches), 2):
            prev_match1 = current_round_matches[i]
            prev_match2 = current_round_matches[i + 1]

            # Determine round naming
            if len(current_round_matches) == 2:
                r_name = "Final"
            elif len(current_round_matches) == 4:
                r_name = "Semi-Final"
            elif len(current_round_matches) == 8:
                r_name = "Quarter-Final"
            else:
                r_name = f"Round {round_num}"

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
        round_num += 1

    # Commit everything to the database
    db.session.commit()
    # Return a success message with a link to manage the bracket
    return f"""
    <div style="padding: 15px; background: #d1fae5; color: #065f46; border-radius: 4px;">
        <strong>Success!</strong> Bracket generated for {num_comp} competitors.
        <br><br>
        <a href="/admin/divisions/{div_id}/bracket_manage" style="display: inline-block; background: #059669; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; margin-top: 10px;">
            Manage & Schedule Bracket
        </a>
    </div>
    """


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
        comp = Competitor.query.get(comp_id)
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


# --- PAGE ROUTES ---
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/admin")
def admin_view():
    return render_template("admin.html")


@app.route("/ui/divisions/<int:div_id>/bracket", methods=["GET"])
def brack(div_id):
    return render_template("bracket_view.html", division=Division.query.get(div_id))


@app.route("/divisions/<int:div_id>/bracket_ui", methods=["GET"])
def get_bracket_ui(div_id):
    matches = Match.query.filter_by(division_id=div_id).all()

    if not matches:
        return "<p>No bracket generated yet.</p>", 404

    # Group matches by round name directly in Python
    grouped_matches = defaultdict(list)
    for match in matches:
        match.competitor1_name = Competitor.query.get(match.competitor1_id).name if match.competitor1_id else "TBD"
        match.competitor2_name = Competitor.query.get(match.competitor2_id).name if match.competitor2_id else "TBD"
        grouped_matches[match.round_name].append(match)

    # Optional: Sort the dictionary so "Round 1" comes before "Quarter-Final", etc.
    # For a real app, you might use a round_number integer to sort easily.

    return render_template("bracket_fragment.html", rounds=grouped_matches)


# --- HTMX FRAGMENT ROUTES ---


# 1. Public Live Rings View
@app.route("/ui/public_rings")
def ui_public_rings():
    rings = Ring.query.all()
    # Find active/upcoming matches for each ring
    ring_data = []
    for ring in rings:
        matches = Match.query.filter(Match.ring_id == ring.id, Match.status.in_(["Pending", "In Progress"])).all()
        for match in matches:
            match.comp_1 = (
                f"{match.competitor1.name.split()[0][0]}. {match.competitor1.name.split()[-1]}" if match.competitor1 else "TBD"
            )
            match.comp_2 = (
                f"{match.competitor2.name.split()[0][0]}. {match.competitor2.name.split()[-1]}" if match.competitor2 else "TBD"
            )

        ring_data.append({"name": ring.name, "matches": matches})

    html = """
    {% for ring in rings %}
    <div class="ring-card">
        <h2>{{ ring.name }}</h2>
        {% if not ring.matches %}
            <p style="color: #94a3b8;">No upcoming matches.</p>
        {% else %}
            {% for match in ring.matches %}
            <strong>{{ match.match_number }}</strong> - <a href="/ui/divisions/{{ match.division.id }}/bracket">{{ match.division.name }}</a> ({{ match.round_name }})
            <div class="match-item">
                <span><font style="color: #252ceb; font-weight: bold;">{{ match.comp_1 }}</font> vs <font style="color: #eb2525; font-weight: bold;">{{ match.comp_2 }}</font></span>
                <span class="{% if match.status == 'In Progress' %}status-in-progress{% else %}status-pending{% endif %}">
                    {{ match.status }}
                </span>
            </div>
            {% endfor %}
        {% endif %}
    </div>
    {% endfor %}
    """
    return render_template_string(html, rings=ring_data)


# --- RING ROUTES ---


@app.route("/ui/rings", methods=["POST"])
def ui_add_ring():
    name = request.form.get("name")
    new_ring = Ring(name=name)
    db.session.add(new_ring)
    db.session.commit()

    return f"""
    <li>
        <span>{new_ring.name}</span>
        <button class="danger-btn" 
                hx-delete="/ui/rings/{new_ring.id}" 
                hx-target="closest li" 
                hx-swap="outerHTML"
                hx-confirm="Are you sure you want to delete {new_ring.name}?">
            Delete
        </button>
    </li>
    """


@app.route("/ui/rings_list")
def ui_rings_list():
    rings = Ring.query.all()
    html = ""
    for r in rings:
        html += f"""
        <li>
            <span>{r.name}</span>
            <div>
                <a href="/ring/{r.id}/scorekeeper" class="button" style="text-decoration: none; display: inline-block;">
                    Score Keeper
                </a>
                <button class="danger-btn" 
                        hx-delete="/ui/rings/{r.id}" 
                        hx-target="closest li" 
                        hx-swap="outerHTML"
                        hx-confirm="Are you sure you want to delete {r.name}?">
                    Delete
                </button>
            </div>
        </li>
        """
    return html


@app.route("/ui/rings/<int:ring_id>", methods=["DELETE"])
def ui_delete_ring(ring_id):
    ring = Ring.query.get_or_404(ring_id)
    db.session.delete(ring)
    db.session.commit()
    # Return an empty string. HTMX will swap the <li> with this empty string, effectively removing it.
    return ""


# --- DIVISION ROUTES ---


@app.route("/ui/divisions", methods=["POST"])
def ui_add_division():
    name = request.form.get("name")
    new_div = Division(name=name)
    db.session.add(new_div)
    db.session.commit()

    return f"""
    <li>
        <span>{new_div.name}</span>
        <div>
            <a href="/admin/divisions/{new_div.id}/setup" class="button" style="text-decoration: none; display: inline-block;">
                Manage
            </a>
            <button class="danger-btn" 
                    hx-delete="/ui/divisions/{new_div.id}" 
                    hx-target="closest li" 
                    hx-swap="outerHTML"
                    hx-confirm="Delete division {new_div.name} and all its matches?">
                Delete
            </button>
        </div>
    </li>
    """


@app.route("/ui/divisions_list")
def ui_divisions_list():
    divisions = Division.query.all()
    html = ""
    for d in divisions:
        html += f"""
        <li>
            <span>{d.name}</span>
            <div>
                <a href="/admin/divisions/{d.id}/setup" class="button" style="text-decoration: none; display: inline-block;">
                Manage
            </a>
                <button class="danger-btn" 
                        hx-delete="/ui/divisions/{d.id}" 
                        hx-target="closest li" 
                        hx-swap="outerHTML"
                        hx-confirm="Delete division {d.name} and all its matches?">
                    Delete
                </button>
            </div>
        </li>
        """
    return html


@app.route("/ui/divisions/<int:div_id>", methods=["DELETE"])
def ui_delete_division(div_id):
    div = Division.query.get_or_404(div_id)

    # Optional: Delete all associated matches and competitors first to maintain database integrity
    Match.query.filter_by(division_id=div_id).delete()
    Competitor.query.filter_by(division_id=div_id).delete()

    db.session.delete(div)
    db.session.commit()
    return ""


@app.route("/admin/divisions/<int:div_id>/setup")
def admin_division_setup(div_id):
    division = Division.query.get_or_404(div_id)
    return render_template("division_setup.html", division=division)


@app.route("/ui/divisions/<int:div_id>/competitors", methods=["POST"])
def ui_add_competitors(div_id):
    names_text = request.form.get("names")

    if names_text:
        # Split the text area by newlines and remove empty lines
        name_list = [name.strip() for name in names_text.split("\n") if name.strip()]

        for name in name_list:
            comp = Competitor(name=name, division_id=div_id)
            db.session.add(comp)

        db.session.commit()

    # Return the updated list of competitors
    competitors = Competitor.query.filter_by(division_id=div_id).all()
    return "".join([f"<li>{c.name}</li>" for c in competitors])


@app.route("/ui/divisions/<int:div_id>/competitors_list")
def ui_competitors_list(div_id):
    competitors = Competitor.query.filter_by(division_id=div_id).all()
    if not competitors:
        return "<li style='color: #94a3b8;'>No competitors added yet.</li>"
    return "".join([f"<li>{c.name}</li>" for c in competitors])


@app.route("/admin/divisions/<int:div_id>/bracket_manage")
def manage_bracket_page(div_id):
    division = Division.query.get_or_404(div_id)
    matches = Match.query.filter_by(division_id=div_id).all()
    rings = Ring.query.all()

    # Group matches by round
    grouped_matches = defaultdict(list)
    for match in matches:
        grouped_matches[match.round_name].append(match)

    return render_template("bracket_manage.html", division=division, rounds=grouped_matches, rings=rings)


@app.route("/matches/<int:match_id>/schedule", methods=["PUT"])
def schedule_match_htmx(match_id):
    match = Match.query.get_or_404(match_id)

    ring_id = request.form.get("ring_id")
    ring_sequence = request.form.get("ring_sequence")  # e.g., the '25' in 525

    if ring_id and ring_sequence:
        match.ring_id = int(ring_id)
        match.match_number = (int(ring_id) * 100) + int(ring_sequence)
        db.session.commit()

    # Fetch rings again to populate the dropdown in the response
    rings = Ring.query.all()
    ring_options = "".join(
        [f'<option value="{r.id}" {"selected" if r.id == match.ring_id else ""}>{r.name}</option>' for r in rings]
    )

    # Return the updated match card HTML
    return f"""
    <div class="match-card" id="match-{match.id}">
        <div class="match-body">
            <div><font style="color: #252ceb; font-weight: bold;">Chung</font>: {match.competitor1.name if match.competitor1 else "TBD"}</div>
            <div><font style="color: #eb2525; font-weight: bold;">Hong</font>: {match.competitor2.name if match.competitor2 else "TBD"}</div>
        </div>
        
        <div class="schedule-form">
            <div style="margin-bottom: 8px; font-weight: bold; color: #2563eb;">
                Scheduled: {"Match " + str(match.match_number) if match.match_number else "Unassigned"}
            </div>
            <form hx-put="/matches/{{ match.id }}/schedule" hx-target="#match-{{ match.id }}"
                        hx-swap="outerHTML" style="display: flex; gap: 5px;">
                <select name="ring_id" required style="flex: 1;">
                    <option value="">Select Ring...</option>
                    {ring_options}
                </select>
                <input type="number" name="ring_sequence" value="{int(ring_sequence)}" required
                    style="width: 80px;">
                <button type="submit" class="save-btn">Save</button>
            </form>
        </div>
    </div>
    """


# --- SCOREKEEPER ROUTES ---
@app.route("/ring/<int:ring_id>/scorekeeper")
def ring_scorekeeper(ring_id):
    ring = Ring.query.get_or_404(ring_id)

    # Get all pending or in-progress matches for this ring, ordered by match number
    # We only want matches where both competitors are known (no TBDs)
    matches = (
        Match.query.filter(
            Match.ring_id == ring.id,
            Match.status.in_(["Pending", "In Progress"]),
            Match.competitor1_id.isnot(None),
            Match.competitor2_id.isnot(None),
        )
        .order_by(Match.match_number)
        .all()
    )

    return render_template("scorekeeper.html", ring=ring, matches=matches)


@app.route("/ui/matches/<int:match_id>/result", methods=["POST"])
def ui_record_result(match_id):
    match = Match.query.get_or_404(match_id)

    status = request.form.get("status")
    winner_id = request.form.get("winner_id")

    match.status = status

    if status == "In Progress":
        db.session.commit()
        return f"""
        <div style="padding: 15px; background: #fef08a; color: #854d0e; border-radius: 8px; margin-bottom: 15px;">
            Match {match.match_number} Started. Waiting for results.
            <button onclick="location.reload()" style="margin-left: 10px; padding: 5px;">Refresh</button>
        </div>
        """

    if status in ["Completed", "Disqualification"]:
        if not winner_id:
            return "<div style='color: red;'>Error: Winner must be selected.</div>", 400

        match.winner_id = int(winner_id)

        # --- BRACKET ADVANCEMENT LOGIC ---
        if match.next_match_id:
            next_match = Match.query.get(match.next_match_id)
            # Push the winner into the next match's open slot
            if not next_match.competitor1_id:
                next_match.competitor1_id = match.winner_id
            elif not next_match.competitor2_id:
                next_match.competitor2_id = match.winner_id

        db.session.commit()

        winner = Competitor.query.get(match.winner_id)

        # Return a success message that replaces the match card
        return f"""
        <div style="padding: 20px; background: #d1fae5; color: #065f46; border-radius: 8px; margin-bottom: 15px; border: 1px solid #34d399;">
            <h3 style="margin-top: 0;">Match {match.match_number} Complete</h3>
            <p><strong>{winner.name}</strong> advances to the next round!</p>
        </div>
        """


# Initialize DB for testing
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0")
