"""
Deal Store — deal_store.py
SQLite-backed persistence for loan officer deals, documents, and profiles.
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deals.db")

STATUSES = ["Intake", "Extracting", "Review", "Gaps", "Ready", "Submitted", "Approved", "Rejected"]

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS deals (
            deal_id      TEXT PRIMARY KEY,
            borrower_name TEXT NOT NULL,
            loan_amount  REAL,
            status       TEXT DEFAULT 'Intake',
            urgency      INTEGER DEFAULT 0,
            created_at   TEXT,
            updated_at   TEXT,
            notes        TEXT
        );

        CREATE TABLE IF NOT EXISTS documents (
            doc_id       TEXT PRIMARY KEY,
            deal_id      TEXT NOT NULL,
            filename     TEXT,
            doc_type     TEXT,
            summary      TEXT,
            upload_time  TEXT,
            status       TEXT DEFAULT 'pending',
            fields_json  TEXT,
            FOREIGN KEY (deal_id) REFERENCES deals(deal_id)
        );

        CREATE TABLE IF NOT EXISTS profiles (
            deal_id      TEXT PRIMARY KEY,
            profile_json TEXT,
            meta_json    TEXT,
            updated_at   TEXT,
            FOREIGN KEY (deal_id) REFERENCES deals(deal_id)
        );

        CREATE TABLE IF NOT EXISTS packages (
            package_id   TEXT PRIMARY KEY,
            deal_id      TEXT NOT NULL,
            generated_at TEXT,
            files_json   TEXT,
            status       TEXT DEFAULT 'draft',
            FOREIGN KEY (deal_id) REFERENCES deals(deal_id)
        );
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------

def create_deal(borrower_name: str, loan_amount: float = None, notes: str = "") -> str:
    import uuid
    deal_id = f"D{str(uuid.uuid4())[:6].upper()}"
    now = datetime.utcnow().isoformat()
    conn = get_conn()
    conn.execute(
        "INSERT INTO deals (deal_id, borrower_name, loan_amount, status, created_at, updated_at, notes) VALUES (?,?,?,?,?,?,?)",
        (deal_id, borrower_name, loan_amount, "Intake", now, now, notes)
    )
    conn.commit()
    conn.close()
    return deal_id


def get_deal(deal_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM deals WHERE deal_id=?", (deal_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_deals():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM deals ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_deal_status(deal_id: str, status: str):
    now = datetime.utcnow().isoformat()
    conn = get_conn()
    conn.execute("UPDATE deals SET status=?, updated_at=? WHERE deal_id=?", (status, now, deal_id))
    conn.commit()
    conn.close()


def set_urgency(deal_id: str, urgent: bool):
    conn = get_conn()
    conn.execute("UPDATE deals SET urgency=? WHERE deal_id=?", (int(urgent), deal_id))
    conn.commit()
    conn.close()


def update_deal_notes(deal_id: str, notes: str):
    now = datetime.utcnow().isoformat()
    conn = get_conn()
    conn.execute("UPDATE deals SET notes=?, updated_at=? WHERE deal_id=?", (notes, now, deal_id))
    conn.commit()
    conn.close()


def delete_deal(deal_id: str):
    conn = get_conn()
    conn.execute("DELETE FROM packages WHERE deal_id=?", (deal_id,))
    conn.execute("DELETE FROM profiles WHERE deal_id=?", (deal_id,))
    conn.execute("DELETE FROM documents WHERE deal_id=?", (deal_id,))
    conn.execute("DELETE FROM deals WHERE deal_id=?", (deal_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

def add_document(deal_id: str, filename: str, doc_type: str = None, summary: str = "") -> str:
    import uuid
    doc_id = f"DOC-{str(uuid.uuid4())[:8]}"
    now = datetime.utcnow().isoformat()
    conn = get_conn()
    conn.execute(
        "INSERT INTO documents (doc_id, deal_id, filename, doc_type, summary, upload_time, status) VALUES (?,?,?,?,?,?,?)",
        (doc_id, deal_id, filename, doc_type, summary, now, "pending")
    )
    conn.commit()
    conn.close()
    # Move deal to Extracting
    update_deal_status(deal_id, "Extracting")
    return doc_id


def save_document_fields(doc_id: str, doc_type: str, summary: str, fields: dict):
    conn = get_conn()
    conn.execute(
        "UPDATE documents SET doc_type=?, summary=?, fields_json=?, status=? WHERE doc_id=?",
        (doc_type, summary, json.dumps(fields), "done", doc_id)
    )
    conn.commit()
    conn.close()


def get_documents(deal_id: str):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM documents WHERE deal_id=? ORDER BY upload_time", (deal_id,)).fetchall()
    conn.close()
    docs = []
    for r in rows:
        d = dict(r)
        d["fields"] = json.loads(d["fields_json"]) if d["fields_json"] else {}
        docs.append(d)
    return docs


def delete_document(doc_id: str):
    conn = get_conn()
    conn.execute("DELETE FROM documents WHERE doc_id=?", (doc_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

def save_profile(deal_id: str, profile: dict, meta: dict):
    now = datetime.utcnow().isoformat()
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO profiles (deal_id, profile_json, meta_json, updated_at) VALUES (?,?,?,?)",
        (deal_id, json.dumps(profile), json.dumps(meta), now)
    )
    conn.commit()
    conn.close()


def get_profile(deal_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM profiles WHERE deal_id=?", (deal_id,)).fetchone()
    conn.close()
    if not row:
        return None, None
    return json.loads(row["profile_json"]), json.loads(row["meta_json"])


# ---------------------------------------------------------------------------
# Packages
# ---------------------------------------------------------------------------

def save_package(deal_id: str, files: list) -> str:
    import uuid
    package_id = f"PKG-{str(uuid.uuid4())[:8]}"
    now = datetime.utcnow().isoformat()
    conn = get_conn()
    conn.execute(
        "INSERT INTO packages (package_id, deal_id, generated_at, files_json, status) VALUES (?,?,?,?,?)",
        (package_id, deal_id, now, json.dumps(files), "draft")
    )
    conn.commit()
    conn.close()
    update_deal_status(deal_id, "Ready")
    return package_id


def get_packages(deal_id: str):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM packages WHERE deal_id=? ORDER BY generated_at DESC", (deal_id,)).fetchall()
    conn.close()
    pkgs = []
    for r in rows:
        p = dict(r)
        p["files"] = json.loads(p["files_json"])
        pkgs.append(p)
    return pkgs


# Init on import
init_db()
