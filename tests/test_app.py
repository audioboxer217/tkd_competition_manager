"""Tests for every endpoint in the TKD Competition Manager Flask app."""

import re

import pytest

from app import Competitor, Division, Match, Ring, _abbrev_round, db

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_ring(client, name="Ring 1"):
    return client.post("/rings", json={"name": name})


def _create_division(client, name="Male - Black Belt - Under 70kg", event_type="kyorugi"):
    return client.post("/divisions", json={"name": name, "event_type": event_type})


def _add_competitors(client, div_id, names):
    """Add competitors via the UI endpoint (newline-separated)."""
    return client.post(
        f"/ui/divisions/{div_id}/competitors",
        data={"names": "\n".join(names)},
    )


def _generate_bracket(client, div_id):
    return client.post(f"/divisions/{div_id}/generate_bracket")


# ---------------------------------------------------------------------------
# _abbrev_round unit tests
# ---------------------------------------------------------------------------


class TestAbbrevRound:
    def test_final(self):
        assert _abbrev_round("Final") == "F"

    def test_semi_final(self):
        assert _abbrev_round("Semi-Final") == "SF"

    def test_quarter_final(self):
        assert _abbrev_round("Quarter-Final") == "QF"

    def test_round_1(self):
        assert _abbrev_round("Round of 16") == "R16"

    def test_round_2(self):
        assert _abbrev_round("Round of 32") == "R32"

    def test_unknown_passthrough(self):
        assert _abbrev_round("Mystery Round") == "Mystery Round"

    def test_none_passthrough(self):
        assert _abbrev_round(None) is None


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
    def test_generate_bracket_nonexistent_division(self, client):
        resp = _generate_bracket(client, 9999)
        assert resp.status_code == 404

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
        # 2 competitors → 1 match → named "Final"
        assert Match.query.filter_by(division_id=div_id, round_name="Final").count() == 1

    def test_generate_bracket_four_competitors(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["A", "B", "C", "D"])
        resp = _generate_bracket(client, div_id)
        assert resp.status_code == 200
        # 4 competitors → 2 Semi-Final matches + 1 Final
        assert Match.query.filter_by(division_id=div_id, round_name="Semi-Final").count() == 2
        assert Match.query.filter_by(division_id=div_id, round_name="Final").count() == 1

    def test_generate_bracket_eight_competitors_round_names(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["A", "B", "C", "D", "E", "F", "G", "H"])
        _generate_bracket(client, div_id)
        # 8 competitors → Quarter-Final (4), Semi-Final (2), Final (1)
        assert Match.query.filter_by(division_id=div_id, round_name="Quarter-Final").count() == 4
        assert Match.query.filter_by(division_id=div_id, round_name="Semi-Final").count() == 2
        assert Match.query.filter_by(division_id=div_id, round_name="Final").count() == 1

    def test_generate_bracket_sixteen_competitors_round_names(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, [str(i) for i in range(1, 17)])
        _generate_bracket(client, div_id)
        # 16 competitors → Round of 16 (8), Quarter-Final (4), Semi-Final (2), Final (1)
        assert Match.query.filter_by(division_id=div_id, round_name="Round of 16").count() == 8
        assert Match.query.filter_by(division_id=div_id, round_name="Quarter-Final").count() == 4
        assert Match.query.filter_by(division_id=div_id, round_name="Semi-Final").count() == 2
        assert Match.query.filter_by(division_id=div_id, round_name="Final").count() == 1

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

        match = Match.query.filter_by(division_id=div_id, round_name="Final").first()
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

        match = Match.query.filter_by(division_id=div_id, round_name="Final").first()
        resp = client.post(f"/matches/{match.id}/result", json={"status": "Completed"})
        assert resp.status_code == 400

    def test_record_result_disqualification(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id, round_name="Final").first()
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

        Uses 4 competitors so the Semi-Final produces two matches each with a next_match_id
        pointing to the Final match. Verifies that the winning competitor
        appears as competitor1 or competitor2 of that next match.
        """
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["A", "B", "C", "D"])
        _generate_bracket(client, div_id)

        r1_matches = Match.query.filter_by(division_id=div_id, round_name="Semi-Final").all()
        match = r1_matches[0]
        winner_id = match.competitor1_id

        client.post(
            f"/matches/{match.id}/result",
            json={"status": "Completed", "winner_id": winner_id},
        )

        # The winner should appear in the next match
        db.session.expire_all()
        next_match = db.session.get(Match, match.next_match_id)
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
        assert db.session.get(Ring, ring.id) is None

    def test_ui_delete_ring_not_found(self, client):
        resp = client.delete("/ui/rings/9999")
        assert resp.status_code == 404

    def test_ui_public_rings_empty(self, client):
        resp = client.get("/ui/public_rings")
        assert resp.status_code == 200

    def test_ui_public_rings_sort_order(self, client):
        """In Progress matches appear before Pending, then sorted by match_number."""
        ring = Ring(name="Ring 1")
        division = Division(name="Test Division", event_type="kyorugi")
        db.session.add_all([ring, division])
        db.session.flush()

        c1 = Competitor(name="Alice Smith", division_id=division.id)
        c2 = Competitor(name="Bob Jones", division_id=division.id)
        c3 = Competitor(name="Carol White", division_id=division.id)
        c4 = Competitor(name="Dave Brown", division_id=division.id)
        db.session.add_all([c1, c2, c3, c4])
        db.session.flush()

        # match_number 102 is Pending but lower number
        m1 = Match(ring_id=ring.id, division_id=division.id, competitor1_id=c1.id,
                   competitor2_id=c2.id, status="Pending", match_number=102, round_name="Round 1")
        # match_number 101 is In Progress — should appear first despite being created second
        m2 = Match(ring_id=ring.id, division_id=division.id, competitor1_id=c3.id,
                   competitor2_id=c4.id, status="In Progress", match_number=101, round_name="Round 1")
        # match_number 103 is Pending
        m3 = Match(ring_id=ring.id, division_id=division.id, competitor1_id=c1.id,
                   competitor2_id=c3.id, status="Pending", match_number=103, round_name="Semi-Final")
        db.session.add_all([m1, m2, m3])
        db.session.commit()

        resp = client.get("/ui/public_rings")
        assert resp.status_code == 200
        body = resp.data.decode()

        rendered_numbers = [int(n) for n in re.findall(r"<strong>(\d+)</strong>", body)]
        assert rendered_numbers == [101, 102, 103]

    def test_ui_public_rings_null_match_number_excluded(self, client):
        """Matches without a match_number are excluded from the Live View."""
        ring = Ring(name="Ring 1")
        division = Division(name="Test Division", event_type="kyorugi")
        db.session.add_all([ring, division])
        db.session.flush()

        c1 = Competitor(name="Alice Smith", division_id=division.id)
        c2 = Competitor(name="Bob Jones", division_id=division.id)
        db.session.add_all([c1, c2])
        db.session.flush()

        m_no_number = Match(
            ring_id=ring.id, division_id=division.id, competitor1_id=c1.id,
            competitor2_id=c2.id, status="Pending", match_number=None, round_name="Round 1"
        )
        db.session.add(m_no_number)
        db.session.commit()

        resp = client.get("/ui/public_rings")
        assert resp.status_code == 200
        assert b"Alice Smith" not in resp.data
        assert b"Bob Jones" not in resp.data

    def test_ui_public_rings_filters_by_event_type(self, client):
        ring = Ring(name="Ring 1")
        div_kyorugi = Division(name="Kyorugi Division", event_type="kyorugi")
        div_poomsae = Division(name="Poomsae Division", event_type="poomsae")
        db.session.add_all([ring, div_kyorugi, div_poomsae])
        db.session.flush()

        k1 = Competitor(name="Alice Smith", division_id=div_kyorugi.id)
        k2 = Competitor(name="Bob Jones", division_id=div_kyorugi.id)
        p1 = Competitor(name="Carol White", division_id=div_poomsae.id)
        p2 = Competitor(name="Dave Brown", division_id=div_poomsae.id)
        db.session.add_all([k1, k2, p1, p2])
        db.session.flush()

        k_match = Match(
            ring_id=ring.id,
            division_id=div_kyorugi.id,
            competitor1_id=k1.id,
            competitor2_id=k2.id,
            status="Pending",
            match_number=101,
            round_name="Round 1",
        )
        p_match = Match(
            ring_id=ring.id,
            division_id=div_poomsae.id,
            competitor1_id=p1.id,
            competitor2_id=p2.id,
            status="Pending",
            match_number=201,
            round_name="Round 1",
        )
        db.session.add_all([k_match, p_match])
        db.session.commit()

        resp_kyorugi = client.get("/ui/public_rings?event_type=kyorugi")
        assert resp_kyorugi.status_code == 200
        assert b"Kyorugi Division" in resp_kyorugi.data
        assert b"Poomsae Division" not in resp_kyorugi.data

        resp_poomsae = client.get("/ui/public_rings?event_type=poomsae")
        assert resp_poomsae.status_code == 200
        assert b"Poomsae Division" in resp_poomsae.data
        assert b"Kyorugi Division" not in resp_poomsae.data

    def test_ui_public_rings_invalid_event_type(self, client):
        resp = client.get("/ui/public_rings?event_type=unknown")
        assert resp.status_code == 400

    def test_ui_public_rings_shows_last_completed_match(self, client):
        """Most recently completed match appears at the top with W/L indicators."""
        ring = Ring(name="Ring 1")
        division = Division(name="Test Division", event_type="kyorugi")
        db.session.add_all([ring, division])
        db.session.flush()

        c1 = Competitor(name="Alice Smith", division_id=division.id)
        c2 = Competitor(name="Bob Jones", division_id=division.id)
        c3 = Competitor(name="Carol White", division_id=division.id)
        c4 = Competitor(name="Dave Brown", division_id=division.id)
        db.session.add_all([c1, c2, c3, c4])
        db.session.flush()

        # Completed match — Alice wins
        m_done = Match(
            ring_id=ring.id, division_id=division.id,
            competitor1_id=c1.id, competitor2_id=c2.id,
            status="Completed", winner_id=c1.id, match_number=100, round_name="Round 1"
        )
        # Upcoming pending match
        m_pending = Match(
            ring_id=ring.id, division_id=division.id,
            competitor1_id=c3.id, competitor2_id=c4.id,
            status="Pending", match_number=101, round_name="Round 1"
        )
        db.session.add_all([m_done, m_pending])
        db.session.commit()

        resp = client.get("/ui/public_rings")
        assert resp.status_code == 200
        body = resp.data.decode()

        # Completed match appears (with W/L indicators)
        assert "A. Smith" in body
        assert "B. Jones" in body
        assert "result-win" in body
        assert "result-loss" in body
        # Pending match also appears
        assert "C. White" in body
        assert "D. Brown" in body

        # Completed match block appears before the pending match block
        assert body.index("A. Smith") < body.index("C. White")

    def test_ui_public_rings_limit_four_matches(self, client):
        """Only up to 4 pending/in-progress matches are shown."""
        ring = Ring(name="Ring 1")
        division = Division(name="Test Division", event_type="kyorugi")
        db.session.add_all([ring, division])
        db.session.flush()

        competitors = [Competitor(name=f"Competitor {i}", division_id=division.id) for i in range(1, 11)]
        db.session.add_all(competitors)
        db.session.flush()

        # Create 5 pending matches — only 4 should appear
        for i in range(5):
            m = Match(
                ring_id=ring.id, division_id=division.id,
                competitor1_id=competitors[i * 2].id,
                competitor2_id=competitors[i * 2 + 1].id,
                status="Pending", match_number=200 + i, round_name="Round 1"
            )
            db.session.add(m)
        db.session.commit()

        resp = client.get("/ui/public_rings")
        assert resp.status_code == 200
        body = resp.data.decode()

        rendered_numbers = [int(n) for n in re.findall(r"<strong>(\d+)</strong>", body)]
        assert len(rendered_numbers) == 4
        assert rendered_numbers == [200, 201, 202, 203]

    def test_ui_public_rings_most_recent_completed_by_match_number(self, client):
        """When multiple completed matches exist, the one with the highest match_number is shown."""
        ring = Ring(name="Ring 1")
        division = Division(name="Test Division", event_type="kyorugi")
        db.session.add_all([ring, division])
        db.session.flush()

        c1 = Competitor(name="Alice Smith", division_id=division.id)
        c2 = Competitor(name="Bob Jones", division_id=division.id)
        c3 = Competitor(name="Carol White", division_id=division.id)
        c4 = Competitor(name="Dave Brown", division_id=division.id)
        db.session.add_all([c1, c2, c3, c4])
        db.session.flush()

        m_older = Match(
            ring_id=ring.id, division_id=division.id,
            competitor1_id=c1.id, competitor2_id=c2.id,
            status="Completed", winner_id=c1.id, match_number=100, round_name="Round 1"
        )
        m_newer = Match(
            ring_id=ring.id, division_id=division.id,
            competitor1_id=c3.id, competitor2_id=c4.id,
            status="Completed", winner_id=c3.id, match_number=101, round_name="Semi-Final"
        )
        db.session.add_all([m_older, m_newer])
        db.session.commit()

        resp = client.get("/ui/public_rings")
        assert resp.status_code == 200
        body = resp.data.decode()

        # Only the most recent completed match (101) should be shown
        assert "C. White" in body
        assert "D. Brown" in body
        assert "A. Smith" not in body
        assert "B. Jones" not in body

    def test_ui_public_rings_round_name_abbreviated(self, client):
        """Round names are shown as short codes: R16, QF, SF, F."""
        ring = Ring(name="Ring 1")
        division = Division(name="Test Division", event_type="kyorugi")
        db.session.add_all([ring, division])
        db.session.flush()

        comps = [Competitor(name=f"Fighter {i}", division_id=division.id) for i in range(1, 9)]
        db.session.add_all(comps)
        db.session.flush()

        rounds = [
            ("Round of 16", comps[0], comps[1], 200),
            ("Quarter-Final", comps[2], comps[3], 201),
            ("Semi-Final", comps[4], comps[5], 202),
            ("Final", comps[6], comps[7], 203),
        ]
        for rname, c1, c2, mnum in rounds:
            db.session.add(Match(
                ring_id=ring.id, division_id=division.id,
                competitor1_id=c1.id, competitor2_id=c2.id,
                status="Pending", match_number=mnum, round_name=rname,
            ))
        db.session.commit()

        resp = client.get("/ui/public_rings")
        assert resp.status_code == 200
        body = resp.data.decode()

        assert "(R16)" in body
        assert "(QF)" in body
        assert "(SF)" in body
        assert "(F)" in body
        assert "Round of 16" not in body
        assert "Quarter-Final" not in body
        assert "Semi-Final" not in body
        assert "Final" not in body


# ---------------------------------------------------------------------------
# HTMX UI – Division routes
# ---------------------------------------------------------------------------


class TestUIDivisions:
    def test_ui_add_division(self, client):
        resp = client.post("/ui/divisions", data={"name": "Junior Boys", "event_type": "kyorugi"})
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
        div = Division(name="To Remove", event_type="kyorugi")
        db.session.add(div)
        db.session.commit()

        resp = client.delete(f"/ui/divisions/{div.id}")
        assert resp.status_code == 200
        assert resp.data == b""
        assert db.session.get(Division, div.id) is None

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

    def test_ui_delete_competitor(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        comp = Competitor.query.filter_by(division_id=div_id, name="Alice").first()

        resp = client.delete(f"/ui/divisions/{div_id}/competitors/{comp.id}")
        assert resp.status_code == 200
        assert b"Alice" not in resp.data
        assert b"Bob" in resp.data
        assert db.session.get(Competitor, comp.id) is None

    def test_ui_delete_competitor_clears_bracket(self, client):
        """Deleting a competitor must also clear all bracket matches for the division."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol"])
        _generate_bracket(client, div_id)
        assert Match.query.filter_by(division_id=div_id).count() > 0

        comp = Competitor.query.filter_by(division_id=div_id, name="Carol").first()
        resp = client.delete(f"/ui/divisions/{div_id}/competitors/{comp.id}")
        assert resp.status_code == 200
        # All matches for this division must be gone; bracket must be regenerated
        assert Match.query.filter_by(division_id=div_id).count() == 0

    def test_ui_delete_competitor_not_found(self, client):
        div_id = _create_division(client).get_json()["id"]
        resp = client.delete(f"/ui/divisions/{div_id}/competitors/9999")
        assert resp.status_code == 404

    def test_ui_delete_competitor_wrong_division(self, client):
        div1_id = _create_division(client, "Div 1").get_json()["id"]
        div2_id = _create_division(client, "Div 2").get_json()["id"]
        _add_competitors(client, div1_id, ["Alice"])
        comp = Competitor.query.filter_by(division_id=div1_id).first()

        resp = client.delete(f"/ui/divisions/{div2_id}/competitors/{comp.id}")
        assert resp.status_code == 404

    def test_ui_move_competitor_down(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["First", "Second", "Third"])
        comp = Competitor.query.filter_by(division_id=div_id, name="First").first()

        resp = client.post(
            f"/ui/divisions/{div_id}/competitors/{comp.id}/move",
            data={"direction": "down"},
        )
        assert resp.status_code == 200

        # First should now appear after Second
        body = resp.data.decode()
        assert body.index("First") > body.index("Second")

    def test_ui_move_competitor_up(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["First", "Second", "Third"])
        comp = Competitor.query.filter_by(division_id=div_id, name="Third").first()

        resp = client.post(
            f"/ui/divisions/{div_id}/competitors/{comp.id}/move",
            data={"direction": "up"},
        )
        assert resp.status_code == 200

        # Third should now appear before Second
        body = resp.data.decode()
        assert body.index("Third") < body.index("Second")

    def test_ui_move_competitor_at_top_noop(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["First", "Second"])
        comp = Competitor.query.filter_by(division_id=div_id, name="First").first()
        original_position = comp.position

        client.post(
            f"/ui/divisions/{div_id}/competitors/{comp.id}/move",
            data={"direction": "up"},
        )

        db.session.refresh(comp)
        assert comp.position == original_position

    def test_ui_move_competitor_at_bottom_noop(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["First", "Second"])
        comp = Competitor.query.filter_by(division_id=div_id, name="Second").first()
        original_position = comp.position

        client.post(
            f"/ui/divisions/{div_id}/competitors/{comp.id}/move",
            data={"direction": "down"},
        )

        db.session.refresh(comp)
        assert comp.position == original_position

    def test_ui_move_competitor_not_found(self, client):
        div_id = _create_division(client).get_json()["id"]
        resp = client.post(
            f"/ui/divisions/{div_id}/competitors/9999/move",
            data={"direction": "up"},
        )
        assert resp.status_code == 404

    def test_ui_competitors_ordered_by_position(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alpha", "Beta", "Gamma"])

        resp = client.get(f"/ui/divisions/{div_id}/competitors_list")
        body = resp.data.decode()
        assert body.index("Alpha") < body.index("Beta") < body.index("Gamma")

    def test_ui_add_competitors_appends_with_position(self, client):
        """Adding competitors in two batches keeps them in insertion order."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _add_competitors(client, div_id, ["Carol"])

        resp = client.get(f"/ui/divisions/{div_id}/competitors_list")
        body = resp.data.decode()
        assert body.index("Alice") < body.index("Bob") < body.index("Carol")


# ---------------------------------------------------------------------------
# HTMX UI – Division rename routes
# ---------------------------------------------------------------------------


class TestUIDivisionRename:
    def test_ui_rename_division(self, client):
        div_id = _create_division(client, "Old Name").get_json()["id"]
        resp = client.patch(
            f"/ui/divisions/{div_id}/name",
            data={"name": "New Name"},
        )
        assert resp.status_code == 200
        assert b"New Name" in resp.data

        division = db.session.get(Division, div_id)
        assert division.name == "New Name"

    def test_ui_rename_division_empty_name_ignored(self, client):
        """Submitting an empty name leaves the division name unchanged."""
        div_id = _create_division(client, "Keep Me").get_json()["id"]
        client.patch(f"/ui/divisions/{div_id}/name", data={"name": "  "})

        division = db.session.get(Division, div_id)
        assert division.name == "Keep Me"

    def test_ui_rename_division_not_found(self, client):
        resp = client.patch("/ui/divisions/9999/name", data={"name": "X"})
        assert resp.status_code == 404

    def test_ui_division_name_form(self, client):
        div_id = _create_division(client, "My Division").get_json()["id"]
        resp = client.get(f"/ui/divisions/{div_id}/name_form")
        assert resp.status_code == 200
        assert b"My Division" in resp.data
        assert b"form" in resp.data

    def test_ui_division_name_display(self, client):
        div_id = _create_division(client, "Display Test").get_json()["id"]
        resp = client.get(f"/ui/divisions/{div_id}/name_display")
        assert resp.status_code == 200
        assert b"Display Test" in resp.data


# ---------------------------------------------------------------------------
# Bracket regeneration
# ---------------------------------------------------------------------------


class TestBracketRegeneration:
    def test_regenerate_bracket_replaces_existing_matches(self, client):
        """Calling generate_bracket a second time deletes old matches and creates new ones."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        # Add a third competitor so the bracket structure changes
        _add_competitors(client, div_id, ["Carol"])
        match_count_before = Match.query.filter_by(division_id=div_id).count()

        resp = _generate_bracket(client, div_id)
        assert resp.status_code == 200
        assert b"Success" in resp.data

        # 3-competitor bracket has more matches than 2-competitor bracket
        match_count_after = Match.query.filter_by(division_id=div_id).count()
        assert match_count_after != match_count_before

    def test_regenerate_bracket_with_added_competitor(self, client):
        """After adding a competitor and regenerating, the new competitor appears in matches."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        _add_competitors(client, div_id, ["Carol"])
        resp = _generate_bracket(client, div_id)
        assert resp.status_code == 200

        all_matches = Match.query.filter_by(division_id=div_id).all()
        all_competitor_ids = {m.competitor1_id for m in all_matches} | {m.competitor2_id for m in all_matches}
        carol = Competitor.query.filter_by(division_id=div_id, name="Carol").first()
        assert carol.id in all_competitor_ids


# ---------------------------------------------------------------------------
# HTMX UI – Match result recording
# ---------------------------------------------------------------------------


class TestUIMatchResult:
    def test_ui_record_result_in_progress(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id, round_name="Final").first()
        resp = client.post(
            f"/ui/matches/{match.id}/result",
            data={"status": "In Progress"},
        )
        assert resp.status_code == 200
        assert b"Normal Win" in resp.data
        db.session.refresh(match)
        assert match.status == "In Progress"

    def test_ui_record_result_completed(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id, round_name="Final").first()
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

        match = Match.query.filter_by(division_id=div_id, round_name="Final").first()
        resp = client.post(
            f"/ui/matches/{match.id}/result",
            data={"status": "Completed"},
        )
        assert resp.status_code == 400

    def test_ui_record_result_disqualification(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id, round_name="Final").first()
        winner_id = match.competitor2_id

        resp = client.post(
            f"/ui/matches/{match.id}/result",
            data={"status": "Disqualification", "winner_id": str(winner_id)},
        )
        assert resp.status_code == 200

    def test_ui_record_result_completed_includes_oob_notification(self, client):
        """Response should include OOB result notification and refreshed matches list."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id, round_name="Final").first()
        winner_id = match.competitor1_id

        resp = client.post(
            f"/ui/matches/{match.id}/result",
            data={"status": "Completed", "winner_id": str(winner_id)},
        )
        assert resp.status_code == 200
        assert b'id="result-notification"' in resp.data
        assert b'hx-swap-oob="innerHTML"' in resp.data
        assert b'id="matches-container"' in resp.data
        assert b'result-notification-content' in resp.data

    def test_ui_record_result_disqualification_includes_oob_notification(self, client):
        """Disqualification result should include OOB notification and refreshed matches."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id, round_name="Final").first()
        winner_id = match.competitor2_id

        resp = client.post(
            f"/ui/matches/{match.id}/result",
            data={"status": "Disqualification", "winner_id": str(winner_id)},
        )
        assert resp.status_code == 200
        assert b'id="result-notification"' in resp.data
        assert b'hx-swap-oob="innerHTML"' in resp.data
        assert b'id="matches-container"' in resp.data

    def test_ui_record_result_completed_refreshes_bracket_advancement(self, client):
        """After a match completes, next match should show winner name in the OOB matches list."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol", "Dave"])
        _generate_bracket(client, div_id)

        # Schedule all matches to the ring so they appear in the matches refresh
        all_matches = Match.query.filter_by(division_id=div_id).order_by(Match.match_number).all()
        for seq, m in enumerate(all_matches, start=1):
            client.put(
                f"/matches/{m.id}/schedule",
                data={"ring_id": str(ring_id), "ring_sequence": str(seq)},
            )

        first_match = Match.query.filter_by(division_id=div_id, round_name="Semi-Final").first()
        winner = db.session.get(Competitor, first_match.competitor1_id)

        resp = client.post(
            f"/ui/matches/{first_match.id}/result",
            data={"status": "Completed", "winner_id": str(winner.id)},
        )
        assert resp.status_code == 200
        # The refreshed matches-container should include the winner's name in the next match
        assert winner.name.encode() in resp.data
        # Non-final match: "advances to the next round!" message
        assert b"advances to the next round!" in resp.data

    def test_ui_record_result_final_match_shows_gold_message(self, client):
        """Completing the Final match should show 'wins gold!' instead of 'advances'."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol", "Dave"])
        _generate_bracket(client, div_id)

        # Complete both Semi-Final matches so the Final's competitors are populated
        semi_final_matches = Match.query.filter_by(division_id=div_id, round_name="Semi-Final").all()
        for m in semi_final_matches:
            client.post(
                f"/ui/matches/{m.id}/result",
                data={"status": "Completed", "winner_id": str(m.competitor1_id)},
            )

        final_match = Match.query.filter_by(division_id=div_id, round_name="Final").first()
        assert final_match is not None
        db.session.refresh(final_match)
        winner_id = final_match.competitor1_id

        resp = client.post(
            f"/ui/matches/{final_match.id}/result",
            data={"status": "Completed", "winner_id": str(winner_id)},
        )
        assert resp.status_code == 200
        assert b"wins gold!" in resp.data
        assert b"advances to the next round!" not in resp.data


    def test_ui_record_result_match_not_found(self, client):
        resp = client.post(
            "/ui/matches/9999/result",
            data={"status": "Completed", "winner_id": "1"},
        )
        assert resp.status_code == 404

    def test_ui_record_result_tbd_competitor_rejected(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol"])
        _generate_bracket(client, div_id)

        # Find a Pending match with a TBD slot (excludes Completed (Bye) matches)
        tbd_match = Match.query.filter_by(division_id=div_id, status="Pending").filter(
            Match.competitor1_id.is_(None) | Match.competitor2_id.is_(None)
        ).first()
        assert tbd_match is not None

        resp = client.post(
            f"/ui/matches/{tbd_match.id}/result",
            data={"status": "In Progress"},
        )
        assert resp.status_code == 400

    def test_ui_record_result_in_progress_conflict_blocked(self, client):
        """Starting a match while another is In Progress on the same ring triggers an error response."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol", "Dave"])
        _generate_bracket(client, div_id)

        matches = (
            Match.query.filter_by(division_id=div_id, status="Pending")
            .filter(
                (Match.competitor1_id.isnot(None) & Match.competitor2_id.isnot(None))
                | (Match.round_name == "Semi-Final")
            )
            .order_by(Match.id)
            .all()
        )
        assert len(matches) >= 2

        # Schedule both matches to the same ring
        for seq, match in enumerate(matches[:2], start=1):
            client.put(
                f"/matches/{match.id}/schedule",
                data={"ring_id": str(ring_id), "ring_sequence": str(seq)},
            )

        first_match, second_match = matches[0], matches[1]

        # Start first match
        resp = client.post(
            f"/ui/matches/{first_match.id}/result",
            data={"status": "In Progress"},
        )
        assert resp.status_code == 200
        db.session.refresh(first_match)
        assert first_match.status == "In Progress"

        # Attempt to start second match while first is still In Progress
        resp = client.post(
            f"/ui/matches/{second_match.id}/result",
            data={"status": "In Progress"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("HX-Trigger") == "showInProgressError"
        db.session.refresh(second_match)
        # Second match must remain Pending
        assert second_match.status == "Pending"

    def test_ui_record_result_in_progress_no_conflict_different_rings(self, client):
        """Starting a match when another ring has an In Progress match is allowed."""
        ring1_id = _create_ring(client, "Ring 1").get_json()["id"]
        ring2_id = _create_ring(client, "Ring 2").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol", "Dave"])
        _generate_bracket(client, div_id)

        matches = Match.query.filter_by(division_id=div_id, status="Pending").all()
        assert len(matches) >= 2

        first_match, second_match = matches[0], matches[1]

        # Schedule matches to different rings
        client.put(
            f"/matches/{first_match.id}/schedule",
            data={"ring_id": str(ring1_id), "ring_sequence": "1"},
        )
        client.put(
            f"/matches/{second_match.id}/schedule",
            data={"ring_id": str(ring2_id), "ring_sequence": "1"},
        )

        # Start first match on ring 1
        resp = client.post(
            f"/ui/matches/{first_match.id}/result",
            data={"status": "In Progress"},
        )
        assert resp.status_code == 200
        db.session.refresh(first_match)
        assert first_match.status == "In Progress"

        # Start second match on ring 2 — should succeed with no HX-Trigger error
        resp = client.post(
            f"/ui/matches/{second_match.id}/result",
            data={"status": "In Progress"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("HX-Trigger") != "showInProgressError"
        db.session.refresh(second_match)
        assert second_match.status == "In Progress"


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

    def test_schedule_duplicate_match_number(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id1 = _create_division(client, "Male - Black Belt - Under 70kg").get_json()["id"]
        div_id2 = _create_division(client, "Female - Black Belt - Under 60kg").get_json()["id"]
        _add_competitors(client, div_id1, ["Alice", "Bob"])
        _add_competitors(client, div_id2, ["Carol", "Dave"])
        _generate_bracket(client, div_id1)
        _generate_bracket(client, div_id2)

        match1 = Match.query.filter_by(division_id=div_id1).first()
        match2 = Match.query.filter_by(division_id=div_id2).first()

        # Schedule first match successfully
        resp1 = client.put(
            f"/matches/{match1.id}/schedule",
            data={"ring_id": str(ring_id), "ring_sequence": "1"},
        )
        assert resp1.status_code == 200
        assert match1.match_number == (ring_id * 100) + 1

        # Attempt to assign the same match number to a second match
        resp2 = client.put(
            f"/matches/{match2.id}/schedule",
            data={"ring_id": str(ring_id), "ring_sequence": "1"},
        )
        assert resp2.status_code == 200
        assert b"Error" in resp2.data
        assert match2.match_number is None

    def test_schedule_match_sequence_out_of_range(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id).first()
        resp = client.put(
            f"/matches/{match.id}/schedule",
            data={"ring_id": str(ring_id), "ring_sequence": "100"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Page / full-HTML routes
# ---------------------------------------------------------------------------


class TestPageRoutes:
    def test_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b'name="viewport"' in resp.data
        assert b'width=device-width' in resp.data
        assert b'class="top-nav"' in resp.data
        assert b'word-break: break-word' in resp.data

    def test_admin(self, client):
        resp = client.get("/admin")
        assert resp.status_code == 200
        assert b'name="viewport"' in resp.data
        assert b'width=device-width' in resp.data
        assert b'flex-direction: column' in resp.data
        assert b'@media (max-width: 700px)' in resp.data

    def test_admin_division_setup(self, client):
        div_id = _create_division(client).get_json()["id"]
        resp = client.get(f"/admin/divisions/{div_id}/setup")
        assert resp.status_code == 200
        assert b'id="htmx-confirm-modal"' in resp.data
        assert b"htmx:confirm" in resp.data
        assert b'name="viewport"' in resp.data
        assert b'width=device-width' in resp.data
        assert b'grid-template-columns: 1fr' in resp.data
        assert b'@media (max-width: 600px)' in resp.data

    def test_admin_division_setup_not_found(self, client):
        resp = client.get("/admin/divisions/9999/setup")
        assert resp.status_code == 404

    def test_ui_bracket_controls_no_competitors(self, client):
        div_id = _create_division(client).get_json()["id"]
        resp = client.get(f"/ui/divisions/{div_id}/bracket_controls")
        assert resp.status_code == 200
        assert b"Add competitors above" in resp.data

    def test_ui_bracket_controls_with_competitors(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        resp = client.get(f"/ui/divisions/{div_id}/bracket_controls")
        assert resp.status_code == 200
        assert b"Generate Bracket" in resp.data

    def test_ui_bracket_controls_with_bracket(self, client):
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)
        resp = client.get(f"/ui/divisions/{div_id}/bracket_controls")
        assert resp.status_code == 200
        assert b"Manage" in resp.data
        assert b"Regenerate Bracket" in resp.data

    def test_ui_bracket_controls_not_found(self, client):
        resp = client.get("/ui/divisions/9999/bracket_controls")
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
        assert b'id="htmx-confirm-modal"' in resp.data
        assert b"htmx:confirm" in resp.data

    def test_bracket_manage_not_found(self, client):
        resp = client.get("/admin/divisions/9999/bracket_manage")
        assert resp.status_code == 404

    def test_results_page(self, client):
        resp = client.get("/results")
        assert resp.status_code == 200
        assert b"Tournament Results" in resp.data
        assert b"Kyorugi" in resp.data
        assert b"Poomsae" in resp.data
        assert b"Live View" in resp.data

    def test_results_page_links_from_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"/results" in resp.data
        assert b"View Results" in resp.data

    def test_ui_results_divisions_empty(self, client):
        resp = client.get("/ui/results_divisions?event_type=kyorugi")
        assert resp.status_code == 200
        assert b"No divisions found" in resp.data

    def test_ui_results_divisions_kyorugi(self, client):
        _create_division(client, "Kyorugi Div", "kyorugi")
        _create_division(client, "Poomsae Div", "poomsae")
        resp = client.get("/ui/results_divisions?event_type=kyorugi")
        assert resp.status_code == 200
        assert b"Kyorugi Div" in resp.data
        assert b"Poomsae Div" not in resp.data

    def test_ui_results_divisions_poomsae(self, client):
        _create_division(client, "Kyorugi Div", "kyorugi")
        _create_division(client, "Poomsae Div", "poomsae")
        resp = client.get("/ui/results_divisions?event_type=poomsae")
        assert resp.status_code == 200
        assert b"Poomsae Div" in resp.data
        assert b"Kyorugi Div" not in resp.data

    def test_ui_results_divisions_invalid_event_type(self, client):
        resp = client.get("/ui/results_divisions?event_type=invalid")
        assert resp.status_code == 400

    def test_ui_results_divisions_bracket_link(self, client):
        div_id = _create_division(client, "Test Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)
        resp = client.get("/ui/results_divisions?event_type=kyorugi")
        assert resp.status_code == 200
        assert f"/ui/divisions/{div_id}/bracket".encode() in resp.data

    def test_ui_results_divisions_status_no_bracket(self, client):
        _create_division(client, "No Bracket Div", "kyorugi")
        resp = client.get("/ui/results_divisions?event_type=kyorugi")
        assert resp.status_code == 200
        assert b"No bracket" in resp.data

    def test_ui_results_divisions_status_pending(self, client):
        div_id = _create_division(client, "Pending Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)
        resp = client.get("/ui/results_divisions?event_type=kyorugi")
        assert resp.status_code == 200
        assert b"Pending" in resp.data

    def test_ui_results_divisions_status_in_progress(self, client):
        div_id = _create_division(client, "InProgress Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol", "Dave"])
        _generate_bracket(client, div_id)
        # Complete only one of the Semi-Final matches to get "In Progress" status
        match = Match.query.filter_by(division_id=div_id, round_name="Semi-Final").first()
        client.post(
            f"/ui/matches/{match.id}/result",
            data={"status": "Completed", "winner_id": match.competitor1_id},
        )
        resp = client.get("/ui/results_divisions?event_type=kyorugi")
        assert resp.status_code == 200
        assert b"In Progress" in resp.data

    def test_ui_results_divisions_status_completed(self, client):
        div_id = _create_division(client, "Completed Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)
        match = Match.query.filter_by(division_id=div_id).first()
        client.post(
            f"/ui/matches/{match.id}/result",
            data={"status": "Completed", "winner_id": match.competitor1_id},
        )
        resp = client.get("/ui/results_divisions?event_type=kyorugi")
        assert resp.status_code == 200
        assert b"Completed" in resp.data


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


class TestEventTypes:
    def test_create_division_with_event_type(self, client):
        resp = client.post("/divisions", json={"name": "Poomsae Div", "event_type": "poomsae"})
        assert resp.status_code == 201
        from app import Division, db

        div = db.session.get(Division, resp.get_json()["id"])
        assert div.event_type == "poomsae"

    def test_create_division_invalid_event_type(self, client):
        resp = client.post("/divisions", json={"name": "Bad", "event_type": "unknown"})
        assert resp.status_code == 400

    def test_ui_add_division_invalid_event_type(self, client):
        resp = client.post("/ui/divisions", data={"name": "Bad", "event_type": "unknown"})
        assert resp.status_code == 400

    def test_ui_divisions_list_filtered_by_event_type(self, client):
        client.post("/ui/divisions", data={"name": "Kyorugi Div", "event_type": "kyorugi"})
        client.post("/ui/divisions", data={"name": "Poomsae Div", "event_type": "poomsae"})

        resp_k = client.get("/ui/divisions_list?event_type=kyorugi")
        assert b"Kyorugi Div" in resp_k.data
        assert b"Poomsae Div" not in resp_k.data

        resp_p = client.get("/ui/divisions_list?event_type=poomsae")
        assert b"Poomsae Div" in resp_p.data
        assert b"Kyorugi Div" not in resp_p.data

    def test_ui_divisions_list_no_filter_returns_all(self, client):
        client.post("/ui/divisions", data={"name": "Kyorugi Div", "event_type": "kyorugi"})
        client.post("/ui/divisions", data={"name": "Poomsae Div", "event_type": "poomsae"})

        resp = client.get("/ui/divisions_list")
        assert b"Kyorugi Div" in resp.data
        assert b"Poomsae Div" in resp.data

    def test_ui_divisions_list_invalid_event_type(self, client):
        resp = client.get("/ui/divisions_list?event_type=unknown")
        assert resp.status_code == 400

    def test_same_match_number_allowed_across_events(self, client):
        """Match number 101 in kyorugi should not conflict with 101 in poomsae."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_kyorugi = _create_division(client, "Kyorugi Div", "kyorugi").get_json()["id"]
        div_poomsae = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_kyorugi, ["Alice", "Bob"])
        _add_competitors(client, div_poomsae, ["Carol", "Dave"])
        _generate_bracket(client, div_kyorugi)
        _generate_bracket(client, div_poomsae)

        match_k = Match.query.filter_by(division_id=div_kyorugi).first()
        match_p = Match.query.filter_by(division_id=div_poomsae).first()

        # Schedule match_number 101 in kyorugi (ring 1 * 100 + 1)
        resp1 = client.put(
            f"/matches/{match_k.id}/schedule",
            data={"ring_id": str(ring_id), "ring_sequence": "1"},
        )
        assert resp1.status_code == 200
        assert b"Error" not in resp1.data
        db.session.refresh(match_k)
        assert match_k.match_number == (ring_id * 100) + 1

        # Schedule the same match_number 101 in poomsae — must succeed (different event)
        resp2 = client.put(
            f"/matches/{match_p.id}/schedule",
            data={"ring_id": str(ring_id), "ring_sequence": "1"},
        )
        assert resp2.status_code == 200
        assert b"Error" not in resp2.data
        db.session.refresh(match_p)
        assert match_p.match_number == (ring_id * 100) + 1

    def test_duplicate_match_number_rejected_within_event(self, client):
        """Two matches in the same event cannot share a match number."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div1 = _create_division(client, "Kyorugi A", "kyorugi").get_json()["id"]
        div2 = _create_division(client, "Kyorugi B", "kyorugi").get_json()["id"]
        _add_competitors(client, div1, ["Alice", "Bob"])
        _add_competitors(client, div2, ["Carol", "Dave"])
        _generate_bracket(client, div1)
        _generate_bracket(client, div2)

        match1 = Match.query.filter_by(division_id=div1).first()
        match2 = Match.query.filter_by(division_id=div2).first()

        client.put(
            f"/matches/{match1.id}/schedule",
            data={"ring_id": str(ring_id), "ring_sequence": "5"},
        )
        db.session.refresh(match1)
        assert match1.match_number == (ring_id * 100) + 5

        resp2 = client.put(
            f"/matches/{match2.id}/schedule",
            data={"ring_id": str(ring_id), "ring_sequence": "5"},
        )
        assert resp2.status_code == 200
        assert b"Error" in resp2.data
        db.session.refresh(match2)
        assert match2.match_number is None

    def test_ring_scorekeeper(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        resp = client.get(f"/ring/{ring_id}/scorekeeper")
        assert resp.status_code == 200
        assert b'id="htmx-confirm-modal"' in resp.data
        assert b"htmx:confirm" in resp.data
        assert b'name="viewport"' in resp.data
        assert b'@media (max-width: 600px)' in resp.data
        assert b'flex-direction: column' in resp.data

    def test_ring_scorekeeper_not_found(self, client):
        resp = client.get("/ring/9999/scorekeeper")
        assert resp.status_code == 404

    def test_ring_scorekeeper_shows_tbd_matches(self, client):
        """Matches with a TBD competitor should still appear on the scorekeeper page."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        # 3 competitors causes a bye, so one semi-final match will have a TBD slot
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol"])
        _generate_bracket(client, div_id)

        # Schedule all matches to the ring
        for seq, match in enumerate(Match.query.filter_by(division_id=div_id).all(), start=1):
            client.put(
                f"/matches/{match.id}/schedule",
                data={"ring_id": str(ring_id), "ring_sequence": str(seq)},
            )

        resp = client.get(f"/ring/{ring_id}/scorekeeper")
        assert resp.status_code == 200
        assert b"TBD" in resp.data

    def test_ring_scorekeeper_tbd_submit_disabled(self, client):
        """Action buttons should be disabled when a competitor is TBD."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol"])
        _generate_bracket(client, div_id)

        # Find a Pending match with a TBD slot (excludes Completed (Bye) matches)
        tbd_match = Match.query.filter_by(division_id=div_id, status="Pending").filter(
            Match.competitor1_id.is_(None) | Match.competitor2_id.is_(None)
        ).first()
        assert tbd_match is not None

        client.put(
            f"/matches/{tbd_match.id}/schedule",
            data={"ring_id": str(ring_id), "ring_sequence": "1"},
        )

        resp = client.get(f"/ring/{ring_id}/scorekeeper")
        assert resp.status_code == 200
        # Winner-required action button should be disabled for TBD match
        assert b'class="submit-btn" disabled' in resp.data

    def test_ring_scorekeeper_no_tbd_submit_enabled(self, client):
        """Start should be enabled while winner-required actions begin disabled until a winner is selected."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id).first()
        client.put(
            f"/matches/{match.id}/schedule",
            data={"ring_id": str(ring_id), "ring_sequence": "1"},
        )

        resp = client.get(f"/ring/{ring_id}/scorekeeper")
        assert resp.status_code == 200
        assert b"Start" in resp.data
        assert b'class="submit-btn"' in resp.data
        assert b'class="submit-btn dsq-btn winner-required" disabled' in resp.data

    def test_ring_scorekeeper_filters_by_event_type(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_kyorugi = _create_division(client, "Kyorugi Division", "kyorugi").get_json()["id"]
        div_poomsae = _create_division(client, "Poomsae Division", "poomsae").get_json()["id"]

        _add_competitors(client, div_kyorugi, ["Alice", "Bob"])
        _add_competitors(client, div_poomsae, ["Carol", "Dave"])
        _generate_bracket(client, div_kyorugi)
        _generate_bracket(client, div_poomsae)

        match_k = Match.query.filter_by(division_id=div_kyorugi).first()
        match_p = Match.query.filter_by(division_id=div_poomsae).first()

        client.put(
            f"/matches/{match_k.id}/schedule",
            data={"ring_id": str(ring_id), "ring_sequence": "1"},
        )
        client.put(
            f"/matches/{match_p.id}/schedule",
            data={"ring_id": str(ring_id), "ring_sequence": "2"},
        )

        resp_k = client.get(f"/ring/{ring_id}/scorekeeper?event_type=kyorugi")
        assert resp_k.status_code == 200
        assert b"Kyorugi Division" in resp_k.data
        assert b"Poomsae Division" not in resp_k.data

        resp_p = client.get(f"/ring/{ring_id}/scorekeeper?event_type=poomsae")
        assert resp_p.status_code == 200
        assert b"Poomsae Division" in resp_p.data
        assert b"Kyorugi Division" not in resp_p.data

    def test_ring_scorekeeper_invalid_event_type(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        resp = client.get(f"/ring/{ring_id}/scorekeeper?event_type=unknown")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Medal Placements
# ---------------------------------------------------------------------------


class TestMedalPlacements:
    """Tests for the medal placement table shown on the bracket results page."""

    def _complete_match(self, client, match, winner_id):
        """Helper to record a completed result via the JSON API."""
        return client.post(
            f"/matches/{match.id}/result",
            json={"status": "Completed", "winner_id": winner_id},
        )

    def test_no_placements_before_bracket_complete(self, client):
        """Medal table should NOT appear while matches are still pending."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        resp = client.get(f"/divisions/{div_id}/bracket_ui")
        assert resp.status_code == 200
        assert b"Medal Placements" not in resp.data

    def test_placements_two_competitors(self, client):
        """2-competitor bracket: 1st and 2nd shown; no 3rd place entries."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id).first()
        winner_id = match.competitor1_id
        loser_id = match.competitor2_id

        self._complete_match(client, match, winner_id)

        resp = client.get(f"/divisions/{div_id}/bracket_ui")
        assert resp.status_code == 200
        assert b"Medal Placements" in resp.data

        winner = db.session.get(Competitor, winner_id)
        loser = db.session.get(Competitor, loser_id)
        assert winner.name.encode() in resp.data
        assert loser.name.encode() in resp.data
        assert b"3rd Place" not in resp.data

    def test_placements_four_competitors(self, client):
        """4-competitor bracket (Semi-Final → Final):
        both Semi-Final losers appear as 3rd place.

        4-competitor bracket layout:
          SF_1: Alice vs Bob   → winner advances to Final
          SF_2: Carol vs Dave  → winner advances to Final
          Final: SF_1 winner vs SF_2 winner
        The two Semi-Final losers are the bronze medalists (their matches feed
        directly into the championship via next_match_id).
        """
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol", "Dave"])
        _generate_bracket(client, div_id)

        r1_matches = Match.query.filter_by(division_id=div_id, round_name="Semi-Final").all()
        assert len(r1_matches) == 2

        r1_loser_names = []
        for r1 in r1_matches:
            db.session.expire_all()
            r1 = db.session.get(Match, r1.id)
            assert r1.competitor1_id is not None
            assert r1.competitor2_id is not None
            winner_id = r1.competitor1_id
            loser_id = r1.competitor2_id
            resp = self._complete_match(client, r1, winner_id)
            assert resp.status_code == 200
            r1_loser_names.append(db.session.get(Competitor, loser_id).name)

        # Complete the Final
        db.session.expire_all()
        final = Match.query.filter_by(division_id=div_id, round_name="Final").first()
        assert final is not None
        final = db.session.get(Match, final.id)
        assert final.competitor1_id is not None
        assert final.competitor2_id is not None
        final_winner_id = final.competitor1_id
        final_loser_id = final.competitor2_id
        resp = self._complete_match(client, final, final_winner_id)
        assert resp.status_code == 200

        resp = client.get(f"/divisions/{div_id}/bracket_ui")
        assert resp.status_code == 200
        assert b"Medal Placements" in resp.data
        assert b"1st Place" in resp.data
        assert b"2nd Place" in resp.data
        assert resp.data.count(b"3rd Place") == 2

        final_winner = db.session.get(Competitor, final_winner_id)
        final_loser = db.session.get(Competitor, final_loser_id)
        assert final_winner.name.encode() in resp.data
        assert final_loser.name.encode() in resp.data
        for loser_name in r1_loser_names:
            assert loser_name.encode() in resp.data

    def test_placements_with_semifinals(self, client):
        """Bracket with Quarter-Finals (5 competitors → 3 byes in Quarter-Final round):
        all four placements are shown after the Final is completed.

        5-competitor bracket layout:
          QF_1: Alice vs Eve  (real match)
          QF_2: Bob  vs --    (bye → Bob advances)
          QF_3: Carol vs --   (bye → Carol advances)
          QF_4: Dave  vs --   (bye → Dave advances)
        Semi-Finals:
          SF_1: Eve-or-Alice vs Bob
          SF_2: Carol vs Dave
        Final: SF_1 winner vs SF_2 winner
        """
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol", "Dave", "Eve"])
        _generate_bracket(client, div_id)

        # Step 1: Complete the only real Quarter-Final match (Alice vs Eve)
        r1_real = Match.query.filter_by(division_id=div_id, round_name="Quarter-Final").filter(
            Match.competitor1_id.isnot(None), Match.competitor2_id.isnot(None)
        ).first()
        assert r1_real is not None
        r1_winner_id = r1_real.competitor1_id
        resp = self._complete_match(client, r1_real, r1_winner_id)
        assert resp.status_code == 200

        # Step 2: Complete both Semi-Final matches
        db.session.expire_all()
        semi_finals = Match.query.filter_by(division_id=div_id, round_name="Semi-Final").all()
        assert len(semi_finals) == 2

        sf_loser_names = []
        for sf in semi_finals:
            db.session.expire_all()
            sf = db.session.get(Match, sf.id)
            assert sf.competitor1_id is not None, "SF competitor1 should be populated"
            assert sf.competitor2_id is not None, "SF competitor2 should be populated"
            sf_winner_id = sf.competitor1_id
            sf_loser_id = sf.competitor2_id
            resp = self._complete_match(client, sf, sf_winner_id)
            assert resp.status_code == 200
            sf_loser_names.append(db.session.get(Competitor, sf_loser_id).name)

        # Step 3: Complete the Final
        db.session.expire_all()
        final = Match.query.filter_by(division_id=div_id, round_name="Final").first()
        assert final is not None
        final = db.session.get(Match, final.id)
        assert final.competitor1_id is not None
        assert final.competitor2_id is not None
        final_winner_id = final.competitor1_id
        final_loser_id = final.competitor2_id
        resp = self._complete_match(client, final, final_winner_id)
        assert resp.status_code == 200

        # Verify medal placements appear in the bracket UI
        resp = client.get(f"/divisions/{div_id}/bracket_ui")
        assert resp.status_code == 200
        assert b"Medal Placements" in resp.data
        assert b"1st Place" in resp.data
        assert b"2nd Place" in resp.data
        assert b"3rd Place" in resp.data

        final_winner = db.session.get(Competitor, final_winner_id)
        final_loser = db.session.get(Competitor, final_loser_id)
        assert final_winner.name.encode() in resp.data
        assert final_loser.name.encode() in resp.data
        for loser_name in sf_loser_names:
            assert loser_name.encode() in resp.data


# ---------------------------------------------------------------------------
# Symmetric Bracket Display
# ---------------------------------------------------------------------------


class TestBracketDisplayLayout:
    """Tests for _build_bracket_display and _extract_bracket_half helpers."""

    def test_bracket_ui_two_competitors_single_center_column(self, client):
        """2-competitor bracket: just a Final column, no left/right columns."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        resp = client.get(f"/divisions/{div_id}/bracket_ui")
        assert resp.status_code == 200
        html = resp.data.decode()
        titles = re.findall(r'<h3 class="round-title">([^<]+)</h3>', html)
        assert titles == ["Final"]

    def test_bracket_ui_four_competitors_three_columns(self, client):
        """4-competitor bracket: Semi-Final | Final | Semi-Final (3 columns)."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["A", "B", "C", "D"])
        _generate_bracket(client, div_id)

        resp = client.get(f"/divisions/{div_id}/bracket_ui")
        assert resp.status_code == 200
        html = resp.data.decode()
        titles = re.findall(r'<h3 class="round-title">([^<]+)</h3>', html)
        assert titles == ["Semi-Final", "Final", "Semi-Final"]

    def test_bracket_ui_eight_competitors_five_columns(self, client):
        """8-competitor bracket: Quarter-Final | Semi-Final | Final | Semi-Final | Quarter-Final."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["A", "B", "C", "D", "E", "F", "G", "H"])
        _generate_bracket(client, div_id)

        resp = client.get(f"/divisions/{div_id}/bracket_ui")
        assert resp.status_code == 200
        html = resp.data.decode()
        titles = re.findall(r'<h3 class="round-title">([^<]+)</h3>', html)
        assert titles == ["Quarter-Final", "Semi-Final", "Final", "Semi-Final", "Quarter-Final"]

    def test_bracket_ui_sixteen_competitors_seven_columns(self, client):
        """16-competitor bracket has 7 columns: Round of 16 | QF | SF | F | SF | QF | Round of 16."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, [str(i) for i in range(1, 17)])
        _generate_bracket(client, div_id)

        resp = client.get(f"/divisions/{div_id}/bracket_ui")
        assert resp.status_code == 200
        html = resp.data.decode()
        titles = re.findall(r'<h3 class="round-title">([^<]+)</h3>', html)
        assert titles == [
            "Round of 16", "Quarter-Final", "Semi-Final",
            "Final",
            "Semi-Final", "Quarter-Final", "Round of 16",
        ]

    def test_bracket_ui_columns_are_symmetric(self, client):
        """Left and right halves should be mirror images (same round names)."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["A", "B", "C", "D", "E", "F", "G", "H"])
        _generate_bracket(client, div_id)

        resp = client.get(f"/divisions/{div_id}/bracket_ui")
        assert resp.status_code == 200
        html = resp.data.decode()
        titles = re.findall(r'<h3 class="round-title">([^<]+)</h3>', html)
        # Remove the center Final column; the remaining columns should be a palindrome
        assert titles[0] == titles[-1]
        final_idx = titles.index("Final")
        left = titles[:final_idx]
        right = titles[final_idx + 1:]
        assert left == list(reversed(right))
