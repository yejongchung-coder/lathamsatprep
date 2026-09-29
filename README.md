# ABLE Enrichment — lathamsatprep.com

Rebuilt as plain HTML/CSS/JS + a small Flask backend. Previously a Wix site;
rebuilt for speed of editing: every change is a pull request.

## Structure

- `site/` — the entire website (served as static files)
  - `index.html`, `sat-prep.html`, `college-consulting.html`, `mentorship.html`,
    `why-able.html`, `blog.html`, `free-resources.html`, `404.html`
  - `blog/<slug>.html` — individual articles
  - `assets/css/style.css`, `assets/js/main.js`, `assets/img/`
- `server.py` — Flask app: serves `site/`, collects inquiries, receives SMS
- `build_blog.py` — regenerates `site/blog.html` + `site/blog/*.html`
  from `content/blog/*.json`
- `content/blog/*.json` — article content (source of truth for posts)
- `assets/img/` — original downloaded images (large); web-optimized copies
  live in `site/assets/img/`

## Inquiry form → SID relay

The site's contact section offers two paths: **text the business number** or
fill the **quick inquiry form** (student name/grade/school, parent
name/phone/email, interest = SAT Prep or College Consulting, found via
Referral or Online).

- `POST /api/inquiry` validates the form (honeypot + rate limit) and stores
  it in SQLite (`data/`, gitignored) — it does **not** email anyone.
- `POST /api/sms` is the Twilio webhook for incoming texts; Twilio POSTs
  form-encoded `From`/`Body`, stored the same way.
- A scheduled SID job polls `GET /api/inquiries/pending?key=INQUIRY_KEY`,
  relays each new item to Yejong in chat, then `POST /api/inquiries/ack`
  with the delivered ids.
- `GET /api/config` serves the text number to the site (`TEXT_NUMBER` /
  `TEXT_NUMBER_DISPLAY` env vars) so the number can change without editing
  every page.

## Local dev

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
INQUIRY_KEY=devkey .venv/bin/python server.py  # :8000
```

## Deploy

`render.yaml` defines the Render web service (gunicorn). Set `INQUIRY_KEY`
in the Render dashboard — never commit it. Point the Twilio number's
webhook at `https://<service>/api/sms`.
