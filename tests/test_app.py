"""Tests for every endpoint in the TKD Competition Manager Flask app."""

import pytest

from app import Competitor, Division, Match, Ring, db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_ring(client, name="Ring 1"):
    return client.post("/rings", json={"name": name})


def _create_division(client, name="Male - Black Belt - Under 70kg"):
    return client.post("/divisions", json={"name": name})


def _add_competitors(client, div_id, names):
    """Add competitors via the UI endpoint (newline-separated)."""
    return client.post(
        f"/ui/divisions/{div_id}/competitors",
        data={"names": "\n".join(names)},
    )


def _generate_bracket(client, div_id):
    return client.post(f"/divisions/{div_id}/generate_bracket")


def _get_first_match(div_id):
    return Match.query.filter_by(division_id=div_id).first()


# ---------------------------------------------------------------------------
# Ring API endpoints
# ---------------------------------------------------------------------------


class TestRingAPI:
    def test_get_rings_empty(self, client):
        resp = client.get("/rings")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_ring(self, client):
        resp = _create_ring(client, "Ring 1")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["message"] == "Ring created"
        assert "id" in data

    def test_get_rings_after_create(self, client):
        _create_ring(client, "Ring A")
        resp = client.get("/rings")
        assert resp.status_code == 200
        rings = resp.get_json()
        assert len(rings) == 1
        assert rings[0]["name"] == "Ring A"

    def test_create_multiple_rings(self, client):
        _create_ring(client, "Ring 1")
        _create_ring(client, "Ring 2")
        resp = client.get("/rings")
        assert len(resp.get_json()) == 2


# ---------------------------------------------------------------------------
# Division API endpoints
# ---------------------------------------------------------------------------


class TestDivisionAPI:
    def test_get_divisions_empty(self, client):
        resp = client.get("/divisions")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_division(self, client):
        resp = _create_division(client, "Female - White Belt")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["message"] == "Division created"
        assert "id" in data

    def test_get_divisions_after_create(self, client):
        _create_division(client, "Div A")
        resp = client.get("/divisions")
        divisions = resp.get_json()
        assert len(divisions) == 1
        assert divisions[0]["name"] == "Div A"

    def test_delete_division(self, client):
        resp = _create_division(client, "To Delete")
        div_id = resp.get_json()["id"]

        del_resp = client.delete(f"/divisions/{div_id}")
        assert del_resp.status_code == 200
        assert del_resp.get_json()["message"] == "Division deleted"

        resp = client.get("/divisions")
        assert resp.get_json() == []

    def test_delete_division_not_found(self, client):
        resp = client.delete("/divisions/9999")
        assert resp.status_code == 404

    def test_update_division(self, client):
        resp = _create_division(client, "Old Name")
        div_id = resp.get_json()["id"]

        put_resp = client.put(f"/divisions/{div_id}", json={"name": "New Name"})
        assert put_resp.status_code == 200
        assert put_resp.get_json()["message"] == "Division updated"

        resp = client.get("/divisions")
        assert resp.get_json()[0]["name"] == "New Name"

    def test_update_division_not_found(self, client):
        resp = client.put("/divisions/9999", json={"name": "X"})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Bracket generation & retrieval
# ---------------------------------------------------------------------------


class TestBracketAPI:
    def test_generate_bracket_too_few_competitors(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice"])
        resp = _generate_bracket(client, div_id)
        assert resp.status_code == 400

    def test_generate_bracket_two_competitors(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        resp = _generate_bracket(client, div_id)
        assert resp.status_code == 200
        assert b"Success" in resp.data

    def test_generate_bracket_four_competitors(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["A", "B", "C", "D"])
        resp = _generate_bracket(client, div_id)
        assert resp.status_code == 200

    def test_generate_bracket_three_competitors_creates_bye(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["A", "B", "C"])
        resp = _generate_bracket(client, div_id)
        assert resp.status_code == 200
        # 3 competitors → bracket of 4 → one bye match
        bye_matches = Match.query.filter_by(division_id=div_id, status="Completed (Bye)").all()
        assert len(bye_matches) >= 1

    def test_get_bracket_no_bracket(self, client):
        div_id = _create_division(client).get_json()["id"]
        resp = client.get(f"/divisions/{div_id}/bracket")
        assert resp.status_code == 404

    def test_get_bracket_returns_matches(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        resp = client.get(f"/divisions/{div_id}/bracket")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) > 0
        match = data[0]
        assert "match_id" in match
        assert "round_name" in match
        assert "status" in match


# ---------------------------------------------------------------------------
# Match result recording
# ---------------------------------------------------------------------------


class TestMatchResultAPI:
    def test_record_result_completed(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id, round_name="Round 1").first()
        winner_id = match.competitor1_id

        resp = client.post(
            f"/matches/{match.id}/result",
            json={"status": "Completed", "winner_id": winner_id},
        )
        assert resp.status_code == 200
        assert "Result recorded" in resp.get_json()["message"]

    def test_record_result_missing_winner(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id, round_name="Round 1").first()
        resp = client.post(f"/matches/{match.id}/result", json={"status": "Completed"})
        assert resp.status_code == 400

    def test_record_result_disqualification(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id, round_name="Round 1").first()
        winner_id = match.competitor2_id

        resp = client.post(
            f"/matches/{match.id}/result",
            json={"status": "Disqualification", "winner_id": winner_id},
        )
        assert resp.status_code == 200

    def test_record_result_match_not_found(self, client):
        resp = client.post(f"/matches/9999/result", json={"status": "Completed", "winner_id": 1})
        assert resp.status_code == 404

    def test_bracket_advancement_after_result(self, client):
        """Winner should be placed into the next match after recording result.

        Uses 4 competitors so Round 1 produces two matches each with a next_match_id
        pointing to the Semi-Final/Final match. Verifies that the winning competitor
        appears as competitor1 or competitor2 of that next match.
        """
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["A", "B", "C", "D"])
        _generate_bracket(client, div_id)

        r1_matches = Match.query.filter_by(division_id=div_id, round_name="Round 1").all()
        match = r1_matches[0]
        winner_id = match.competitor1_id

        client.post(
            f"/matches/{match.id}/result",
            json={"status": "Completed", "winner_id": winner_id},
        )

        # The winner should appear in the next match
        db.session.expire_all()
        next_match = Match.query.get(match.next_match_id)
        assert next_match.competitor1_id == winner_id or next_match.competitor2_id == winner_id


# ---------------------------------------------------------------------------
# HTMX UI – Ring routes
# ---------------------------------------------------------------------------


class TestUIRings:
    def test_ui_add_ring(self, client):
        resp = client.post("/ui/rings", data={"name": "Ring 1"})
        assert resp.status_code == 200
        assert b"Ring 1" in resp.data

    def test_ui_rings_list_empty(self, client):
        resp = client.get("/ui/rings_list")
        assert resp.status_code == 200

    def test_ui_rings_list_with_rings(self, client):
        _create_ring(client, "Ring X")
        resp = client.get("/ui/rings_list")
        assert resp.status_code == 200
        assert b"Ring X" in resp.data

    def test_ui_delete_ring(self, client):
        ring = Ring(name="Temp Ring")
        db.session.add(ring)
        db.session.commit()

        resp = client.delete(f"/ui/rings/{ring.id}")
        assert resp.status_code == 200
        assert resp.data == b""
        assert Ring.query.get(ring.id) is None

    def test_ui_delete_ring_not_found(self, client):
        resp = client.delete("/ui/rings/9999")
        assert resp.status_code == 404

    def test_ui_public_rings_empty(self, client):
        resp = client.get("/ui/public_rings")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# HTMX UI – Division routes
# ---------------------------------------------------------------------------


class TestUIDivisions:
    def test_ui_add_division(self, client):
        resp = client.post("/ui/divisions", data={"name": "Junior Boys"})
        assert resp.status_code == 200
        assert b"Junior Boys" in resp.data

    def test_ui_divisions_list_empty(self, client):
        resp = client.get("/ui/divisions_list")
        assert resp.status_code == 200

    def test_ui_divisions_list_with_division(self, client):
        _create_division(client, "Senior Women")
        resp = client.get("/ui/divisions_list")
        assert resp.status_code == 200
        assert b"Senior Women" in resp.data

    def test_ui_delete_division(self, client):
        div = Division(name="To Remove")
        db.session.add(div)
        db.session.commit()

        resp = client.delete(f"/ui/divisions/{div.id}")
        assert resp.status_code == 200
        assert resp.data == b""
        assert Division.query.get(div.id) is None

    def test_ui_delete_division_not_found(self, client):
        resp = client.delete("/ui/divisions/9999")
        assert resp.status_code == 404

    def test_ui_delete_division_cascades(self, client):
        """Deleting a division should also remove its competitors and matches.

        The cascade is implemented explicitly in the ui_delete_division route via
        Match.query.filter_by().delete() and Competitor.query.filter_by().delete()
        before deleting the division record itself.
        """
        div_id = _create_division(client, "Cascade Div").get_json()["id"]
        _add_competitors(client, div_id, ["A", "B"])
        _generate_bracket(client, div_id)

        client.delete(f"/ui/divisions/{div_id}")

        assert Competitor.query.filter_by(division_id=div_id).count() == 0
        assert Match.query.filter_by(division_id=div_id).count() == 0


# ---------------------------------------------------------------------------
# HTMX UI – Competitor routes
# ---------------------------------------------------------------------------


class TestUICompetitors:
    def test_ui_add_competitors(self, client):
        div_id = _create_division(client).get_json()["id"]
        resp = _add_competitors(client, div_id, ["Alice", "Bob"])
        assert resp.status_code == 200
        assert b"Alice" in resp.data
        assert b"Bob" in resp.data

    def test_ui_add_competitors_empty_input(self, client):
        div_id = _create_division(client).get_json()["id"]
        resp = client.post(f"/ui/divisions/{div_id}/competitors", data={"names": ""})
        assert resp.status_code == 200

    def test_ui_competitors_list_empty(self, client):
        div_id = _create_division(client).get_json()["id"]
        resp = client.get(f"/ui/divisions/{div_id}/competitors_list")
        assert resp.status_code == 200
        assert b"No competitors" in resp.data

    def test_ui_competitors_list_with_competitors(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Charlie", "Dana"])
        resp = client.get(f"/ui/divisions/{div_id}/competitors_list")
        assert resp.status_code == 200
        assert b"Charlie" in resp.data
        assert b"Dana" in resp.data


# ---------------------------------------------------------------------------
# HTMX UI – Match result recording
# ---------------------------------------------------------------------------


class TestUIMatchResult:
    def test_ui_record_result_in_progress(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id, round_name="Round 1").first()
        resp = client.post(
            f"/ui/matches/{match.id}/result",
            data={"status": "In Progress"},
        )
        assert resp.status_code == 200
        assert b"Started" in resp.data

    def test_ui_record_result_completed(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id, round_name="Round 1").first()
        winner_id = match.competitor1_id

        resp = client.post(
            f"/ui/matches/{match.id}/result",
            data={"status": "Completed", "winner_id": str(winner_id)},
        )
        assert resp.status_code == 200
        assert b"Complete" in resp.data

    def test_ui_record_result_missing_winner(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id, round_name="Round 1").first()
        resp = client.post(
            f"/ui/matches/{match.id}/result",
            data={"status": "Completed"},
        )
        assert resp.status_code == 400

    def test_ui_record_result_disqualification(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id, round_name="Round 1").first()
        winner_id = match.competitor2_id

        resp = client.post(
            f"/ui/matches/{match.id}/result",
            data={"status": "Disqualification", "winner_id": str(winner_id)},
        )
        assert resp.status_code == 200

    def test_ui_record_result_match_not_found(self, client):
        resp = client.post(
            "/ui/matches/9999/result",
            data={"status": "Completed", "winner_id": "1"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Match scheduling (HTMX)
# ---------------------------------------------------------------------------


class TestMatchSchedule:
    def test_schedule_match(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id).first()
        resp = client.put(
            f"/matches/{match.id}/schedule",
            data={"ring_id": str(ring_id), "ring_sequence": "25"},
        )
        assert resp.status_code == 200
        assert b"match-card" in resp.data

    def test_schedule_match_not_found(self, client):
        resp = client.put(
            "/matches/9999/schedule",
            data={"ring_id": "1", "ring_sequence": "1"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Page / full-HTML routes
# ---------------------------------------------------------------------------


class TestPageRoutes:
    def test_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_admin(self, client):
        resp = client.get("/admin")
        assert resp.status_code == 200

    def test_admin_division_setup(self, client):
        div_id = _create_division(client).get_json()["id"]
        resp = client.get(f"/admin/divisions/{div_id}/setup")
        assert resp.status_code == 200

    def test_admin_division_setup_not_found(self, client):
        resp = client.get("/admin/divisions/9999/setup")
        assert resp.status_code == 404

    def test_ui_bracket_view(self, client):
        div_id = _create_division(client).get_json()["id"]
        resp = client.get(f"/ui/divisions/{div_id}/bracket")
        assert resp.status_code == 200

    def test_bracket_ui_no_bracket(self, client):
        div_id = _create_division(client).get_json()["id"]
        resp = client.get(f"/divisions/{div_id}/bracket_ui")
        assert resp.status_code == 404

    def test_bracket_ui_with_bracket(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        resp = client.get(f"/divisions/{div_id}/bracket_ui")
        assert resp.status_code == 200

    def test_bracket_manage_page(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        resp = client.get(f"/admin/divisions/{div_id}/bracket_manage")
        assert resp.status_code == 200

    def test_bracket_manage_not_found(self, client):
        resp = client.get("/admin/divisions/9999/bracket_manage")
        assert resp.status_code == 404

    def test_ring_scorekeeper(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        resp = client.get(f"/ring/{ring_id}/scorekeeper")
        assert resp.status_code == 200

    def test_ring_scorekeeper_not_found(self, client):
        resp = client.get("/ring/9999/scorekeeper")
        assert resp.status_code == 404
