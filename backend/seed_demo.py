"""Seed a couple of demo submissions into the local dev workspace (coachcw).

Run from backend/ with the venv active:

    python seed_demo.py

Each sample becomes a completed-extraction workflow run sitting in the shared
review queue (pending), so the dashboard's hero action items and review panel
show real rows. Timestamps are backdated so they read like "2h ago" / "7h ago".
Re-running adds more rows (it does not de-duplicate).
"""

import json
import sqlite3
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app import db
from app.main import app

# (submitter / client name, intent, hours-ago, fields)
SAMPLES = [
    (
        "Riverside Physio",
        "client_intake",
        2,
        {
            "business_name": "Riverside Physiotherapy",
            "contact_email": "admin@riversidephysio.com.au",
            "abn": "51 824 753 556",
            "engagement": "Annual tax return + quarterly BAS",
        },
    ),
    (
        "Bright Spark Tutors",
        "onboarding",
        7,
        {
            "business_name": "Bright Spark Tutors Pty Ltd",
            "contact_email": "hello@brightsparktutors.com.au",
            "abn": "72 629 951 766",
            "engagement": "Bookkeeping setup + payroll",
        },
    ),
]


def backdate(workflow_run_id: str, document_id: str, hours: int) -> None:
    when = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
    with sqlite3.connect(db.DB_PATH) as conn:
        conn.execute(
            "UPDATE workflow_runs SET created_at = ?, updated_at = ? WHERE id = ?",
            (when, when, workflow_run_id),
        )
        conn.execute(
            "UPDATE documents SET uploaded_at = ? WHERE id = ?",
            (when, document_id),
        )
        conn.commit()


def main() -> None:
    db.init_db()
    with TestClient(app) as client:
        for submitter, intent, hours, fields in SAMPLES:
            resp = client.post(
                "/submissions",
                data={
                    "submitter": submitter,
                    "intent": intent,
                    "fields": json.dumps(fields),
                },
            )
            if resp.status_code != 201:
                print(f"  ! {submitter}: {resp.status_code} {resp.text}")
                continue
            body = resp.json()
            backdate(body["workflow_run"]["id"], body["document"]["id"], hours)
            print(f"  + seeded {submitter} ({intent}, {hours}h ago)")

        queue = client.get(
            "/workflow-runs/review-queue", headers={"X-STS-User": "platform-admin"}
        )
        count = len(queue.json()) if queue.status_code == 200 else queue.text
        print(f"review queue now holds: {count}")


if __name__ == "__main__":
    main()
