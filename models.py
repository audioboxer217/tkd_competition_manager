from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

VALID_EVENT_TYPES = {"poomsae", "kyorugi"}
COMPLETED_MATCH_STATUSES = {"Completed", "Completed (Bye)", "Disqualification"}


class Ring(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # e.g., 'Ring 1'
    matches = db.relationship("Match", backref="ring", lazy=True)
    divisions = db.relationship("Division", backref="ring", lazy=True)


class Division(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # e.g., 'Male - Black Belt - Under 70kg'
    event_type = db.Column(db.String(20), nullable=False, default="kyorugi")  # 'poomsae' or 'kyorugi'
    poomsae_style = db.Column(db.String(10), nullable=True)  # For poomsae: 'bracket' or 'group'; None = not yet set
    ring_id = db.Column(db.Integer, db.ForeignKey("ring.id"), nullable=True)  # For poomsae: which ring is hosting this event
    ring_sequence = db.Column(db.Integer, nullable=True)  # For poomsae: display order within the ring (1, 2, 3, ...)
    event_status = db.Column(
        db.String(20), nullable=False, default="Pending"
    )  # For poomsae: 'Pending', 'In Progress', 'Completed'

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


class ApiToken(db.Model):
    """Persistent API bearer token.  Only the SHA-256 hash is stored."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_used_at = db.Column(db.DateTime(timezone=True), nullable=True)
    user_id = db.Column(db.String(255), nullable=True)  # optional owner reference (e.g. Supabase user id)
