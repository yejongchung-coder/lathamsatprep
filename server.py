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
    TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN
        Twilio REST API credentials (Render dashboard secrets). Used to
        text NOTIFY_PHONE the moment a contact-form submission lands.
    NOTIFY_PHONE
        Yejong's phone in E.164 format (Render dashboard secret).
        Receives the new-form push SMS from TEXT_NUMBER.
    PORT
        Port to listen on (Render sets this).

Inquiries, SMS, and pageviews are stored in SQLite at $DATA_DIR/inquiries.db
(default <repo>/data/inquiries.db, gitignored). On Render DATA_DIR points at
the persistent disk so numbers survive restarts and redeploys.
A scheduled job polls /api/inquiries/pending, relays new items to Yejong
in chat, then acknowledges them via /api/inquiries/ack.
A monthly job pulls /api/stats for the website report.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import time
from collections import deque
from datetime import datetime, timezone

from flask import Flask, Response, jsonify, redirect, request, send_from_directory

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE_DIR = os.path.join(ROOT, "site")
# Render persistent disk mount (set DATA_DIR env var); falls back to local data/.
DATA_DIR = os.environ.get("DATA_DIR", "").strip() or os.path.join(ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "inquiries.db")

TEXT_NUMBER = os.environ.get("TEXT_NUMBER", "").strip()
TEXT_NUMBER_DISPLAY = os.environ.get("TEXT_NUMBER_DISPLAY", "").strip() or TEXT_NUMBER
INQUIRY_KEY = os.environ.get("INQUIRY_KEY", "").strip()
# Push notifications: when set, new contact-form submissions are texted to
# NOTIFY_PHONE via the Twilio REST API (same number families already get
# their inbound SMS forwarded to). Values live in the Render dashboard.
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
NOTIFY_PHONE = os.environ.get("NOTIFY_PHONE", "").strip()

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
    conn.execute(
        """CREATE TABLE IF NOT EXISTS pageviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,              -- ISO UTC timestamp
            path TEXT NOT NULL,
            referrer TEXT DEFAULT '',
            ip_hash TEXT NOT NULL,         -- sha256(ip + day): daily-rotating, not reversible
            ua TEXT DEFAULT '',
            mobile INTEGER NOT NULL DEFAULT 0,
            is_bot INTEGER NOT NULL DEFAULT 0
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pageviews_ts ON pageviews(ts)")
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


def _send_sms(to: str, body: str) -> bool:
    """Send an SMS via the Twilio REST API. Never raises; returns success."""
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TEXT_NUMBER and to):
        return False
    try:
        import base64
        import urllib.parse
        import urllib.request

        url = (
            "https://api.twilio.com/2010-04-01/Accounts/"
            f"{TWILIO_ACCOUNT_SID}/Messages.json"
        )
        data = urllib.parse.urlencode(
            {"To": to, "From": TEXT_NUMBER, "Body": body}
        ).encode()
        creds = base64.b64encode(
            f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode()
        ).decode()
        req = urllib.request.Request(
            url, data=data, headers={"Authorization": f"Basic {creds}"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


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


# --- lightweight privacy-friendly analytics (no cookies, no fingerprinting) ---
BOT_UA_RE = re.compile(
    r"bot|crawl|spider|slurp|mediapartners|baidu|yandex|sogou|exabot|facebot|ia_archiver|ahrefs|semrush|mj12bot|dotbot",
    re.I,
)
MOBILE_UA_RE = re.compile(r"mobile|android|iphone|ipad|ipod", re.I)
TRACK_SNIPPET = b'<script src="/assets/js/track.js" defer></script>'


def _ip_hash(ip: str) -> str:
    # Daily-rotating hash: enough to count unique visitors per day,
    # not reversible to an address and not linkable across days.
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return hashlib.sha256(f"{ip}|{day}".encode()).hexdigest()[:32]


@app.post("/api/track")
def track():
    data = request.get_json(force=True, silent=True) or {}
    path = str(data.get("path", ""))[:200]
    if not path.startswith("/"):
        return ("", 204)
    referrer = str(data.get("referrer", ""))[:300]
    ua = request.headers.get("User-Agent", "")[:200]
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
    conn = _db()
    try:
        conn.execute(
            """INSERT INTO pageviews (ts, path, referrer, ip_hash, ua, mobile, is_bot)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                path,
                referrer,
                _ip_hash(ip),
                ua,
                1 if MOBILE_UA_RE.search(ua) else 0,
                1 if BOT_UA_RE.search(ua) else 0,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return ("", 204)


@app.get("/api/stats")
def stats():
    """Monthly aggregates for the website report. Guarded by INQUIRY_KEY."""
    if not _key_ok():
        return jsonify(ok=False, error="forbidden"), 403
    month = (request.args.get("month") or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        month = datetime.now(timezone.utc).strftime("%Y-%m")
    prefix = month + "%"
    conn = _db()
    try:
        pv = conn.execute(
            "SELECT COUNT(*) FROM pageviews WHERE is_bot = 0 AND ts LIKE ?", (prefix,)
        ).fetchone()[0]
        uniques = conn.execute(
            "SELECT COUNT(DISTINCT ip_hash) FROM pageviews WHERE is_bot = 0 AND ts LIKE ?",
            (prefix,),
        ).fetchone()[0]
        mobile = conn.execute(
            "SELECT COUNT(*) FROM pageviews WHERE is_bot = 0 AND mobile = 1 AND ts LIKE ?",
            (prefix,),
        ).fetchone()[0]
        top_pages = [
            dict(r)
            for r in conn.execute(
                """SELECT path, COUNT(*) AS views
                   FROM pageviews WHERE is_bot = 0 AND ts LIKE ?
                   GROUP BY path ORDER BY views DESC LIMIT 10""",
                (prefix,),
            ).fetchall()
        ]
        top_refs = [
            dict(r)
            for r in conn.execute(
                """SELECT referrer, COUNT(*) AS views
                   FROM pageviews
                   WHERE is_bot = 0 AND ts LIKE ? AND referrer != ''
                     AND referrer NOT LIKE '%lathamsatprep.com%'
                   GROUP BY referrer ORDER BY views DESC LIMIT 10""",
                (prefix,),
            ).fetchall()
        ]
        inquiries = conn.execute(
            "SELECT COUNT(*) FROM inquiries WHERE created_at LIKE ?", (prefix,)
        ).fetchone()[0]
    finally:
        conn.close()
    return jsonify(
        ok=True,
        month=month,
        pageviews=pv,
        unique_visitors=uniques,
        mobile_share=round(mobile / pv, 3) if pv else 0,
        top_pages=top_pages,
        top_referrers=top_refs,
        inquiries=inquiries,
        conversion_pct=round(inquiries / uniques * 100, 2) if uniques else 0,
    )


@app.after_request
def _inject_tracking(resp):
    # (Kept as a no-op guard: HTML injection happens in _serve_html below,
    # because send_from_directory responses stream the file directly.)
    return resp


def _serve_html(full_path: str):
    with open(full_path, "rb") as f:
        data = f.read()
    if TRACK_SNIPPET not in data and b"</body>" in data:
        data = data.replace(b"</body>", TRACK_SNIPPET + b"</body>", 1)
    return Response(data, mimetype="text/html")


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
    # Push notification: text Yejong the moment a form lands, so the
    # 15-minute polling watch is no longer needed for relay. The form
    # itself is already saved; a failed SMS never blocks the response.
    _send_sms(
        NOTIFY_PHONE,
        f"ABLE new form — {INTERESTS[interest]}: {student_name}, "
        f"grade {grade}, {school}. Parent: {parent_name}, {parent_phone}.",
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
    return _serve_html(os.path.join(SITE_DIR, "index.html"))


@app.get("/<path:path>")
def static_or_page(path: str):
    if path in REDIRECTS:
        return redirect(REDIRECTS[path], code=301)
    full = os.path.join(SITE_DIR, path)
    if os.path.isdir(full):
        index = os.path.join(full, "index.html")
        if os.path.isfile(index):
            return _serve_html(index)
    if os.path.isfile(full):
        if full.endswith(".html"):
            return _serve_html(full)
        return send_from_directory(SITE_DIR, path)
    # Pretty URLs: /sat-prep -> /sat-prep.html
    candidate = full + ".html"
    if os.path.isfile(candidate):
        return _serve_html(candidate)
    return _serve_html(os.path.join(SITE_DIR, "404.html")), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
