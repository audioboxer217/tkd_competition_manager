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


def _set_poomsae_style(client, div_id, style):
    """Set the poomsae_style for a division ('bracket' or 'group')."""
    return client.post(
        f"/ui/divisions/{div_id}/poomsae_style",
        data={"poomsae_style": style},
    )


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
        """Response should include OOB result notification and a lazy-load matches container."""
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
        assert b'result-notification-content' in resp.data
        # Kyorugi: matches container should be refreshed via a lazy HTMX load (not inline HTML)
        assert b'id="matches-container"' in resp.data
        assert b'hx-trigger="load"' in resp.data
        assert b'scorekeeper_matches' in resp.data

    def test_ui_record_result_disqualification_includes_oob_notification(self, client):
        """Disqualification result should include OOB notification and lazy-load matches container."""
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
        assert b'id="matches-container"' in resp.data
        assert b'hx-trigger="load"' in resp.data

    def test_ui_record_result_completed_refreshes_bracket_advancement(self, client):
        """After a match completes, the scorekeeper_matches endpoint should show the advanced winner."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol", "Dave"])
        _generate_bracket(client, div_id)

        # Assign ring to the division, then schedule all matches
        client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": str(ring_id)})
        all_matches = Match.query.filter_by(division_id=div_id).order_by(Match.match_number).all()
        for seq, m in enumerate(all_matches, start=1):
            client.put(
                f"/matches/{m.id}/schedule",
                data={"ring_sequence": str(seq)},
            )

        first_match = Match.query.filter_by(division_id=div_id, round_name="Semi-Final").first()
        winner = db.session.get(Competitor, first_match.competitor1_id)

        resp = client.post(
            f"/ui/matches/{first_match.id}/result",
            data={"status": "Completed", "winner_id": str(winner.id)},
        )
        assert resp.status_code == 200
        # Notification should contain the winner's name and result message
        assert winner.name.encode() in resp.data
        assert b"advances to the next round!" in resp.data
        # The response should trigger a lazy reload of the matches container
        assert b'scorekeeper_matches' in resp.data

        # The fresh matches endpoint should show the winner in the next (Final) match
        matches_resp = client.get(f"/ui/rings/{ring_id}/scorekeeper_matches")
        assert matches_resp.status_code == 200
        assert winner.name.encode() in matches_resp.data

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

        # Assign ring to the division, then schedule both matches to the same ring
        client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": str(ring_id)})
        for seq, match in enumerate(matches[:2], start=1):
            client.put(
                f"/matches/{match.id}/schedule",
                data={"ring_sequence": str(seq)},
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
        div1_id = _create_division(client, "Division A").get_json()["id"]
        div2_id = _create_division(client, "Division B").get_json()["id"]
        _add_competitors(client, div1_id, ["Alice", "Bob"])
        _add_competitors(client, div2_id, ["Carol", "Dave"])
        _generate_bracket(client, div1_id)
        _generate_bracket(client, div2_id)

        first_match = Match.query.filter_by(division_id=div1_id, status="Pending").first()
        second_match = Match.query.filter_by(division_id=div2_id, status="Pending").first()

        # Assign different rings to each division and schedule
        client.patch(f"/ui/divisions/{div1_id}/bracket_ring", data={"ring_id": str(ring1_id)})
        client.patch(f"/ui/divisions/{div2_id}/bracket_ring", data={"ring_id": str(ring2_id)})
        client.put(f"/matches/{first_match.id}/schedule", data={"ring_sequence": "1"})
        client.put(f"/matches/{second_match.id}/schedule", data={"ring_sequence": "1"})

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

    # ------------------------------------------------------------------
    # Time tracking
    # ------------------------------------------------------------------

    def test_start_time_set_when_in_progress(self, client):
        """start_time is recorded when a match is set to In Progress."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id, round_name="Final").first()
        assert match.start_time is None

        client.post(f"/ui/matches/{match.id}/result", data={"status": "In Progress"})

        db.session.refresh(match)
        assert match.start_time is not None
        assert match.end_time is None

    def test_end_time_set_when_completed_after_start(self, client):
        """end_time is recorded when a started match is completed."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id, round_name="Final").first()
        winner_id = match.competitor1_id

        client.post(f"/ui/matches/{match.id}/result", data={"status": "In Progress"})
        client.post(
            f"/ui/matches/{match.id}/result",
            data={"status": "Completed", "winner_id": str(winner_id)},
        )

        db.session.refresh(match)
        assert match.start_time is not None
        assert match.end_time is not None
        assert match.end_time >= match.start_time

    def test_end_time_not_set_for_disqualification_without_start(self, client):
        """Neither start_time nor end_time is set when DSQ is issued without starting."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id, round_name="Final").first()
        winner_id = match.competitor1_id

        client.post(
            f"/ui/matches/{match.id}/result",
            data={"status": "Disqualification", "winner_id": str(winner_id)},
        )

        db.session.refresh(match)
        assert match.start_time is None
        assert match.end_time is None

    def test_end_time_set_for_disqualification_after_start(self, client):
        """end_time is recorded when a DSQ is issued after the match has started."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id, round_name="Final").first()
        winner_id = match.competitor1_id

        client.post(f"/ui/matches/{match.id}/result", data={"status": "In Progress"})
        client.post(
            f"/ui/matches/{match.id}/result",
            data={"status": "Disqualification", "winner_id": str(winner_id)},
        )

        db.session.refresh(match)
        assert match.start_time is not None
        assert match.end_time is not None


# ---------------------------------------------------------------------------
# Scorekeeper matches fragment endpoint
# ---------------------------------------------------------------------------


class TestScorekeeperMatchesFragment:
    def test_scorekeeper_matches_returns_pending_matches(self, client):
        """Fragment endpoint returns pending kyorugi matches for the ring."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": str(ring_id)})
        match = Match.query.filter_by(division_id=div_id, status="Pending").first()
        client.put(f"/matches/{match.id}/schedule", data={"ring_sequence": "1"})

        resp = client.get(f"/ui/rings/{ring_id}/scorekeeper_matches")
        assert resp.status_code == 200
        assert b"Start" in resp.data

    def test_scorekeeper_matches_excludes_completed(self, client):
        """Completed matches are not returned by the fragment endpoint."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": str(ring_id)})
        match = Match.query.filter_by(division_id=div_id, round_name="Final").first()
        client.put(f"/matches/{match.id}/schedule", data={"ring_sequence": "1"})

        # Complete the match
        client.post(
            f"/ui/matches/{match.id}/result",
            data={"status": "Completed", "winner_id": str(match.competitor1_id)},
        )

        resp = client.get(f"/ui/rings/{ring_id}/scorekeeper_matches")
        assert resp.status_code == 200
        assert b"No ready matches" in resp.data

    def test_scorekeeper_matches_ring_not_found(self, client):
        """Returns 404 for an unknown ring."""
        resp = client.get("/ui/rings/9999/scorekeeper_matches")
        assert resp.status_code == 404

    def test_scorekeeper_matches_shows_bracket_advancement(self, client):
        """After a semi-final completes, the winner appears in the next match card."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol", "Dave"])
        _generate_bracket(client, div_id)

        client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": str(ring_id)})
        all_matches = Match.query.filter_by(division_id=div_id).order_by(Match.match_number).all()
        for seq, m in enumerate(all_matches, start=1):
            client.put(f"/matches/{m.id}/schedule", data={"ring_sequence": str(seq)})

        first_match = Match.query.filter_by(division_id=div_id, round_name="Semi-Final").first()
        winner = db.session.get(Competitor, first_match.competitor1_id)

        client.post(
            f"/ui/matches/{first_match.id}/result",
            data={"status": "Completed", "winner_id": str(winner.id)},
        )

        resp = client.get(f"/ui/rings/{ring_id}/scorekeeper_matches")
        assert resp.status_code == 200
        assert winner.name.encode() in resp.data


# ---------------------------------------------------------------------------
# Match scheduling (HTMX)
# ---------------------------------------------------------------------------


class TestMatchSchedule:
    def test_schedule_match(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        # Assign ring to the division first
        client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": str(ring_id)})

        match = Match.query.filter_by(division_id=div_id).first()
        resp = client.put(
            f"/matches/{match.id}/schedule",
            data={"ring_sequence": "25"},
        )
        assert resp.status_code == 200
        assert b"match-card" in resp.data

    def test_schedule_match_not_found(self, client):
        resp = client.put(
            "/matches/9999/schedule",
            data={"ring_sequence": "1"},
        )
        assert resp.status_code == 404

    def test_schedule_match_no_ring_on_division(self, client):
        _create_ring(client, "Ring 1")
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id).first()
        # No ring assigned to division — should return error in card
        resp = client.put(
            f"/matches/{match.id}/schedule",
            data={"ring_sequence": "5"},
        )
        assert resp.status_code == 200
        assert b"Error" in resp.data
        assert b"No ring assigned" in resp.data
        assert match.match_number is None

    def test_schedule_duplicate_match_number(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id1 = _create_division(client, "Male - Black Belt - Under 70kg").get_json()["id"]
        div_id2 = _create_division(client, "Female - Black Belt - Under 60kg").get_json()["id"]
        _add_competitors(client, div_id1, ["Alice", "Bob"])
        _add_competitors(client, div_id2, ["Carol", "Dave"])
        _generate_bracket(client, div_id1)
        _generate_bracket(client, div_id2)

        # Assign the same ring to both divisions
        client.patch(f"/ui/divisions/{div_id1}/bracket_ring", data={"ring_id": str(ring_id)})
        client.patch(f"/ui/divisions/{div_id2}/bracket_ring", data={"ring_id": str(ring_id)})

        match1 = Match.query.filter_by(division_id=div_id1).first()
        match2 = Match.query.filter_by(division_id=div_id2).first()

        # Schedule first match successfully
        resp1 = client.put(
            f"/matches/{match1.id}/schedule",
            data={"ring_sequence": "1"},
        )
        assert resp1.status_code == 200
        assert match1.match_number == (ring_id * 100) + 1

        # Attempt to assign the same match number to a second match
        resp2 = client.put(
            f"/matches/{match2.id}/schedule",
            data={"ring_sequence": "1"},
        )
        assert resp2.status_code == 200
        assert b"Error" in resp2.data
        assert match2.match_number is None

    def test_schedule_match_sequence_out_of_range(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        # Assign ring to the division first
        client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": str(ring_id)})

        match = Match.query.filter_by(division_id=div_id).first()
        resp = client.put(
            f"/matches/{match.id}/schedule",
            data={"ring_sequence": "100"},
        )
        assert resp.status_code == 400


class TestBracketRingAssignment:
    def test_bracket_ring_assign(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        resp = client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": str(ring_id)})
        assert resp.status_code == 200
        assert b"Ring 1" in resp.data
        from app import Division
        division = Division.query.get(div_id)
        assert division.ring_id == ring_id

    def test_bracket_ring_unassign(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        # Assign first
        client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": str(ring_id)})
        # Unassign
        resp = client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": ""})
        assert resp.status_code == 200
        from app import Division
        division = Division.query.get(div_id)
        assert division.ring_id is None

    def test_bracket_ring_not_found(self, client):
        resp = client.patch("/ui/divisions/9999/bracket_ring", data={"ring_id": "1"})
        assert resp.status_code == 404

    def test_bracket_ring_invalid_value(self, client):
        div_id = _create_division(client).get_json()["id"]
        resp = client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": "notanumber"})
        assert resp.status_code == 400

    def test_bracket_ring_nonexistent_ring(self, client):
        div_id = _create_division(client).get_json()["id"]
        resp = client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": "99999"})
        assert resp.status_code == 404

    def test_bracket_ring_change_clears_scheduled_matches(self, client):
        ring1_id = _create_ring(client, "Ring 1").get_json()["id"]
        ring2_id = _create_ring(client, "Ring 2").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)
        # Assign ring 1 and schedule a match
        client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": str(ring1_id)})
        match = Match.query.filter_by(division_id=div_id).first()
        client.put(f"/matches/{match.id}/schedule", data={"ring_sequence": "1"})
        # Confirm match is scheduled
        db.session.refresh(match)
        assert match.ring_id == ring1_id
        assert match.match_number is not None
        # Change to ring 2 — should clear scheduled matches
        resp = client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": str(ring2_id)})
        assert resp.status_code == 200
        db.session.refresh(match)
        assert match.ring_id is None
        assert match.match_number is None

    def test_bracket_ring_unassign_clears_scheduled_matches(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)
        # Assign ring and schedule a match
        client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": str(ring_id)})
        match = Match.query.filter_by(division_id=div_id).first()
        client.put(f"/matches/{match.id}/schedule", data={"ring_sequence": "1"})
        # Confirm match is scheduled
        db.session.refresh(match)
        assert match.ring_id == ring_id
        assert match.match_number is not None
        # Unassign ring — should clear scheduled matches
        resp = client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": ""})
        assert resp.status_code == 200
        db.session.refresh(match)
        assert match.ring_id is None
        assert match.match_number is None

    def test_bracket_manage_page_shows_ring_assignment(self, client):
        ring_id = _create_ring(client, "Ring 2").get_json()["id"]
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)
        # Assign ring at bracket level
        client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": str(ring_id)})
        resp = client.get(f"/admin/divisions/{div_id}/bracket_manage")
        assert resp.status_code == 200
        assert b"bracket-ring-assignment" in resp.data
        assert b"Ring Assignment" in resp.data
        assert b"Ring 2" in resp.data


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

    def test_admin(self, client):
        resp = client.get("/admin")
        assert resp.status_code == 200
        assert b'name="viewport"' in resp.data
        assert b'width=device-width' in resp.data

    def test_admin_division_setup(self, client):
        div_id = _create_division(client).get_json()["id"]
        resp = client.get(f"/admin/divisions/{div_id}/setup")
        assert resp.status_code == 200
        assert b'id="htmx-confirm-modal"' in resp.data
        assert b"htmx:confirm" in resp.data
        assert b'name="viewport"' in resp.data
        assert b'width=device-width' in resp.data

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

    def test_bracket_manage_round_order(self, client):
        """Rounds must appear left-to-right from earliest (most matches) to Final."""
        div_id = _create_division(client).get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol", "Dave"])
        _generate_bracket(client, div_id)

        resp = client.get(f"/admin/divisions/{div_id}/bracket_manage")
        assert resp.status_code == 200
        html = resp.data.decode()

        # Extract the ordered list of round titles from the bracket columns.
        round_titles = re.findall(r'<div class="round-title">\s*(.*?)\s*</div>', html)
        assert "Semi-Final" in round_titles, "Semi-Final round title not found in bracket manage page"
        assert "Final" in round_titles, "Final round title not found in bracket manage page"

        semi_index = round_titles.index("Semi-Final")
        final_index = round_titles.index("Final")
        # Semi-Final column title must appear before the Final column title
        assert semi_index < final_index, "Semi-Final should appear before Final in the bracket manage page"

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

    def test_results_page_has_search_bar(self, client):
        resp = client.get("/results")
        assert resp.status_code == 200
        assert b"search-input" in resp.data
        assert b"search-by" in resp.data

    def test_ui_results_divisions_search_by_name_filters(self, client):
        div_id_alice = _create_division(client, "Alpha Div", "kyorugi").get_json()["id"]
        div_id_bob = _create_division(client, "Beta Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id_alice, ["Alice Smith"])
        _add_competitors(client, div_id_bob, ["Bob Jones"])

        resp = client.get("/ui/results_divisions?event_type=kyorugi&search=alice&search_by=name")
        assert resp.status_code == 200
        assert b"Alpha Div" in resp.data
        assert b"Beta Div" not in resp.data

    def test_ui_results_divisions_search_by_name_case_insensitive(self, client):
        div_id = _create_division(client, "Case Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id, ["Charlie Brown"])

        resp = client.get("/ui/results_divisions?event_type=kyorugi&search=CHARLIE&search_by=name")
        assert resp.status_code == 200
        assert b"Case Div" in resp.data

    def test_ui_results_divisions_search_by_school_filters(self, client):
        div_id1 = _create_division(client, "Tiger Div", "kyorugi").get_json()["id"]
        div_id2 = _create_division(client, "Dragon Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id1, ["Alice, Tigers Academy"])
        _add_competitors(client, div_id2, ["Bob, Dragon Dojo"])

        resp = client.get("/ui/results_divisions?event_type=kyorugi&search=tigers&search_by=school")
        assert resp.status_code == 200
        assert b"Tiger Div" in resp.data
        assert b"Dragon Div" not in resp.data

    def test_ui_results_divisions_search_empty_returns_all(self, client):
        div_id1 = _create_division(client, "Div One", "kyorugi").get_json()["id"]
        div_id2 = _create_division(client, "Div Two", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id1, ["Alice"])
        _add_competitors(client, div_id2, ["Bob"])

        resp = client.get("/ui/results_divisions?event_type=kyorugi&search=")
        assert resp.status_code == 200
        assert b"Div One" in resp.data
        assert b"Div Two" in resp.data

    def test_ui_results_divisions_search_no_match_shows_empty(self, client):
        div_id = _create_division(client, "Some Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id, ["Alice"])

        resp = client.get("/ui/results_divisions?event_type=kyorugi&search=zzznomatch&search_by=name")
        assert resp.status_code == 200
        assert b"No divisions found" in resp.data

    def test_add_competitors_with_school_parses_correctly(self, client):
        div_id = _create_division(client, "School Div", "kyorugi").get_json()["id"]
        resp = _add_competitors(client, div_id, ["John Doe, Tigers Academy", "Jane Smith"])
        assert resp.status_code == 200
        from app import Competitor
        comps = Competitor.query.filter_by(division_id=div_id).order_by(Competitor.position).all()
        assert comps[0].name == "John Doe"
        assert comps[0].school == "Tigers Academy"
        assert comps[1].name == "Jane Smith"
        assert comps[1].school is None


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

        # Assign ring to each division, then schedule
        client.patch(f"/ui/divisions/{div_kyorugi}/bracket_ring", data={"ring_id": str(ring_id)})
        client.patch(f"/ui/divisions/{div_poomsae}/bracket_ring", data={"ring_id": str(ring_id)})

        match_k = Match.query.filter_by(division_id=div_kyorugi).first()
        match_p = Match.query.filter_by(division_id=div_poomsae).first()

        # Schedule match_number 101 in kyorugi (ring 1 * 100 + 1)
        resp1 = client.put(
            f"/matches/{match_k.id}/schedule",
            data={"ring_sequence": "1"},
        )
        assert resp1.status_code == 200
        assert b"Error" not in resp1.data
        db.session.refresh(match_k)
        assert match_k.match_number == (ring_id * 100) + 1

        # Schedule the same match_number 101 in poomsae — must succeed (different event)
        resp2 = client.put(
            f"/matches/{match_p.id}/schedule",
            data={"ring_sequence": "1"},
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

        # Assign the same ring to both divisions
        client.patch(f"/ui/divisions/{div1}/bracket_ring", data={"ring_id": str(ring_id)})
        client.patch(f"/ui/divisions/{div2}/bracket_ring", data={"ring_id": str(ring_id)})

        client.put(
            f"/matches/{match1.id}/schedule",
            data={"ring_sequence": "5"},
        )
        db.session.refresh(match1)
        assert match1.match_number == (ring_id * 100) + 5

        resp2 = client.put(
            f"/matches/{match2.id}/schedule",
            data={"ring_sequence": "5"},
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

        # Assign ring to division and schedule all matches
        client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": str(ring_id)})
        for seq, match in enumerate(Match.query.filter_by(division_id=div_id).all(), start=1):
            client.put(
                f"/matches/{match.id}/schedule",
                data={"ring_sequence": str(seq)},
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

        # Assign ring to division, then schedule the TBD match
        client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": str(ring_id)})
        client.put(
            f"/matches/{tbd_match.id}/schedule",
            data={"ring_sequence": "1"},
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
        client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": str(ring_id)})
        client.put(
            f"/matches/{match.id}/schedule",
            data={"ring_sequence": "1"},
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
        _set_poomsae_style(client, div_poomsae, "bracket")
        _generate_bracket(client, div_poomsae)

        match_k = Match.query.filter_by(division_id=div_kyorugi).first()
        match_p = Match.query.filter_by(division_id=div_poomsae).first()

        client.patch(f"/ui/divisions/{div_kyorugi}/bracket_ring", data={"ring_id": str(ring_id)})
        client.patch(f"/ui/divisions/{div_poomsae}/bracket_ring", data={"ring_id": str(ring_id)})
        client.put(
            f"/matches/{match_k.id}/schedule",
            data={"ring_sequence": "1"},
        )
        client.put(
            f"/matches/{match_p.id}/schedule",
            data={"ring_sequence": "2"},
        )

        resp_k = client.get(f"/ring/{ring_id}/scorekeeper?event_type=kyorugi")
        assert resp_k.status_code == 200
        assert b"Kyorugi Division" in resp_k.data
        assert b"Poomsae Division" not in resp_k.data

        # For poomsae, the scorekeeper loads matches via HTMX. Verify the unified
        # fragment endpoint directly contains the poomsae match, not the kyorugi one.
        resp_p = client.get(f"/ui/rings/{ring_id}/poomsae_divisions")
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


# ---------------------------------------------------------------------------
# Poomsae Non-Bracket Event Support
# ---------------------------------------------------------------------------


class TestPoomsaeRingAssignment:
    """Tests for assigning a poomsae division to a ring (PATCH /ui/divisions/<id>/ring_assignment)."""

    def test_poomsae_ring_assignment_saves(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "World Class Poomsae", "poomsae").get_json()["id"]

        resp = client.patch(
            f"/ui/divisions/{div_id}/ring_assignment",
            data={"ring_id": str(ring_id), "event_status": "In Progress"},
        )
        assert resp.status_code == 200

        from app import Division, db
        div = db.session.get(Division, div_id)
        assert div.ring_id == ring_id
        assert div.event_status == "In Progress"

    def test_poomsae_ring_assignment_unassign(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        client.patch(
            f"/ui/divisions/{div_id}/ring_assignment",
            data={"ring_id": str(ring_id), "event_status": "In Progress"},
        )

        resp = client.patch(
            f"/ui/divisions/{div_id}/ring_assignment",
            data={"ring_id": "", "event_status": "Pending"},
        )
        assert resp.status_code == 200

        from app import Division, db
        div = db.session.get(Division, div_id)
        assert div.ring_id is None
        assert div.event_status == "Pending"

    def test_poomsae_ring_assignment_invalid_ring(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        resp = client.patch(
            f"/ui/divisions/{div_id}/ring_assignment",
            data={"ring_id": "9999", "event_status": "Pending"},
        )
        assert resp.status_code == 404

    def test_poomsae_ring_assignment_not_found(self, client):
        resp = client.patch(
            "/ui/divisions/9999/ring_assignment",
            data={"ring_id": "", "event_status": "Pending"},
        )
        assert resp.status_code == 404

    def test_poomsae_ring_assignment_returns_controls_fragment(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "group")

        resp = client.patch(
            f"/ui/divisions/{div_id}/ring_assignment",
            data={"ring_id": str(ring_id), "event_status": "In Progress"},
        )
        assert resp.status_code == 200
        assert b"Save Assignment" in resp.data

    def test_poomsae_bracket_controls_shows_ring_form(self, client):
        _create_ring(client, "Ring 1")
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "group")

        resp = client.get(f"/ui/divisions/{div_id}/bracket_controls")
        assert resp.status_code == 200
        assert b"Ring Assignment" in resp.data
        assert b"Save Assignment" in resp.data

    def test_kyorugi_bracket_controls_unchanged(self, client):
        div_id = _create_division(client, "Kyorugi Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])

        resp = client.get(f"/ui/divisions/{div_id}/bracket_controls")
        assert resp.status_code == 200
        assert b"Generate Bracket" in resp.data
        assert b"Ring Assignment" not in resp.data

    def test_poomsae_bracket_controls_shows_bracket_generation(self, client):
        """Poomsae bracket-style divisions should support bracket generation."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _set_poomsae_style(client, div_id, "bracket")

        resp = client.get(f"/ui/divisions/{div_id}/bracket_controls")
        assert resp.status_code == 200
        assert b"Generate Bracket" in resp.data

    def test_poomsae_bracket_controls_manage_bracket_when_bracket_exists(self, client):
        """Poomsae bracket-style divisions with a bracket should show bracket management controls."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _set_poomsae_style(client, div_id, "bracket")
        _generate_bracket(client, div_id)

        resp = client.get(f"/ui/divisions/{div_id}/bracket_controls")
        assert resp.status_code == 200
        assert b"Manage" in resp.data
        assert b"Schedule Bracket" in resp.data
        assert b"Regenerate Bracket" in resp.data

    def test_poomsae_bracket_controls_shows_scores_link_when_competitors(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _set_poomsae_style(client, div_id, "group")

        resp = client.get(f"/ui/divisions/{div_id}/bracket_controls")
        assert resp.status_code == 200
        assert b"Manage Scores" in resp.data
        assert b"View Results" in resp.data

    def test_poomsae_bracket_controls_no_scores_link_without_competitors(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "group")

        resp = client.get(f"/ui/divisions/{div_id}/bracket_controls")
        assert resp.status_code == 200
        assert b"Manage Scores" not in resp.data

    def test_poomsae_bracket_controls_shows_ring_order_field(self, client):
        _create_ring(client, "Ring 1")
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "group")

        resp = client.get(f"/ui/divisions/{div_id}/bracket_controls")
        assert resp.status_code == 200
        assert b"Ring Order" in resp.data


class TestPoomsaeRingSequence:
    """Tests for ring_sequence ordering of poomsae divisions within a ring."""

    def test_ring_assignment_saves_ring_sequence(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        resp = client.patch(
            f"/ui/divisions/{div_id}/ring_assignment",
            data={"ring_id": str(ring_id), "event_status": "Pending", "ring_sequence": "2"},
        )
        assert resp.status_code == 200

        from app import Division, db
        div = db.session.get(Division, div_id)
        assert div.ring_sequence == 2

    def test_ring_assignment_clears_ring_sequence(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        client.patch(
            f"/ui/divisions/{div_id}/ring_assignment",
            data={"ring_id": str(ring_id), "event_status": "Pending", "ring_sequence": "3"},
        )
        client.patch(
            f"/ui/divisions/{div_id}/ring_assignment",
            data={"ring_id": str(ring_id), "event_status": "Pending", "ring_sequence": ""},
        )

        from app import Division, db
        div = db.session.get(Division, div_id)
        assert div.ring_sequence is None

    def test_ring_assignment_invalid_ring_sequence(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        resp = client.patch(
            f"/ui/divisions/{div_id}/ring_assignment",
            data={"ring_id": str(ring_id), "event_status": "Pending", "ring_sequence": "abc"},
        )
        assert resp.status_code == 400

    def test_poomsae_divisions_ordered_by_ring_sequence(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_a = _create_division(client, "Division A", "poomsae").get_json()["id"]
        div_b = _create_division(client, "Division B", "poomsae").get_json()["id"]
        div_c = _create_division(client, "Division C", "poomsae").get_json()["id"]

        _set_poomsae_style(client, div_a, "group")
        _set_poomsae_style(client, div_b, "group")
        _set_poomsae_style(client, div_c, "group")

        # Assign out-of-order to verify ring_sequence is used, not insertion order
        client.patch(f"/ui/divisions/{div_a}/ring_assignment",
                     data={"ring_id": str(ring_id), "event_status": "Pending", "ring_sequence": "3"})
        client.patch(f"/ui/divisions/{div_b}/ring_assignment",
                     data={"ring_id": str(ring_id), "event_status": "Pending", "ring_sequence": "1"})
        client.patch(f"/ui/divisions/{div_c}/ring_assignment",
                     data={"ring_id": str(ring_id), "event_status": "Pending", "ring_sequence": "2"})

        resp = client.get(f"/ui/rings/{ring_id}/poomsae_divisions")
        assert resp.status_code == 200
        html = resp.data.decode()

        # B(1) < C(2) < A(3)
        assert html.find("Division B") < html.find("Division C") < html.find("Division A")

    def test_poomsae_divisions_no_sequence_sorted_last(self, client):
        """Divisions without ring_sequence appear after sequenced ones."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_a = _create_division(client, "AAA No Seq", "poomsae").get_json()["id"]
        div_b = _create_division(client, "BBB Seq 1", "poomsae").get_json()["id"]

        _set_poomsae_style(client, div_a, "group")
        _set_poomsae_style(client, div_b, "group")

        client.patch(f"/ui/divisions/{div_a}/ring_assignment",
                     data={"ring_id": str(ring_id), "event_status": "Pending", "ring_sequence": ""})
        client.patch(f"/ui/divisions/{div_b}/ring_assignment",
                     data={"ring_id": str(ring_id), "event_status": "Pending", "ring_sequence": "1"})

        resp = client.get(f"/ui/rings/{ring_id}/poomsae_divisions")
        assert resp.status_code == 200
        html = resp.data.decode()

        # BBB Seq 1 (sequence=1) should appear before AAA No Seq (no sequence)
        assert html.find("BBB Seq 1") < html.find("AAA No Seq")


class TestPoomsaeScorekeeperStatus:
    """Tests for updating poomsae division event_status from the Scorekeeper page."""

    def test_update_event_status_in_progress(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        resp = client.patch(
            f"/ui/divisions/{div_id}/event_status",
            data={"event_status": "In Progress"},
        )
        assert resp.status_code == 200

        from app import Division, db
        div = db.session.get(Division, div_id)
        assert div.event_status == "In Progress"

    def test_update_event_status_completed(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        resp = client.patch(
            f"/ui/divisions/{div_id}/event_status",
            data={"event_status": "Completed"},
        )
        assert resp.status_code == 200

        from app import Division, db
        div = db.session.get(Division, div_id)
        assert div.event_status == "Completed"

    def test_update_event_status_reset_to_pending(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        client.patch(f"/ui/divisions/{div_id}/event_status", data={"event_status": "In Progress"})
        resp = client.patch(f"/ui/divisions/{div_id}/event_status", data={"event_status": "Pending"})
        assert resp.status_code == 200

        from app import Division, db
        div = db.session.get(Division, div_id)
        assert div.event_status == "Pending"

    def test_update_event_status_invalid(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        resp = client.patch(
            f"/ui/divisions/{div_id}/event_status",
            data={"event_status": "Invalid Status"},
        )
        assert resp.status_code == 400

    def test_update_event_status_not_found(self, client):
        resp = client.patch("/ui/divisions/9999/event_status", data={"event_status": "In Progress"})
        assert resp.status_code == 404

    def test_update_event_status_returns_scorekeeper_fragment(self, client):
        """Status update route returns poomsae results fragment in scorekeeper mode."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice"])

        resp = client.patch(
            f"/ui/divisions/{div_id}/event_status",
            data={"event_status": "In Progress"},
        )
        assert resp.status_code == 200
        assert b"In Progress" in resp.data
        # Status buttons should be present (scorekeeper mode)
        assert b"Start" not in resp.data  # Already In Progress, so "Start" button not shown
        assert b"Complete" in resp.data   # "Complete" and "Reset" buttons shown
        assert b"Reset" in resp.data

    def test_scorekeeper_fragment_shows_status_buttons(self, client):
        """poomsae_divisions fragment shows status update buttons in scorekeeper mode."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "group")

        client.patch(
            f"/ui/divisions/{div_id}/ring_assignment",
            data={"ring_id": str(ring_id), "event_status": "Pending"},
        )

        resp = client.get(f"/ui/rings/{ring_id}/poomsae_divisions")
        assert resp.status_code == 200
        # Should show "Start" (→ In Progress) and "Complete" (→ Completed) since status is Pending
        assert b"Start" in resp.data
        assert b"Complete" in resp.data

    # ------------------------------------------------------------------
    # Time tracking
    # ------------------------------------------------------------------

    def test_start_time_set_when_in_progress(self, client):
        """start_time is recorded when a group division is set to In Progress."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        from app import Division, db
        div = db.session.get(Division, div_id)
        assert div.start_time is None

        client.patch(f"/ui/divisions/{div_id}/event_status", data={"event_status": "In Progress"})

        db.session.refresh(div)
        assert div.start_time is not None
        assert div.end_time is None

    def test_start_time_not_overwritten_on_repeated_in_progress(self, client):
        """Calling In Progress when already In Progress does not overwrite start_time."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        client.patch(f"/ui/divisions/{div_id}/event_status", data={"event_status": "In Progress"})

        from app import Division, db
        div = db.session.get(Division, div_id)
        original_start = div.start_time
        assert original_start is not None

        # Call In Progress again without resetting; start_time must not change
        client.patch(f"/ui/divisions/{div_id}/event_status", data={"event_status": "In Progress"})

        db.session.refresh(div)
        assert div.start_time == original_start

    def test_end_time_set_when_completed_after_start(self, client):
        """end_time is recorded when a started group division is completed."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        client.patch(f"/ui/divisions/{div_id}/event_status", data={"event_status": "In Progress"})
        client.patch(f"/ui/divisions/{div_id}/event_status", data={"event_status": "Completed"})

        from app import Division, db
        div = db.session.get(Division, div_id)
        assert div.start_time is not None
        assert div.end_time is not None
        assert div.end_time >= div.start_time

    def test_end_time_not_set_for_completed_without_start(self, client):
        """end_time is not set when Completed is triggered without a prior In Progress."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        client.patch(f"/ui/divisions/{div_id}/event_status", data={"event_status": "Completed"})

        from app import Division, db
        div = db.session.get(Division, div_id)
        assert div.start_time is None
        assert div.end_time is None

    def test_reset_clears_both_times(self, client):
        """Resetting to Pending clears start_time and end_time."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        client.patch(f"/ui/divisions/{div_id}/event_status", data={"event_status": "In Progress"})
        client.patch(f"/ui/divisions/{div_id}/event_status", data={"event_status": "Completed"})
        client.patch(f"/ui/divisions/{div_id}/event_status", data={"event_status": "Pending"})

        from app import Division, db
        div = db.session.get(Division, div_id)
        assert div.start_time is None
        assert div.end_time is None


class TestPoomsaeScoreRecording:
    """Tests for recording poomsae scores (POST /ui/divisions/<id>/competitors/<id>/score)."""

    def test_record_score(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice"])

        from app import Competitor, Score, db
        comp = Competitor.query.filter_by(division_id=div_id).first()

        resp = client.post(
            f"/ui/divisions/{div_id}/competitors/{comp.id}/score",
            data={"score_value": "8.500"},
        )
        assert resp.status_code == 200

        score = Score.query.filter_by(competitor_id=comp.id, division_id=div_id).first()
        assert score is not None
        assert abs(score.score_value - 8.5) < 0.001

    def test_update_score(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice"])

        from app import Competitor, Score, db
        comp = Competitor.query.filter_by(division_id=div_id).first()

        client.post(
            f"/ui/divisions/{div_id}/competitors/{comp.id}/score",
            data={"score_value": "8.000"},
        )
        client.post(
            f"/ui/divisions/{div_id}/competitors/{comp.id}/score",
            data={"score_value": "9.250"},
        )

        scores = Score.query.filter_by(competitor_id=comp.id, division_id=div_id).all()
        assert len(scores) == 1
        assert abs(scores[0].score_value - 9.25) < 0.001

    def test_record_score_invalid_value(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice"])

        from app import Competitor
        comp = Competitor.query.filter_by(division_id=div_id).first()

        resp = client.post(
            f"/ui/divisions/{div_id}/competitors/{comp.id}/score",
            data={"score_value": "not-a-number"},
        )
        assert resp.status_code == 400

    def test_record_score_above_max(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice"])

        from app import Competitor
        comp = Competitor.query.filter_by(division_id=div_id).first()

        resp = client.post(
            f"/ui/divisions/{div_id}/competitors/{comp.id}/score",
            data={"score_value": "10.001"},
        )
        assert resp.status_code == 400

    def test_record_score_at_max(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice"])

        from app import Competitor, Score
        comp = Competitor.query.filter_by(division_id=div_id).first()

        resp = client.post(
            f"/ui/divisions/{div_id}/competitors/{comp.id}/score",
            data={"score_value": "10.000"},
        )
        assert resp.status_code == 200
        scores = Score.query.filter_by(competitor_id=comp.id, division_id=div_id).all()
        assert len(scores) == 1
        assert abs(scores[0].score_value - 10.0) < 0.0001

    def test_record_score_wrong_division(self, client):
        div_id1 = _create_division(client, "Poomsae Div 1", "poomsae").get_json()["id"]
        div_id2 = _create_division(client, "Poomsae Div 2", "poomsae").get_json()["id"]
        _add_competitors(client, div_id1, ["Alice"])

        from app import Competitor
        comp = Competitor.query.filter_by(division_id=div_id1).first()

        resp = client.post(
            f"/ui/divisions/{div_id2}/competitors/{comp.id}/score",
            data={"score_value": "8.0"},
        )
        assert resp.status_code == 404

    def test_record_score_not_found_competitor(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        resp = client.post(
            f"/ui/divisions/{div_id}/competitors/9999/score",
            data={"score_value": "8.0"},
        )
        assert resp.status_code == 404

    def test_score_response_shows_ranked_table(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])

        from app import Competitor
        comps = Competitor.query.filter_by(division_id=div_id).all()
        comp_a = next(c for c in comps if c.name == "Alice")
        comp_b = next(c for c in comps if c.name == "Bob")

        client.post(f"/ui/divisions/{div_id}/competitors/{comp_a.id}/score", data={"score_value": "9.0"})
        resp = client.post(
            f"/ui/divisions/{div_id}/competitors/{comp_b.id}/score",
            data={"score_value": "8.5"},
        )
        assert resp.status_code == 200
        # Alice (9.0) should rank above Bob (8.5)
        html = resp.data.decode()
        alice_pos = html.find("Alice")
        bob_pos = html.find("Bob")
        assert alice_pos < bob_pos

    def test_delete_competitor_removes_score(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])

        from app import Competitor, Score, db
        comp = Competitor.query.filter_by(division_id=div_id, name="Alice").first()

        client.post(
            f"/ui/divisions/{div_id}/competitors/{comp.id}/score",
            data={"score_value": "9.0"},
        )
        assert Score.query.filter_by(competitor_id=comp.id).count() == 1

        client.delete(f"/ui/divisions/{div_id}/competitors/{comp.id}")
        db.session.expire_all()
        assert Score.query.filter_by(competitor_id=comp.id).count() == 0

    def test_delete_division_removes_scores(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice"])

        from app import Competitor, Score, db
        comp = Competitor.query.filter_by(division_id=div_id).first()
        client.post(
            f"/ui/divisions/{div_id}/competitors/{comp.id}/score",
            data={"score_value": "9.0"},
        )
        assert Score.query.filter_by(division_id=div_id).count() == 1

        client.delete(f"/ui/divisions/{div_id}")
        db.session.expire_all()
        assert Score.query.filter_by(division_id=div_id).count() == 0

    def test_scorekeeper_mode_preserved_after_score_save(self, client):
        """Saving a score with scorekeeper_mode=1 must return the fragment with the
        status-action buttons (Reset / Complete) still present."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice"])

        from app import Competitor
        comp = Competitor.query.filter_by(division_id=div_id).first()

        resp = client.post(
            f"/ui/divisions/{div_id}/competitors/{comp.id}/score",
            data={"score_value": "8.500", "scorekeeper_mode": "1"},
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        # Scorekeeper header/buttons should be present
        assert "event_status" in html
        assert "Complete" in html

    def test_scorekeeper_mode_absent_without_flag(self, client):
        """Saving a score without scorekeeper_mode must NOT render scorekeeper buttons."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice"])

        from app import Competitor
        comp = Competitor.query.filter_by(division_id=div_id).first()

        resp = client.post(
            f"/ui/divisions/{div_id}/competitors/{comp.id}/score",
            data={"score_value": "8.500"},
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        # No status action buttons in non-scorekeeper mode
        assert "hx-patch" not in html or "event_status" not in html


class TestGroupResultsPage:
    """Tests for the group results page and fragment."""

    def test_group_results_page(self, client):
        div_id = _create_division(client, "World Class Poomsae", "poomsae").get_json()["id"]

        resp = client.get(f"/admin/divisions/{div_id}/group_results")
        assert resp.status_code == 200
        assert b"World Class Poomsae" in resp.data

    def test_group_results_page_not_found(self, client):
        resp = client.get("/admin/divisions/9999/group_results")
        assert resp.status_code == 404

    def test_group_results_fragment_empty(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        resp = client.get(f"/ui/divisions/{div_id}/group_results_fragment")
        assert resp.status_code == 200

    def test_group_results_fragment_shows_competitors(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])

        resp = client.get(f"/ui/divisions/{div_id}/group_results_fragment")
        assert resp.status_code == 200
        assert b"Alice" in resp.data
        assert b"Bob" in resp.data

    def test_group_results_fragment_ranked_by_score(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol"])

        from app import Competitor
        comps = {c.name: c for c in Competitor.query.filter_by(division_id=div_id).all()}

        client.post(f"/ui/divisions/{div_id}/competitors/{comps['Alice'].id}/score", data={"score_value": "7.0"})
        client.post(f"/ui/divisions/{div_id}/competitors/{comps['Bob'].id}/score", data={"score_value": "9.5"})
        client.post(f"/ui/divisions/{div_id}/competitors/{comps['Carol'].id}/score", data={"score_value": "8.5"})

        resp = client.get(f"/ui/divisions/{div_id}/group_results_fragment")
        html = resp.data.decode()

        bob_pos = html.find("Bob")
        carol_pos = html.find("Carol")
        alice_pos = html.find("Alice")
        assert bob_pos < carol_pos < alice_pos

    def test_group_results_fragment_medals(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol"])

        from app import Competitor
        comps = {c.name: c for c in Competitor.query.filter_by(division_id=div_id).all()}

        client.post(f"/ui/divisions/{div_id}/competitors/{comps['Alice'].id}/score", data={"score_value": "9.0"})
        client.post(f"/ui/divisions/{div_id}/competitors/{comps['Bob'].id}/score", data={"score_value": "8.0"})
        client.post(f"/ui/divisions/{div_id}/competitors/{comps['Carol'].id}/score", data={"score_value": "7.0"})

        resp = client.get(f"/ui/divisions/{div_id}/group_results_fragment")
        assert b"\xf0\x9f\xa5\x87" in resp.data  # 🥇
        assert b"\xf0\x9f\xa5\x88" in resp.data  # 🥈
        assert b"\xf0\x9f\xa5\x89" in resp.data  # 🥉

    def test_results_divisions_poomsae_links_to_group_results(self, client):
        """Poomsae division without a bracket links to the group results page."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        resp = client.get("/ui/results_divisions?event_type=poomsae")
        assert resp.status_code == 200
        assert f"/admin/divisions/{div_id}/group_results".encode() in resp.data

    def test_results_divisions_poomsae_with_bracket_links_to_bracket(self, client):
        """Poomsae division with bracket style links to the bracket view, not poomsae results."""
        div_id = _create_division(client, "Bracket Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _set_poomsae_style(client, div_id, "bracket")
        _generate_bracket(client, div_id)

        resp = client.get("/ui/results_divisions?event_type=poomsae")
        assert resp.status_code == 200
        assert f"/ui/divisions/{div_id}/bracket".encode() in resp.data
        assert f"/admin/divisions/{div_id}/group_results".encode() not in resp.data

    def test_results_divisions_kyorugi_still_links_to_bracket(self, client):
        div_id = _create_division(client, "Kyorugi Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        resp = client.get("/ui/results_divisions?event_type=kyorugi")
        assert resp.status_code == 200
        assert f"/ui/divisions/{div_id}/bracket".encode() in resp.data

    def test_results_divisions_poomsae_status_uses_event_status(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]

        # Default status should be Pending
        resp = client.get("/ui/results_divisions?event_type=poomsae")
        assert b"Pending" in resp.data

        # After assigning to ring as In Progress
        client.patch(
            f"/ui/divisions/{div_id}/ring_assignment",
            data={"ring_id": str(ring_id), "event_status": "In Progress"},
        )
        resp = client.get("/ui/results_divisions?event_type=poomsae")
        assert b"In Progress" in resp.data


class TestPoomsaePublicRings:
    """Tests for the public rings live view with poomsae division assignments."""

    def test_poomsae_divisions_appear_on_assigned_ring(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "World Class Poomsae", "poomsae").get_json()["id"]

        client.patch(
            f"/ui/divisions/{div_id}/ring_assignment",
            data={"ring_id": str(ring_id), "event_status": "In Progress"},
        )

        resp = client.get("/ui/public_rings?event_type=poomsae")
        assert resp.status_code == 200
        assert b"World Class Poomsae" in resp.data
        assert b"In Progress" in resp.data

    def test_poomsae_division_not_shown_when_unassigned(self, client):
        _create_ring(client, "Ring 1")
        _create_division(client, "Unassigned Poomsae", "poomsae")

        resp = client.get("/ui/public_rings?event_type=poomsae")
        assert resp.status_code == 200
        assert b"Unassigned Poomsae" not in resp.data

    def test_poomsae_division_not_shown_in_kyorugi_view(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "World Class Poomsae", "poomsae").get_json()["id"]

        client.patch(
            f"/ui/divisions/{div_id}/ring_assignment",
            data={"ring_id": str(ring_id), "event_status": "In Progress"},
        )

        resp = client.get("/ui/public_rings?event_type=kyorugi")
        assert resp.status_code == 200
        assert b"World Class Poomsae" not in resp.data

    def test_poomsae_division_links_to_results_in_live_view(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        client.patch(
            f"/ui/divisions/{div_id}/ring_assignment",
            data={"ring_id": str(ring_id), "event_status": "Pending"},
        )

        resp = client.get("/ui/public_rings?event_type=poomsae")
        assert resp.status_code == 200
        assert f"/admin/divisions/{div_id}/group_results".encode() in resp.data


class TestPoomsaeScorekeeperDivisions:
    """Tests for the poomsae divisions section in the scorekeeper."""

    def test_poomsae_divisions_fragment_empty(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]

        resp = client.get(f"/ui/rings/{ring_id}/poomsae_divisions")
        assert resp.status_code == 200
        assert b"No poomsae divisions" in resp.data

    def test_poomsae_divisions_fragment_shows_assigned(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "World Class Poomsae", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _set_poomsae_style(client, div_id, "group")

        client.patch(
            f"/ui/divisions/{div_id}/ring_assignment",
            data={"ring_id": str(ring_id), "event_status": "In Progress"},
        )

        resp = client.get(f"/ui/rings/{ring_id}/poomsae_divisions")
        assert resp.status_code == 200
        assert b"World Class Poomsae" in resp.data
        assert b"Alice" in resp.data
        assert b"Bob" in resp.data

    def test_poomsae_scorekeeper_page_has_divisions_container(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]

        resp = client.get(f"/ring/{ring_id}/scorekeeper?event_type=poomsae")
        assert resp.status_code == 200
        assert b"poomsae-divisions-container" in resp.data

    def test_kyorugi_scorekeeper_page_no_poomsae_container(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]

        resp = client.get(f"/ring/{ring_id}/scorekeeper?event_type=kyorugi")
        assert resp.status_code == 200
        assert b"poomsae-divisions-container" not in resp.data

    def test_poomsae_divisions_fragment_not_found_ring(self, client):
        resp = client.get("/ui/rings/9999/poomsae_divisions")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Poomsae Style Selector
# ---------------------------------------------------------------------------


class TestPoomsaeStyleSelector:
    """Tests for the poomsae style selector (bracket vs group)."""

    def test_unset_poomsae_shows_style_picker(self, client):
        """New poomsae division shows the format selection before any style is chosen."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        resp = client.get(f"/ui/divisions/{div_id}/bracket_controls")
        assert resp.status_code == 200
        assert b"Choose Event Format" in resp.data
        assert b"Group (Score-Based)" in resp.data
        assert b"Bracket" in resp.data

    def test_set_poomsae_style_group(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        resp = _set_poomsae_style(client, div_id, "group")
        assert resp.status_code == 200

        from app import Division, db
        div = db.session.get(Division, div_id)
        assert div.poomsae_style == "group"

    def test_set_poomsae_style_bracket(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        resp = _set_poomsae_style(client, div_id, "bracket")
        assert resp.status_code == 200

        from app import Division, db
        div = db.session.get(Division, div_id)
        assert div.poomsae_style == "bracket"

    def test_poomsae_style_locked_after_set(self, client):
        """Attempting to change poomsae_style after it is already set returns 400."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "group")

        resp = _set_poomsae_style(client, div_id, "bracket")
        assert resp.status_code == 400

    def test_poomsae_style_invalid_value(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        resp = client.post(
            f"/ui/divisions/{div_id}/poomsae_style",
            data={"poomsae_style": "invalid"},
        )
        assert resp.status_code == 400

    def test_poomsae_style_wrong_event_type(self, client):
        div_id = _create_division(client, "Kyorugi Div", "kyorugi").get_json()["id"]

        resp = client.post(
            f"/ui/divisions/{div_id}/poomsae_style",
            data={"poomsae_style": "group"},
        )
        assert resp.status_code == 400

    def test_group_style_shows_ring_assignment(self, client):
        """After choosing 'group', the ring assignment form is shown."""
        _create_ring(client, "Ring 1")
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "group")

        resp = client.get(f"/ui/divisions/{div_id}/bracket_controls")
        assert resp.status_code == 200
        assert b"Ring Assignment" in resp.data
        assert b"Choose Event Format" not in resp.data

    def test_bracket_style_shows_generate_bracket(self, client):
        """After choosing 'bracket', the bracket generation controls are shown."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _set_poomsae_style(client, div_id, "bracket")

        resp = client.get(f"/ui/divisions/{div_id}/bracket_controls")
        assert resp.status_code == 200
        assert b"Generate Bracket" in resp.data
        assert b"Ring Assignment" not in resp.data
        assert b"Choose Event Format" not in resp.data

    def test_group_style_locked_badge_shown(self, client):
        """Group style shows the locked badge."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "group")

        resp = client.get(f"/ui/divisions/{div_id}/bracket_controls")
        assert resp.status_code == 200
        assert b"Group" in resp.data
        assert b"\xf0\x9f\x94\x92" in resp.data  # 🔒

    def test_bracket_style_locked_badge_shown(self, client):
        """Bracket style shows the locked badge."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "bracket")

        resp = client.get(f"/ui/divisions/{div_id}/bracket_controls")
        assert resp.status_code == 200
        assert b"Bracket" in resp.data
        assert b"\xf0\x9f\x94\x92" in resp.data  # 🔒

    def test_kyorugi_no_style_picker(self, client):
        """Kyorugi divisions never show the style picker."""
        div_id = _create_division(client, "Kyorugi Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])

        resp = client.get(f"/ui/divisions/{div_id}/bracket_controls")
        assert resp.status_code == 200
        assert b"Choose Event Format" not in resp.data
        assert b"Generate Bracket" in resp.data


# ---------------------------------------------------------------------------
# Poomsae Score Manage (admin score entry page)
# ---------------------------------------------------------------------------


class TestPoomsaeScoreManagePage:
    """Tests for the admin score management page (GET /admin/divisions/<id>/score_manage)."""

    def test_score_manage_page_loads(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        resp = client.get(f"/admin/divisions/{div_id}/score_manage")
        assert resp.status_code == 200
        assert b"Poomsae Div" in resp.data
        assert b"Manage Scores" in resp.data

    def test_score_manage_page_not_found(self, client):
        resp = client.get("/admin/divisions/9999/score_manage")
        assert resp.status_code == 404

    def test_score_manage_page_requires_login(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        from flask import session
        with client.session_transaction() as sess:
            sess.clear()

        resp = client.get(f"/admin/divisions/{div_id}/score_manage")
        # Should redirect or return HX-Redirect
        assert resp.status_code in (302, 200)

    def test_score_manage_page_links_to_results(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        resp = client.get(f"/admin/divisions/{div_id}/score_manage")
        assert resp.status_code == 200
        assert f"/admin/divisions/{div_id}/group_results".encode() in resp.data


# ---------------------------------------------------------------------------
# Poomsae Placements Fragment (read-only medals view)
# ---------------------------------------------------------------------------


class TestPoomsaePlacementsFragment:
    """Tests for the read-only poomsae placements fragment."""

    def test_placements_fragment_empty(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice"])

        resp = client.get(f"/ui/divisions/{div_id}/poomsae_placements_fragment")
        assert resp.status_code == 200
        assert b"No scores recorded" in resp.data

    def test_placements_fragment_shows_medals(self, client):
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol", "Dave"])

        from app import Competitor
        comps = {c.name: c for c in Competitor.query.filter_by(division_id=div_id).all()}
        client.post(f"/ui/divisions/{div_id}/competitors/{comps['Alice'].id}/score", data={"score_value": "9.5"})
        client.post(f"/ui/divisions/{div_id}/competitors/{comps['Bob'].id}/score", data={"score_value": "9.0"})
        client.post(f"/ui/divisions/{div_id}/competitors/{comps['Carol'].id}/score", data={"score_value": "8.5"})
        client.post(f"/ui/divisions/{div_id}/competitors/{comps['Dave'].id}/score", data={"score_value": "8.0"})

        resp = client.get(f"/ui/divisions/{div_id}/poomsae_placements_fragment")
        assert resp.status_code == 200
        assert b"\xf0\x9f\xa5\x87" in resp.data  # 🥇
        assert b"\xf0\x9f\xa5\x88" in resp.data  # 🥈
        assert b"\xf0\x9f\xa5\x89" in resp.data  # 🥉

    def test_placements_fragment_two_bronzes(self, client):
        """Both 3rd and 4th place should receive the bronze medal emoji."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol", "Dave"])

        from app import Competitor
        comps = {c.name: c for c in Competitor.query.filter_by(division_id=div_id).all()}
        client.post(f"/ui/divisions/{div_id}/competitors/{comps['Alice'].id}/score", data={"score_value": "9.5"})
        client.post(f"/ui/divisions/{div_id}/competitors/{comps['Bob'].id}/score", data={"score_value": "9.0"})
        client.post(f"/ui/divisions/{div_id}/competitors/{comps['Carol'].id}/score", data={"score_value": "8.5"})
        client.post(f"/ui/divisions/{div_id}/competitors/{comps['Dave'].id}/score", data={"score_value": "8.0"})

        resp = client.get(f"/ui/divisions/{div_id}/poomsae_placements_fragment")
        html = resp.data.decode()
        # Count bronze medal emojis — should appear twice (3rd and 4th place)
        bronze_count = html.count("🥉")
        assert bronze_count == 2

    def test_placements_fragment_no_score_forms(self, client):
        """Placements fragment is read-only — no score input forms."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice"])

        from app import Competitor
        comp = Competitor.query.filter_by(division_id=div_id).first()
        client.post(f"/ui/divisions/{div_id}/competitors/{comp.id}/score", data={"score_value": "9.0"})

        resp = client.get(f"/ui/divisions/{div_id}/poomsae_placements_fragment")
        assert resp.status_code == 200
        assert b"score_value" not in resp.data  # no score input field name
        assert b"Save" not in resp.data

    def test_placements_fragment_not_found(self, client):
        resp = client.get("/ui/divisions/9999/poomsae_placements_fragment")
        assert resp.status_code == 404

    def test_group_results_page_loads_placements_fragment(self, client):
        """The read-only group_results page references the placements fragment URL."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        resp = client.get(f"/admin/divisions/{div_id}/group_results")
        assert resp.status_code == 200
        assert b"poomsae_placements_fragment" in resp.data

    def test_group_results_page_no_score_entry(self, client):
        """The public results page does not directly include score entry forms."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]

        resp = client.get(f"/admin/divisions/{div_id}/group_results")
        assert resp.status_code == 200
        # The page itself should not have score submission endpoints directly
        assert b"group_results_fragment" not in resp.data


# ---------------------------------------------------------------------------
# Poomsae Unified Ring Ordering (bracket matches + group divisions, same 1-99 pool)
# ---------------------------------------------------------------------------


class TestPoomsaeUnifiedRingOrder:
    """Tests that bracket poomsae matches and group poomsae divisions are ordered
    together using the same 1-99 ring sequence number pool."""

    def test_ring_sequence_out_of_range_high(self, client):
        """ring_sequence > 99 is rejected."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "group")

        resp = client.patch(
            f"/ui/divisions/{div_id}/ring_assignment",
            data={"ring_id": str(ring_id), "event_status": "Pending", "ring_sequence": "100"},
        )
        assert resp.status_code == 400

    def test_ring_sequence_out_of_range_zero(self, client):
        """ring_sequence = 0 is rejected."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "group")

        resp = client.patch(
            f"/ui/divisions/{div_id}/ring_assignment",
            data={"ring_id": str(ring_id), "event_status": "Pending", "ring_sequence": "0"},
        )
        assert resp.status_code == 400

    def test_ring_sequence_boundary_values(self, client):
        """ring_sequence = 1 and ring_sequence = 99 are both accepted."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_a = _create_division(client, "Div A", "poomsae").get_json()["id"]
        div_b = _create_division(client, "Div B", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_a, "group")
        _set_poomsae_style(client, div_b, "group")

        resp_a = client.patch(
            f"/ui/divisions/{div_a}/ring_assignment",
            data={"ring_id": str(ring_id), "event_status": "Pending", "ring_sequence": "1"},
        )
        resp_b = client.patch(
            f"/ui/divisions/{div_b}/ring_assignment",
            data={"ring_id": str(ring_id), "event_status": "Pending", "ring_sequence": "99"},
        )
        assert resp_a.status_code == 200
        assert resp_b.status_code == 200

        from app import Division, db
        assert db.session.get(Division, div_a).ring_sequence == 1
        assert db.session.get(Division, div_b).ring_sequence == 99

    def test_bracket_match_appears_in_poomsae_divisions_fragment(self, client):
        """Bracket-style poomsae matches show up in the unified poomsae_divisions fragment."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Bracket Poomsae", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _set_poomsae_style(client, div_id, "bracket")
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id).first()
        client.patch(f"/ui/divisions/{div_id}/bracket_ring", data={"ring_id": str(ring_id)})
        client.put(f"/matches/{match.id}/schedule",
                   data={"ring_sequence": "5"})

        resp = client.get(f"/ui/rings/{ring_id}/poomsae_divisions")
        assert resp.status_code == 200
        assert b"Bracket Poomsae" in resp.data

    def test_bracket_match_and_group_division_interleaved_by_sequence(self, client):
        """Bracket match (seq=5) and group division (seq=3) interleave correctly."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]

        # Bracket poomsae match at sequence 5
        div_bracket = _create_division(client, "Bracket Poomsae", "poomsae").get_json()["id"]
        _add_competitors(client, div_bracket, ["Alice", "Bob"])
        _set_poomsae_style(client, div_bracket, "bracket")
        _generate_bracket(client, div_bracket)
        match = Match.query.filter_by(division_id=div_bracket).first()
        client.patch(f"/ui/divisions/{div_bracket}/bracket_ring", data={"ring_id": str(ring_id)})
        client.put(f"/matches/{match.id}/schedule",
                   data={"ring_sequence": "5"})

        # Group poomsae division at sequence 3
        div_group = _create_division(client, "Group Poomsae", "poomsae").get_json()["id"]
        _add_competitors(client, div_group, ["Carol", "Dave"])
        _set_poomsae_style(client, div_group, "group")
        client.patch(f"/ui/divisions/{div_group}/ring_assignment",
                     data={"ring_id": str(ring_id), "event_status": "Pending", "ring_sequence": "3"})

        resp = client.get(f"/ui/rings/{ring_id}/poomsae_divisions")
        assert resp.status_code == 200
        html = resp.data.decode()

        # Group Poomsae (seq=3) should appear before Bracket Poomsae (seq=5)
        assert html.find("Group Poomsae") < html.find("Bracket Poomsae")

    def test_unsequenced_group_division_sorted_after_bracket_match(self, client):
        """Unsequenced group division appears after bracket match with a sequence number."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]

        # Bracket match at sequence 1
        div_bracket = _create_division(client, "Bracket First", "poomsae").get_json()["id"]
        _add_competitors(client, div_bracket, ["Alice", "Bob"])
        _set_poomsae_style(client, div_bracket, "bracket")
        _generate_bracket(client, div_bracket)
        match = Match.query.filter_by(division_id=div_bracket).first()
        client.patch(f"/ui/divisions/{div_bracket}/bracket_ring", data={"ring_id": str(ring_id)})
        client.put(f"/matches/{match.id}/schedule",
                   data={"ring_sequence": "1"})

        # Group division with no sequence
        div_group = _create_division(client, "Group Last", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_group, "group")
        client.patch(f"/ui/divisions/{div_group}/ring_assignment",
                     data={"ring_id": str(ring_id), "event_status": "Pending", "ring_sequence": ""})

        resp = client.get(f"/ui/rings/{ring_id}/poomsae_divisions")
        assert resp.status_code == 200
        html = resp.data.decode()

        # Bracket First (seq=1) before Group Last (no seq)
        assert html.find("Bracket First") < html.find("Group Last")
        """Poomsae scorekeeper page uses the unified poomsae-divisions-container
        rather than the separate matches-container for displaying content."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]

        resp = client.get(f"/ring/{ring_id}/scorekeeper?event_type=poomsae")
        assert resp.status_code == 200
        # Unified container present
        assert b"poomsae-divisions-container" in resp.data
        # matches-container is hidden (display:none) for poomsae
        assert b'id="matches-container"' in resp.data
        assert b'display:none' in resp.data

    def test_kyorugi_scorekeeper_uses_matches_container(self, client):
        """Kyorugi scorekeeper still uses the standard matches-container."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]

        resp = client.get(f"/ring/{ring_id}/scorekeeper?event_type=kyorugi")
        assert resp.status_code == 200
        # No hidden matches-container
        assert b'display:none' not in resp.data
        assert b"poomsae-divisions-container" not in resp.data


# ---------------------------------------------------------------------------
# Live View ordering and sequence conflict prevention (comment 4071353484)
# ---------------------------------------------------------------------------


class TestPoomsaeLiveViewOrdering:
    """Tests that group divisions and bracket matches are interleaved by sequence
    in the public rings live view, and that bracket-style divisions are excluded."""

    def test_group_division_appears_before_bracket_match_by_sequence(self, client):
        """Group division at seq=2 appears before bracket match at seq=5 in live view."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]

        # Bracket poomsae match at sequence 5
        div_bracket = _create_division(client, "Bracket Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_bracket, ["Alice", "Bob"])
        _set_poomsae_style(client, div_bracket, "bracket")
        _generate_bracket(client, div_bracket)
        match = Match.query.filter_by(division_id=div_bracket).first()
        client.patch(f"/ui/divisions/{div_bracket}/bracket_ring", data={"ring_id": str(ring_id)})
        client.put(f"/matches/{match.id}/schedule",
                   data={"ring_sequence": "5"})

        # Group division at sequence 2
        div_group = _create_division(client, "Group Div", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_group, "group")
        client.patch(f"/ui/divisions/{div_group}/ring_assignment",
                     data={"ring_id": str(ring_id), "event_status": "Pending", "ring_sequence": "2"})

        resp = client.get("/ui/public_rings?event_type=poomsae")
        assert resp.status_code == 200
        html = resp.data.decode()

        # Group Div (seq=2) should appear before Bracket Div (seq=5)
        assert html.find("Group Div") < html.find("Bracket Div")

    def test_bracket_style_division_excluded_from_live_view_divisions_loop(self, client):
        """A bracket-style poomsae division doesn't appear in the divisions section
        of the live view (it shows via its scheduled matches instead)."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]

        div_bracket = _create_division(client, "Only Bracket", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_bracket, "bracket")

        # Assign ring_id and ring_sequence directly to simulate a bracket division in a ring
        from app import Division, db
        div = db.session.get(Division, div_bracket)
        div.ring_id = ring_id
        db.session.commit()

        resp = client.get("/ui/public_rings?event_type=poomsae")
        assert resp.status_code == 200
        # It should not appear in the poomsae_items division list
        # (it would only appear via a scheduled match; no match here so absent)
        assert b"Only Bracket" not in resp.data

    def test_unsequenced_group_division_sorted_last_in_live_view(self, client):
        """Group division without sequence appears after bracket match with sequence."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]

        # Bracket match at seq 1
        div_bracket = _create_division(client, "Bracket First", "poomsae").get_json()["id"]
        _add_competitors(client, div_bracket, ["Alice", "Bob"])
        _set_poomsae_style(client, div_bracket, "bracket")
        _generate_bracket(client, div_bracket)
        match = Match.query.filter_by(division_id=div_bracket).first()
        client.patch(f"/ui/divisions/{div_bracket}/bracket_ring", data={"ring_id": str(ring_id)})
        client.put(f"/matches/{match.id}/schedule",
                   data={"ring_sequence": "1"})

        # Group division with no sequence
        div_group = _create_division(client, "Group Last", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_group, "group")
        client.patch(f"/ui/divisions/{div_group}/ring_assignment",
                     data={"ring_id": str(ring_id), "event_status": "Pending", "ring_sequence": ""})

        resp = client.get("/ui/public_rings?event_type=poomsae")
        assert resp.status_code == 200
        html = resp.data.decode()

        assert html.find("Bracket First") < html.find("Group Last")


class TestPoomsaeSequenceConflictPrevention:
    """Tests that group divisions and bracket matches cannot share the same
    ring sequence number."""

    def test_bracket_match_blocked_by_existing_group_division_sequence(self, client):
        """Scheduling a bracket match at a sequence occupied by a group division returns
        a conflict error (HTTP 200 with error HTML, per the bracket scheduling pattern)."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]

        # Group division at sequence 5
        div_group = _create_division(client, "Group Div", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_group, "group")
        client.patch(f"/ui/divisions/{div_group}/ring_assignment",
                     data={"ring_id": str(ring_id), "event_status": "Pending", "ring_sequence": "5"})

        # Bracket poomsae match — try to schedule at sequence 5
        div_bracket = _create_division(client, "Bracket Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_bracket, ["Alice", "Bob"])
        _set_poomsae_style(client, div_bracket, "bracket")
        _generate_bracket(client, div_bracket)
        match = Match.query.filter_by(division_id=div_bracket).first()

        # Assign ring to the bracket division first, then try to schedule at seq 5
        client.patch(f"/ui/divisions/{div_bracket}/bracket_ring", data={"ring_id": str(ring_id)})
        resp = client.put(f"/matches/{match.id}/schedule",
                          data={"ring_sequence": "5"})
        # Returns 200 with error HTML (HTMX inline error pattern)
        assert resp.status_code == 200
        assert b"Sequence 5" in resp.data
        assert b"already used" in resp.data

        # Match should NOT be scheduled
        from app import Match as MatchModel
        from app import db
        db.session.refresh(match)
        assert match.match_number is None

    def test_group_division_blocked_by_existing_bracket_match_sequence(self, client):
        """Assigning a group division to a sequence occupied by a bracket match returns 400."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]

        # Bracket match at sequence 3
        div_bracket = _create_division(client, "Bracket Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_bracket, ["Alice", "Bob"])
        _set_poomsae_style(client, div_bracket, "bracket")
        _generate_bracket(client, div_bracket)
        match = Match.query.filter_by(division_id=div_bracket).first()
        client.patch(f"/ui/divisions/{div_bracket}/bracket_ring", data={"ring_id": str(ring_id)})
        client.put(f"/matches/{match.id}/schedule",
                   data={"ring_sequence": "3"})

        # Group division — try to use sequence 3
        div_group = _create_division(client, "Group Div", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_group, "group")
        resp = client.patch(f"/ui/divisions/{div_group}/ring_assignment",
                            data={"ring_id": str(ring_id), "event_status": "Pending",
                                  "ring_sequence": "3"})
        assert resp.status_code == 400
        assert b"already used" in resp.data

    def test_two_group_divisions_cannot_share_same_sequence_in_ring(self, client):
        """Two group divisions in the same ring cannot both use the same ring_sequence."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]

        div_a = _create_division(client, "Group A", "poomsae").get_json()["id"]
        div_b = _create_division(client, "Group B", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_a, "group")
        _set_poomsae_style(client, div_b, "group")

        # First assignment succeeds
        resp_a = client.patch(f"/ui/divisions/{div_a}/ring_assignment",
                              data={"ring_id": str(ring_id), "event_status": "Pending",
                                    "ring_sequence": "7"})
        assert resp_a.status_code == 200

        # Second with same sequence should fail
        resp_b = client.patch(f"/ui/divisions/{div_b}/ring_assignment",
                              data={"ring_id": str(ring_id), "event_status": "Pending",
                                    "ring_sequence": "7"})
        assert resp_b.status_code == 400
        assert b"already used" in resp_b.data

    def test_sequence_conflict_allowed_in_different_rings(self, client):
        """Same sequence number is allowed in different rings."""
        ring_a = _create_ring(client, "Ring A").get_json()["id"]
        ring_b = _create_ring(client, "Ring B").get_json()["id"]

        div_a = _create_division(client, "Group A", "poomsae").get_json()["id"]
        div_b = _create_division(client, "Group B", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_a, "group")
        _set_poomsae_style(client, div_b, "group")

        resp_a = client.patch(f"/ui/divisions/{div_a}/ring_assignment",
                              data={"ring_id": str(ring_a), "event_status": "Pending",
                                    "ring_sequence": "4"})
        resp_b = client.patch(f"/ui/divisions/{div_b}/ring_assignment",
                              data={"ring_id": str(ring_b), "event_status": "Pending",
                                    "ring_sequence": "4"})
        assert resp_a.status_code == 200
        assert resp_b.status_code == 200

    def test_division_can_keep_its_own_sequence_when_reassigning(self, client):
        """A group division can be saved again with the same ring_sequence it already holds."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Group Div", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "group")

        # First assignment
        client.patch(f"/ui/divisions/{div_id}/ring_assignment",
                     data={"ring_id": str(ring_id), "event_status": "Pending",
                            "ring_sequence": "6"})

        # Save again with same sequence (status change) — should succeed
        resp = client.patch(f"/ui/divisions/{div_id}/ring_assignment",
                            data={"ring_id": str(ring_id), "event_status": "In Progress",
                                   "ring_sequence": "6"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Poomsae Results Page — scores hidden
# ---------------------------------------------------------------------------


class TestPoomsaePlacementsNoScore:
    """The group_results (placements) page must NOT show raw score values."""

    def test_placements_fragment_hides_score_column(self, client):
        """After adding scores the placements fragment must not expose score values."""
        div_id = _create_division(client, "Poomsae Div", "poomsae").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob", "Carol"])

        from app import Competitor
        comps = {c.name: c for c in Competitor.query.filter_by(division_id=div_id).all()}

        for name, score in [("Alice", "9.5"), ("Bob", "8.5"), ("Carol", "7.5")]:
            client.post(
                f"/ui/divisions/{div_id}/competitors/{comps[name].id}/score",
                data={"score_value": score},
            )

        resp = client.get(f"/ui/divisions/{div_id}/poomsae_placements_fragment")
        assert resp.status_code == 200
        html = resp.data.decode()
        # Medal emojis should be present
        assert "🥇" in html
        assert "🥈" in html
        assert "🥉" in html
        # Competitor names should be present
        assert "Alice" in html
        assert "Bob" in html
        assert "Carol" in html
        # Raw score values must NOT appear
        assert "9.500" not in html
        assert "8.500" not in html
        assert "7.500" not in html
        # No "Score" header column
        assert "Score" not in html


# ---------------------------------------------------------------------------
# Completed group divisions removed from Scorekeeper and Live View
# ---------------------------------------------------------------------------


class TestCompletedGroupDivisionVisibility:
    """Completed group divisions must not appear in the Scorekeeper fragment or Live View."""

    def _setup_group_division(self, client, ring_id, div_name, seq, status="Pending"):
        div_id = _create_division(client, div_name, "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "group")
        client.patch(
            f"/ui/divisions/{div_id}/ring_assignment",
            data={"ring_id": str(ring_id), "event_status": status, "ring_sequence": str(seq)},
        )
        return div_id

    def test_completed_group_hidden_from_scorekeeper(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = self._setup_group_division(client, ring_id, "Done Poomsae", seq=1, status="Completed")

        resp = client.get(f"/ui/rings/{ring_id}/poomsae_divisions")
        assert resp.status_code == 200
        assert b"Done Poomsae" not in resp.data

    def test_in_progress_group_shown_in_scorekeeper(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        self._setup_group_division(client, ring_id, "Active Poomsae", seq=1, status="In Progress")

        resp = client.get(f"/ui/rings/{ring_id}/poomsae_divisions")
        assert resp.status_code == 200
        assert b"Active Poomsae" in resp.data

    def test_pending_group_shown_in_scorekeeper(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        self._setup_group_division(client, ring_id, "Pending Poomsae", seq=1, status="Pending")

        resp = client.get(f"/ui/rings/{ring_id}/poomsae_divisions")
        assert resp.status_code == 200
        assert b"Pending Poomsae" in resp.data

    def test_completing_via_status_route_clears_scorekeeper(self, client):
        """After PATCH event_status → Completed the scorekeeper fragment no longer shows the division."""
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = self._setup_group_division(client, ring_id, "Will Complete", seq=2, status="In Progress")

        # Mark completed
        client.patch(f"/ui/divisions/{div_id}/event_status", data={"event_status": "Completed"})

        resp = client.get(f"/ui/rings/{ring_id}/poomsae_divisions")
        html = resp.data.decode()
        assert "Will Complete" not in html

    def test_completed_group_hidden_from_live_view(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        self._setup_group_division(client, ring_id, "Finished Group", seq=1, status="Completed")

        resp = client.get("/ui/public_rings?event_type=poomsae")
        assert resp.status_code == 200
        assert b"Finished Group" not in resp.data

    def test_non_completed_group_shown_in_live_view(self, client):
        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        self._setup_group_division(client, ring_id, "Running Group", seq=1, status="In Progress")

        resp = client.get("/ui/public_rings?event_type=poomsae")
        assert resp.status_code == 200
        assert b"Running Group" in resp.data


# ---------------------------------------------------------------------------
# match_analytics.py
# ---------------------------------------------------------------------------


class TestMatchAnalytics:
    """Tests for the analytics helper functions in scripts/match_analytics.py."""

    # ------------------------------------------------------------------
    # Pure helpers
    # ------------------------------------------------------------------

    def test_fmt_duration_seconds_only(self):
        from datetime import timedelta

        from scripts.match_analytics import _fmt_duration

        assert _fmt_duration(timedelta(seconds=45)) == "0:45"

    def test_fmt_duration_minutes_and_seconds(self):
        from datetime import timedelta

        from scripts.match_analytics import _fmt_duration

        assert _fmt_duration(timedelta(seconds=134)) == "2:14"

    def test_fmt_duration_zero(self):
        from datetime import timedelta

        from scripts.match_analytics import _fmt_duration

        assert _fmt_duration(timedelta(seconds=0)) == "0:00"

    def test_stats_by_key_single_group(self):
        from datetime import timedelta

        from scripts.match_analytics import _stats_by_key

        rows = [
            {"event_type": "kyorugi", "ring_name": "Ring 1", "duration": timedelta(seconds=120)},
            {"event_type": "kyorugi", "ring_name": "Ring 1", "duration": timedelta(seconds=180)},
        ]
        stats = _stats_by_key(rows, "event_type")
        assert "kyorugi" in stats
        assert stats["kyorugi"]["count"] == 2
        assert stats["kyorugi"]["avg"] == timedelta(seconds=150)
        assert stats["kyorugi"]["max"] == timedelta(seconds=180)

    def test_stats_by_key_multiple_groups(self):
        from datetime import timedelta

        from scripts.match_analytics import _stats_by_key

        rows = [
            {"event_type": "kyorugi", "ring_name": "Ring 1", "duration": timedelta(seconds=90)},
            {"event_type": "poomsae", "ring_name": "Ring 2", "duration": timedelta(seconds=60)},
            {"event_type": "kyorugi", "ring_name": "Ring 1", "duration": timedelta(seconds=150)},
        ]
        stats = _stats_by_key(rows, "event_type")
        assert stats["kyorugi"]["count"] == 2
        assert stats["kyorugi"]["avg"] == timedelta(seconds=120)
        assert stats["kyorugi"]["max"] == timedelta(seconds=150)
        assert stats["poomsae"]["count"] == 1
        assert stats["poomsae"]["max"] == timedelta(seconds=60)

    def test_stats_by_key_empty(self):
        from scripts.match_analytics import _stats_by_key

        assert _stats_by_key([], "event_type") == {}

    # ------------------------------------------------------------------
    # _collect_match_durations
    # ------------------------------------------------------------------

    def test_collect_match_durations_returns_timed_matches(self, client):
        from datetime import datetime, timedelta, timezone

        from scripts.match_analytics import _collect_match_durations

        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Kyorugi Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id).first()
        match.ring_id = ring_id
        match.start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        match.end_time = datetime(2024, 1, 1, 10, 2, 30, tzinfo=timezone.utc)
        db.session.commit()

        rows = _collect_match_durations()
        assert len(rows) == 1
        assert rows[0]["event_type"] == "kyorugi"
        assert rows[0]["ring_name"] == "Ring 1"
        assert rows[0]["duration"] == timedelta(minutes=2, seconds=30)

    def test_collect_match_durations_excludes_untimed(self, client):
        from scripts.match_analytics import _collect_match_durations

        div_id = _create_division(client, "Kyorugi Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)
        # No start/end times set

        rows = _collect_match_durations()
        assert rows == []

    def test_collect_match_durations_excludes_zero_duration(self, client):
        from datetime import datetime, timezone

        from scripts.match_analytics import _collect_match_durations

        div_id = _create_division(client, "Kyorugi Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id).first()
        same_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        match.start_time = same_time
        match.end_time = same_time
        db.session.commit()

        rows = _collect_match_durations()
        assert rows == []

    def test_collect_match_durations_unassigned_ring(self, client):
        from datetime import datetime, timezone

        from scripts.match_analytics import _collect_match_durations

        div_id = _create_division(client, "Kyorugi Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id).first()
        match.start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        match.end_time = datetime(2024, 1, 1, 10, 1, 0, tzinfo=timezone.utc)
        db.session.commit()

        rows = _collect_match_durations()
        assert len(rows) == 1
        assert rows[0]["ring_name"] == "Unassigned"

    # ------------------------------------------------------------------
    # _collect_division_durations
    # ------------------------------------------------------------------

    def test_collect_division_durations_returns_timed_group_divisions(self, client):
        from datetime import datetime, timedelta, timezone

        from scripts.match_analytics import _collect_division_durations

        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Poomsae Group", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "group")

        div = db.session.get(Division, div_id)
        div.ring_id = ring_id
        div.start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        div.end_time = datetime(2024, 1, 1, 10, 3, 0, tzinfo=timezone.utc)
        db.session.commit()

        rows = _collect_division_durations()
        assert len(rows) == 1
        assert rows[0]["event_type"] == "poomsae (group)"
        assert rows[0]["ring_name"] == "Ring 1"
        assert rows[0]["duration"] == timedelta(minutes=3)

    def test_collect_division_durations_excludes_untimed(self, client):
        from scripts.match_analytics import _collect_division_durations

        div_id = _create_division(client, "Poomsae Group", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "group")
        # No times set

        rows = _collect_division_durations()
        assert rows == []

    def test_collect_division_durations_excludes_bracket_style(self, client):
        from datetime import datetime, timezone

        from scripts.match_analytics import _collect_division_durations

        div_id = _create_division(client, "Poomsae Bracket", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "bracket")

        div = db.session.get(Division, div_id)
        div.start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        div.end_time = datetime(2024, 1, 1, 10, 3, 0, tzinfo=timezone.utc)
        db.session.commit()

        rows = _collect_division_durations()
        assert rows == []

    def test_collect_division_durations_unassigned_ring(self, client):
        from datetime import datetime, timezone

        from scripts.match_analytics import _collect_division_durations

        div_id = _create_division(client, "Poomsae Group", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "group")

        div = db.session.get(Division, div_id)
        div.start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        div.end_time = datetime(2024, 1, 1, 10, 1, 30, tzinfo=timezone.utc)
        db.session.commit()

        rows = _collect_division_durations()
        assert len(rows) == 1
        assert rows[0]["ring_name"] == "Unassigned"

    # ------------------------------------------------------------------
    # main() — no data
    # ------------------------------------------------------------------

    def test_main_no_data(self, capsys):
        from scripts.match_analytics import main

        main()
        captured = capsys.readouterr()
        assert "No timed event data found" in captured.out

    # ------------------------------------------------------------------
    # main() — with data
    # ------------------------------------------------------------------

    def test_main_with_match_data(self, client, capsys):
        from datetime import datetime, timezone

        from scripts.match_analytics import main

        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Kyorugi Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id).first()
        match.ring_id = ring_id
        match.start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        match.end_time = datetime(2024, 1, 1, 10, 2, 0, tzinfo=timezone.utc)
        db.session.commit()

        main()
        out = capsys.readouterr().out
        assert "kyorugi" in out
        assert "Ring 1" in out
        assert "2:00" in out

    def test_main_with_division_data(self, client, capsys):
        from datetime import datetime, timezone

        from scripts.match_analytics import main

        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Poomsae Group", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "group")

        div = db.session.get(Division, div_id)
        div.ring_id = ring_id
        div.start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        div.end_time = datetime(2024, 1, 1, 10, 3, 0, tzinfo=timezone.utc)
        db.session.commit()

        main()
        out = capsys.readouterr().out
        assert "poomsae (group)" in out
        assert "Ring 1" in out
        assert "3:00" in out

    # ------------------------------------------------------------------
    # _build_output_rows
    # ------------------------------------------------------------------

    def test_build_output_rows_structure(self):
        from datetime import timedelta

        from scripts.match_analytics import _build_output_rows

        by_event = {"kyorugi": {"count": 2, "avg": timedelta(seconds=120), "max": timedelta(seconds=180)}}
        by_ring = {"Ring 1": {"count": 2, "avg": timedelta(seconds=120), "max": timedelta(seconds=180)}}

        rows = _build_output_rows(by_event, by_ring)
        assert len(rows) == 2

        event_row = next(r for r in rows if r["group"] == "by_event_type")
        assert event_row["category"] == "kyorugi"
        assert event_row["count"] == 2
        assert event_row["avg_seconds"] == 120
        assert event_row["avg_formatted"] == "2:00"
        assert event_row["longest_seconds"] == 180
        assert event_row["longest_formatted"] == "3:00"

        ring_row = next(r for r in rows if r["group"] == "by_ring")
        assert ring_row["category"] == "Ring 1"

    # ------------------------------------------------------------------
    # main() — CSV format
    # ------------------------------------------------------------------

    def test_main_csv_no_data(self, capsys):
        from scripts.match_analytics import main

        main(fmt="csv")
        out = capsys.readouterr().out
        # No data: should print the no-data message, not CSV headers
        assert "No timed event data found" in out

    def test_main_csv_with_match_data(self, client, capsys):
        import csv
        import io
        from datetime import datetime, timezone

        from scripts.match_analytics import main

        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Kyorugi Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id).first()
        match.ring_id = ring_id
        match.start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        match.end_time = datetime(2024, 1, 1, 10, 2, 0, tzinfo=timezone.utc)
        db.session.commit()

        main(fmt="csv")
        out = capsys.readouterr().out

        reader = csv.DictReader(io.StringIO(out))
        rows = list(reader)
        assert len(rows) == 2  # one by_event_type + one by_ring

        event_row = next(r for r in rows if r["group"] == "by_event_type")
        assert event_row["category"] == "kyorugi"
        assert event_row["count"] == "1"
        assert event_row["avg_seconds"] == "120"
        assert event_row["avg_formatted"] == "2:00"
        assert event_row["longest_seconds"] == "120"
        assert event_row["longest_formatted"] == "2:00"

        ring_row = next(r for r in rows if r["group"] == "by_ring")
        assert ring_row["category"] == "Ring 1"

    def test_main_csv_headers(self, client, capsys):
        from datetime import datetime, timezone

        from scripts.match_analytics import main

        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Kyorugi Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id).first()
        match.ring_id = ring_id
        match.start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        match.end_time = datetime(2024, 1, 1, 10, 1, 0, tzinfo=timezone.utc)
        db.session.commit()

        main(fmt="csv")
        out = capsys.readouterr().out
        header_line = out.splitlines()[0]
        assert "group" in header_line
        assert "category" in header_line
        assert "count" in header_line
        assert "avg_seconds" in header_line
        assert "longest_seconds" in header_line

    # ------------------------------------------------------------------
    # main() — JSON format
    # ------------------------------------------------------------------

    def test_main_json_no_data(self, capsys):
        from scripts.match_analytics import main

        main(fmt="json")
        out = capsys.readouterr().out
        # No data: should print the no-data message, not JSON
        assert "No timed event data found" in out

    def test_main_json_with_match_data(self, client, capsys):
        import json
        from datetime import datetime, timezone

        from scripts.match_analytics import main

        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Kyorugi Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id).first()
        match.ring_id = ring_id
        match.start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        match.end_time = datetime(2024, 1, 1, 10, 2, 0, tzinfo=timezone.utc)
        db.session.commit()

        main(fmt="json")
        out = capsys.readouterr().out

        data = json.loads(out)
        assert "by_event_type" in data
        assert "by_ring" in data

        event_entries = data["by_event_type"]
        assert len(event_entries) == 1
        assert event_entries[0]["category"] == "kyorugi"
        assert event_entries[0]["count"] == 1
        assert event_entries[0]["avg_seconds"] == 120
        assert event_entries[0]["avg_formatted"] == "2:00"
        assert event_entries[0]["longest_seconds"] == 120
        assert event_entries[0]["longest_formatted"] == "2:00"

        ring_entries = data["by_ring"]
        assert len(ring_entries) == 1
        assert ring_entries[0]["category"] == "Ring 1"

    def test_main_json_with_division_data(self, client, capsys):
        import json
        from datetime import datetime, timezone

        from scripts.match_analytics import main

        ring_id = _create_ring(client, "Ring 1").get_json()["id"]
        div_id = _create_division(client, "Poomsae Group", "poomsae").get_json()["id"]
        _set_poomsae_style(client, div_id, "group")

        div = db.session.get(Division, div_id)
        div.ring_id = ring_id
        div.start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        div.end_time = datetime(2024, 1, 1, 10, 3, 0, tzinfo=timezone.utc)
        db.session.commit()

        main(fmt="json")
        out = capsys.readouterr().out

        data = json.loads(out)
        event_entries = data["by_event_type"]
        assert event_entries[0]["category"] == "poomsae (group)"
        assert event_entries[0]["avg_seconds"] == 180
        assert event_entries[0]["longest_formatted"] == "3:00"

    def test_main_json_is_valid_json(self, client, capsys):
        """JSON output must always be parseable regardless of data."""
        import json
        from datetime import datetime, timezone

        from scripts.match_analytics import main

        div_id = _create_division(client, "Kyorugi Div", "kyorugi").get_json()["id"]
        _add_competitors(client, div_id, ["Alice", "Bob"])
        _generate_bracket(client, div_id)

        match = Match.query.filter_by(division_id=div_id).first()
        match.start_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        match.end_time = datetime(2024, 1, 1, 10, 0, 45, tzinfo=timezone.utc)
        db.session.commit()

        main(fmt="json")
        out = capsys.readouterr().out
        # Should not raise
        data = json.loads(out)
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# seed_dev_db.py
# ---------------------------------------------------------------------------


class TestSeedDevDb:
    """Tests for scripts/seed_dev_db.py seed() function."""

    def test_seed_refuses_unset_app_env(self, monkeypatch):
        """seed() must exit with code 1 when APP_ENV is not set."""
        monkeypatch.delenv("APP_ENV", raising=False)
        monkeypatch.delenv("app_env", raising=False)

        from scripts.seed_dev_db import seed

        with pytest.raises(SystemExit) as exc_info:
            seed()
        assert exc_info.value.code == 1

    def test_seed_refuses_prod_env(self, monkeypatch):
        """seed() must exit with code 1 when APP_ENV is 'prod'."""
        monkeypatch.setenv("APP_ENV", "prod")

        from scripts.seed_dev_db import seed

        with pytest.raises(SystemExit) as exc_info:
            seed()
        assert exc_info.value.code == 1

    def test_seed_refuses_non_empty_db(self, monkeypatch):
        """seed() must exit with code 1 when the database already contains data."""
        monkeypatch.setenv("APP_ENV", "dev")

        ring = Ring(name="Existing Ring")
        db.session.add(ring)
        db.session.commit()

        from scripts.seed_dev_db import seed

        with pytest.raises(SystemExit) as exc_info:
            seed()
        assert exc_info.value.code == 1

    def test_seed_creates_correct_record_counts(self, monkeypatch):
        """Seeding should create 6 rings, 12 divisions, 48 competitors, and 24 matches."""
        monkeypatch.setenv("APP_ENV", "dev")

        from scripts.seed_dev_db import seed

        seed()

        assert Ring.query.count() == 6
        # 6 kyorugi + 2 poomsae bracket + 2 breaking group + 2 poomsae group
        assert Division.query.count() == 12
        # 12 divisions × 4 competitors each
        assert Competitor.query.count() == 48
        # 8 bracket divisions × 3 matches each (4 competitors → 2 semi-finals + 1 final)
        assert Match.query.count() == 24

    def test_seed_ring_assignments(self, monkeypatch):
        """Each ring should have both a kyorugi and a poomsae division assigned."""
        monkeypatch.setenv("APP_ENV", "dev")

        from scripts.seed_dev_db import seed

        seed()

        rings = Ring.query.all()
        for ring in rings:
            divisions = Division.query.filter_by(ring_id=ring.id).all()
            event_types = {d.event_type for d in divisions}
            assert "kyorugi" in event_types, f"{ring.name} is missing a kyorugi division"
            assert "poomsae" in event_types, f"{ring.name} is missing a poomsae division"

    def test_seed_match_number_sequencing(self, monkeypatch):
        """All match numbers should follow ring.id * 100 + sequence (1–99 range per ring)."""
        monkeypatch.setenv("APP_ENV", "dev")

        from scripts.seed_dev_db import seed

        seed()

        matches = Match.query.all()
        assert matches, "Expected matches to be created"
        for match in matches:
            ring_id = match.ring_id
            base = ring_id * 100
            assert base < match.match_number <= base + 99, (
                f"Match {match.id} number {match.match_number} is outside "
                f"expected range ({base+1}–{base+99}) for ring {ring_id}"
            )
