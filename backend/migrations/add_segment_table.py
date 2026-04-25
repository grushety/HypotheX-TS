"""Migration: create segments table with decomposition_json column (SEG-019).

For fresh databases, db.create_all() in factory.py handles table creation
automatically.  Run this script on an existing database to add the table
without data loss.

Usage (with venv active, from repo root):
    python backend/migrations/add_segment_table.py
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.factory import create_app


def run_migration() -> None:
    app = create_app()
    with app.app_context():
        from app.extensions import db
        from app.models.segment import Segment  # noqa: F401 — ensure model is registered

        inspector = db.inspect(db.engine)
        existing_tables = inspector.get_table_names()

        if "segments" not in existing_tables:
            print("Creating 'segments' table...")
            Segment.__table__.create(db.engine)
            print("Done.")
        else:
            # Table exists; ensure decomposition_json column is present
            existing_cols = {col["name"] for col in inspector.get_columns("segments")}
            if "decomposition_json" not in existing_cols:
                print("Adding 'decomposition_json' column to existing 'segments' table...")
                with db.engine.connect() as conn:
                    conn.execute(
                        db.text("ALTER TABLE segments ADD COLUMN decomposition_json TEXT")
                    )
                    conn.commit()
                print("Done.")
            else:
                print("'segments' table already up to date — nothing to do.")


if __name__ == "__main__":
    run_migration()
