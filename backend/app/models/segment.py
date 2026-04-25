"""Segment SQLAlchemy model with decomposition storage (SEG-019)."""

from app.extensions import db


class Segment(db.Model):
    __tablename__ = "segments"

    id = db.Column(db.String(128), primary_key=True)
    series_id = db.Column(db.String(128), nullable=False, index=True)
    segment_id = db.Column(db.String(128), nullable=False)
    start_index = db.Column(db.Integer, nullable=False)
    end_index = db.Column(db.Integer, nullable=False)
    label = db.Column(db.String(64), nullable=True)
    decomposition_json = db.Column(db.JSON, nullable=True)
