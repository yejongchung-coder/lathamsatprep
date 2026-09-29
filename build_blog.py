#!/usr/bin/env python3
"""Generate blog post pages from content/blog/*.json and inject cards into site/blog.html."""

import html
import json
import os
import re
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(ROOT, "content", "blog")
SITE = os.path.join(ROOT, "site")
BLOG_DIR = os.path.join(SITE, "blog")

HEADER = """<header class="site-header">
  <div class="wrap">
    <a class="brand" href="/"><img src="/assets/img/logo.png" alt="ABLE Enrichment"></a>
    <button class="menu-toggle" aria-label="Open menu">\u2630</button>
    <nav class="nav">
      <a href="/">Home</a>
      <a href="/sat-prep">SAT Prep</a>
      <a href="/college-consulting">College Consulting</a>
      <a href="/mentorship">Mentorship</a>
      <a href="/why-able">Why ABLE</a>
      <a href="/blog" class="active">Blog</a>
      <a href="/#contact" class="btn small">Get Started</a>
    </nav>
  </div>
</header>"""

FOOTER = """<footer class="site-footer">
  <div class="wrap">
    <div class="footer-grid">
      <div>
        <div class="footer-brand">ABLE Enrichment</div>
        <p style="font-size:0.95rem;">Personalized SAT preparation, college admissions consulting, and student mentorship in Latham, NY \u2014 serving Capital Region families since 2018.</p>
      </div>
      <div>
        <h4>Programs</h4>
        <ul>
          <li><a href="/sat-prep">SAT Preparation</a></li>
          <li><a href="/college-consulting">College Consulting</a></li>
          <li><a href="/college-consulting#essay">Essay Coaching</a></li>
          <li><a href="/mentorship">High School Mentorship</a></li>
        </ul>
      </div>
      <div>
        <h4>Explore</h4>
        <ul>
          <li><a href="/why-able">Why ABLE</a></li>
          <li><a href="/blog">Blog</a></li>
          <li><a href="/free-resources">Free Resources</a></li>
          <li><a href="/#contact">Contact</a></li>
        </ul>
      </div>
      <div>
        <h4>Contact</h4>
        <ul>
          <li><a href="tel:+15183907346">(518) 390-7346</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-areas">
      <strong>Areas served:</strong> SAT prep and college consulting for families in Latham, Colonie, Albany, Troy, Schenectady, Clifton Park, Niskayuna, Loudonville, Delmar, Guilderland, Bethlehem, Saratoga Springs, Scotia, Cohoes, Watervliet, and Mechanicville, NY.
    </div>
    <div class="footer-bottom">
      <span>\u00a9 <span data-year>2026</span> ABLE Enrichment. All rights reserved.</span>
      <span><a href="/privacy-policy">Privacy Policy</a> · <a href="/sms-terms">SMS Terms</a></span>
      <span>SAT\u00ae is a trademark of the College Board, which is not affiliated with ABLE Enrichment.</span>
    </div>
  </div>
</footer>"""

HEAD = """<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&display=swap" rel="stylesheet">
<link rel="icon" href="/assets/img/favicon.png">
<link rel="stylesheet" href="/assets/css/style.css">"""


def fmt_date(raw):
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%b %d, %Y")
        except ValueError:
            continue
    return raw


def excerpt(body_html, length=160):
    text = re.sub(r"<[^>]+>", " ", body_html or "")
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text[:length].rstrip() + ("..." if len(text) > length else "")


def load_posts():
    posts = []
    for fname in sorted(os.listdir(CONTENT)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(CONTENT, fname)) as f:
            posts.append(json.load(f))
    posts.sort(key=lambda p: p.get("date", ""), reverse=True)
    return posts


def post_page(p):
    title = html.escape(p["title"])
    date = html.escape(fmt_date(p.get("date", "")))
    author = html.escape(p.get("author", "ABLE Enrichment"))
    cover = p.get("cover") or ""
    cover_tag = (
        '<img class="cover" src="%s" alt="%s">' % (html.escape(cover), title)
        if cover else ""
    )
    return """<!DOCTYPE html>
<html lang="en">
<head>
<title>%s | ABLE Enrichment Blog</title>
<meta name="description" content="%s">
%s
</head>
<body>
%s
<section>
  <div class="wrap">
    <article class="article">
      <p><a href="/blog">&larr; All articles</a></p>
      <h1>%s</h1>
      <p class="pdate">%s &middot; %s</p>
      %s
      %s
      <div class="cta-band" style="margin-top: 48px;">
        <h2>Want help with this?</h2>
        <p>Text us or send the quick form — we'll build a plan around your student.</p>
        <div class="btn-row" style="justify-content: center;"><a href="/#contact" class="btn light">Get started</a></div>
      </div>
    </article>
  </div>
</section>
%s
<script src="/assets/js/main.js"></script>
</body>
</html>
""" % (title, html.escape(excerpt(p.get("body_html", ""))), HEAD, HEADER, title, author, date,
       cover_tag, p.get("body_html", ""), FOOTER)


def build_index(posts):
    cards = []
    for p in posts:
        cover = p.get("cover") or ""
        img = '<img src="%s" alt="%s" loading="lazy">' % (html.escape(cover), html.escape(p["title"])) if cover else ""
        cards.append(
            '<a class="post-card" href="/blog/%s">%s<div class="pbody">'
            '<p class="pdate">%s</p><h3>%s</h3><p>%s</p>'
            '</div></a>'
            % (html.escape(p["slug"]), img,
               html.escape(fmt_date(p.get("date", ""))),
               html.escape(p["title"]),
               html.escape(excerpt(p.get("body_html", ""))))
        )
    path = os.path.join(SITE, "blog.html")
    with open(path) as f:
        page = f.read()
    start, end = "<!--POSTS-->", "<!--/POSTS-->"
    if start not in page or end not in page:
        raise SystemExit("blog.html is missing the POSTS markers")
    page = re.sub(re.escape(start) + r".*?" + re.escape(end),
                  start + "\n" + "\n".join(cards) + "\n" + end,
                  page, flags=re.S)
    with open(path, "w") as f:
        f.write(page)


def main():
    posts = load_posts()
    if not posts:
        print("no posts found in", CONTENT)
        return
    os.makedirs(BLOG_DIR, exist_ok=True)
    for p in posts:
        path = os.path.join(BLOG_DIR, p["slug"] + ".html")
        with open(path, "w") as f:
            f.write(post_page(p))
    build_index(posts)
    print("generated %d posts + index" % len(posts))


if __name__ == "__main__":
    main()
