from app.extensions import db


class AuditSession(db.Model):
    __tablename__ = "audit_sessions"

    session_id = db.Column(db.String(128), primary_key=True)
    series_id = db.Column(db.String(128), nullable=False)
    segmentation_id = db.Column(db.String(128), nullable=False)
    started_at = db.Column(db.String(64), nullable=False)
    ended_at = db.Column(db.String(64), nullable=True)

    events = db.relationship(
        "AuditEvent",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AuditEvent.sequence",
        lazy="select",
    )


class AuditEvent(db.Model):
    __tablename__ = "audit_events"

    event_id = db.Column(db.String(128), primary_key=True)
    session_id = db.Column(db.String(128), db.ForeignKey("audit_sessions.session_id"), nullable=False, index=True)
    sequence = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.String(64), nullable=False)
    event_type = db.Column(db.String(64), nullable=False)
    payload_json = db.Column(db.Text, nullable=False)

    session = db.relationship("AuditSession", back_populates="events")
