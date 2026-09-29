#!/usr/bin/env python3
"""ABLE Enrichment website — serves the static site, collects inquiries,
and receives incoming SMS (Twilio webhook) so SID can relay them to Yejong.

Environment:
    TEXT_NUMBER
        The public text-message number, E.164 (e.g. +15187389750).
        Served to the site via /api/config; never hard-coded in HTML.
    TEXT_NUMBER_DISPLAY
        Pretty display version (e.g. (518) 738-9750). Defaults to TEXT_NUMBER.
    INQUIRY_KEY
        Shared secret guarding /api/inquiries/pending and /ack.
        The scheduled SID watch job uses this to pull new inquiries/texts.
    PORT
        Port to listen on (Render sets this).

Inquiries and SMS are stored in SQLite at data/inquiries.db (gitignored).
A scheduled job polls /api/inquiries/pending, relays new items to Yejong
in chat, then acknowledges them via /api/inquiries/ack.
"""

from __future__ import annotations

import os
import re
import sqlite3
import time
from collections import deque
from datetime import datetime, timezone

from flask import Flask, jsonify, redirect, request, send_from_directory

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE_DIR = os.path.join(ROOT, "site")
DATA_DIR = os.path.join(ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "inquiries.db")

TEXT_NUMBER = os.environ.get("TEXT_NUMBER", "").strip()
TEXT_NUMBER_DISPLAY = os.environ.get("TEXT_NUMBER_DISPLAY", "").strip() or TEXT_NUMBER
INQUIRY_KEY = os.environ.get("INQUIRY_KEY", "").strip()

app = Flask(__name__, static_folder=None)

# --- simple in-memory rate limiting: max 10 submissions per IP per 10 minutes ---
_submissions: dict[str, deque] = {}
RATE_LIMIT = 10
RATE_WINDOW = 600


def _rate_ok(ip: str) -> bool:
    now = time.time()
    bucket = _submissions.setdefault(ip, deque())
    while bucket and now - bucket[0] > RATE_WINDOW:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT:
        return False
    bucket.append(now)
    return True


def _db() -> sqlite3.Connection:
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            kind TEXT NOT NULL,          -- 'form' or 'sms'
            student_name TEXT DEFAULT '',
            grade TEXT DEFAULT '',
            school TEXT DEFAULT '',
            parent_name TEXT DEFAULT '',
            parent_phone TEXT DEFAULT '',
            parent_email TEXT DEFAULT '',
            interest TEXT DEFAULT '',
            source TEXT DEFAULT '',
            from_number TEXT DEFAULT '',
            body TEXT DEFAULT '',
            acked INTEGER NOT NULL DEFAULT 0
        )"""
    )
    return conn


def _save(kind: str, **fields) -> int:
    conn = _db()
    try:
        cur = conn.execute(
            """INSERT INTO inquiries
               (created_at, kind, student_name, grade, school, parent_name,
                parent_phone, parent_email, interest, source, from_number, body)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                kind,
                fields.get("student_name", ""),
                fields.get("grade", ""),
                fields.get("school", ""),
                fields.get("parent_name", ""),
                fields.get("parent_phone", ""),
                fields.get("parent_email", ""),
                fields.get("interest", ""),
                fields.get("source", ""),
                fields.get("from_number", ""),
                fields.get("body", ""),
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
INTERESTS = {"sat": "SAT Prep", "consulting": "College Consulting"}
SOURCES = {"referral": "Referral", "online": "Online"}


@app.get("/api/health")
def health():
    conn = _db()
    try:
        pending = conn.execute("SELECT COUNT(*) FROM inquiries WHERE acked = 0").fetchone()[0]
    finally:
        conn.close()
    return jsonify(ok=True, sms_configured=bool(TEXT_NUMBER), pending_inquiries=pending)


@app.get("/api/config")
def config():
    return jsonify(text_number=TEXT_NUMBER, text_number_display=TEXT_NUMBER_DISPLAY)


@app.post("/api/inquiry")
def inquiry():
    data = request.get_json(force=True, silent=True) or {}
    # Honeypot: bots fill this, humans never see it.
    if (data.get("company") or "").strip():
        return jsonify(ok=True)
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    if not _rate_ok(ip):
        return jsonify(ok=False, error="Too many submissions. Please try again later."), 429

    def s(key: str, limit: int) -> str:
        return (data.get(key) or "").strip()[:limit]

    student_name = s("student_name", 120)
    grade = s("grade", 20)
    school = s("school", 160)
    parent_name = s("parent_name", 120)
    parent_phone = s("parent_phone", 40)
    parent_email = s("parent_email", 160)
    interest = s("interest", 20)
    source = s("source", 20)

    errors = []
    if not student_name:
        errors.append("student_name")
    if not grade:
        errors.append("grade")
    if not school:
        errors.append("school")
    if not parent_name:
        errors.append("parent_name")
    if not parent_phone:
        errors.append("parent_phone")
    if not EMAIL_RE.match(parent_email):
        errors.append("parent_email")
    if interest not in INTERESTS:
        errors.append("interest")
    if source not in SOURCES:
        errors.append("source")
    if errors:
        return jsonify(ok=False, error="Please complete the highlighted fields.", fields=errors), 400

    _save(
        "form",
        student_name=student_name,
        grade=grade,
        school=school,
        parent_name=parent_name,
        parent_phone=parent_phone,
        parent_email=parent_email,
        interest=INTERESTS[interest],
        source=SOURCES[source],
    )
    return jsonify(ok=True)


@app.post("/api/sms")
def sms_webhook():
    """Twilio webhook: incoming text messages. Twilio POSTs form-encoded."""
    from_number = (request.form.get("From") or "").strip()[:40]
    body = (request.form.get("Body") or "").strip()[:2000]
    if not (from_number and body):
        return ("", 200)
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    if not _rate_ok(ip):
        return ("", 200)
    _save("sms", from_number=from_number, body=body)
    # Empty 200: Twilio sends no reply SMS.
    return ("", 200)


def _key_ok() -> bool:
    if not INQUIRY_KEY:
        return False
    provided = request.args.get("key", "") or (request.get_json(force=True, silent=True) or {}).get("key", "")
    return provided == INQUIRY_KEY


@app.get("/api/inquiries/pending")
def pending():
    if not _key_ok():
        return jsonify(ok=False, error="forbidden"), 403
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT * FROM inquiries WHERE acked = 0 ORDER BY id ASC LIMIT 100"
        ).fetchall()
    finally:
        conn.close()
    return jsonify(ok=True, items=[dict(r) for r in rows])


@app.post("/api/inquiries/ack")
def ack():
    if not _key_ok():
        return jsonify(ok=False, error="forbidden"), 403
    data = request.get_json(force=True, silent=True) or {}
    ids = [i for i in (data.get("ids") or []) if isinstance(i, int)]
    if ids:
        conn = _db()
        try:
            conn.execute(
                "UPDATE inquiries SET acked = 1 WHERE id IN (%s)" % ",".join("?" * len(ids)), ids
            )
            conn.commit()
        finally:
            conn.close()
    return jsonify(ok=True, acked=len(ids))


# --- legacy page redirects (old IA -> new IA) ---
REDIRECTS = {
    "mission": "/why-able",
    "mission.html": "/why-able",
    "spark": "/mentorship",
    "spark.html": "/mentorship",
    "summer-camp": "/sat-prep",
    "summer-camp.html": "/sat-prep",
}


@app.get("/")
def root():
    return send_from_directory(SITE_DIR, "index.html")


@app.get("/<path:path>")
def static_or_page(path: str):
    if path in REDIRECTS:
        return redirect(REDIRECTS[path], code=301)
    full = os.path.join(SITE_DIR, path)
    if os.path.isdir(full):
        index = os.path.join(full, "index.html")
        if os.path.isfile(index):
            return send_from_directory(full, "index.html")
    if os.path.isfile(full):
        return send_from_directory(SITE_DIR, path)
    # Pretty URLs: /sat-prep -> /sat-prep.html
    candidate = full + ".html"
    if os.path.isfile(candidate):
        return send_from_directory(SITE_DIR, path + ".html")
    return send_from_directory(SITE_DIR, "404.html"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
